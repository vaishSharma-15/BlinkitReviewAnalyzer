"""Phase 03 — Relevance gate: LLM binary classifier over normalized records.

Keeps items that speak to shopping behaviour, category choice, product discovery,
assortment, or trialing something new; drops pure delivery/refund/crash rants unless
they encode a category-level barrier.

Items are classified in batches (multiple review texts per LLM call, matched back by
index) rather than one-per-call, since the Gemini free tier caps at 500 requests/day —
one-per-call would take ~65 days for the full corpus; batching ~25 items/call needs
only ~400 requests total. A batch that fails to parse is retried once, then recursively
split in half; only individual items that still fail at the smallest split are
quarantined, so one malformed response can't silently drop a whole batch.

Usage:
    python -m src.relevance --config config.yaml [--limit N] [--workers 4] [--batch-size 25]
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from src.ingest.common import base_arg_parser, setup_logging
from src.llm import DailyQuotaExhausted, call_llm
from src.schemas import NormalizedRecord

REPO_ROOT = Path(__file__).resolve().parent.parent
NORMALIZED_PATH = REPO_ROOT / "data" / "normalized" / "normalized.jsonl"
DATA_RELEVANT = REPO_ROOT / "data" / "relevant"
RELEVANT_PATH = DATA_RELEVANT / "relevant.jsonl"
ALL_CLASSIFICATIONS_PATH = DATA_RELEVANT / "all_classifications.jsonl"
FAILED_PATH = DATA_RELEVANT / "failed.jsonl"
MANIFEST_PATH = DATA_RELEVANT / "manifest.json"

PROMPT_PATH = REPO_ROOT / "prompts" / "relevance_batch.md"
PROMPT_VERSION = "v2-batch"
MIN_BATCH_SIZE = 5  # below this, stop recursing and quarantine individually

# Cheap keyword pre-filter, run before any LLM call, to avoid spending free-tier quota
# on items that are near-certainly pure delivery/refund/crash noise. This trades some
# recall (a relevant item using no thematic keyword at all would be missed) for a large
# cut in LLM calls; the reduction ratio is logged so the tradeoff is visible, not hidden.
THEME_KEYWORDS = [
    # category names / synonyms
    "grocery", "groceries", "vegetable", "fruit", "dairy", "bakery", "snack", "beverage",
    "household", "personal care", "beauty", "makeup", "cosmetic", "baby", "diaper",
    "pet", "dog", "cat", "electronics", "earphone", "charger", "cable", "gadget",
    "home", "kitchen", "utensil", "toy", "stationery", "gift", "festival", "pharmacy",
    "medicine", "wellness", "supplement",
    # specific product exemplars — category words alone miss items that only name the
    # product (e.g. "fake ghee" never says "dairy" or "quality")
    "ghee", "milk", "paneer", "curd", "atta", "flour", "rice", "oil", "spice", "masala",
    "soap", "shampoo", "serum", "cream", "lotion", "sanitary", "napkin", "formula",
    "diapers", "mixer", "cookware", "cutlery", "candle", "decor", "wrapping",
    # discovery / behaviour / barrier language
    "discover", "explore", "find", "search", "recommend", "suggest", "never tried",
    "first time", "new to", "switch", "compare", "zepto", "instamart", "swiggy",
    "dmart", "bigbasket", "amazon", "nykaa", "why do i", "always buy", "every time",
    "habit", "reorder", "re-order", "same item", "same product", "trust", "quality",
    "fresh", "expired", "expiry", "brand", "assortment", "in stock", "out of stock",
    "doesn't have", "don't have", "not available", "variety", "options", "range",
    "stick to", "comfortable buying", "would never", "only order", "only buy",
    "won't buy", "will not buy", "wont buy", "not buying", "avoid", "stopped buying",
    "prefer", "rather buy", "better than", "used to buy", "shifted to", "moved to",
    # authenticity / defect language — often the only signal for a trust barrier
    "fake", "duplicate", "counterfeit", "spoiled", "spoilt", "rotten", "stale",
    "moldy", "mouldy", "damaged", "defective", "adulterated", "low quality",
    "cheap quality", "poor quality", "not genuine", "not original",
    # hinglish equivalents
    "bharosa", "vishwas", "naya", "nayi", "try nahi", "kabhi nahi liya",
]
THEME_KEYWORDS_RE = re.compile("|".join(re.escape(k) for k in THEME_KEYWORDS), re.IGNORECASE)


def has_theme_signal(text: str) -> bool:
    return bool(THEME_KEYWORDS_RE.search(text))


def load_system_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return text.split("---", 2)[-1].strip()


def build_batch_content(records: List[NormalizedRecord]) -> str:
    lines = [f"{i}: {r.text}" for i, r in enumerate(records, start=1)]
    return "\n".join(lines)


def parse_batch_response(raw: Optional[str], expected_count: int) -> Optional[List[dict]]:
    if raw is None:
        return None
    cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or len(data) != expected_count:
        return None
    for item in data:
        if not isinstance(item, dict) or "index" not in item or "relevant" not in item or "reason" not in item:
            return None
    return data


def classify_batch(system_prompt: str, records: List[NormalizedRecord]) -> dict:
    """Returns {record.id: {"relevant": bool, "reason": str}} for every record, or
    raises DailyQuotaExhausted. Recursively halves the batch on persistent parse
    failure; individual items are quarantined (status "failed") only once the batch
    can't be split further."""
    user_content = build_batch_content(records)
    raw = call_llm(system_prompt, user_content, PROMPT_VERSION, json_mode=True)
    parsed = parse_batch_response(raw, len(records))

    if parsed is None:
        repair_suffix = (
            f"\n\nYour previous response was not a valid JSON array of exactly "
            f"{len(records)} objects. Respond again with ONLY the JSON array, one "
            f"object per item, in the same order."
        )
        raw_repair = call_llm(system_prompt + repair_suffix, user_content, PROMPT_VERSION + "-repair", json_mode=True)
        parsed = parse_batch_response(raw_repair, len(records))

    if parsed is not None:
        results = {}
        for item, record in zip(sorted(parsed, key=lambda x: x["index"]), records):
            results[record.id] = {"status": "ok", "relevant": bool(item["relevant"]), "reason": item["reason"]}
        return results

    if len(records) <= MIN_BATCH_SIZE:
        return {r.id: {"status": "failed", "raw": raw} for r in records}

    mid = len(records) // 2
    left = classify_batch(system_prompt, records[:mid])
    right = classify_batch(system_prompt, records[mid:])
    return {**left, **right}


