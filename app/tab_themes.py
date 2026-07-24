"""Theme Intelligence tab: 'Discovery Themes & User Voice' — a light Blinkit-palette
theme board modelled on the spotify-discovery-intel reference. Three summary chips (most
mentioned / most negative / most positive), a research-question coverage strip, then a
2-column grid of theme cards, each with an average-sentiment gradient bar, mention stats,
and a collapsible set of real user quotes.
"""
import json
from pathlib import Path

import streamlit as st

from app import ui
from app.data import load_themes_df

REPO_ROOT = Path(__file__).resolve().parents[1]


def render():
    themes_df = load_themes_df()
    if themes_df.empty:
        st.warning("No themes yet — run `python -m src.synthesize` first.")
        return

    themes = themes_df.sort_values("rank_score", ascending=False).to_dict("records")
    total_corpus = sum(t["size"] for t in themes) or 1

    ui.flush(ui.hero("layers", "Theme Intelligence", "Discovery Themes & User Voice",
                     "Every category barrier, classified from an LLM's reading of the reviews — ranked by "
                     "mentions, with the real user quotes behind each one.",
                     pill=f"{ui.fmt_full(total_corpus)} reviews"))

    parts = [_summary_chips(themes), _rq_strip(), '<div class="ui-label">All Themes</div>', '<div class="ui-g2">']
    for i, t in enumerate(themes):
        parts.append(_theme_card(t, i, total_corpus))
    parts.append("</div>")
    ui.flush(parts)


def _sent100(avg):
    return round((avg + 1) / 2 * 100)


def _summary_chips(themes):
    most_mentioned = max(themes, key=lambda t: t["size"])
    most_neg = min(themes, key=lambda t: t["avg_sentiment"])
    most_pos = max(themes, key=lambda t: t["avg_sentiment"])
    total = sum(t["size"] for t in themes) or 1

    def chip(icon_name, eyebrow, right, name, sub, border, bg, ecol):
        return (f'<div class="ui-summary" style="border-color:{border};background:{bg};">'
                f'<div class="ui-summary-eyebrow" style="color:{ecol};">'
                f'<span style="display:inline-flex;align-items:center;gap:6px;">{ui.icon(icon_name, size=14, color=ecol)}{eyebrow}</span>'
                f'<span>{right}</span></div>'
                f'<div class="ui-summary-title">{ui.esc(name)}</div>'
                f'<div class="ui-summary-sub">{sub}</div></div>')

    chips = [
        chip("flame", "Most Mentioned", f"{ui.fmt_full(most_mentioned['size'])} reviews",
             ui.THEME_META.get(most_mentioned["theme_id"], (most_mentioned["name"], ""))[0],
             f"{most_mentioned['size']/total:.1%} of themed feedback", ui.YELLOW, ui.YELLOW_SOFT, ui.YELLOW_DK),
        chip("frown", "Most Negative", f"{_sent100(most_neg['avg_sentiment'])}/100",
             ui.THEME_META.get(most_neg["theme_id"], (most_neg["name"], ""))[0],
             "The most painful theme", ui.NEG, "#fef2f4", ui.NEG),
        chip("smile", "Most Positive", f"{_sent100(most_pos['avg_sentiment'])}/100",
             ui.THEME_META.get(most_pos["theme_id"], (most_pos["name"], ""))[0],
             "What users are happiest about", ui.POS, "#f0fdf4", ui.POS),
    ]
    return f'<div class="ui-g3 ui-row">{"".join(chips)}</div>'


