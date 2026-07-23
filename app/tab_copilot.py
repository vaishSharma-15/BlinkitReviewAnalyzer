"""Discovery Copilot tab: chat interface with structured answer cards (Executive
Summary / Theme Breakdown / Affected User Segments / Product Recommendations /
Supporting Evidence), styled after the Stitch "Chat Terminal" screen.

Product Recommendations is included at the user's explicit request, overriding the
project spec's default insight-only constraint (docs/ProblemStatement.md) — see
app/rag_engine.py's generate_structured_answer for how that field is generated and why
it's the one field allowed to be judgment rather than pure evidence extraction.
"""
import streamlit as st

from app.rag_engine import generate_structured_answer, get_db, retrieve_evidence, retrieve_themes
from app.theme import card_end, card_start, quote_block, source_badge

SUGGESTED_QUESTIONS = [
    "Why do users repeatedly buy from the same categories?",
    "What prevents users from exploring new categories?",
    "How do users discover products on the platform today?",
    "What role do habits and reorder behaviour play?",
    "What frustrations emerge repeatedly?",
    "What unmet needs emerge consistently across sources?",
]


def _sentiment_label(score: float) -> str:
    return "Positive" if score > 0.2 else ("Negative" if score < -0.2 else "Neutral")


def _theme_tag(e: dict) -> str:
    return e["barrier_type"] if e.get("barrier_type", "none") != "none" else e.get("behaviour_signal", "")


def _render_answer_card(query: str, structured: dict, evidence: list, matched_themes: list):
    card_start()
    st.markdown(f"### ✨ {query}")

    st.markdown("**📄 EXECUTIVE SUMMARY**")
    st.write(structured["executive_summary"])

    if structured["theme_breakdown"] or structured["affected_segments"]:
        c1, c2 = st.columns(2)
        if structured["theme_breakdown"]:
            with c1:
                st.markdown("**THEME BREAKDOWN**")
                for theme in structured["theme_breakdown"]:
                    st.markdown(f"- {theme}")
        if structured["affected_segments"]:
            with c2:
                st.markdown("**AFFECTED USER SEGMENTS**")
                for seg in structured["affected_segments"]:
                    st.markdown(f"- {seg}")

    if structured.get("product_recommendations"):
        st.markdown("**PRODUCT RECOMMENDATIONS**")
        for i, rec in enumerate(structured["product_recommendations"], start=1):
            c1, c2 = st.columns([1, 20])
            c1.markdown(
                f"<div style='width:24px;height:24px;border-radius:50%;background:#F9D507;"
                f"color:#191c1e;font-weight:700;font-size:12px;display:flex;align-items:center;"
                f"justify-content:center;'>{i}</div>",
                unsafe_allow_html=True,
            )
            c2.write(rec)

    if evidence:
        st.markdown("**SUPPORTING EVIDENCE**")
        for e in evidence[:5]:
            c1, c2, c3 = st.columns([1.2, 1, 2])
            c1.markdown(source_badge(e["source"]), unsafe_allow_html=True)
            c2.markdown(f"_{_sentiment_label(e['sentiment'])}_")
            tag = _theme_tag(e)
            c3.markdown(f"`{tag}`" if tag else "")
            st.markdown(quote_block(e["text"][:280]), unsafe_allow_html=True)
            date_str = e["date"][:10] if e.get("date") else ""
            st.caption(f"{date_str} · {e['url']}")

    method_label = {
        "gemini": "Vector similarity (RAG) · Gemini-generated",
        "extractive": "Vector similarity (RAG) · Extractive fallback (daily LLM quota exhausted)",
        "none": "No evidence retrieved",
    }[structured["method"]]
    st.caption(method_label)
    card_end()


def render():
    db = get_db()
    if db is None:
        st.error("No index found at data/index/lancedb. Run `python -m src.index` first.")
        return

    if "copilot_messages" not in st.session_state:
        st.session_state.copilot_messages = []

    def ask(query: str):
        matched_themes = retrieve_themes(query)
        evidence = retrieve_evidence(query, top_k=8)
        structured = generate_structured_answer(query, evidence, matched_themes)
        st.session_state.copilot_messages.append({
            "query": query, "structured": structured, "evidence": evidence, "themes": matched_themes,
        })

    if not st.session_state.copilot_messages:
        st.markdown(
            "<div style='text-align:center;padding:32px 0;'>"
            "<div style='width:56px;height:56px;background:#F9D507;border-radius:10px;"
            "display:inline-flex;align-items:center;justify-content:center;font-size:28px;'>🔎</div>"
            "<h2 style='margin-top:12px;'>Insight Engine</h2>"
            "<p style='color:#5f5e5e;'>Query the enriched Blinkit review corpus using natural language "
            "for evidence-backed insight.</p></div>",
            unsafe_allow_html=True,
        )
        st.markdown("**Suggested questions**")
        cols = st.columns(2)
        for i, question in enumerate(SUGGESTED_QUESTIONS):
            if cols[i % 2].button(question, use_container_width=True, key=f"suggested_{i}"):
                ask(question)
                st.rerun()

    for message in st.session_state.copilot_messages:
        _render_answer_card(message["query"], message["structured"], message["evidence"], message["themes"])

    if query := st.chat_input("Ask a follow-up question or start a new analysis..."):
        ask(query)
        st.rerun()