def main():
    parser = base_arg_parser("Run the relevance gate over normalized records")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent batch calls")
    parser.add_argument("--batch-size", type=int, default=40, help="Items per LLM call")
    args = parser.parse_args()
    logger = setup_logging("relevance")

    if not NORMALIZED_PATH.exists():
        logger.error("no normalized data found at %s — run src.normalize first", NORMALIZED_PATH)
        return

    all_records = []
    with open(NORMALIZED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            all_records.append(NormalizedRecord.model_validate_json(line))
            if args.limit is not None and len(all_records) >= args.limit:
                break

    # The keyword list is Latin-script only, so it under-matches Devanagari Hindi
    # almost completely (measured: hi survived at 6.2% vs en at 31.1% before this split
    # — not a real signal difference, a blind spot). Only pre-filter English; send every
    # hi/hinglish/other record straight to the LLM so no non-English review risks being
    # silently dropped before the model even sees it.
    def should_send_to_llm(r: NormalizedRecord) -> bool:
        if r.lang != "en":
            return True
        return has_theme_signal(r.text)

    records = [r for r in all_records if should_send_to_llm(r)]
    prefiltered_out = len(all_records) - len(records)
    logger.info(
        "pre-filter (English-only keyword gate; all non-English pass through): %d -> %d sent to LLM (%d skipped)",
        len(all_records), len(records), prefiltered_out,
    )

    system_prompt = load_system_prompt()

    records_to_send_ids = {r.id for r in records}
    results = {}
    for record in all_records:
        if record.id not in records_to_send_ids:
            results[record.id] = {
                "status": "ok", "relevant": False,
                "reason": "prefiltered: no thematic keyword match (English only), not sent to LLM",
            }

    batches = [records[i:i + args.batch_size] for i in range(0, len(records), args.batch_size)]
    logger.info("classifying %d records in %d batches of up to %d", len(records), len(batches), args.batch_size)

    quota_exhausted = False
    attempted_ids = set()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(classify_batch, system_prompt, batch): batch for batch in batches}
        done_batches = 0
        for future in as_completed(futures):
            batch = futures[future]
            try:
                batch_results = future.result()
            except DailyQuotaExhausted:
                quota_exhausted = True
                logger.warning(
                    "daily quota exhausted after %d/%d batches — stopping early. Cached responses "
                    "are preserved; re-run this exact command once the quota resets to resume at no "
                    "extra cost for already-completed batches.",
                    done_batches, len(batches),
                )
                for f in futures:
                    f.cancel()
                break

            results.update(batch_results)
            attempted_ids.update(batch_results.keys())
            done_batches += 1
            if done_batches % 5 == 0 or done_batches == len(batches):
                logger.info("classified %d/%d batches (%d items)", done_batches, len(batches), len(attempted_ids))

    records = all_records  # write-out loop below needs the full set, not just LLM-sent ones

    DATA_RELEVANT.mkdir(parents=True, exist_ok=True)
    relevant_count = 0
    failed_count = 0
    not_yet_attempted = 0

    with open(RELEVANT_PATH, "w", encoding="utf-8") as relevant_f, \
         open(ALL_CLASSIFICATIONS_PATH, "w", encoding="utf-8") as all_f, \
         open(FAILED_PATH, "w", encoding="utf-8") as failed_f:
        for record in records:
            result = results.get(record.id)
            if result is None:
                not_yet_attempted += 1
                continue
            if result["status"] == "failed":
                failed_f.write(json.dumps({"id": record.id, "text": record.text, "raw_response": result.get("raw")}) + "\n")
                failed_count += 1
                continue

            all_f.write(json.dumps({
                "id": record.id, "relevant": result["relevant"], "reason": result["reason"],
            }) + "\n")

            if result["relevant"]:
                out = record.model_dump()
                out["meta"]["relevance_reason"] = result["reason"]
                relevant_f.write(json.dumps(out) + "\n")
                relevant_count += 1

    not_relevant_count = len(records) - relevant_count - failed_count - not_yet_attempted
    logger.info(
        "done: total=%d sent_to_llm=%d prefiltered_out=%d relevant=%d not_relevant=%d failed=%d not_yet_attempted=%d%s",
        len(records), len(records) - prefiltered_out, prefiltered_out,
        relevant_count, not_relevant_count, failed_count, not_yet_attempted,
        " [STOPPED EARLY: daily quota exhausted]" if quota_exhausted else "",
    )

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "total_records": len(records),
            "sent_to_llm": len(records) - prefiltered_out,
            "prefiltered_out": prefiltered_out,
            "relevant": relevant_count,
            "not_relevant": not_relevant_count,
            "failed": failed_count,
            "not_yet_attempted": not_yet_attempted,
            "quota_exhausted_stopped_early": quota_exhausted,
            "prompt_version": PROMPT_VERSION,
            "batch_size": args.batch_size,
        }, f, indent=2)


if __name__ == "__main__":
    main()
