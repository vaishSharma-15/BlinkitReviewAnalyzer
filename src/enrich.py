"""Phase 04 — Enrich: add structured, closed-vocabulary labels to each relevant record.

Reads data/relevant/relevant.jsonl, writes data/enriched/enriched.jsonl. Items are
enriched in batches (multiple items per LLM call, matched back by index) rather than
one-per-call, since the Gemini free tier caps at 500 requests/day — see src/relevance.py
for the same design rationale. A batch that fails to parse, or contains a
closed-vocabulary violation, is retried once, then recursively split in half; only
individual items that still fail at the smallest split are quarantined to
data/enriched/failed.jsonl.

Usage:
    python -m src.enrich --config config.yaml [--limit N] [--workers 4] [--batch-size 15] [--input PATH]
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from src.ingest.common import base_arg_parser, setup_logging
from src.llm import DailyQuotaExhausted, call_llm
from src.schemas import (
    BARRIER_TYPE, BEHAVIOUR_SIGNAL, CATEGORIES, CITY_TIER, EnrichedRecord,
    FAMILY_STAGE, HAS_PET, NormalizedRecord, PRICE_SENSITIVITY, SegmentSignals, THEMES,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RELEVANT_PATH = REPO_ROOT / "data" / "relevant" / "relevant.jsonl"
DATA_ENRICHED = REPO_ROOT / "data" / "enriched"
ENRICHED_PATH = DATA_ENRICHED / "enriched.jsonl"
FAILED_PATH = DATA_ENRICHED / "failed.jsonl"
MANIFEST_PATH = DATA_ENRICHED / "manifest.json"

PROMPT_PATH = REPO_ROOT / "prompts" / "enrich_batch.md"
PROMPT_VERSION = "v3-batch"
MIN_BATCH_SIZE = 3


def load_system_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return text.split("---", 2)[-1].strip()


def validate_enrichment(data: dict) -> Optional[str]:
    """Returns an error string if data violates the closed vocabulary, else None."""
    categories = data.get("categories_mentioned")
    if not isinstance(categories, list) or any(c not in CATEGORIES for c in categories):
        return f"categories_mentioned outside closed vocabulary: {categories}"

    if data.get("behaviour_signal") not in BEHAVIOUR_SIGNAL:
        return f"behaviour_signal outside closed vocabulary: {data.get('behaviour_signal')}"

    if data.get("barrier_type") not in BARRIER_TYPE:
        return f"barrier_type outside closed vocabulary: {data.get('barrier_type')}"

    if data.get("theme_id") not in THEMES:
        return f"theme_id outside closed vocabulary: {data.get('theme_id')}"

    segment = data.get("segment_signals")
    if not isinstance(segment, dict):
        return "segment_signals missing or not an object"
    if segment.get("family_stage") not in FAMILY_STAGE:
        return f"family_stage outside closed vocabulary: {segment.get('family_stage')}"
    if segment.get("city_tier") not in CITY_TIER:
        return f"city_tier outside closed vocabulary: {segment.get('city_tier')}"
    if segment.get("price_sensitivity") not in PRICE_SENSITIVITY:
        return f"price_sensitivity outside closed vocabulary: {segment.get('price_sensitivity')}"
    if segment.get("has_pet") not in HAS_PET:
        return f"has_pet outside closed vocabulary: {segment.get('has_pet')}"

    sentiment = data.get("sentiment")
    if not isinstance(sentiment, (int, float)) or not (-1.0 <= sentiment <= 1.0):
        return f"sentiment out of range: {sentiment}"

    if not isinstance(data.get("quote_worthy"), bool):
        return f"quote_worthy not a boolean: {data.get('quote_worthy')}"

    return None


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
        if not isinstance(item, dict) or "index" not in item:
            return None
        if validate_enrichment(item) is not None:
            return None
    return data


def enrich_batch(system_prompt: str, records: List[NormalizedRecord]) -> dict:
    """Returns {record.id: {"status": "ok", "data": {...}}} or raises DailyQuotaExhausted.
    Recursively halves the batch on persistent parse/vocab failure."""
    user_content = build_batch_content(records)
    raw = call_llm(system_prompt, user_content, PROMPT_VERSION, json_mode=True)
    parsed = parse_batch_response(raw, len(records))

    if parsed is None:
        repair_suffix = (
            f"\n\nYour previous response was not a valid JSON array of exactly "
            f"{len(records)} objects using only the allowed values. Respond again with "
            f"ONLY the JSON array, one object per item, in the same order."
        )
        raw_repair = call_llm(system_prompt + repair_suffix, user_content, PROMPT_VERSION + "-repair", json_mode=True)
        parsed = parse_batch_response(raw_repair, len(records))

    if parsed is not None:
        results = {}
        for item, record in zip(sorted(parsed, key=lambda x: x["index"]), records):
            results[record.id] = {"status": "ok", "data": item}
        return results

    if len(records) <= MIN_BATCH_SIZE:
        return {r.id: {"status": "failed", "raw": raw} for r in records}

    mid = len(records) // 2
    left = enrich_batch(system_prompt, records[:mid])
    right = enrich_batch(system_prompt, records[mid:])
    return {**left, **right}


def main():
    parser = base_arg_parser("Enrich relevant records with structured closed-vocabulary labels")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent batch calls")
    parser.add_argument("--batch-size", type=int, default=15, help="Items per LLM call")
    parser.add_argument("--input", default=None, help="Override input path (default: data/relevant/relevant.jsonl)")
    args = parser.parse_args()
    logger = setup_logging("enrich")

    input_path = Path(args.input) if args.input else RELEVANT_PATH
    if not input_path.exists():
        logger.error("no relevant data found at %s — run src.relevance first", input_path)
        return

    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            records.append(NormalizedRecord(
                id=raw["id"], source=raw["source"], url=raw["url"], date=raw["date"],
                text=raw["text"], rating=raw.get("rating"), lang=raw["lang"], meta=raw.get("meta", {}),
            ))
            if args.limit is not None and len(records) >= args.limit:
                break

    system_prompt = load_system_prompt()
    batches = [records[i:i + args.batch_size] for i in range(0, len(records), args.batch_size)]
    logger.info("enriching %d records in %d batches of up to %d", len(records), len(batches), args.batch_size)

    results = {}
    quota_exhausted = False
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(enrich_batch, system_prompt, batch): batch for batch in batches}
        done_batches = 0
        for future in as_completed(futures):
            try:
                batch_results = future.result()
            except DailyQuotaExhausted:
                quota_exhausted = True
                logger.warning(
                    "daily quota exhausted after %d/%d batches — stopping early. Re-run this exact "
                    "command once the quota resets to resume via the disk cache at no extra cost.",
                    done_batches, len(batches),
                )
                for f in futures:
                    f.cancel()
                break

            results.update(batch_results)
            done_batches += 1
            if done_batches % 5 == 0 or done_batches == len(batches):
                logger.info("enriched %d/%d batches", done_batches, len(batches))

    DATA_ENRICHED.mkdir(parents=True, exist_ok=True)
    enriched_count = 0
    failed_count = 0
    not_yet_attempted = 0

    with open(ENRICHED_PATH, "w", encoding="utf-8") as enriched_f, \
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

            data = result["data"]
            enriched = EnrichedRecord(
                id=record.id, source=record.source, url=record.url, date=record.date,
                text=record.text, lang=record.lang, rating=record.rating,
                relevant=True, relevance_reason=record.meta.get("relevance_reason", ""),
                categories_mentioned=data["categories_mentioned"],
                behaviour_signal=data["behaviour_signal"],
                barrier_type=data["barrier_type"],
                theme_id=data["theme_id"],
                segment_signals=SegmentSignals(**data["segment_signals"]),
                sentiment=data["sentiment"],
                quote_worthy=data["quote_worthy"],
                prompt_version=PROMPT_VERSION,
                meta=record.meta,
            )
            enriched_f.write(enriched.model_dump_json() + "\n")
            enriched_count += 1

    logger.info(
        "done: total=%d enriched=%d failed=%d not_yet_attempted=%d%s",
        len(records), enriched_count, failed_count, not_yet_attempted,
        " [STOPPED EARLY: daily quota exhausted]" if quota_exhausted else "",
    )

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(records),
            "enriched": enriched_count,
            "failed": failed_count,
            "not_yet_attempted": not_yet_attempted,
            "quota_exhausted_stopped_early": quota_exhausted,
            "prompt_version": PROMPT_VERSION,
            "batch_size": args.batch_size,
        }, f, indent=2)


if __name__ == "__main__":
    main()
