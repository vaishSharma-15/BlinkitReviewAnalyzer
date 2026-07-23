import argparse
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator, List

import yaml

from src.schemas import RawRecord

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"

USERNAME_KEYS = {"author", "username", "user", "reviewer", "channel", "handle"}


def setup_logging(source: str) -> logging.Logger:
    logger = logging.getLogger(source)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(f"[{source}] %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def base_arg_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of new records fetched")
    return parser


def window_start(months: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=30 * months)


def strip_pii(meta: dict) -> dict:
    """Drop username-shaped fields so no PII is persisted, per the no-PII hard constraint."""
    return {k: v for k, v in meta.items() if k.lower() not in USERNAME_KEYS}


def load_existing_ids(source: str) -> set:
    path = DATA_RAW / f"{source}.jsonl"
    ids = set()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ids.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return ids


def append_records(source: str, records: Iterable[RawRecord]) -> int:
    """Append new raw records to data/raw/<source>.jsonl, skipping ids already present.

    Never truncates or rewrites the file, so a re-run is safe and resumable.
    """
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    existing_ids = load_existing_ids(source)
    path = DATA_RAW / f"{source}.jsonl"
    written = 0
    with open(path, "a", encoding="utf-8") as f:
        for record in records:
            if record.id in existing_ids:
                continue
            f.write(record.model_dump_json() + "\n")
            existing_ids.add(record.id)
            written += 1
    return written


def write_manifest(source: str, config: dict, extra: dict) -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    manifest_path = DATA_RAW / f"{source}.manifest.json"
    manifest = {
        "source": source,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        **extra,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)


def total_count(source: str) -> int:
    path = DATA_RAW / f"{source}.jsonl"
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


SPAM_PATTERNS = [
    re.compile(r"use\s+my\s+referral\s+code", re.IGNORECASE),
    re.compile(r"promo\s*code", re.IGNORECASE),
    re.compile(r"^[\W\d_]*$"),  # pure punctuation/emoji/numbers, no letters
]


def is_probably_spam(text: str) -> bool:
    if not text or len(text.strip()) < 3:
        return True
    return any(pattern.search(text) for pattern in SPAM_PATTERNS)
