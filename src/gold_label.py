"""Phase 07 (part 1) — Gold set: interactive CLI for hand-labelling a fixed 100-item
sample, per docs/ProblemStatement.md §7 item 1.

This is deliberately NOT automatable — the whole point of a gold set is an independent
human judgment to check the LLM classifiers against, so no LLM call happens here. Do not
substitute a model-generated label for a human one; that would make the validation
circular (grading the classifier's own outputs).

Sampling is seeded and cached to data/gold/sample.jsonl on first run, so the same 100
items are shown across sessions. Labels are appended to data/gold/labels.jsonl as you
go — safe to quit (Ctrl+C) and resume later; already-labelled ids are skipped.

For each item you'll be asked:
  1. Is this relevant to shopping behaviour/category choice/discovery/assortment/trial?
     (y/n) — ground truth for the Phase 03 relevance gate.
  2. If yes: which barrier_type best fits (or "none")? — ground truth for Phase 04's
     barrier classifier. Skipped if not relevant.

Usage:
    python -m src.gold_label --config config.yaml [--sample-size 100] [--seed 42]
"""
import json
import random
from pathlib import Path

from src.ingest.common import base_arg_parser, setup_logging
from src.schemas import BARRIER_TYPE

REPO_ROOT = Path(__file__).resolve().parent.parent
NORMALIZED_PATH = REPO_ROOT / "data" / "normalized" / "normalized.jsonl"
DATA_GOLD = REPO_ROOT / "data" / "gold"
SAMPLE_PATH = DATA_GOLD / "sample.jsonl"
LABELS_PATH = DATA_GOLD / "labels.jsonl"


def load_or_create_sample(sample_size: int, seed: int, logger) -> list:
    DATA_GOLD.mkdir(parents=True, exist_ok=True)
    if SAMPLE_PATH.exists():
        with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
            sample = [json.loads(line) for line in f if line.strip()]
        logger.info("using existing cached sample of %d items from %s", len(sample), SAMPLE_PATH)
        return sample

    with open(NORMALIZED_PATH, "r", encoding="utf-8") as f:
        pool = [json.loads(line) for line in f if line.strip()]

    rng = random.Random(seed)
    sample = rng.sample(pool, min(sample_size, len(pool)))
    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        for row in sample:
            f.write(json.dumps(row) + "\n")
    logger.info("sampled %d new items (seed=%d), cached to %s", len(sample), seed, SAMPLE_PATH)
    return sample


def load_existing_labels() -> dict:
    if not LABELS_PATH.exists():
        return {}
    labels = {}
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                labels[row["id"]] = row
    return labels


def prompt_relevant() -> bool:
    while True:
        ans = input("  Relevant to shopping behaviour/category choice/discovery? [y/n]: ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  please answer y or n")


def prompt_barrier_type() -> str:
    options = [b for b in BARRIER_TYPE if b != "none"]
    print("  barrier_type options: " + ", ".join(f"{i+1}={b}" for i, b in enumerate(options)) + f", 0=none")
    while True:
        ans = input("  barrier_type [number or name]: ").strip().lower()
        if ans in ("0", "none", ""):
            return "none"
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return options[int(ans) - 1]
        if ans in options:
            return ans
        print("  invalid choice")


def main():
    parser = base_arg_parser("Interactively hand-label the 100-item gold set")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logger = setup_logging("gold_label")

    if not NORMALIZED_PATH.exists():
        logger.error("no normalized data found at %s — run src.normalize first", NORMALIZED_PATH)
        return

    sample = load_or_create_sample(args.sample_size, args.seed, logger)
    existing = load_existing_labels()
    remaining = [row for row in sample if row["id"] not in existing]

    if not remaining:
        logger.info("all %d items already labelled — nothing to do. See %s", len(sample), LABELS_PATH)
        return

    logger.info(
        "%d/%d already labelled. Labelling %d remaining. Ctrl+C anytime to save and resume later.",
        len(existing), len(sample), len(remaining),
    )

    with open(LABELS_PATH, "a", encoding="utf-8") as f:
        for i, row in enumerate(remaining, start=1):
            print(f"\n[{len(existing) + i}/{len(sample)}] id={row['id']} source={row['source']}")
            print(f"  \"{row['text']}\"")
            try:
                relevant = prompt_relevant()
                barrier_type = prompt_barrier_type() if relevant else "none"
            except KeyboardInterrupt:
                print("\nSaved progress. Resume anytime with the same command.")
                return
            label = {"id": row["id"], "relevant": relevant, "barrier_type": barrier_type}
            f.write(json.dumps(label) + "\n")
            f.flush()

    logger.info("done: %d/%d items labelled. See %s", len(sample), len(sample), LABELS_PATH)


if __name__ == "__main__":
    main()
