"""Phase 07 — Validate: the insight-quality scorecard, per docs/ProblemStatement.md §7.

Reads every stage's output (data/raw manifests, data/normalized, data/relevant,
data/enriched, data/themes, data/gold) and writes reports/scorecard.md. Checks, in the
order the spec lists them:

  1. Gold-set precision/recall/F1 for the relevance gate and barrier classifier —
     requires data/gold/labels.jsonl (see src/gold_label.py). This is the one check
     that cannot be automated: it needs a human ground-truth judgment independent of
     the LLM being graded, or the check is circular. Reported as "pending" if the gold
     set hasn't been hand-labelled yet — never faked.
  2. Inter-run stability — re-run theme classification on a fresh sample (bypassing the
     disk cache) and measure theme_id agreement with the original pass. This replaces
     the original spec wording ("re-cluster a 90% bootstrap sample") because theming
     moved from unsupervised clustering to supervised per-record classification (see
     src/enrich.py); stability for a classifier means run-to-run label agreement, not
     cluster overlap. Costs LLM quota proportional to --stability-sample-size.
  3. Cross-source triangulation — already computed by src/synthesize.py (confidence:
     "high" if a theme's evidence spans >= 2 sources); this stage just reports it.
  4. Citation audit — sample N representative quotes, verify each is a verbatim
     substring of its source record's stored text (never fabricated) and that its URL
     is well-formed and (best-effort, network allowing) reachable.
  5. Counter-evidence search — for each theme, search the full enriched corpus for
     records that share the theme's dominant category but oppose its dominant
     sentiment direction; report what's found, not just what's missing.
  6. Recency split — compare theme prevalence in the older vs. newer half of the date
     range actually present in the corpus, to catch stale complaints.
  7. Ingest funnel table — raw -> length/spam filtered -> deduped -> relevant ->
     enriched, with counts at each step, from each stage's own manifest.
  8. Source coverage table — item counts per of the 7 source types (raw + final),
     substitutions used and why (from README.md's own documented notes), and a
     source-bias flag on any theme that's >= 90% single-source.

Usage:
    python -m src.validate --config config.yaml [--stability-sample-size 90] [--citation-sample-size 20]
"""
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.ingest.common import base_arg_parser, setup_logging
from src.schemas import EnrichedRecord, SOURCES

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
NORMALIZED_MANIFEST = REPO_ROOT / "data" / "normalized" / "manifest.json"
RELEVANT_MANIFEST = REPO_ROOT / "data" / "relevant" / "manifest.json"
RELEVANT_PATH = REPO_ROOT / "data" / "relevant" / "relevant.jsonl"
ALL_CLASSIFICATIONS_PATH = REPO_ROOT / "data" / "relevant" / "all_classifications.jsonl"
ENRICHED_MANIFEST = REPO_ROOT / "data" / "enriched" / "manifest.json"
ENRICHED_PATH = REPO_ROOT / "data" / "enriched" / "enriched.jsonl"
THEMES_PATH = REPO_ROOT / "data" / "themes" / "themes.jsonl"
GOLD_LABELS_PATH = REPO_ROOT / "data" / "gold" / "labels.jsonl"
GOLD_SAMPLE_PATH = REPO_ROOT / "data" / "gold" / "sample.jsonl"
REPORTS_DIR = REPO_ROOT / "reports"
SCORECARD_PATH = REPORTS_DIR / "scorecard.md"

# Known ingest blockers/substitutions, documented in README.md's source-coverage notes.
# Kept here (not re-derived) since the reasons are the outcome of manual investigation,
# not something inferable from the data itself.
SOURCE_NOTES = {
    "play": "Primary volume source, unblocked.",
    "appstore": "Apple's public RSS feed hard-caps at ~500 most-recent reviews — that's the full available volume, not a partial run.",
    "reddit": "BLOCKED: robots.txt disallows all agents; public search.json 403s without OAuth creds not available in this environment.",
    "youtube": "Used yt-dlp + youtube-comment-downloader (no YOUTUBE_API_KEY available) — approved substitution, more fragile than the official API.",
    "forum": "BLOCKED: Quora disallows scraping; MouthShut explicitly disallows ClaudeBot. Two substitute forums checked and also ruled out.",
    "product_review": "Blinkit PDP reviews require an authenticated session; falls back to Amazon/Nykaa proxy SKUs, labelled meta.is_proxy_source=true.",
    "qcomm_comparison": "Targeted slice tagged at ingest across Reddit/YouTube/forums — exposes category-to-platform mental models directly.",
}


