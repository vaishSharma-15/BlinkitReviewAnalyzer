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
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "data" / "cache"
MODEL = "gemini-3.5-flash-lite"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 5

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


def _cache_path(prompt_version: str, text: str) -> Path:
    key = hashlib.sha256(f"{prompt_version}:{text}".encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}.json"


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
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_path(prompt_version, user_content)
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))["response"]

    api_key = os.environ["GEMINI_API_KEY"]
    payload = {
        "contents": [{"parts": [{"text": user_content}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    if json_mode:
        payload["generationConfig"] = {"responseMimeType": "application/json"}

    last_error = None
    with httpx.Client(timeout=60.0) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            _rate_limiter.acquire()
            try:
                response = client.post(f"{API_URL}?key={api_key}", json=payload)
                if response.status_code == 429 and _is_daily_quota_violation(response):
                    raise DailyQuotaExhausted(response.text)
                if response.status_code in (429, 503):
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                response.raise_for_status()
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                cache_path.write_text(json.dumps({"response": text, "prompt_version": prompt_version}), encoding="utf-8")
                return text
            except DailyQuotaExhausted:
                raise
            except Exception as exc:
                last_error = exc
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    return None
