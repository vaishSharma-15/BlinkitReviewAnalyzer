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


def esc(s) -> str:
    return _html.escape(str(s))


def fmt(n: int) -> str:
    return f"{n/1000:.1f}k" if n >= 1000 else str(int(n))


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


def hero(icon: str, eyebrow: str, title: str, sub: str, pill: str = None) -> str:
    pill_html = f'<div class="ui-hero-pill">{esc(pill)}</div>' if pill else ""
    return f"""
    <div class="ui-hero">
      <div class="ui-hero-icon">{icon}</div>
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
.ui-wrap {{ font-family:'Inter',sans-serif; }}
.ui-wrap * {{ box-sizing:border-box; }}
.ui-label {{ color:{FAINT}; font-size:11px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; margin:22px 2px 12px; }}
.ui-dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:8px; vertical-align:middle; }}
.ui-muted {{ color:{MUTED}; font-size:13px; }}

/* Hero banner */
.ui-hero {{ background:{CARD}; border:1px solid {BORDER}; border-radius:16px; padding:24px 26px; display:flex; align-items:flex-start; gap:18px; position:relative; box-shadow:0 1px 2px rgba(16,24,40,0.04); }}
.ui-hero-icon {{ width:52px; height:52px; border-radius:13px; background:{YELLOW}; display:flex; align-items:center; justify-content:center; font-size:26px; flex-shrink:0; }}
.ui-eyebrow {{ color:{YELLOW_DK}; font-size:11px; font-weight:800; letter-spacing:0.14em; text-transform:uppercase; }}
.ui-hero-title {{ color:{TXT}; font-size:29px; font-weight:800; letter-spacing:-0.02em; margin:4px 0 6px; }}
.ui-hero-sub {{ color:{MUTED}; font-size:14px; max-width:660px; line-height:1.55; }}
.ui-hero-pill {{ position:absolute; top:24px; right:26px; background:{YELLOW_SOFT}; color:{YELLOW_DK}; border:1px solid {YELLOW}; border-radius:9999px; padding:6px 14px; font-size:12px; font-weight:800; white-space:nowrap; }}

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
</style>"""
