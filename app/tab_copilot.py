"""Insight Engine tab: a light Blinkit-palette RAG chat. Conversation is rendered as
chat bubbles — the user's question right-aligned, the assistant's evidence-cited answer
left-aligned — with clickable source citations. Empty state shows a centered hero and
suggested-question chips, matching the spotify-discovery-intel copilot screen.

Product Recommendations is included at the user's explicit request, overriding the
project spec's default insight-only constraint (docs/ProblemStatement.md) — see
app/rag_engine.py's generate_structured_answer for how that field is generated.
"""
import re

import streamlit as st
import streamlit.components.v1 as components

from app import ui
from app.data import load_enriched_df, scraped_count
from app.rag_engine import generate_structured_answer, get_db, retrieve_evidence, retrieve_themes

SUGGESTED_QUESTIONS = [
    "Why do users repeatedly buy from the same categories?",
    "What prevents users from exploring new categories?",
    "How do users discover products today?",
    "What role do habits play in shopping behavior?",
    "What information do users need before trying a new category?",
    "What frustrations emerge repeatedly?",
    "Which user segments are more likely to experiment?",
    "What unmet needs emerge consistently across discussions?",
]


def _seclabel(text):
    return f'<div class="ui-secline">{text}</div>'


def _cite_links(summary: str, midx: int, n_evidence: int) -> str:
    """Turn the model's "[1, 4, 5]" citations into chips that jump to those quotes.

    Escape first, then substitute, so the chip anchors are the only markup that survives.
    A number outside the retrieved range is left as plain text rather than linked to a
    card that does not exist.
    """
    safe = ui.esc(summary)

    def repl(m):
        chips = []
        for part in m.group(1).split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= n_evidence:
                chips.append(f'<a class="ui-citechip" href="#ev-{midx}-{part}" '
                             f'title="Jump to supporting quote {part}">{part}</a>')
            elif part:
                chips.append(f"[{ui.esc(part)}]")
        return "".join(chips)

    return re.sub(r"\[([\d,\s]+)\]", repl, safe)


def _render_message(msg, midx: int = 0):
    query, structured, evidence = msg["query"], msg["structured"], msg["evidence"]

    # Question bubble (right-aligned). The id is the scroll target for a new answer —
    # landing here shows the question and the top of its answer, not the tail of it.
    q_html = (f'<div class="ui-chat-q" id="msg-{midx}"><div class="ui-chat-q-bubble">{ui.esc(query)}</div>'
              f'<div class="ui-chat-avatar q">{ui.icon("user", size=17, color="#191c1e")}</div></div>')

    # Answer (left-aligned card)
    body = [f'<div class="ui-card" style="border-radius:14px 14px 14px 4px;">',
            _seclabel("Executive Summary"),
            f'<div style="color:{ui.TXT};font-size:14px;line-height:1.6;">'
            f'{_cite_links(structured["executive_summary"], midx, len(evidence))}</div>']

    if structured.get("theme_breakdown") or structured.get("affected_segments"):
        body.append('<div class="ui-g2" style="margin-top:14px;">')
        for title, items in [("Theme Breakdown", structured.get("theme_breakdown")),
                             ("Affected Segments", structured.get("affected_segments"))]:
            if items:
                li = "".join(f'<li style="margin-bottom:6px;">{ui.esc(x)}</li>' for x in items)
                body.append(f'<div>{_seclabel(title)}<ul style="margin:0;padding-left:18px;color:{ui.MUTED};font-size:13px;">{li}</ul></div>')
        body.append("</div>")

    if structured.get("product_recommendations"):
        recs = "".join(
            f'<div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:8px;">'
            f'<div style="width:22px;height:22px;border-radius:50%;background:{ui.YELLOW};color:#191c1e;font-weight:700;font-size:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">{i}</div>'
            f'<div style="color:{ui.MUTED};font-size:13px;line-height:1.5;">{ui.esc(rec)}</div></div>'
            for i, rec in enumerate(structured["product_recommendations"], start=1)
        )
        body.append(_seclabel("Product Recommendations") + recs)

    if evidence:
        # Every retrieved quote is listed and numbered: the summary cites [n] against the
        # numbering the model was given (rag_engine builds its context as [1]..[k]), so
        # truncating this list to 5 left citations like [7] pointing at nothing.
        body.append(_seclabel("Supporting Evidence")
                    + f'<div style="color:{ui.FAINT};font-size:11px;margin:-4px 0 8px;">'
                      f'Numbers in the summary above refer to these quotes.</div>')
        for i, e in enumerate(evidence, start=1):
            name, color = ui.SOURCE_META.get(e["source"], (e["source"].title(), ui.MUTED))
            scol = ui.sentiment_color(e["sentiment"])
            slabel = ui.sentiment_label(e["sentiment"])
            tag = e["barrier_type"] if e.get("barrier_type", "none") != "none" else e.get("behaviour_signal", "")
            date = e["date"][:10] if e.get("date") else ""
            url = e.get("url", "")
            cite = (f'<a class="ui-cite" href="{ui.esc(url)}" target="_blank" rel="noopener">'
                    f'{ui.icon("link", size=12, color=ui.YELLOW_DK)}view source</a>') if url else ""
            body.append(f'<div id="ev-{midx}-{i}" style="border-left:2px solid {color};padding:2px 0 2px 12px;margin:10px 0;scroll-margin-top:80px;">'
                        f'<div style="display:flex;gap:10px;align-items:center;margin-bottom:4px;flex-wrap:wrap;">'
                        f'<span class="ui-citenum">[{i}]</span>'
                        f'<span class="ui-badge" style="color:{color};border-color:{color}55;background:{color}12;">{name}</span>'
                        f'<span style="color:{scol};font-size:12px;font-style:italic;">{slabel}</span>'
                        f'<span style="color:{ui.FAINT};font-size:11px;font-family:monospace;">{ui.esc(tag)}</span></div>'
                        f'<div style="color:{ui.TXT};font-size:12px;font-style:italic;line-height:1.5;">"{ui.esc(e["text"][:260])}"</div>'
                        f'<div style="display:flex;gap:10px;align-items:center;margin-top:4px;">'
                        f'<span style="color:{ui.FAINT};font-size:11px;">{date}</span>{cite}</div></div>')

    method = {
        "gemini": "Vector similarity (RAG) · LLM-generated",
        "extractive": "Vector similarity (RAG) · Extractive fallback (daily LLM quota exhausted)",
        "none": "No evidence retrieved",
    }.get(structured.get("method"), "")
    body.append(f'<div style="color:{ui.FAINT};font-size:11px;margin-top:14px;">{method}</div></div>')

    a_html = (f'<div class="ui-chat-a"><div class="ui-chat-avatar a">{ui.icon("sparkles", size=17, color=ui.YELLOW)}</div>'
              f'<div class="ui-chat-a-body">{"".join(body)}</div></div>')

    ui.flush([q_html, a_html])


