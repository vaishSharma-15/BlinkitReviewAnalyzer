"""Pre-answer the Copilot's suggested questions and commit the results.

Why this exists. src/llm.py caches every response to data/cache/, but that directory is
gitignored — it holds 9MB+ of pipeline responses and is regenerable, so it has no business
in the repo. The consequence is easy to miss: a *deployed* copy of this app starts with a
completely cold cache, so every question a visitor asks is a live free-tier API call. If
the daily quota is spent, or the rate limiter trips, or the network wobbles, the app
quietly serves its extractive fallback instead of a written answer.

The suggested-question chips are the first thing anyone clicks, so those are the answers
that must never depend on the network. This script pre-computes exactly those and writes
them to data/cache_seed/, which IS committed. call_llm reads the run cache first and the
seed second, so a deployment answers the demo path instantly and offline, while anything
typed by hand still goes to the API as normal.

The cache key is sha256(prompt_version + user_content), and user_content is built from the
committed index and corpus stats, so a key computed here matches the one computed on the
deployed instance — provided the retrieval index and prompt version are unchanged. Both
are in git, so that holds. If either changes the seed silently stops matching, which is
why --verify re-derives every key and reports misses rather than trusting the directory.

Usage:
    python -m src.warm_cache            # fill any missing seed entries
    python -m src.warm_cache --verify   # check every question hits, make no API calls
    python -m src.warm_cache --force    # re-answer everything (after a prompt change)
"""
import argparse
import json
import sys

from app.rag_engine import (
    build_answer_request,
    detect_smalltalk,
    is_out_of_retrieval_range,
    retrieve_evidence,
)
from app.tab_copilot import SUGGESTED_QUESTIONS
from src.llm import SEED_CACHE_DIR, call_llm, seed_cache_path


def _request_for(question: str):
    """The exact request the live app would send, or None if it would never send one.

    The same three guards generate_structured_answer applies before reaching for the
    model: small talk, no evidence, and evidence too distant to be about the question.
    Seeding an answer the app would never ask for would be a cache entry that can only
    ever miss.
    """
    if detect_smalltalk(question):
        return None
    evidence = retrieve_evidence(question, top_k=8)
    if not evidence or is_out_of_retrieval_range(evidence):
        return None
    return build_answer_request(question, evidence)


def verify() -> int:
    missing = []
    for q in SUGGESTED_QUESTIONS:
        req = _request_for(q)
        if req is None:
            print(f"  SKIP  {q}\n        (no generative request — smalltalk or out of scope)")
            continue
        path = seed_cache_path(req["prompt_version"], req["user_content"])
        ok = path.exists()
        print(f"  {'HIT ' if ok else 'MISS'}  {q}")
        if not ok:
            missing.append(q)
    if missing:
        print(f"\n{len(missing)} of {len(SUGGESTED_QUESTIONS)} questions would hit the live API.")
        print("Run `python -m src.warm_cache` to fill them.")
        return 1
    print(f"\nAll {len(SUGGESTED_QUESTIONS)} suggested questions are seeded — "
          "the demo path needs no API call.")
    return 0


def warm(force: bool) -> int:
    SEED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if force:
        for stale in SEED_CACHE_DIR.glob("*.json"):
            stale.unlink()
        print(f"Cleared {SEED_CACHE_DIR}")

    written = skipped = failed = 0
    for q in SUGGESTED_QUESTIONS:
        req = _request_for(q)
        if req is None:
            print(f"  skip    {q} (no generative request)")
            continue
        path = seed_cache_path(req["prompt_version"], req["user_content"])
        if path.exists():
            print(f"  have    {q}")
            skipped += 1
            continue

        # Goes through call_llm so the run cache is populated too, then copied across:
        # the seed is a curated subset, not a mirror of whatever else has been asked.
        raw = call_llm(req["system_prompt"], req["user_content"], req["prompt_version"],
                       json_mode=True)
        if not raw:
            print(f"  FAILED  {q} (no response — see the logged error above)")
            failed += 1
            continue
        try:
            json.loads(raw.strip().strip("`").removeprefix("json").strip())
        except Exception:
            # A seed entry is served without ever being re-validated, so an unparseable
            # one would be a permanent broken answer on the deployed app.
            print(f"  FAILED  {q} (response was not valid JSON — not seeding it)")
            failed += 1
            continue
        path.write_text(json.dumps({"response": raw, "prompt_version": req["prompt_version"]}),
                        encoding="utf-8")
        print(f"  wrote   {q}")
        written += 1

    print(f"\n{written} written, {skipped} already present, {failed} failed "
          f"-> {SEED_CACHE_DIR.relative_to(SEED_CACHE_DIR.parent.parent)}")
    if failed:
        print("Re-run once the quota resets to fill the rest.")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true",
                        help="report which questions are seeded; makes no API calls")
    parser.add_argument("--force", action="store_true",
                        help="delete and re-answer every seed entry")
    args = parser.parse_args()
    return verify() if args.verify else warm(args.force)


if __name__ == "__main__":
    sys.exit(main())
