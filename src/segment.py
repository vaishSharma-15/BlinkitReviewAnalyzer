"""Phase 04b — Segment: derive shopper segments from the reviews themselves, and assign
one to every enriched record, with a verbatim quote proving each assignment.

Why this exists alongside the segment_signals already in src/enrich.py: those four
fields (family_stage, city_tier, price_sensitivity, has_pet) are demographic slots, and
a public app-store review almost never reveals them. The enrichment prompt is right to
answer "unknown" rather than guess, which is exactly why three of the four are unknown
for 98-99% of the corpus — the labels are honest but nearly empty. This step segments on
what reviews DO state: how people shop, what they refuse to buy, what they compare
against. Those are observable in the text, so the segmentation can be both strict and
populated.

Two stages:

  discover — a stratified sample goes to the LLM, which proposes 4-7 behaviour-defined
             segments, each with verbatim example quotes. Frozen to taxonomy.json so
             every later run classifies against a stable list.
  assign   — every record is classified against that frozen taxonomy in batches. Each
             assignment must carry an evidence_quote copied verbatim from the review.

"No guesswork" is enforced here, not merely requested in the prompt: an evidence quote
that does not appear in the review text is rejected in code and the record is recorded
as unassigned. A prompt rule the model can quietly ignore is not a guarantee; a
post-hoc string check is.

Usage:
    python -m src.segment discover [--sample 240]
    python -m src.segment assign [--limit N] [--workers 4] [--batch-size 12]
    python -m src.segment report
"""
import argparse
import json
import random
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple

from src.ingest.common import setup_logging
from src.llm import DailyQuotaExhausted, call_llm

REPO_ROOT = Path(__file__).resolve().parent.parent
ENRICHED_PATH = REPO_ROOT / "data" / "enriched" / "enriched.jsonl"
DATA_SEGMENTS = REPO_ROOT / "data" / "segments"
TAXONOMY_PATH = DATA_SEGMENTS / "taxonomy.json"
ASSIGNMENTS_PATH = DATA_SEGMENTS / "assignments.jsonl"
MANIFEST_PATH = DATA_SEGMENTS / "manifest.json"

DISCOVER_PROMPT_PATH = REPO_ROOT / "prompts" / "segment_discover.md"
ASSIGN_PROMPT_PATH = REPO_ROOT / "prompts" / "segment_assign.md"
DISCOVER_VERSION = "segment-discover-v1"
ASSIGN_VERSION = "segment-assign-v1"

UNASSIGNED = "unassigned"
MIN_BATCH_SIZE = 3
# Long enough that a quote is a real span of the review rather than a common word that
# would match almost anything ("good", "app"), short enough not to reject a terse review.
MIN_QUOTE_CHARS = 12
SAMPLE_TEXT_CHARS = 400
REVIEW_TEXT_CHARS = 600


def load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8").split("---", 2)[-1].strip()