def _scroll_to_latest():
    """Scroll to the top of the newest exchange, once, after it is rendered.

    Two obstacles. st.markdown strips <script>, so the JS runs from a components iframe
    and reaches into the parent document. And the scroller is Streamlit's
    stAppScrollToBottomContainer, which — with a chat_input on the page — pins itself to
    the bottom, i.e. the tail of the answer that just arrived. A single scroll call loses
    that race, so the position is re-asserted over the second following the rerun.
    """
    idx = st.session_state.pop("copilot_scroll_to", None)
    if idx is None:
        return
    components.html(
        f"""
        <script>
        const doc = window.parent.document;
        function jump() {{
            const el = doc.getElementById("msg-{idx}");
            if (!el) return false;
            const cont = doc.querySelector('[data-testid="stAppScrollToBottomContainer"]');
            if (cont) {{
                // 76px clears Streamlit's 60px fixed header, which overlays the
                // scroll container and would otherwise cut off the question bubble.
                const top = el.getBoundingClientRect().top
                          - cont.getBoundingClientRect().top + cont.scrollTop - 76;
                cont.scrollTo({{top: top, behavior: "smooth"}});
            }} else {{
                el.scrollIntoView({{behavior: "smooth", block: "start"}});
            }}
            return true;
        }}
        [0, 80, 200, 450, 800, 1200].forEach(d => setTimeout(jump, d));
        </script>
        """,
        height=0,
    )


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
        # Land on the top of the new exchange. Streamlit otherwise leaves the viewport at
        # the foot of the page, i.e. the tail end of the answer that just appeared.
        st.session_state.copilot_scroll_to = len(st.session_state.copilot_messages) - 1

    grounded = len(load_enriched_df())
    scraped = scraped_count(grounded)
    ui.flush(ui.hero("message", "Blinkit · Voice of Customer", "Blinkit Insight Engine",
                     f"Trained on thousands of Blinkit reviews, Reddit threads and community "
                     f"discussions — every answer grounded in what real users said. "
                     f"{ui.fmt_full(scraped)} reviews scraped, {ui.fmt_full(grounded)} indexed for retrieval.",
                     pill=f"{ui.fmt_full(scraped)} scraped · {ui.fmt_full(grounded)} indexed"))

    if not st.session_state.copilot_messages:
        st.markdown(f'<div class="ui-label">Suggested Questions</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, q in enumerate(SUGGESTED_QUESTIONS):
            if cols[i % 2].button(q, use_container_width=True, key=f"sug_{i}"):
                ask(q)
                st.rerun()

    for i, msg in enumerate(st.session_state.copilot_messages):
        _render_message(msg, i)

    _scroll_to_latest()

    if query := st.chat_input("Ask about barriers, categories, segments, discovery…"):
        ask(query)
        st.rerun()
