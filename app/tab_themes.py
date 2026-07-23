"""Theme Intelligence tab: the ranked theme table from Phase 06 synthesize, filterable
by research question / source / confidence — mirrors the Stitch "Theme Intelligence"
card-list + drill-down layout."""
import json
from pathlib import Path

import streamlit as st

from app.data import load_themes_df
from app.theme import badge, card_end, card_start, confidence_badge_kind, quote_block
from src.schemas import RESEARCH_QUESTIONS

REPO_ROOT = Path(__file__).resolve().parents[1]


def render():
    themes_df = load_themes_df()
    if themes_df.empty:
        st.warning("No themes yet — run `python -m src.cluster` and `python -m src.synthesize` first.")
        return

    card_start("RESEARCH QUESTION COVERAGE")
    rq_file = REPO_ROOT / "data" / "themes" / "research_questions.json"
    if rq_file.exists():
        rq_data = json.loads(rq_file.read_text())
        rq_rows = [
            {"question_id": qid, "question": info["question"], "status": info["status"], "n_themes": len(info["theme_ids"])}
            for qid, info in rq_data.items()
        ]
        st.dataframe(rq_rows, use_container_width=True, hide_index=True)
    card_end()

    st.markdown("#### Ranked themes")
    col1, col2, col3 = st.columns(3)
    all_rqs = sorted(RESEARCH_QUESTIONS.keys())
    rq_filter = col1.multiselect("Filter by research question", all_rqs)
    all_sources = sorted({s for sources in themes_df["sources"] for s in sources.keys()})
    source_filter = col2.multiselect("Filter by source", all_sources)
    confidence_filter = col3.multiselect("Filter by confidence", sorted(themes_df["confidence"].unique()))

    filtered = themes_df.copy()
    if rq_filter:
        filtered = filtered[filtered["research_questions"].apply(lambda rqs: any(q in rqs for q in rq_filter))]
    if source_filter:
        filtered = filtered[filtered["sources"].apply(lambda s: any(src in s for src in source_filter))]
    if confidence_filter:
        filtered = filtered[filtered["confidence"].isin(confidence_filter)]

    filtered = filtered.sort_values("rank_score", ascending=False)

    for _, theme in filtered.iterrows():
        card_start()
        top_row = st.columns([3, 1])
        top_row[0].markdown(f"### {theme['name']}")
        top_row[1].markdown(
            f"<div style='text-align:right;font-size:24px;font-weight:800;'>{theme['prevalence']:.0%}"
            f"<div style='font-size:11px;font-weight:600;color:#5f5e5e;text-transform:uppercase;'>prevalence</div></div>",
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Size", f"{theme['size']} items")
        c2.metric("Severity", f"{theme['severity']:.2f}")
        c3.metric("Strategic relevance", f"{theme['strategic_relevance']:.2f}")
        c4.markdown(f"**Confidence**<br>{badge(theme['confidence'].upper(), confidence_badge_kind(theme['confidence']))}", unsafe_allow_html=True)

        st.markdown(f"**Research questions:** {', '.join(theme['research_questions']) or 'none mapped'}")
        st.markdown(
            f"**Dominant category:** {theme['dominant_category']} · "
            f"**behaviour:** {theme['dominant_behaviour_signal']} · "
            f"**barrier:** {theme['dominant_barrier_type']}"
        )
        st.markdown(f"**Sources:** {', '.join(f'{s}×{c}' for s, c in theme['sources'].items())}")
        if theme["confidence"] == "single_source":
            st.warning("Single-source theme — not yet cross-source triangulated.")

        with st.expander("Representative quotes"):
            for q in theme["representative_quotes"]:
                st.markdown(quote_block(q["text"][:200], q["source"]), unsafe_allow_html=True)
        card_end()
