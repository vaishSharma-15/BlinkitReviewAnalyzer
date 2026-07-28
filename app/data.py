"""Shared data-loading helpers for the Streamlit app, used by every tab.

Reads directly from the pipeline's own output files (data/enriched, data/themes,
data/raw manifests) — the app never re-derives numbers, it displays what the pipeline
already computed, so the dashboard and the CLI logs can never silently disagree.
"""
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
ENRICHED_PATH = ROOT / "data" / "enriched" / "enriched.jsonl"
THEMES_PATH = ROOT / "data" / "themes" / "themes.jsonl"
RAW_DIR = ROOT / "data" / "raw"
SEG_TAXONOMY_PATH = ROOT / "data" / "segments" / "taxonomy.json"
SEG_ASSIGNMENTS_PATH = ROOT / "data" / "segments" / "assignments.jsonl"
SEG_MANIFEST_PATH = ROOT / "data" / "segments" / "manifest.json"

# Kept in sync with src/schemas.py SOURCES — all seven must be checked, not just the
# ones with data, so a genuinely-zero source (e.g. forum) still shows up as a row.
SOURCES = ["play", "appstore", "reddit", "youtube", "forum", "product_review", "qcomm_comparison"]


@st.cache_data(show_spinner=False)
def load_enriched_df() -> pd.DataFrame:
    if not ENRICHED_PATH.exists():
        return pd.DataFrame()
    rows = []
    with open(ENRICHED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            seg = r.get("segment_signals", {})
            rows.append({
                "id": r["id"], "source": r["source"], "url": r["url"], "date": r["date"],
                "text": r["text"], "lang": r["lang"], "rating": r.get("rating"),
                "categories_mentioned": r.get("categories_mentioned", []),
                "behaviour_signal": r["behaviour_signal"], "barrier_type": r["barrier_type"],
                "theme_id": r.get("theme_id", "unclassified"),
                "family_stage": seg.get("family_stage", "unknown"),
                "city_tier": seg.get("city_tier", "unknown"),
                "price_sensitivity": seg.get("price_sensitivity", "unknown"),
                "has_pet": seg.get("has_pet", "unknown"),
                "sentiment": r["sentiment"], "quote_worthy": r["quote_worthy"],
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        # format="ISO8601" so dates both with and without fractional seconds parse — the
        # scrapers emit both (Play/App Store without microseconds, YouTube/Q-Comm with),
        # and the default inferrer silently coerced the microsecond ones to NaT, which
        # dropped every YouTube/Q-Comm review out of the date-based coverage chart.
        df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce", utc=True, format="ISO8601")
    return df


@st.cache_data(show_spinner=False)
def load_segment_taxonomy() -> List[dict]:
    """The behaviour-defined segments derived from the reviews themselves (src/segment.py).

    Distinct from the four segment_signals columns above, which are demographic slots a
    public review almost never fills. Empty until `python -m src.segment discover` runs.
    """
    if not SEG_TAXONOMY_PATH.exists():
        return []
    return json.loads(SEG_TAXONOMY_PATH.read_text(encoding="utf-8")).get("segments", [])


@st.cache_data(show_spinner=False)
def load_segment_assignments() -> pd.DataFrame:
    """One row per labelled review: id, segment_id, and the verbatim quote that earned
    the label. Every quote here has already been checked against the review text by
    src.segment — an assignment without one was recorded as unassigned, not shown."""
    if not SEG_ASSIGNMENTS_PATH.exists():
        return pd.DataFrame(columns=["id", "segment_id", "evidence_quote"])
    rows = []
    with open(SEG_ASSIGNMENTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def segment_lookup() -> Dict[str, str]:
    """{record id: segment display name} for every assigned review.

    The vector index predates this phase and its evidence rows carry the old demographic
    columns, but they do carry `id` — so the chat joins segments here rather than forcing
    a re-embed of the whole corpus to add one field.
    """
    taxonomy = {s["segment_id"]: s["name"] for s in load_segment_taxonomy()}
    assignments = load_segment_assignments()
    if assignments.empty:
        return {}
    return {row.id: taxonomy.get(row.segment_id, "")
            for row in assignments.itertuples()
            if row.segment_id != "unassigned" and taxonomy.get(row.segment_id)}


@st.cache_data(show_spinner=False)
def load_segment_manifest() -> dict:
    if not SEG_MANIFEST_PATH.exists():
        return {}
    return json.loads(SEG_MANIFEST_PATH.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_themes_df() -> pd.DataFrame:
    if not THEMES_PATH.exists():
        return pd.DataFrame()
    rows = []
    with open(THEMES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def load_raw_source_counts() -> Dict[str, int]:
    counts = {}
    for source in SOURCES:
        path = RAW_DIR / f"{source}.jsonl"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                counts[source] = sum(1 for line in f if line.strip())
        else:
            counts[source] = 0
    return counts


@st.cache_data(show_spinner=False)
def load_funnel() -> Dict[str, dict]:
    funnel = {}
    normalized_manifest = ROOT / "data" / "normalized" / "manifest.json"
    relevant_manifest = ROOT / "data" / "relevant" / "manifest.json"
    enriched_manifest = ROOT / "data" / "enriched" / "manifest.json"
    if normalized_manifest.exists():
        funnel["normalized"] = json.loads(normalized_manifest.read_text())
    if relevant_manifest.exists():
        funnel["relevant"] = json.loads(relevant_manifest.read_text())
    if enriched_manifest.exists():
        funnel["enriched"] = json.loads(enriched_manifest.read_text())
    return funnel


def scraped_count(fallback: int = 0) -> int:
    """Everything pulled from the sources before the dedup/relevance gates. Every tab
    reports this alongside its own working count, so the headline scrape figure is not
    only visible on Overview."""
    return load_funnel().get("normalized", {}).get("funnel", {}).get("raw") or fallback


@st.cache_data(show_spinner=False)
def load_source_blocked_reasons() -> Dict[str, str]:
    """Surfaces the honest 'genuinely unscrapable' documentation from each raw
    manifest (see README §01-Ingest), rather than letting a zero-count source look
    like an unexplained gap on the dashboard."""
    reasons = {}
    for source in SOURCES:
        manifest_path = RAW_DIR / f"{source}.manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            reason = manifest.get("blocked_reason") or manifest.get("note")
            if reason:
                reasons[source] = reason
    return reasons
