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
                "family_stage": seg.get("family_stage", "unknown"),
                "city_tier": seg.get("city_tier", "unknown"),
                "price_sensitivity": seg.get("price_sensitivity", "unknown"),
                "has_pet": seg.get("has_pet", "unknown"),
                "sentiment": r["sentiment"], "quote_worthy": r["quote_worthy"],
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    return df


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