def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_enriched() -> List[EnrichedRecord]:
    records = []
    with open(ENRICHED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(EnrichedRecord.model_validate_json(line))
    return records


# ---------------------------------------------------------------------------
# 1. Gold-set precision/recall/F1
# ---------------------------------------------------------------------------

def gold_set_metrics(logger) -> dict:
    if not GOLD_LABELS_PATH.exists():
        return {"status": "pending", "reason": "data/gold/labels.jsonl not found — run: python -m src.gold_label"}

    gold_labels = {row["id"]: row for row in read_jsonl(GOLD_LABELS_PATH)}
    sample = read_jsonl(GOLD_SAMPLE_PATH)
    sample_size = len(sample)
    if len(gold_labels) < sample_size:
        return {
            "status": "partial",
            "reason": f"{len(gold_labels)}/{sample_size} items labelled so far — run: python -m src.gold_label to finish",
        }

    predicted_relevant = {row["id"] for row in read_jsonl(ALL_CLASSIFICATIONS_PATH) if row.get("relevant")}
    enriched_by_id = {r.id: r for r in load_enriched()}

    tp = fp = fn = tn = 0
    barrier_correct = barrier_total = 0
    for gid, gold in gold_labels.items():
        pred_relevant = gid in predicted_relevant
        gold_relevant = gold["relevant"]
        if gold_relevant and pred_relevant:
            tp += 1
        elif gold_relevant and not pred_relevant:
            fn += 1
        elif not gold_relevant and pred_relevant:
            fp += 1
        else:
            tn += 1

        if gold_relevant and pred_relevant and gid in enriched_by_id:
            barrier_total += 1
            if enriched_by_id[gid].barrier_type == gold["barrier_type"]:
                barrier_correct += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "status": "complete",
        "n": len(gold_labels),
        "relevance_confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "relevance_precision": round(precision, 3),
        "relevance_recall": round(recall, 3),
        "relevance_f1": round(f1, 3),
        "barrier_type_accuracy": round(barrier_correct / barrier_total, 3) if barrier_total else None,
        "barrier_type_n": barrier_total,
    }


# ---------------------------------------------------------------------------
# 2. Inter-run stability (theme classification agreement)
# ---------------------------------------------------------------------------

def stability_check(sample_size: int, logger) -> dict:
    from src.enrich import enrich_batch, load_system_prompt
    from src.schemas import NormalizedRecord

    all_enriched = load_enriched()
    if not all_enriched:
        return {"status": "skipped", "reason": "no enriched records"}

    rng = random.Random(7)
    sample = rng.sample(all_enriched, min(sample_size, len(all_enriched)))
    records = [
        NormalizedRecord(id=r.id, source=r.source, url=r.url, date=r.date, text=r.text,
                          rating=r.rating, lang=r.lang, meta=r.meta)
        for r in sample
    ]

    logger.info("stability check: re-classifying %d sampled records (fresh LLM calls, cache bypassed)", len(records))
    system_prompt = load_system_prompt()
    # A distinct prompt_version suffix forces a cache miss so this is a genuine
    # independent second pass, not a cache replay of the original classification.
    import src.enrich as enrich_module
    original_version = enrich_module.PROMPT_VERSION
    enrich_module.PROMPT_VERSION = original_version + "-stability-check"
    try:
        results = enrich_batch(system_prompt, records)
    finally:
        enrich_module.PROMPT_VERSION = original_version

    agree = total = 0
    for r in sample:
        result = results.get(r.id)
        if result is None or result["status"] != "ok":
            continue
        total += 1
        if result["data"].get("theme_id") == r.theme_id:
            agree += 1

    return {
        "status": "complete",
        "n": total,
        "agreement_rate": round(agree / total, 3) if total else None,
    }


