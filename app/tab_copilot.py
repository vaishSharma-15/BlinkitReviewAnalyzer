"""Chat Terminal tab: a light Blinkit-palette RAG chat modelled on the
spotify-discovery-intel copilot screen — a centered 'How can I help…' hero with
suggested-question chips and a bottom input, then structured, evidence-cited answer cards.

Product Recommendations is included at the user's explicit request, overriding the
project spec's default insight-only constraint (docs/ProblemStatement.md) — see
app/rag_engine.py's generate_structured_answer for how that field is generated.
"""
import streamlit as st

from app import ui
from app.rag_engine import generate_structured_answer, get_db, retrieve_evidence, retrieve_themes

SUGGESTED_QUESTIONS = [
    "Why do users repeatedly buy from the same categories?",
    "What prevents users from exploring new categories?",
    "How do users discover products on the platform today?",
    "What role do habits and reorder behaviour play?",
    "Which user segments are most frustrated?",
    "What unmet needs emerge consistently across sources?",
]


def _render_answer_card(msg):
    query, structured, evidence = msg["query"], msg["structured"], msg["evidence"]
    parts = [f'<div class="ui-card ui-row"><div class="ui-card-title">✨ {ui.esc(query)}</div>',
             f'<div style="color:{ui.FAINT};font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;margin:14px 0 6px;">Executive Summary</div>',
             f'<div style="color:{ui.TXT};font-size:14px;line-height:1.6;">{ui.esc(structured["executive_summary"])}</div>']

    if structured.get("theme_breakdown") or structured.get("affected_segments"):
        parts.append('<div class="ui-g2" style="margin-top:16px;">')
        for title, items in [("Theme Breakdown", structured.get("theme_breakdown")),
                             ("Affected Segments", structured.get("affected_segments"))]:
            if items:
                li = "".join(f'<li style="margin-bottom:6px;">{ui.esc(x)}</li>' for x in items)
                parts.append(f'<div><div style="color:{ui.FAINT};font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:8px;">{title}</div>'
                             f'<ul style="margin:0;padding-left:18px;color:{ui.MUTED};font-size:13px;">{li}</ul></div>')
        parts.append("</div>")

    if structured.get("product_recommendations"):
        recs = "".join(
            f'<div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:8px;">'
            f'<div style="width:22px;height:22px;border-radius:50%;background:{ui.YELLOW};color:#191c1e;font-weight:700;font-size:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">{i}</div>'
            f'<div style="color:{ui.MUTED};font-size:13px;line-height:1.5;">{ui.esc(rec)}</div></div>'
            for i, rec in enumerate(structured["product_recommendations"], start=1)
        )
        parts.append(f'<div style="color:{ui.FAINT};font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;margin:16px 0 8px;">Product Recommendations</div>{recs}')

    if evidence:
        parts.append(f'<div style="color:{ui.FAINT};font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;margin:16px 0 8px;">Supporting Evidence</div>')
        for e in evidence[:5]:
            name, color = ui.SOURCE_META.get(e["source"], (e["source"].title(), ui.MUTED))
            scol = ui.sentiment_color(e["sentiment"])
            slabel = ui.sentiment_label(e["sentiment"])
            tag = e["barrier_type"] if e.get("barrier_type", "none") != "none" else e.get("behaviour_signal", "")
            date = e["date"][:10] if e.get("date") else ""
            parts.append(f'<div style="border-left:2px solid {color};padding:2px 0 2px 12px;margin:10px 0;">'
                         f'<div style="display:flex;gap:10px;align-items:center;margin-bottom:4px;">'
                         f'<span class="ui-badge" style="color:{color};border-color:{color}55;background:{color}12;">{name}</span>'
                         f'<span style="color:{scol};font-size:12px;font-style:italic;">{slabel}</span>'
                         f'<span style="color:{ui.FAINT};font-size:11px;font-family:monospace;">{ui.esc(tag)}</span></div>'
                         f'<div style="color:{ui.TXT};font-size:12px;font-style:italic;line-height:1.5;">"{ui.esc(e["text"][:260])}"</div>'
                         f'<div style="color:{ui.FAINT};font-size:11px;margin-top:3px;">{date} · {ui.esc(e["url"][:70])}</div></div>')

    method = {
        "gemini": "Vector similarity (RAG) · LLM-generated",
        "extractive": "Vector similarity (RAG) · Extractive fallback (daily LLM quota exhausted)",
        "none": "No evidence retrieved",
    }.get(structured.get("method"), "")
    parts.append(f'<div style="color:{ui.FAINT};font-size:11px;margin-top:14px;">{method}</div></div>')
    ui.flush(parts)


def render():
    db = get_db()
    if db is None:
        st.error("No index found at data/index/lancedb. Run `python -m src.index` first.")
        return

    if "copilot_messages" not in st.session_state:
        st.session_state.copilot_messages = []

    def ask(query):
        matched = retrieve_themes(query)
        evidence = retrieve_evidence(query, top_k=8)
        structured = generate_structured_answer(query, evidence, matched)
        st.session_state.copilot_messages.append({"query": query, "structured": structured, "evidence": evidence})

    ui.flush(ui.hero("💬", "Chat Terminal", "How can I help your discovery research?",
                     "I analyze thousands of real Blinkit reviews and discussions to answer product "
                     "questions with evidence-backed, cited insight."))

    if not st.session_state.copilot_messages:
        st.markdown(f'<div style="color:{ui.FAINT};font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;margin:20px 2px 12px;">Suggested Questions</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, q in enumerate(SUGGESTED_QUESTIONS):
            if cols[i % 2].button("✦  " + q, use_container_width=True, key=f"sug_{i}"):
                ask(q)
                st.rerun()

    for msg in st.session_state.copilot_messages:
        _render_answer_card(msg)

    if query := st.chat_input("Ask about barriers, categories, segments, discovery…"):
        ask(query)
        st.rerun()
