"""Phase 06 — Synthesize: aggregate enriched records by theme_id, map to the eight
research questions, and rank themes.

Reads data/enriched/enriched.jsonl, writes:
  - data/themes/themes.jsonl              (one ranked row per theme_id, incl. unclassified)
  - data/themes/research_questions.json   (Q1-Q8 -> supporting theme ids, or "unanswerable")
  - data/themes/manifest.json

Theming is now supervised, not unsupervised: Phase 04 (src/enrich.py) assigns each
record exactly one theme_id from the fixed 9-theme taxonomy (or "unclassified") as part
of the same LLM call that produces the other closed-vocabulary labels. This stage just
groups by that label — it does no clustering and spends no LLM quota itself. The
unsupervised HDBSCAN path in src/cluster.py still exists, but only as a secondary check
run on the "unclassified" subset (see src/cluster.py's module docstring) to catch a
theme that should have been in the fixed taxonomy but wasn't.

Deliberately local/rule-based for the research-question mapping, same rationale as
before: driven entirely by the closed-vocabulary labels Phase 04 already assigned
(behaviour_signal, barrier_type, segment_signals, theme_id), so it's auditable and free.

Ranking is prevalence x severity x strategic_relevance, each in [0, 1]:
  - prevalence: theme size / total enriched corpus size.
  - severity: abs(avg_sentiment) — how strongly the theme skews away from neutral, in
    either direction. A strongly positive habit-reorder theme is as noteworthy as a
    strongly negative trust-barrier theme, just for a different research question.
  - strategic_relevance: 0.5 base, +0.25 if the theme includes any qcomm_comparison
    source item (the problem statement calls category-to-platform mental models "the
    single most important signal for this project"), +0.25 if the theme maps to >= 3
    distinct research questions (broad explanatory power). Capped at 1.0.

Confidence is a provisional cross-source check (a real, more rigorous version of this
same rule reappears in Phase 07 validate): "high" if the theme's evidence spans >= 2
distinct sources, "single_source" otherwise, per the triangulation rule in
docs/ProblemStatement.md §8 item 3.

"unclassified" is reported as its own row (like the old noise bucket) — not merged into
any theme, not silently dropped.

Usage:
    python -m src.synthesize --config config.yaml [--enriched PATH]
"""
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

from src.ingest.common import base_arg_parser, setup_logging
from src.schemas import EnrichedRecord, RESEARCH_QUESTIONS, THEMES

REPO_ROOT = Path(__file__).resolve().parent.parent
ENRICHED_PATH = REPO_ROOT / "data" / "enriched" / "enriched.jsonl"
DATA_THEMES = REPO_ROOT / "data" / "themes"
THEMES_PATH = DATA_THEMES / "themes.jsonl"
RQ_PATH = DATA_THEMES / "research_questions.json"
MANIFEST_PATH = DATA_THEMES / "manifest.json"

TOP_TERMS_PER_THEME = 6
REPRESENTATIVE_QUOTES_PER_THEME = 5

# Human-readable names for the fixed taxonomy (src/schemas.py THEMES).
THEME_NAMES = {
    "platform_mental_model": "Platform Mental Model",
    "category_specific_distrust": "Category-Specific Distrust",
    "first_trial_story": "First-Trial Stories",
    "habit_and_reorder": "Habit & Reorder",
    "discovery_mechanics": "Discovery Mechanics",
    "assortment_gaps": "Assortment Gaps",
    "price_and_value": "Price & Value",
    "life_event_trigger": "Life-Event Triggers",
    "cross_platform_comparison": "Cross-Platform Comparison",
}

# theme_id -> research questions it speaks to directly, per the mapping agreed against
# docs/ProblemStatement.md §4 (all 8 questions get real coverage, nothing forced).
THEME_TO_RQ = {
    "platform_mental_model": {"Q1", "Q3", "Q8"},
    "category_specific_distrust": {"Q2", "Q5", "Q6"},
    "first_trial_story": {"Q3", "Q5", "Q7"},
    "habit_and_reorder": {"Q1", "Q4"},
    "discovery_mechanics": {"Q3"},
    "assortment_gaps": {"Q2", "Q6", "Q8"},
    "price_and_value": {"Q2", "Q5", "Q6"},
    "life_event_trigger": {"Q7", "Q8"},
    "cross_platform_comparison": {"Q1", "Q3", "Q8"},
}


def load_enriched(path: Path) -> List[EnrichedRecord]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(EnrichedRecord.model_validate_json(line))
    return records


def dominant_value(values: List[str]) -> str:
    counts = Counter(v for v in values if v and v != "none")
    if not counts:
        return "none"
    return counts.most_common(1)[0][0]


def research_questions_for_theme(theme_id: str, theme_records: List[EnrichedRecord]) -> Set[str]:
    rqs: Set[str] = set(THEME_TO_RQ.get(theme_id, set()))
    if any(
        any(v != "unknown" for v in (
            r.segment_signals.family_stage, r.segment_signals.city_tier,
            r.segment_signals.price_sensitivity, r.segment_signals.has_pet,
        ))
        for r in theme_records
    ):
        rqs.add("Q7")
    return rqs