def _rq_strip():
    rq_file = REPO_ROOT / "data" / "themes" / "research_questions.json"
    if not rq_file.exists():
        return ""
    rq = json.loads(rq_file.read_text())
    answered = sum(1 for v in rq.values() if v["status"] == "answered")
    cells = []
    for qid, info in rq.items():
        ok = info["status"] == "answered"
        color = ui.POS if ok else ui.NEG
        cells.append(f'<div style="display:flex;align-items:center;gap:8px;padding:6px 0;">'
                     f'<span class="ui-dot" style="background:{color};"></span>'
                     f'<b style="color:{ui.TXT};font-size:12px;">{qid}</b>'
                     f'<span class="ui-muted" style="font-size:12px;">{ui.esc(info["question"])}</span>'
                     f'<span style="margin-left:auto;color:{color};font-size:11px;font-weight:700;">'
                     f'{"✓ " + str(len(info["theme_ids"])) + " themes" if ok else "unanswered"}</span></div>')
    return (f'<div class="ui-card ui-row"><div class="ui-card-title">Research Question Coverage</div>'
            f'<div class="ui-card-sub">{answered}/{len(rq)} of the eight research questions are answered by at least one theme.</div>'
            f'{"".join(cells)}</div>')


def _theme_card(t, i, total_corpus):
    name = ui.THEME_META.get(t["theme_id"], (t["name"], ""))[0]
    desc = ui.THEME_META.get(t["theme_id"], ("", "LLM-classified theme."))[1]
    color = ui.CAT[i % len(ui.CAT)]
    s100 = _sent100(t["avg_sentiment"])
    scol = ui.sentiment_color(t["avg_sentiment"])
    slabel = ui.sentiment_label(t["avg_sentiment"])
    prevalence = t["size"] / total_corpus

    quotes = ""
    reps = t.get("representative_quotes", [])
    if reps:
        qhtml = "".join(
            f'<div class="ui-quote">"{ui.esc(q["text"][:200])}"'
            f'<div class="ui-quote-src">— {ui.SOURCE_META.get(q.get("source",""), (q.get("source",""), ""))[0]}</div></div>'
            for q in reps
        )
        summary_icon = ui.icon("message", size=13, color=ui.MUTED)
        quotes = (f'<details class="ui-quotes"><summary><span style="display:inline-flex;align-items:center;gap:6px;">'
                  f'{summary_icon}Show {len(reps)} user quotes</span></summary>{qhtml}</details>')

    conf = t.get("confidence", "")
    conf_badge = ""
    if conf:
        ccol = ui.POS if conf == "high" else ui.NEU
        conf_badge = f'<span class="ui-badge" style="color:{ccol};border-color:{ccol}55;background:{ccol}12;margin-left:8px;">{conf.replace("_"," ")}</span>'

    return (f'<div class="ui-card">'
            f'<div class="ui-theme-head"><div class="ui-theme-name">'
            f'<span class="ui-dot" style="background:{color};width:12px;height:12px;"></span>{ui.esc(name)}</div>'
            f'<span class="ui-badge" style="color:{scol};border-color:{scol}55;background:{scol}12;">{slabel}</span></div>'
            f'<div class="ui-theme-desc">{ui.esc(desc)}</div>'
            f'<div style="display:flex;justify-content:space-between;color:{ui.FAINT};font-size:10px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;">'
            f'<span>Average Sentiment</span><span style="color:{scol};">{s100}/100</span></div>'
            f'<div class="ui-sentbar-track"><span class="ui-sentbar-mark" style="left:{s100}%;"></span></div>'
            f'<div class="ui-theme-stats">'
            f'<div class="ui-theme-stat"><div class="ui-theme-stat-v">{ui.fmt_full(t["size"])}</div><div class="ui-theme-stat-l">Mentions</div></div>'
            f'<div class="ui-theme-stat"><div class="ui-theme-stat-v">{prevalence:.1%}</div><div class="ui-theme-stat-l">Of Reviews</div></div>'
            f'</div>'
            f'<div style="margin-top:12px;color:{ui.MUTED};font-size:12px;">'
            f'Research questions: <b style="color:{ui.TXT};">{", ".join(t.get("research_questions", [])) or "none"}</b>{conf_badge}</div>'
            f'{quotes}</div>')
