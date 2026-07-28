"""Shared LLM client: Gemini API calls with disk caching and retries.

Deviation from docs/ProblemStatement.md §5 (which decided Anthropic/Claude): the user
does not have an Anthropic API key and asked to use their free-tier Gemini key instead,
approved explicitly in conversation. Model is pinned to gemini-3.5-flash-lite rather
than a "-latest" alias (which can silently change the underlying model over time,
breaking reproducibility) and rather than the full gemini-3.5-flash (which, in testing,
intermittently leaked chain-of-thought/self-correction text into the JSON output even
with responseMimeType=application/json — unacceptable for a strict-JSON pipeline). The
lite variant returned clean, parseable JSON consistently across repeated trials.

Cache keys are sha256(prompt_version + text), per the spec's requirement that changes
to a prompt don't silently reuse stale results.
"""
import hashlib
import json
import logging
import os
import random
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "data" / "cache"

# The run cache above is gitignored (9MB+ of pipeline responses, regenerable), so a
# deployed copy of this app starts with an empty one and every question is a live
# free-tier API call. The seed cache is the small, committed subset that ships with the
# repo: the demo questions, pre-answered. It is read-only and never written to at
# runtime, so it stays a deliberate, reviewable set rather than whatever the last run
# happened to ask. Regenerate with `python -m src.warm_cache`.
SEED_CACHE_DIR = REPO_ROOT / "data" / "cache_seed"

MODEL = "gemini-3.5-flash-lite"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 5
# Retried with backoff: 429 (rate limit), 503 (overloaded), and the 5xx family that
# means "the far end wobbled", not "your request is wrong". A 400/401/403 is a real
# fault in the request or key and will fail identically five times, so it is not retried.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Free tier is hard-capped at 15 requests/minute for this model (confirmed via the
# API's own 429 quota message). A small safety margin (13, not 15) avoids tripping the
# limit on clock-boundary edge cases. This must be respected globally across all
# threads, not per-thread, since the quota is per-project-per-model, not per-worker.
REQUESTS_PER_MINUTE = 13


class RateLimiter:
    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.timestamps = deque()
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            while self.timestamps and now - self.timestamps[0] > 60:
                self.timestamps.popleft()
            if len(self.timestamps) >= self.max_per_minute:
                sleep_for = 60 - (now - self.timestamps[0]) + 0.1
            else:
                sleep_for = 0
            if sleep_for <= 0:
                self.timestamps.append(time.monotonic())
                return
        if sleep_for > 0:
            time.sleep(sleep_for)
        self.acquire()


_rate_limiter = RateLimiter(REQUESTS_PER_MINUTE)


class DailyQuotaExhausted(Exception):
    """Raised when the API reports a per-day (not per-minute) quota violation.
    Unlike a per-minute limit, backoff-and-retry cannot recover from this within the
    same day, so callers should stop the run rather than burn hours retrying. Since
    responses are cached on disk, simply re-running the same command after the quota
    resets picks up exactly where it left off at no extra cost."""


def _cache_key(prompt_version: str, text: str) -> str:
    return hashlib.sha256(f"{prompt_version}:{text}".encode("utf-8")).hexdigest()


def _cache_path(prompt_version: str, text: str) -> Path:
    return CACHE_DIR / f"{_cache_key(prompt_version, text)}.json"


def seed_cache_path(prompt_version: str, text: str) -> Path:
    return SEED_CACHE_DIR / f"{_cache_key(prompt_version, text)}.json"


def _read_cached(prompt_version: str, user_content: str) -> Optional[str]:
    """Run cache first, then the committed seed cache.

    Order matters: a fresh answer written by this deployment should win over the one
    frozen into the repo, so the seed is a floor and never a ceiling. A corrupt or
    half-written cache file must not take the whole answer down with it — it is treated
    as a miss, which costs one API call, rather than raising.
    """
    for path in (_cache_path(prompt_version, user_content),
                 seed_cache_path(prompt_version, user_content)):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))["response"]
            except Exception:
                logger.warning("Ignoring unreadable cache file %s", path.name)
    return None


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    """How long to wait before the next attempt.

    Prefers the server's own Retry-After over guessing. Otherwise exponential backoff
    with jitter: linear backoff makes every concurrent caller retry in lockstep, which
    is how a brief rate-limit turns into a self-inflicted stampede.
    """
    header = response.headers.get("Retry-After") if response is not None else None
    if header:
        try:
            return min(float(header), 60.0)
        except ValueError:
            pass
    return min(RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)), 45.0) + random.uniform(0, 1.5)


def _is_daily_quota_violation(response: httpx.Response) -> bool:
    try:
        violations = response.json()["error"]["details"]
        for detail in violations:
            for v in detail.get("violations", []):
                if "PerDay" in v.get("quotaId", ""):
                    return True
    except Exception:
        pass
    return False


def call_llm(system_prompt: str, user_content: str, prompt_version: str, json_mode: bool = True) -> Optional[str]:
    """Returns the raw text response, using a disk cache keyed on prompt_version + content.
    Returns None if all retries are exhausted (caller must handle as a quarantine case)."""
    cached = _read_cached(prompt_version, user_content)
    if cached is not None:
        return cached

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Deployed without the secret set. Previously a KeyError from os.environ[...],
        # which read as an unexpected crash rather than the configuration problem it is.
        logger.error("GEMINI_API_KEY is not set — no live call possible, falling back.")
        return None

    payload = {
        "contents": [{"parts": [{"text": user_content}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    if json_mode:
        payload["generationConfig"] = {"responseMimeType": "application/json"}

    last_error = None
    with httpx.Client(timeout=90.0) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            _rate_limiter.acquire()
            response = None
            try:
                response = client.post(f"{API_URL}?key={api_key}", json=payload)
                if response.status_code == 429 and _is_daily_quota_violation(response):
                    raise DailyQuotaExhausted(response.text)
                if response.status_code in RETRYABLE_STATUS:
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}", request=response.request, response=response)
                response.raise_for_status()
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                try:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    _cache_path(prompt_version, user_content).write_text(
                        json.dumps({"response": text, "prompt_version": prompt_version}),
                        encoding="utf-8")
                except OSError as exc:
                    # A read-only or full disk must not throw away an answer we already
                    # have in hand; losing the cache write only costs the next call.
                    logger.warning("Could not write cache entry: %s", exc)
                return text
            except DailyQuotaExhausted:
                raise
            except Exception as exc:
                last_error = exc
                # A non-retryable status (bad key, malformed request) fails identically
                # on every attempt — five rounds of backoff just makes the user wait
                # longer for the same outcome.
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status not in RETRYABLE_STATUS:
                    logger.error("Gemini call failed with non-retryable HTTP %s: %s", status, exc)
                    break
                if attempt < MAX_RETRIES:
                    delay = _retry_after_seconds(response, attempt)
                    logger.warning("Gemini call failed (attempt %d/%d): %s — retrying in %.1fs",
                                   attempt, MAX_RETRIES, exc, delay)
                    time.sleep(delay)

    # The whole point of the change: this used to return None with last_error assigned
    # and never read, so a rate-limited or timed-out call was indistinguishable from a
    # model that simply had nothing to say. The caller still degrades gracefully, but
    # the reason is now on the record.
    logger.error("Gemini call gave up after %d attempts (prompt_version=%s). Last error: %r",
                 MAX_RETRIES, prompt_version, last_error)
    return None
