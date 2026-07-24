"""Shared light 'Blinkit' design system for the dashboard tabs.

One CSS block (injected once from rag_chatbot.py, after theme.inject_theme) defines every
reusable component class (.ui-*): hero banners, stat tiles, cards, lollipop charts,
donuts, sentiment gradient bars, segment cards, theme cards, source cards, review cards,
suggestion chips. Each tab builds plain HTML with these classes and flushes it via
flush() — Streamlit renders markdown, so leading indentation would be read as a code
block; flush() collapses everything to a single line to avoid that entirely.

Palette is light with the Blinkit yellow as the accent and Blinkit green for positive
sentiment, on a near-white page with white cards and hairline borders.
"""
import html as _html

import streamlit as st

# --- Blinkit light palette -------------------------------------------------
PAGE = "#f6f7f9"
CARD = "#ffffff"
CARD2 = "#f9fafb"
BORDER = "#eceef1"
BORDER2 = "#e2e5ea"
TXT = "#16181d"
MUTED = "#6b7280"
FAINT = "#9aa1ab"
YELLOW = "#F8CB46"
YELLOW_DK = "#e0ad10"
YELLOW_SOFT = "#fef6dc"
GREEN = "#0c831f"
POS = "#16a34a"
NEU = "#e0a400"
NEG = "#e11d48"

# Categorical palette for multi-series charts (barriers, themes).
CAT = ["#f97316", "#2563eb", "#16a34a", "#0d9488", "#9333ea", "#db2777", "#d97706", "#0ea5e9", "#ca8a04"]

SOURCE_META = {
    "play": ("Google Play", "#16a34a"),
    "appstore": ("App Store", "#64748b"),
    "youtube": ("YouTube", "#ef4444"),
    "qcomm_comparison": ("Q-Comm Threads", "#d97706"),
    "product_review": ("Product Reviews", "#db2777"),
    "reddit": ("Reddit", "#f97316"),
    "forum": ("Forums", "#2563eb"),
}

BARRIER_LABELS = {
    "trust_quality": "Trust & Quality",
    "price_premium": "Price Premium",
    "assortment_doubt": "Assortment Doubt",
    "findability": "Findability",
    "no_trigger": "No Trigger to Try",
    "returns_risk": "Returns Risk",
    "brand_absence": "Brand Absence",
    "expiry_freshness": "Expiry & Freshness",
    "prefer_specialist_store": "Prefer Specialist Store",
}

THEME_META = {
    "platform_mental_model": ("Platform Mental Model", "Users frame Blinkit as the app for groceries and reach for a different app for everything else."),
    "category_specific_distrust": ("Category-Specific Distrust", "Users buy some things here but explicitly avoid certain categories that feel riskier."),
    "first_trial_story": ("First-Trial Stories", "A user tried a new category once — what happened, and whether they came back."),
    "habit_and_reorder": ("Habit & Reorder", "Routine, repeat, low-effort reordering of the same familiar basket."),
    "discovery_mechanics": ("Discovery Mechanics", "How people actually find products — search vs. browse vs. homepage vs. recommendations."),
    "assortment_gaps": ("Assortment Gaps", "A user looked for something specific and it wasn't there, or their brand was missing."),
    "price_and_value": ("Price & Value", "Blinkit's price and fees run higher — when that premium is worth it, and when it isn't."),
    "life_event_trigger": ("Life-Event Triggers", "A new pet, baby, festival, guests or illness created a fresh shopping need."),
    "cross_platform_comparison": ("Cross-Platform Comparison", "Users explicitly compare Blinkit to Zepto, Instamart, Amazon or the local kirana store."),
}


# --- Inline SVG icon set (Lucide-style, stroke-based) ----------------------
# Emoji were replaced with these so the chrome reads as a designed product, not a
# document. icon(name) returns a single-line <svg> safe to embed inside flush()ed HTML.
ICONS = {
    "grid": '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    "bar-chart": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "layers": '<path d="M12 2 2 7l10 5 10-5-10-5Z"/><path d="m2 12 10 5 10-5"/><path d="m2 17 10 5 10-5"/>',
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "file-text": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
    "compass": '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "smile": '<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/>',
    "frown": '<circle cx="12" cy="12" r="10"/><path d="M16 16s-1.5-2-4-2-4 2-4 2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/>',
    "meh": '<circle cx="12" cy="12" r="10"/><line x1="8" y1="15" x2="16" y2="15"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/>',
    "pie": '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
    "filter": '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "sparkles": '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5Z"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "tag": '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r="1"/>',
    "heart": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.29 1.51 4.04 3 5.5l7 7Z"/>',
    "pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "send": '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
}