def representative_quotes(theme_records: List[EnrichedRecord]) -> List[dict]:
    ranked = sorted(theme_records, key=lambda r: not r.quote_worthy)
    picks = ranked[:REPRESENTATIVE_QUOTES_PER_THEME]
    return [{"id": r.id, "text": r.text, "source": r.source} for r in picks]


def main():
    parser = base_arg_parser("Synthesize enriched records into ranked, research-question-mapped themes")
    parser.add_argument("--enriched", default=None, help="Override enriched records path")
    args = parser.parse_args()
    logger = setup_logging("synthesize")

    enriched_path = Path(args.enriched) if args.enriched else ENRICHED_PATH
    if not enriched_path.exists():
        logger.error("no enriched data found at %s — run src.enrich first", enriched_path)
        return

    records = load_enriched(enriched_path)
    total_corpus = len(records)
    logger.info("loaded %d enriched records", total_corpus)

    theme_to_records: Dict[str, List[EnrichedRecord]] = {t: [] for t in THEMES}
    for r in records:
        theme_to_records.setdefault(r.theme_id, []).append(r)

    themes = []
    rq_support: Dict[str, List[str]] = {q: [] for q in RESEARCH_QUESTIONS}

    for theme_id in THEMES:
        if theme_id == "unclassified":
            continue  # reported separately below, not turned into a ranked theme
        theme_records = theme_to_records.get(theme_id, [])
        if not theme_records:
            continue

        rqs = research_questions_for_theme(theme_id, theme_records)
        sources = Counter(r.source for r in theme_records)
        n_sources = len(sources)
        has_qcomm = "qcomm_comparison" in sources

        all_categories = [c for r in theme_records for c in r.categories_mentioned]
        behaviours = [r.behaviour_signal for r in theme_records]
        barriers = [r.barrier_type for r in theme_records]

        prevalence = len(theme_records) / total_corpus if total_corpus else 0.0
        avg_sentiment = round(sum(r.sentiment for r in theme_records) / len(theme_records), 3)
        severity = min(abs(avg_sentiment), 1.0)
        strategic_relevance = 0.5
        if has_qcomm:
            strategic_relevance += 0.25
        if len(rqs) >= 3:
            strategic_relevance += 0.25
        strategic_relevance = min(strategic_relevance, 1.0)

        rank_score = prevalence * severity * strategic_relevance
        confidence = "high" if n_sources >= 2 else "single_source"

        theme = {
            "theme_id": theme_id,
            "name": THEME_NAMES.get(theme_id, theme_id),
            "research_questions": sorted(rqs) if rqs else [],
            "size": len(theme_records),
            "prevalence": round(prevalence, 4),
            "severity": round(severity, 4),
            "strategic_relevance": round(strategic_relevance, 4),
            "rank_score": round(rank_score, 6),
            "confidence": confidence,
            "sources": dict(sources),
            "n_sources": n_sources,
            "dominant_category": dominant_value(all_categories),
            "dominant_behaviour_signal": dominant_value(behaviours),
            "dominant_barrier_type": dominant_value(barriers),
            "avg_sentiment": avg_sentiment,
            "representative_quotes": representative_quotes(theme_records),
            "evidence_ids": [r.id for r in theme_records],
        }
        themes.append(theme)

        for q in rqs:
            rq_support[q].append(theme_id)

    themes.sort(key=lambda t: -t["rank_score"])

    unclassified_records = theme_to_records.get("unclassified", [])

    DATA_THEMES.mkdir(parents=True, exist_ok=True)
    with open(THEMES_PATH, "w", encoding="utf-8") as f:
        for theme in themes:
            f.write(json.dumps(theme) + "\n")

    rq_output = {}
    unanswered = []
    for q, question_text in RESEARCH_QUESTIONS.items():
        supporting = rq_support[q]
        if supporting:
            rq_output[q] = {"question": question_text, "status": "answered", "theme_ids": supporting}
        else:
            rq_output[q] = {"question": question_text, "status": "unanswerable_so_far", "theme_ids": []}
            unanswered.append(q)

    with open(RQ_PATH, "w", encoding="utf-8") as f:
        json.dump(rq_output, f, indent=2)

    logger.info(
        "done: %d themes from %d records; %d/%d research questions answered so far%s",
        len(themes), total_corpus, len(RESEARCH_QUESTIONS) - len(unanswered), len(RESEARCH_QUESTIONS),
        f" (unanswered: {', '.join(unanswered)})" if unanswered else "",
    )
    logger.info(
        "unclassified bucket: %d records (%.1f%% of corpus) — reported, not themed; "
        "run src.cluster on this subset as a check for a missed theme",
        len(unclassified_records), 100 * len(unclassified_records) / total_corpus if total_corpus else 0,
    )

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "total_corpus": total_corpus,
            "n_themes": len(themes),
            "n_research_questions_answered": len(RESEARCH_QUESTIONS) - len(unanswered),
            "unanswered_research_questions": unanswered,
            "unclassified_bucket_size": len(unclassified_records),
        }, f, indent=2)


if __name__ == "__main__":
    main()