def load_enriched() -> List[dict]:
    if not ENRICHED_PATH.exists():
        return []
    records = []
    with open(ENRICHED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def normalise(text: str) -> str:
    """Fold a string to the form quotes are compared in.

    Deliberately forgiving about the things a model reformats without changing meaning —
    unicode quote characters, case, runs of whitespace — and unforgiving about
    everything else. The point is to catch invented quotes, not to punish the model for
    turning ' into ’.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"[\s​]+", " ", text)
    return text.strip().lower()


def quote_supported(quote: str, source_text: str) -> bool:
    """True when `quote` really is a span of `source_text`."""
    if not quote or len(quote.strip()) < MIN_QUOTE_CHARS:
        return False
    return normalise(quote) in normalise(source_text)


# --- discover ---------------------------------------------------------------

def stratified_sample(records: List[dict], size: int, seed: int = 7) -> List[dict]:
    """Spread the sample across sources and sentiment bands.

    A plain random sample of this corpus is ~89% Play Store and ~60% negative, so the
    segments discovered from it would describe angry Play Store reviewers and miss the
    quieter behaviour the study is actually about.
    """
    rng = random.Random(seed)

    def band(r):
        s = r.get("sentiment", 0)
        return "neg" if s < -0.2 else ("pos" if s > 0.2 else "neu")

    buckets = {}
    for r in records:
        buckets.setdefault((r.get("source"), band(r)), []).append(r)
    for items in buckets.values():
        rng.shuffle(items)

    picked, keys = [], sorted(buckets, key=lambda k: (str(k[0]), str(k[1])))
    while len(picked) < size and any(buckets[k] for k in keys):
        for k in keys:
            if buckets[k] and len(picked) < size:
                picked.append(buckets[k].pop())
    rng.shuffle(picked)
    return picked


def parse_discovery(raw: Optional[str], sample: List[dict]) -> Tuple[List[dict], List[str]]:
    """Returns (accepted segments, rejection notes).

    A segment is only kept when its example quotes are genuinely in the sampled reviews.
    A model that invents an illustrative quote here would seed the whole taxonomy with a
    shopper who does not exist.
    """
    if raw is None:
        return [], ["no response from the model"]
    cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return [], [f"unparseable response: {exc}"]

    corpus = " \n ".join(r["text"] for r in sample)
    accepted, notes = [], []
    for seg in data.get("segments", []):
        seg_id = str(seg.get("segment_id", "")).strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,48}", seg_id) or seg_id == UNASSIGNED:
            notes.append(f"dropped segment with unusable id {seg_id!r}")
            continue
        quotes = [q for q in seg.get("example_quotes", []) if quote_supported(q, corpus)]
        if not quotes:
            notes.append(f"dropped {seg_id}: no example quote appears verbatim in the sample")
            continue
        accepted.append({
            "segment_id": seg_id,
            "name": str(seg.get("name", seg_id)).strip(),
            "definition": str(seg.get("definition", "")).strip(),
            "inclusion_rule": str(seg.get("inclusion_rule", "")).strip(),
            "distinguished_from": str(seg.get("distinguished_from", "")).strip(),
            "example_quotes": quotes[:3],
        })
    return accepted, notes


def cmd_discover(args, logger):
    records = load_enriched()
    if not records:
        logger.error("no enriched data at %s — run src.enrich first", ENRICHED_PATH)
        return
    sample = stratified_sample(records, args.sample)
    logger.info("discovering segments from a stratified sample of %d reviews", len(sample))

    numbered = "\n".join(f"{i}: {r['text'][:SAMPLE_TEXT_CHARS]}" for i, r in enumerate(sample, start=1))
    raw = call_llm(load_prompt(DISCOVER_PROMPT_PATH), numbered, DISCOVER_VERSION, json_mode=True)
    segments, notes = parse_discovery(raw, sample)
    for note in notes:
        logger.warning("%s", note)
    if not segments:
        logger.error("no segment survived the verbatim-quote check — taxonomy not written")
        return

    DATA_SEGMENTS.mkdir(parents=True, exist_ok=True)
    TAXONOMY_PATH.write_text(json.dumps({
        "prompt_version": DISCOVER_VERSION,
        "sample_size": len(sample),
        "segments": segments,
        "rejected": notes,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("wrote %d segments to %s", len(segments), TAXONOMY_PATH)
    for seg in segments:
        logger.info("  %-28s %s", seg["segment_id"], seg["definition"])


# --- assign -----------------------------------------------------------------

def taxonomy_block(segments: List[dict]) -> str:
    lines = ["SEGMENT DEFINITIONS:"]
    for seg in segments:
        lines.append(f"- {seg['segment_id']} ({seg['name']}): {seg['definition']}")
        if seg.get("inclusion_rule"):
            lines.append(f"    include when: {seg['inclusion_rule']}")
        if seg.get("distinguished_from"):
            lines.append(f"    not to be confused with: {seg['distinguished_from']}")
    lines.append(f"- {UNASSIGNED}: the review does not evidence any segment above.")
    return "\n".join(lines)


def parse_assignments(raw: Optional[str], expected: int) -> Optional[List[dict]]:
    if raw is None:
        return None
    cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or len(data) != expected:
        return None
    for item in data:
        if not isinstance(item, dict) or "index" not in item or "segment_id" not in item:
            return None
    return data


def assign_batch(system_prompt: str, records: List[dict], valid_ids: set) -> dict:
    """Returns {id: {"segment_id", "evidence_quote", "rejected"}}, halving the batch on
    a persistent parse failure exactly as src.enrich does."""
    user_content = "\n".join(f"{i}: {r['text'][:REVIEW_TEXT_CHARS]}" for i, r in enumerate(records, start=1))
    raw = call_llm(system_prompt, user_content, ASSIGN_VERSION, json_mode=True)
    parsed = parse_assignments(raw, len(records))

    if parsed is None:
        repair = (f"\n\nYour previous response was not a valid JSON array of exactly "
                  f"{len(records)} objects. Respond again with ONLY the JSON array, one "
                  f"object per item, in the same order.")
        parsed = parse_assignments(
            call_llm(system_prompt + repair, user_content, ASSIGN_VERSION + "-repair", json_mode=True),
            len(records))

    if parsed is None:
        if len(records) <= MIN_BATCH_SIZE:
            return {r["id"]: {"segment_id": UNASSIGNED, "evidence_quote": "", "rejected": "unparseable"}
                    for r in records}
        mid = len(records) // 2
        return {**assign_batch(system_prompt, records[:mid], valid_ids),
                **assign_batch(system_prompt, records[mid:], valid_ids)}

    out = {}
    for item, record in zip(sorted(parsed, key=lambda x: x.get("index", 0)), records):
        seg_id = str(item.get("segment_id", UNASSIGNED)).strip()
        quote = str(item.get("evidence_quote", "") or "")
        if seg_id == UNASSIGNED or seg_id not in valid_ids:
            # An off-taxonomy id is a label the dashboard has no definition for; it is
            # dropped rather than displayed as if it were a discovered segment.
            reason = "" if seg_id == UNASSIGNED else "off_taxonomy"
            out[record["id"]] = {"segment_id": UNASSIGNED, "evidence_quote": "", "rejected": reason}
        elif not quote_supported(quote, record["text"]):
            # The label may well be right — but nothing in the text proves it, which is
            # the definition of guesswork for this pipeline.
            out[record["id"]] = {"segment_id": UNASSIGNED, "evidence_quote": "", "rejected": "unverifiable_quote"}
        else:
            out[record["id"]] = {"segment_id": seg_id, "evidence_quote": quote.strip(), "rejected": ""}
    return out


def cmd_assign(args, logger):
    if not TAXONOMY_PATH.exists():
        logger.error("no taxonomy at %s — run `python -m src.segment discover` first", TAXONOMY_PATH)
        return
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    segments = taxonomy["segments"]
    valid_ids = {s["segment_id"] for s in segments}

    records = load_enriched()
    if args.limit:
        records = records[:args.limit]
    if not records:
        logger.error("no enriched data at %s — run src.enrich first", ENRICHED_PATH)
        return

    system_prompt = load_prompt(ASSIGN_PROMPT_PATH) + "\n\n" + taxonomy_block(segments)
    batches = [records[i:i + args.batch_size] for i in range(0, len(records), args.batch_size)]
    logger.info("assigning %d records against %d segments in %d batches of up to %d",
                len(records), len(segments), len(batches), args.batch_size)

    results, quota_exhausted, done = {}, False, 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(assign_batch, system_prompt, b, valid_ids): b for b in batches}
        for future in as_completed(futures):
            try:
                results.update(future.result())
            except DailyQuotaExhausted:
                quota_exhausted = True
                logger.warning("daily quota exhausted after %d/%d batches — re-run this exact "
                               "command tomorrow to resume from the disk cache at no cost",
                               done, len(batches))
                for f in futures:
                    f.cancel()
                break
            done += 1
            if done % 10 == 0 or done == len(batches):
                logger.info("assigned %d/%d batches", done, len(batches))

    DATA_SEGMENTS.mkdir(parents=True, exist_ok=True)
    counts, rejects, written = {}, {}, 0
    with open(ASSIGNMENTS_PATH, "w", encoding="utf-8") as f:
        for record in records:
            result = results.get(record["id"])
            if result is None:
                continue
            f.write(json.dumps({"id": record["id"], "segment_id": result["segment_id"],
                                "evidence_quote": result["evidence_quote"]}, ensure_ascii=False) + "\n")
            counts[result["segment_id"]] = counts.get(result["segment_id"], 0) + 1
            if result["rejected"]:
                rejects[result["rejected"]] = rejects.get(result["rejected"], 0) + 1
            written += 1

    assigned = written - counts.get(UNASSIGNED, 0)
    manifest = {
        "prompt_version": ASSIGN_VERSION,
        "taxonomy_version": taxonomy.get("prompt_version"),
        "total_records": len(records),
        "labelled": written,
        "assigned": assigned,
        "unassigned": counts.get(UNASSIGNED, 0),
        "assigned_share": round(assigned / written, 4) if written else 0,
        "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        # Labels the model produced that this step threw away, and why. The
        # unverifiable_quote line is the cost of the no-guesswork rule, in numbers.
        "rejected": rejects,
        "quota_exhausted_stopped_early": quota_exhausted,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("done: labelled=%d assigned=%d (%.1f%%) unassigned=%d rejected=%s%s",
                written, assigned, 100 * manifest["assigned_share"], manifest["unassigned"],
                rejects or "{}", " [STOPPED EARLY: quota]" if quota_exhausted else "")


def cmd_report(args, logger):
    if not MANIFEST_PATH.exists():
        logger.error("nothing to report — run discover then assign first")
        return
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    names = {s["segment_id"]: s["name"] for s in taxonomy["segments"]}
    total = manifest["labelled"] or 1
    logger.info("segment assignment over %d reviews (%.1f%% carry a segment)",
                total, 100 * manifest["assigned_share"])
    for seg_id, n in manifest["counts"].items():
        logger.info("  %-28s %5d  %5.1f%%  %s", seg_id, n, 100 * n / total, names.get(seg_id, ""))
    if manifest.get("rejected"):
        logger.info("labels rejected by the evidence check: %s", manifest["rejected"])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_discover = sub.add_parser("discover", help="Derive the segment taxonomy from a sample")
    p_discover.add_argument("--sample", type=int, default=240, help="Reviews to read when discovering")

    p_assign = sub.add_parser("assign", help="Assign every record against the frozen taxonomy")
    p_assign.add_argument("--limit", type=int, default=None)
    p_assign.add_argument("--workers", type=int, default=4)
    p_assign.add_argument("--batch-size", type=int, default=12)

    sub.add_parser("report", help="Print the distribution from the last assign run")

    args = parser.parse_args()
    logger = setup_logging("segment")
    {"discover": cmd_discover, "assign": cmd_assign, "report": cmd_report}[args.command](args, logger)


if __name__ == "__main__":
    main()
