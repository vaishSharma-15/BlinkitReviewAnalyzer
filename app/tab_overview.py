"""Overview tab: corpus health at a glance, mirroring the Stitch "Corpus Overview"
design — KPI tiles, top barriers, sentiment mix, coverage over time, recent items."""
import pandas as pd
import streamlit as st

from app.data import load_enriched_df, load_themes_df
from app.theme import card_end, card_start, quote_block


def render():
    df = load_enriched_df()
    themes_df = load_themes_df()

    if df.empty:
        st.warning("No enriched data yet — run `python -m src.enrich` first.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total items (enriched)", f"{len(df):,}")
    with col2:
        relevant_pct = 100.0  # every row in enriched.jsonl is, by definition, relevant
        st.metric("Relevant items", f"{len(df):,}", f"{relevant_pct:.0f}% of enriched")
    with col3:
        pos = (df["sentiment"] > 0.2).mean()
        neu = df["sentiment"].between(-0.2, 0.2).mean()
        neg = (df["sentiment"] < -0.2).mean()
        st.metric("Sentiment mix", f"{pos:.0%} pos", f"{neg:.0%} neg")

    col1, col2 = st.columns(2)
    with col1:
        card_start("WHAT USERS STRUGGLE WITH")
        barrier_counts = df[df["barrier_type"] != "none"]["barrier_type"].value_counts()
        if barrier_counts.empty:
            st.caption("No barrier-labeled items yet.")
        else:
            st.bar_chart(barrier_counts, color="#F9D507")
        card_end()

    with col2:
        card_start("SENTIMENT DISTRIBUTION")
        bins = [-1.01, -0.5, -0.1, 0.1, 0.5, 1.01]
        labels = ["Very negative", "Negative", "Neutral", "Positive", "Very positive"]
        sentiment_bucket = pd.cut(df["sentiment"], bins=bins, labels=labels)
        st.bar_chart(sentiment_bucket.value_counts().reindex(labels), color="#6e5d00")
        card_end()

    card_start("THE REPETITION PROBLEM")
    if not themes_df.empty:
        top_theme = themes_df.sort_values("rank_score", ascending=False).iloc[0]
        st.markdown(
            quote_block(
                f"The single largest concentrated pain point so far is **{top_theme['name']}** — "
                f"{top_theme['size']} items ({top_theme['prevalence']:.1%} of the enriched corpus), "
                f"average sentiment {top_theme['avg_sentiment']:.2f}, confidence `{top_theme['confidence']}`."
            ),
            unsafe_allow_html=True,
        )
    else:
        st.caption("No themes yet — run `python -m src.cluster` and `python -m src.synthesize`.")
    card_end()

    card_start("WHO'S MOST AFFECTED")
    seg_cols = ["family_stage", "city_tier", "price_sensitivity", "has_pet"]
    seg_rows = []
    for col in seg_cols:
        known = df[df[col] != "unknown"]
        if known.empty:
            continue
        grp = known.groupby(col)["sentiment"].agg(["mean", "count"]).sort_values("count", ascending=False)
        for value, row in grp.iterrows():
            seg_rows.append({"segment": f"{col}={value}", "n_items": int(row["count"]), "avg_sentiment": round(row["mean"], 2)})
    if seg_rows:
        st.dataframe(seg_rows, use_container_width=True, hide_index=True)
    else:
        st.caption(
            "No segment signals detected yet in this partial run (family_stage/city_tier/"
            "price_sensitivity/has_pet all unknown) — expected on a small/early sample."
        )
    card_end()

    card_start("COVERAGE OVER TIME")
    dated = df.dropna(subset=["date_parsed"])
    if not dated.empty:
        by_month = dated.set_index("date_parsed").resample("MS").size()
        st.line_chart(by_month, color="#6e5d00")
    else:
        st.caption("No parseable dates in this sample.")
    card_end()

    card_start("RECENT REVIEWS")
    recent = df.dropna(subset=["date_parsed"]).sort_values("date_parsed", ascending=False).head(6)
    for _, row in recent.iterrows():
        sentiment_label = "Positive" if row["sentiment"] > 0.2 else ("Negative" if row["sentiment"] < -0.2 else "Neutral")
        st.markdown(f"**{row['source']}** · {sentiment_label} · {row['date'][:10]}")
        st.caption(row["text"][:220])
    card_end()