def icon(name: str, size: int = 20, color: str = "currentColor", stroke: float = 2) -> str:
    body = ICONS.get(name, "")
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" style="display:block;">{body}</svg>')


def esc(s) -> str:
    return _html.escape(str(s))


def fmt(n: int) -> str:
    return f"{n/1000:.1f}k" if n >= 1000 else str(int(n))


def fmt_full(n: int) -> str:
    return f"{int(n):,}"


def flush(parts):
    """Join HTML parts and render as one line so markdown never treats indented HTML as
    a code block. Accepts a list of strings or a single string."""
    if isinstance(parts, (list, tuple)):
        out = "".join(parts)
    else:
        out = parts
    out = "".join(line.strip() for line in out.splitlines())
    st.markdown(out, unsafe_allow_html=True)


def sentiment_color(score: float) -> str:
    return POS if score > 0.2 else (NEG if score < -0.2 else NEU)


def sentiment_label(score: float) -> str:
    return "Positive" if score > 0.2 else ("Negative" if score < -0.2 else "Neutral")


def hero(icon_name: str, eyebrow: str, title: str, sub: str, pill: str = None) -> str:
    pill_html = f'<div class="ui-hero-pill">{esc(pill)}</div>' if pill else ""
    return f"""
    <div class="ui-hero">
      <div class="ui-hero-icon">{icon(icon_name, size=24, color="#191c1e")}</div>
      <div class="ui-hero-text">
        <div class="ui-eyebrow">{esc(eyebrow)}</div>
        <div class="ui-hero-title">{esc(title)}</div>
        <div class="ui-hero-sub">{esc(sub)}</div>
      </div>
      {pill_html}
    </div>"""


def inject_ui():
    st.markdown(_UI_CSS, unsafe_allow_html=True)


