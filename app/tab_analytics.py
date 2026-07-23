"""Analytics tab: the ingest funnel, source coverage (all 7 required source types,
per docs/ProblemStatement.md §8), and category/behaviour-signal distributions —
mirrors the Stitch "Analytics Terminal" layout."""
from collections import Counter

import streamlit as st

from app.data import load_enriched_df, load_funnel, load_raw_source_counts, load_source_blocked_reasons
from app.theme import badge, card_end, card_start


def render():
    card_start("INGEST FUNNEL")
    funnel = load_funnel()
    normalized = funnel.get("normalized", {}).get("funnel", {})
    relevant = funnel.get("relevant", {})
    enriched = funnel.get("enriched", {})

    if normalized:
        stages = [
            ("Raw", normalized.get("raw")),
            ("After length filter", normalized.get("after_length_filter")),
            ("After spam filter", normalized.get("after_spam_filter")),
            ("After exact dedup", normalized.get("after_exact_dedup")),
            ("Normalized (near-dup deduped)", normalized.get("after_near_dedup")),
            ("Relevant", relevant.get("relevant")),
            ("Enriched so far", enriched.get("enriched")),
        ]
        cols = st.columns(len(stages))
        top = stages[0][1] or 1
        for col, (label, count) in zip(cols, stages):
            with col:
                st.metric(label, f"{count:,}" if count is not None else "—")
                if count is not None:
                    st.progress(min(count / top, 1.0))
        if enriched.get("not_yet_attempted"):
            st.caption(
                f"⚠️ {enriched['not_yet_attempted']} relevant items are not yet enriched "
                "(shared LLM daily quota) — this dashboard reflects the partial corpus."
            )
    else:
        st.caption("No funnel manifest found yet — run the pipeline stages first.")
    card_end()

    col1, col2 = st.columns([2, 1])
    with col1:
        card_start("SOURCE COVERAGE")
        st.caption("All seven source types are graded requirements — a genuine zero must be documented, not hidden.")
        raw_counts = load_raw_source_counts()
        blocked_reasons = load_source_blocked_reasons()
        for source, count in raw_counts.items():
            c1, c2, c3 = st.columns([2, 1, 3])
            c1.markdown(f"**{source}**")
            if count > 0:
                c2.markdown(badge("Success", "success"), unsafe_allow_html=True)
            elif source in blocked_reasons:
                c2.markdown(badge("Blocked", "blocked"), unsafe_allow_html=True)
            else:
                c2.markdown(badge("Zero", "warning"), unsafe_allow_html=True)
            c3.write(f"{count:,} items" + (f" — {blocked_reasons[source][:80]}" if source in blocked_reasons else ""))
        card_end()

    with col2:
        card_start("CATEGORY DISTRIBUTION")
        df = load_enriched_df()
        if not df.empty:
            cat_counts = Counter(c for cats in df["categories_mentioned"] for c in cats)
            if cat_counts:
                st.bar_chart(dict(cat_counts.most_common(8)), color="#F9D507")
            else:
                st.caption("No category labels yet.")
        card_end()

    df = load_enriched_df()
    if df.empty:
        return

    col1, col2 = st.columns(2)
    with col1:
        card_start("BEHAVIOUR SIGNAL DISTRIBUTION")
        behaviour_counts = df[df["behaviour_signal"] != "none"]["behaviour_signal"].value_counts()
        if not behaviour_counts.empty:
            st.bar_chart(behaviour_counts, color="#6e5d00")
        else:
            st.caption("No behaviour-signal labels yet.")
        card_end()

    with col2:
        card_start("EVIDENCE BY SOURCE")
        st.dataframe(
            df.groupby("source").agg(items=("id", "count"), avg_sentiment=("sentiment", "mean")).round(2),
            use_container_width=True,
        )
        card_end()