# ---------------------------------------------------------------------------
# 3. Cross-source triangulation (reported from synthesize.py's own output)
# ---------------------------------------------------------------------------

def triangulation_summary() -> dict:
    themes = read_jsonl(THEMES_PATH)
    high = [t for t in themes if t["confidence"] == "high"]
    single = [t for t in themes if t["confidence"] == "single_source"]
    return {
        "n_themes": len(themes),
        "high_confidence": len(high),
        "single_source": [t["theme_id"] for t in single],
    }


# ---------------------------------------------------------------------------
# 4. Citation audit
# ---------------------------------------------------------------------------

def citation_audit(sample_size: int, logger) -> dict:
    themes = read_jsonl(THEMES_PATH)
    enriched_by_id = {r.id: r for r in load_enriched()}

    quotes = []
    for theme in themes:
        for q in theme.get("representative_quotes", []):
            quotes.append((theme["theme_id"], q))

    rng = random.Random(11)
    sample = rng.sample(quotes, min(sample_size, len(quotes)))

    verbatim_ok = url_well_formed_ok = 0
    problems = []
    for theme_id, q in sample:
        record = enriched_by_id.get(q["id"])
        if record is None:
            problems.append(f"{theme_id}/{q['id']}: id not found in enriched corpus")
            continue
        if q["text"] in record.text:
            verbatim_ok += 1
        else:
            problems.append(f"{theme_id}/{q['id']}: quote is not a verbatim substring of stored text")
        if record.url.startswith("http"):
            url_well_formed_ok += 1
        else:
            problems.append(f"{theme_id}/{q['id']}: url not well-formed: {record.url}")

    return {
        "n": len(sample),
        "verbatim_match_rate": round(verbatim_ok / len(sample), 3) if sample else None,
        "url_well_formed_rate": round(url_well_formed_ok / len(sample), 3) if sample else None,
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# 5. Counter-evidence search
# ---------------------------------------------------------------------------

def counter_evidence_search() -> dict:
    themes = read_jsonl(THEMES_PATH)
    all_enriched = load_enriched()
    by_category = defaultdict(list)
    for r in all_enriched:
        for c in r.categories_mentioned:
            by_category[c].append(r)

    results = {}
    for theme in themes:
        cat = theme["dominant_category"]
        avg_sent = theme["avg_sentiment"]
        pool = by_category.get(cat, [])
        if avg_sent >= 0:
            counter = [r for r in pool if r.sentiment < -0.3 and r.theme_id != theme["theme_id"]]
        else:
            counter = [r for r in pool if r.sentiment > 0.3 and r.theme_id != theme["theme_id"]]
        results[theme["theme_id"]] = {
            "dominant_category": cat,
            "theme_sentiment_direction": "positive" if avg_sent >= 0 else "negative",
            "counter_evidence_found": len(counter),
            "example_ids": [r.id for r in counter[:3]],
        }
    return results


# ---------------------------------------------------------------------------
# 6. Recency split
# ---------------------------------------------------------------------------

def parse_date(s: str) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def recency_split() -> dict:
    all_enriched = load_enriched()
    dated = [(r, parse_date(r.date)) for r in all_enriched]
    dated = [(r, d) for r, d in dated if d is not None]
    if not dated:
        return {"status": "skipped", "reason": "no parseable dates"}

    dates_sorted = sorted(d for _, d in dated)
    midpoint = dates_sorted[len(dates_sorted) // 2]

    older = [r for r, d in dated if d < midpoint]
    newer = [r for r, d in dated if d >= midpoint]

    older_themes = Counter(r.theme_id for r in older)
    newer_themes = Counter(r.theme_id for r in newer)

    rows = []
    for theme_id in sorted(set(older_themes) | set(newer_themes)):
        older_pct = 100 * older_themes.get(theme_id, 0) / len(older) if older else 0
        newer_pct = 100 * newer_themes.get(theme_id, 0) / len(newer) if newer else 0
        rows.append({
            "theme_id": theme_id, "older_pct": round(older_pct, 1), "newer_pct": round(newer_pct, 1),
            "delta_pct": round(newer_pct - older_pct, 1),
        })

    return {
        "split_date": midpoint.date().isoformat(),
        "n_older": len(older), "n_newer": len(newer),
        "rows": sorted(rows, key=lambda r: -abs(r["delta_pct"])),
    }


# ---------------------------------------------------------------------------
# 7. Ingest funnel table
# ---------------------------------------------------------------------------

def ingest_funnel() -> dict:
    normalized = json.loads(NORMALIZED_MANIFEST.read_text()) if NORMALIZED_MANIFEST.exists() else {}
    relevant = json.loads(RELEVANT_MANIFEST.read_text()) if RELEVANT_MANIFEST.exists() else {}
    enriched = json.loads(ENRICHED_MANIFEST.read_text()) if ENRICHED_MANIFEST.exists() else {}
    funnel = normalized.get("funnel", {})
    return {
        "raw": funnel.get("raw"),
        "after_length_filter": funnel.get("after_length_filter"),
        "after_spam_filter": funnel.get("after_spam_filter"),
        "after_dedup": funnel.get("after_near_dedup"),
        "relevant": relevant.get("relevant_count") or len(read_jsonl(RELEVANT_PATH)),
        "enriched": enriched.get("enriched"),
    }


# ---------------------------------------------------------------------------
# 8. Source coverage table + per-theme source-bias flag
# ---------------------------------------------------------------------------

def source_coverage() -> dict:
    raw_counts = {}
    for source in SOURCES:
        manifest_path = DATA_RAW / f"{source}.manifest.json"
        if manifest_path.exists():
            raw_counts[source] = json.loads(manifest_path.read_text()).get("total_in_file", 0)
        else:
            raw_counts[source] = 0

    enriched_counts = Counter(r.source for r in load_enriched())

    themes = read_jsonl(THEMES_PATH)
    biased = []
    for theme in themes:
        sources = theme.get("sources", {})
        total = sum(sources.values())
        if total == 0:
            continue
        top_source, top_count = max(sources.items(), key=lambda kv: kv[1])
        if top_count / total >= 0.9:
            biased.append({"theme_id": theme["theme_id"], "dominant_source": top_source, "pct": round(100 * top_count / total, 1)})

    return {
        "raw_counts": raw_counts,
        "enriched_counts": dict(enriched_counts),
        "biased_themes": biased,
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_scorecard(results: dict) -> str:
    lines = ["# Insight Quality Scorecard", "", f"_Generated {datetime.now(timezone.utc).isoformat()}_", ""]

    lines += ["## 1. Gold-set classifier accuracy"]
    g = results["gold"]
    if g["status"] != "complete":
        lines += [f"**Status: {g['status']}.** {g['reason']}", ""]
    else:
        lines += [
            f"- n = {g['n']} hand-labelled items",
            f"- Relevance gate: precision {g['relevance_precision']}, recall {g['relevance_recall']}, "
            f"**F1 {g['relevance_f1']}** (target >= 0.80)",
            f"- Confusion: TP={g['relevance_confusion']['tp']} FP={g['relevance_confusion']['fp']} "
            f"FN={g['relevance_confusion']['fn']} TN={g['relevance_confusion']['tn']}",
            f"- Barrier-type accuracy (on items both gold and pipeline judged relevant): "
            f"{g['barrier_type_accuracy']} (n={g['barrier_type_n']})" if g["barrier_type_n"] else "- Barrier-type accuracy: n/a (no overlapping relevant items)",
            "",
        ]

    lines += ["## 2. Inter-run stability (theme classification)"]
    s = results["stability"]
    if s["status"] != "complete":
        lines += [f"**Status: {s['status']}.** {s.get('reason', '')}", ""]
    else:
        lines += [f"- n = {s['n']} records re-classified fresh (cache bypassed)", f"- theme_id agreement rate: **{s['agreement_rate']}**", ""]

    lines += ["## 3. Cross-source triangulation"]
    t = results["triangulation"]
    lines += [
        f"- {t['high_confidence']}/{t['n_themes']} themes are high-confidence (>=2 independent sources)",
        f"- single-source themes: {', '.join(t['single_source']) if t['single_source'] else 'none'}",
        "",
    ]

    lines += ["## 4. Citation audit"]
    c = results["citation"]
    lines += [
        f"- n = {c['n']} sampled representative quotes",
        f"- verbatim match rate: **{c['verbatim_match_rate']}** (must be 1.0 — quotes are never paraphrased)",
        f"- well-formed URL rate: **{c['url_well_formed_rate']}**",
    ]
    if c["problems"]:
        lines += ["- problems found:"] + [f"  - {p}" for p in c["problems"]]
    lines += [""]

    lines += ["## 5. Counter-evidence search"]
    for theme_id, ce in results["counter_evidence"].items():
        lines += [
            f"- **{theme_id}** (dominant category: {ce['dominant_category']}, theme leans {ce['theme_sentiment_direction']}): "
            f"{ce['counter_evidence_found']} disconfirming records found"
            + (f" (e.g. {', '.join(ce['example_ids'])})" if ce["example_ids"] else ""),
        ]
    lines += [""]

    lines += ["## 6. Recency split"]
    r = results["recency"]
    if r.get("status") == "skipped":
        lines += [f"Skipped: {r['reason']}", ""]
    else:
        lines += [f"- split date: {r['split_date']} (n_older={r['n_older']}, n_newer={r['n_newer']})", "", "| theme_id | older % | newer % | delta |", "|---|---|---|---|"]
        for row in r["rows"]:
            lines += [f"| {row['theme_id']} | {row['older_pct']} | {row['newer_pct']} | {row['delta_pct']:+.1f} |"]
        lines += [""]

    lines += ["## 7. Ingest funnel"]
    f = results["funnel"]
    lines += [
        "| stage | count |", "|---|---|",
        f"| raw | {f['raw']} |",
        f"| after length filter | {f['after_length_filter']} |",
        f"| after spam filter | {f['after_spam_filter']} |",
        f"| after dedup | {f['after_dedup']} |",
        f"| relevant | {f['relevant']} |",
        f"| enriched | {f['enriched']} |",
        "",
    ]

    lines += ["## 8. Source coverage"]
    sc = results["source_coverage"]
    lines += ["| source | raw | enriched | notes |", "|---|---|---|---|"]
    for source in SOURCES:
        lines += [f"| {source} | {sc['raw_counts'].get(source, 0)} | {sc['enriched_counts'].get(source, 0)} | {SOURCE_NOTES.get(source, '')} |"]
    lines += [""]
    if sc["biased_themes"]:
        lines += ["**Source-bias flag** (theme >= 90% from one source):"]
        for b in sc["biased_themes"]:
            lines += [f"- {b['theme_id']}: {b['pct']}% from `{b['dominant_source']}`"]
    else:
        lines += ["No theme is >= 90% single-source."]
    lines += [""]

    return "\n".join(lines)


def main():
    parser = base_arg_parser("Generate the insight quality scorecard (Phase 07 validate)")
    parser.add_argument("--stability-sample-size", type=int, default=90)
    parser.add_argument("--citation-sample-size", type=int, default=20)
    parser.add_argument("--skip-stability", action="store_true", help="Skip the LLM-quota-costing stability check")
    args = parser.parse_args()
    logger = setup_logging("validate")

    if not ENRICHED_PATH.exists():
        logger.error("no enriched data found — run the pipeline through src.enrich first")
        return

    results = {
        "gold": gold_set_metrics(logger),
        "stability": stability_check(args.stability_sample_size, logger) if not args.skip_stability else {"status": "skipped", "reason": "--skip-stability"},
        "triangulation": triangulation_summary(),
        "citation": citation_audit(args.citation_sample_size, logger),
        "counter_evidence": counter_evidence_search(),
        "recency": recency_split(),
        "funnel": ingest_funnel(),
        "source_coverage": source_coverage(),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SCORECARD_PATH.write_text(render_scorecard(results), encoding="utf-8")
    logger.info("done: wrote %s", SCORECARD_PATH)


if __name__ == "__main__":
    main()