_UI_CSS = f"""<style>
/* Trim Streamlit's tall default top padding so the hero sits near the top. */
.block-container, [data-testid="stMainBlockContainer"] {{ padding-top:2.2rem !important; padding-bottom:3rem !important; }}
.ui-wrap {{ font-family:'Inter',sans-serif; }}
.ui-wrap * {{ box-sizing:border-box; }}
.ui-label {{ color:{FAINT}; font-size:11px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; margin:20px 2px 11px; }}
.ui-dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:8px; vertical-align:middle; }}
.ui-muted {{ color:{MUTED}; font-size:13px; }}

/* Hero banner — compact */
.ui-hero {{ background:{CARD}; border:1px solid {BORDER}; border-radius:14px; padding:16px 20px; display:flex; align-items:center; gap:15px; position:relative; box-shadow:0 1px 2px rgba(16,24,40,0.04); }}
.ui-hero-icon {{ width:42px; height:42px; border-radius:11px; background:{YELLOW}; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
.ui-eyebrow {{ color:{YELLOW_DK}; font-size:10px; font-weight:800; letter-spacing:0.13em; text-transform:uppercase; }}
.ui-hero-title {{ color:{TXT}; font-size:23px; font-weight:800; letter-spacing:-0.02em; margin:2px 0 3px; line-height:1.15; }}
.ui-hero-sub {{ color:{MUTED}; font-size:13px; max-width:680px; line-height:1.5; }}
.ui-hero-pill {{ position:absolute; top:16px; right:20px; background:{YELLOW_SOFT}; color:{YELLOW_DK}; border:1px solid {YELLOW}; border-radius:9999px; padding:5px 13px; font-size:12px; font-weight:800; white-space:nowrap; }}

/* Grids */
.ui-g2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.ui-g3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
.ui-g4 {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; }}
.ui-g5 {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; }}
.ui-split {{ display:grid; grid-template-columns:1.5fr 1fr; gap:16px; }}
.ui-row {{ margin-top:16px; }}

/* Cards */
.ui-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:14px; padding:20px; box-shadow:0 1px 2px rgba(16,24,40,0.04); min-width:0; }}
.ui-card-title {{ color:{TXT}; font-size:16px; font-weight:800; }}
.ui-card-sub {{ color:{MUTED}; font-size:12px; margin:3px 0 16px; }}

/* Source-accent cards */
.ui-src {{ background:{CARD}; border:1px solid {BORDER}; border-radius:12px; padding:15px 17px; box-shadow:0 1px 2px rgba(16,24,40,0.04); min-width:0; }}
.ui-src-name {{ color:{TXT}; font-size:13px; font-weight:700; }}
.ui-src-count {{ color:{TXT}; font-size:24px; font-weight:800; margin:2px 0; }}
.ui-src-metric {{ color:{MUTED}; font-size:12px; }}

/* Stat tiles */
.ui-stat {{ background:{CARD}; border:1px solid {BORDER}; border-radius:12px; padding:15px; display:flex; align-items:center; gap:11px; box-shadow:0 1px 2px rgba(16,24,40,0.04); min-width:0; }}
.ui-stat-icon {{ width:34px; height:34px; border-radius:9px; background:{YELLOW_SOFT}; display:flex; align-items:center; justify-content:center; font-size:16px; flex-shrink:0; }}
.ui-stat-body {{ min-width:0; flex:1; }}
.ui-stat-label {{ color:{MUTED}; font-size:10px; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; line-height:1.3; }}
.ui-stat-sub {{ color:{FAINT}; font-size:10px; margin-top:2px; }}
.ui-stat-value {{ color:{TXT}; font-size:22px; font-weight:800; margin-left:auto; white-space:nowrap; }}
.ui-stat.big {{ flex-direction:column; align-items:flex-start; gap:8px; border-top:3px solid {BORDER2}; }}
.ui-stat.big .ui-stat-value {{ margin-left:0; font-size:30px; }}
.ui-stat.big .ui-stat-top {{ display:flex; align-items:center; gap:9px; }}

/* Lollipop chart */
.ui-lolli {{ display:grid; grid-template-columns:150px 1fr 48px; align-items:center; gap:12px; margin-bottom:13px; }}
.ui-lolli-label {{ color:{TXT}; font-size:13px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.ui-lolli-track {{ position:relative; height:4px; background:{CARD2}; border:1px solid {BORDER}; border-radius:2px; }}
.ui-lolli-fill {{ position:absolute; top:-1px; height:4px; border-radius:2px; }}
.ui-lolli-knob {{ position:absolute; top:50%; width:11px; height:11px; border-radius:50%; background:{CARD}; border:2px solid; transform:translate(-50%,-50%); }}
.ui-lolli-val {{ color:{TXT}; font-size:13px; font-weight:700; text-align:right; }}

/* Horizontal bar rows */
.ui-bar {{ display:grid; grid-template-columns:120px 1fr 60px; align-items:center; gap:12px; margin-bottom:11px; }}
.ui-bar-label {{ color:{TXT}; font-size:13px; font-weight:600; text-align:right; }}
.ui-bar-track {{ height:22px; background:{CARD2}; border-radius:5px; overflow:hidden; }}
.ui-bar-fill {{ height:22px; border-radius:5px; }}
.ui-bar-val {{ color:{MUTED}; font-size:12px; }}

/* Vertical bars (rating dist) */
.ui-vbars {{ display:flex; align-items:flex-end; justify-content:space-around; height:180px; gap:14px; padding:0 6px; }}
.ui-vbar {{ flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; }}
.ui-vbar-fill {{ width:100%; max-width:56px; border-radius:6px 6px 0 0; }}
.ui-vbar-x {{ color:{MUTED}; font-size:12px; font-weight:600; margin-top:8px; }}
.ui-vbar-n {{ color:{FAINT}; font-size:11px; margin-bottom:5px; }}

/* Concentration highlight */
.ui-rep-hero {{ background:{YELLOW_SOFT}; border:1px solid {YELLOW}; border-radius:12px; padding:16px; display:flex; gap:14px; align-items:center; margin-bottom:16px; }}
.ui-rep-big {{ color:{TXT}; font-size:38px; font-weight:800; line-height:1; }}
.ui-rep-sub {{ color:{MUTED}; font-size:12px; line-height:1.45; }}
.ui-rep-row {{ margin-bottom:12px; }}
.ui-rep-head {{ display:flex; justify-content:space-between; color:{TXT}; font-size:13px; font-weight:600; margin-bottom:5px; }}
.ui-rep-track {{ height:6px; background:{CARD2}; border-radius:3px; }}
.ui-rep-fill {{ height:6px; border-radius:3px; }}

/* Segment leaderboard + cards */
.ui-seg-head {{ display:grid; grid-template-columns:26px 1fr 62px 64px; color:{FAINT}; font-size:10px; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; padding-bottom:9px; border-bottom:1px solid {BORDER}; }}
.ui-seg-row {{ display:grid; grid-template-columns:26px 1fr 62px 64px; align-items:center; padding:11px 0; border-bottom:1px solid {BORDER}; }}
.ui-seg-rank {{ color:{FAINT}; font-size:13px; font-weight:700; }}
.ui-seg-name {{ color:{TXT}; font-size:13px; font-weight:600; }}
.ui-seg-rate {{ color:{NEG}; font-size:14px; font-weight:800; text-align:right; }}
.ui-seg-n {{ color:{MUTED}; font-size:13px; text-align:right; }}
.ui-segcard {{ background:{CARD}; border:1px solid {BORDER}; border-radius:12px; padding:16px; position:relative; box-shadow:0 1px 2px rgba(16,24,40,0.04); }}
.ui-segcard-rank {{ position:absolute; top:14px; right:16px; color:{FAINT}; font-size:12px; font-weight:700; }}
.ui-segcard-icon {{ width:30px; height:30px; border-radius:8px; background:{YELLOW_SOFT}; display:inline-flex; align-items:center; justify-content:center; font-size:15px; }}
.ui-segcard-pct {{ font-size:26px; font-weight:800; margin:12px 0 2px; }}
.ui-segcard-name {{ color:{TXT}; font-size:14px; font-weight:700; }}
.ui-segcard-sub {{ color:{FAINT}; font-size:11px; margin-top:3px; }}

/* Donut */
.ui-donut-wrap {{ display:flex; align-items:center; gap:24px; }}
.ui-donut {{ width:150px; height:150px; border-radius:50%; flex-shrink:0; display:flex; align-items:center; justify-content:center; }}
.ui-donut-hole {{ width:104px; height:104px; border-radius:50%; background:{CARD}; display:flex; flex-direction:column; align-items:center; justify-content:center; }}
.ui-donut-big {{ font-size:26px; font-weight:800; }}
.ui-donut-lbl {{ color:{MUTED}; font-size:11px; letter-spacing:0.08em; text-transform:uppercase; }}
.ui-leg {{ display:flex; align-items:center; color:{TXT}; font-size:13px; padding:7px 0; }}
.ui-leg-val {{ margin-left:auto; font-weight:700; }}

/* Sentiment gradient bar (themes) */
.ui-sentbar-track {{ position:relative; height:7px; border-radius:4px; background:linear-gradient(90deg,{NEG} 0%,{NEU} 50%,{POS} 100%); margin:6px 0; }}
.ui-sentbar-mark {{ position:absolute; top:-3px; width:4px; height:13px; border-radius:2px; background:{TXT}; transform:translateX(-50%); }}

/* Theme cards */
.ui-theme-head {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }}
.ui-theme-name {{ color:{TXT}; font-size:16px; font-weight:800; }}
.ui-theme-desc {{ color:{MUTED}; font-size:13px; line-height:1.5; margin-bottom:14px; }}
.ui-theme-stats {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }}
.ui-theme-stat {{ background:{CARD2}; border:1px solid {BORDER}; border-radius:9px; padding:11px 13px; }}
.ui-theme-stat-v {{ color:{TXT}; font-size:19px; font-weight:800; }}
.ui-theme-stat-l {{ color:{FAINT}; font-size:10px; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; margin-top:2px; }}
.ui-summary {{ border-radius:12px; padding:15px 17px; border:1px solid; }}
.ui-summary-eyebrow {{ font-size:10px; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; display:flex; justify-content:space-between; align-items:center; }}
.ui-summary-title {{ color:{TXT}; font-size:17px; font-weight:800; margin:8px 0 3px; }}
.ui-summary-sub {{ color:{MUTED}; font-size:11px; }}

/* Badges + quotes */
.ui-badge {{ display:inline-block; font-size:11px; font-weight:700; padding:2px 10px; border-radius:9999px; border:1px solid; }}
details.ui-quotes {{ margin-top:14px; border-top:1px solid {BORDER}; padding-top:11px; }}
details.ui-quotes summary {{ cursor:pointer; color:{MUTED}; font-size:12px; font-weight:700; list-style:none; }}
details.ui-quotes summary::-webkit-details-marker {{ display:none; }}
.ui-quote {{ border-left:2px solid {YELLOW}; padding:5px 0 5px 12px; margin:10px 0; color:{TXT}; font-size:12px; font-style:italic; line-height:1.5; }}
.ui-quote-src {{ font-style:normal; color:{FAINT}; font-size:11px; margin-top:3px; }}

/* Source/review cards */
.ui-rev {{ background:{CARD}; border:1px solid {BORDER}; border-radius:11px; padding:14px; box-shadow:0 1px 2px rgba(16,24,40,0.04); }}
.ui-rev-head {{ display:flex; justify-content:space-between; align-items:center; color:{TXT}; font-size:12px; font-weight:700; margin-bottom:8px; }}
.ui-rev-date {{ color:{FAINT}; font-weight:500; }}
.ui-rev-text {{ color:{MUTED}; font-size:12px; line-height:1.5; min-height:52px; }}
.ui-rev-foot {{ margin-top:10px; }}

/* Year coverage */
.ui-year {{ background:{CARD2}; border:1px solid {BORDER}; border-radius:10px; padding:14px; }}
.ui-year-head {{ display:flex; justify-content:space-between; color:{TXT}; font-size:14px; font-weight:800; margin-bottom:9px; }}
.ui-year-n {{ color:{MUTED}; font-weight:600; font-size:13px; }}
.ui-year-bar {{ display:flex; height:7px; border-radius:4px; overflow:hidden; background:{PAGE}; }}

/* Collection funnel */
.ui-funnel {{ display:flex; flex-direction:column; gap:10px; }}
.ui-funnel-row {{ display:grid; grid-template-columns:150px 1fr 150px; align-items:center; gap:14px; }}
.ui-funnel-label {{ color:{TXT}; font-size:13px; font-weight:600; }}
.ui-funnel-track {{ height:26px; background:{CARD2}; border-radius:6px; overflow:hidden; }}
.ui-funnel-fill {{ height:26px; border-radius:6px; display:flex; align-items:center; padding-left:12px; color:#fff; font-size:12px; font-weight:700; }}
.ui-funnel-meta {{ color:{MUTED}; font-size:12px; }}
.ui-funnel-meta b {{ color:{TXT}; font-size:14px; }}

/* Chat bubbles */
.ui-chat-q {{ display:flex; justify-content:flex-end; gap:10px; margin:18px 0 8px; }}
.ui-chat-q-bubble {{ background:{YELLOW}; color:#191c1e; border-radius:14px 14px 4px 14px; padding:10px 15px; font-size:14px; font-weight:600; max-width:70%; line-height:1.45; }}
.ui-chat-avatar {{ width:32px; height:32px; border-radius:9px; flex-shrink:0; display:flex; align-items:center; justify-content:center; }}
.ui-chat-avatar.q {{ background:{YELLOW}; }}
.ui-chat-avatar.a {{ background:{TXT}; }}
.ui-chat-a {{ display:flex; justify-content:flex-start; gap:10px; margin:8px 0 6px; }}
.ui-chat-a-body {{ flex:1; max-width:88%; }}

/* Clickable citation link */
.ui-cite {{ color:{YELLOW_DK}; font-size:11px; font-weight:600; text-decoration:none; display:inline-flex; align-items:center; gap:4px; }}
.ui-cite:hover {{ text-decoration:underline; }}
.ui-secline {{ color:{FAINT}; font-size:10px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; margin:16px 0 8px; display:flex; align-items:center; gap:6px; }}
</style>"""
