"""Phase 02 — Normalize: unify raw records into a single schema, detect language,
drop short/spam records, and dedup exact + near-duplicate content.

Reads every data/raw/<source>.jsonl file and writes data/normalized/normalized.jsonl.
Logs counts in/out at each filter step — this funnel feeds the Phase 07 scorecard.

Usage:
    python -m src.normalize --config config.yaml [--limit N]
"""
import hashlib
import re
from pathlib import Path
from typing import List

import numpy as np

from src.ingest.common import base_arg_parser, load_config, setup_logging
from src.lang_detect import detect_language
from src.schemas import NormalizedRecord, RawRecord, SOURCES

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_NORMALIZED = REPO_ROOT / "data" / "normalized"
OUTPUT_PATH = DATA_NORMALIZED / "normalized.jsonl"
MANIFEST_PATH = DATA_NORMALIZED / "manifest.json"

MIN_LENGTH = 15
NEAR_DUP_THRESHOLD = 0.95
EMBED_BATCH_SIZE = 64

SPAM_PATTERNS = [
    re.compile(r"use\s+my\s+referral\s+code", re.IGNORECASE),
    re.compile(r"\breferral\s*code\b", re.IGNORECASE),
    re.compile(r"promo\s*code", re.IGNORECASE),
    re.compile(r"^[\W\d_]*$"),  # pure punctuation/emoji/numbers, no letters
]


def is_spam(text: str) -> bool:
    return any(pattern.search(text) for pattern in SPAM_PATTERNS)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def exact_dedup_key(text: str) -> str:
    return hashlib.sha256(text.lower().encode("utf-8")).hexdigest()


def load_raw_records(limit) -> List[RawRecord]:
    records: List[RawRecord] = []
    for source in SOURCES:
        path = DATA_RAW / f"{source}.jsonl"
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(RawRecord.model_validate_json(line))
                if limit is not None and len(records) >= limit:
                    return records
    return records


def near_dedup(records: List[RawRecord], logger) -> List[RawRecord]:
    """Drop near-duplicate records (cosine > NEAR_DUP_THRESHOLD) within same-day,
    same-source buckets. Blocking by (source, date) bounds the comparison cost —
    near-duplicate spam/copy-paste content is overwhelmingly posted close in time by
    the same actor, so cross-day near-dup pairs are not worth an O(n^2) full scan."""
    from sentence_transformers import SentenceTransformer

    buckets: dict = {}
    for idx, record in enumerate(records):
        key = (record.source, record.date[:10])
        buckets.setdefault(key, []).append(idx)

    model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    keep_mask = [True] * len(records)

    for key, indices in buckets.items():
        if len(indices) < 2:
            continue
        texts = [records[i].text for i in indices]
        embeddings = model.encode(texts, batch_size=EMBED_BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)
        sims = embeddings @ embeddings.T

        for a in range(len(indices)):
            if not keep_mask[indices[a]]:
                continue
            for b in range(a + 1, len(indices)):
                if not keep_mask[indices[b]]:
                    continue
                if sims[a, b] > NEAR_DUP_THRESHOLD:
                    keep_mask[indices[b]] = False

    kept = [record for record, keep in zip(records, keep_mask) if keep]
    logger.info("near-dup dedup: %d -> %d (buckets=%d)", len(records), len(kept), len(buckets))
    return kept


def main():
    parser = base_arg_parser("Normalize raw records into a unified schema")
    args = parser.parse_args()
    load_config(args.config)  # validates config.yaml exists; normalize has no source-specific config
    logger = setup_logging("normalize")

    funnel = {}

    raw_records = load_raw_records(args.limit)
    funnel["raw"] = len(raw_records)
    logger.info("loaded raw=%d", len(raw_records))

    length_filtered = [r for r in raw_records if len(normalize_text(r.text)) >= MIN_LENGTH]
    funnel["after_length_filter"] = len(length_filtered)
    logger.info("after length filter (>=%d chars): %d", MIN_LENGTH, len(length_filtered))

    spam_filtered = [r for r in length_filtered if not is_spam(r.text)]
    funnel["after_spam_filter"] = len(spam_filtered)
    logger.info("after spam filter: %d", len(spam_filtered))

    seen_hashes = set()
    exact_deduped = []
    for record in spam_filtered:
        key = exact_dedup_key(normalize_text(record.text))
        if key in seen_hashes:
            continue
        seen_hashes.add(key)
        exact_deduped.append(record)
    funnel["after_exact_dedup"] = len(exact_deduped)
    logger.info("after exact dedup: %d", len(exact_deduped))

    near_deduped = near_dedup(exact_deduped, logger)
    funnel["after_near_dedup"] = len(near_deduped)

    normalized_records = []
    for record in near_deduped:
        text = normalize_text(record.text)
        normalized_records.append(NormalizedRecord(
            id=record.id,
            source=record.source,
            url=record.url,
            date=record.date,
            text=text,
            rating=record.rating,
            lang=detect_language(text),
            meta=record.meta,
        ))

    DATA_NORMALIZED.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for record in normalized_records:
            f.write(record.model_dump_json() + "\n")

    lang_counts = {}
    source_counts = {}
    for record in normalized_records:
        lang_counts[record.lang] = lang_counts.get(record.lang, 0) + 1
        source_counts[record.source] = source_counts.get(record.source, 0) + 1

    logger.info("wrote %d normalized records to %s", len(normalized_records), OUTPUT_PATH)
    logger.info("language breakdown: %s", lang_counts)
    logger.info("source breakdown: %s", source_counts)

    import json
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "funnel": funnel,
            "language_breakdown": lang_counts,
            "source_breakdown": source_counts,
            "min_length": MIN_LENGTH,
            "near_dup_threshold": NEAR_DUP_THRESHOLD,
        }, f, indent=2)


if __name__ == "__main__":
    main()
