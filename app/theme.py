"""'Luminous Data Systems' theme — ported from the Stitch design at
data/stitch_blinkit_review_discovery_engine/ (see luminous_data_systems/DESIGN.md for
the source design tokens) onto Streamlit's native widget set.

Streamlit can't render arbitrary Tailwind HTML directly, so this module does two things:
  1. injects one global CSS block (Google Font Inter, color tokens, dark sidebar, yellow
     underline tabs, card/metric/expander restyling) targeting Streamlit's own
     data-testid hooks, which is the only stable way to restyle built-in widgets.
  2. exposes small HTML-snippet helpers (card_start/card_end, badge, quote_block,
     section_label) for the handful of custom card layouts (KPI tiles, confidence
     chips, evidence quotes) that don't map onto any built-in Streamlit widget.

The "leaky div" pattern used by card_start()/card_end() (opening a <div> in one
st.markdown call, closing it in a later one, with real widgets in between) works
because Streamlit inserts each markdown call's HTML into one continuous DOM — it's a
common, if inelegant, way to wrap native widgets in custom containers.
"""
import textwrap

import streamlit as st

# Literal hex values below are taken from the Stitch-exported code.html files, not the
# auto-generated Material tokens in DESIGN.md — the two occasionally disagree (e.g. card
# border is the literal #E2E8F0 hardcoded in the CSS, not the `outline-variant` token),
# and the exported code is what actually rendered in the reference screenshots.
BACKGROUND = "#f7f9fb"
SIDEBAR_BG = "#ffffff"
CARD_BG = "#ffffff"
CARD_BORDER = "#E2E8F0"
CARD_BORDER_HOVER = "#CBD5E1"
PRIMARY_YELLOW = "#F9D507"
PRIMARY_YELLOW_DIM = "#e6c500"
PRIMARY_YELLOW_SOFT = "#fef6dc"
ON_PRIMARY = "#191c1e"
TEXT_MAIN = "#191c1e"
TEXT_MUTED = "#5f5e5e"

SOURCE_COLORS = {
    "play": ("#dbeafe", "#1e40af"),
    "appstore": ("#ede9fe", "#5b21b6"),
    "reddit": ("#ffedd5", "#9a3412"),
    "youtube": ("#fee2e2", "#991b1b"),
    "forum": ("#dcfce7", "#166534"),
    "product_review": ("#fce7f3", "#9d174d"),
    "qcomm_comparison": ("#fef9c3", "#854d0e"),
}

BADGE_COLORS = {
    "high": ("#dcfce7", "#166534"),
    "success": ("#dcfce7", "#166534"),
    "ok": ("#dcfce7", "#166534"),
    "medium": ("#fef9c3", "#854d0e"),
    "single_source": ("#fef9c3", "#854d0e"),
    "warning": ("#fef9c3", "#854d0e"),
    "low": ("#fee2e2", "#991b1b"),
    "error": ("#fee2e2", "#991b1b"),
    "blocked": ("#fee2e2", "#991b1b"),
}


def inject_theme():
    css = textwrap.dedent(f"""\
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
        <style>
        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
        .stApp {{ background-color: {BACKGROUND}; }}

        /* Sidebar: light, hairline divider from the main area */
        [data-testid="stSidebar"] {{
            background-color: {SIDEBAR_BG};
            border-right: 1px solid {CARD_BORDER};
        }}
        [data-testid="stSidebar"] * {{
            color: {TEXT_MAIN} !important;
        }}
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {{
            color: {TEXT_MUTED} !important;
        }}
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
            color: {TEXT_MAIN} !important;
        }}

        /* Tabs: underline style, yellow active indicator */
        button[data-baseweb="tab"] {{
            font-weight: 600;
            font-size: 14px;
            color: {TEXT_MUTED};
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {TEXT_MAIN} !important;
            border-bottom: 2px solid {PRIMARY_YELLOW} !important;
        }}
        [data-baseweb="tab-highlight"] {{
            background-color: {PRIMARY_YELLOW} !important;
        }}

        /* Buttons: solid yellow, black text */
        .stButton > button {{
            background-color: {PRIMARY_YELLOW};
            color: {ON_PRIMARY};
            border: 1px solid {PRIMARY_YELLOW_DIM};
            border-radius: 4px;
            font-weight: 600;
        }}
        .stButton > button:hover {{
            background-color: {PRIMARY_YELLOW_DIM};
            border-color: {PRIMARY_YELLOW_DIM};
            color: {ON_PRIMARY};
        }}

        /* Sidebar nav list: secondary (inactive) items look like dark ghost nav rows;
        primary (active) item gets the yellow left-border + tinted background from the
        Stitch design's "Active Tab" treatment, not a solid yellow button. */
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{
            background-color: transparent;
            color: #3f4753 !important;
            border: none;
            border-radius: 8px;
            text-align: left;
            justify-content: flex-start;
            font-weight: 500;
        }}
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {{
            background-color: #f1f3f5;
            color: {TEXT_MAIN} !important;
        }}
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {{
            background-color: {PRIMARY_YELLOW_SOFT};
            color: {TEXT_MAIN} !important;
            border: none;
            border-left: 3px solid {PRIMARY_YELLOW};
            border-radius: 8px;
            text-align: left;
            justify-content: flex-start;
            font-weight: 700;
        }}
        [data-testid="stSidebar"] .stButton > button {{
            width: 100%;
        }}

        /* Metrics: uppercase label, tight card look */
        [data-testid="stMetric"] {{
            background-color: {CARD_BG};
            border: 1px solid {CARD_BORDER};
            border-radius: 8px;
            padding: 16px;
        }}
        [data-testid="stMetricLabel"] {{
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 11px;
            color: {TEXT_MUTED};
        }}
        [data-testid="stMetricValue"] {{
            font-weight: 800;
            color: {TEXT_MAIN};
        }}

        /* Expanders: card look */
        [data-testid="stExpander"] {{
            border: 1px solid {CARD_BORDER};
            border-radius: 8px;
            background-color: {CARD_BG};
        }}

        /* Bordered containers (st.container(border=True)): card look */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-color: {CARD_BORDER} !important;
            border-radius: 8px !important;
        }}

        /* Custom card wrapper for card_start()/card_end() */
        .dcard {{
            background-color: {CARD_BG};
            border: 1px solid {CARD_BORDER};
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 16px;
        }}
        .dcard-header {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {TEXT_MUTED};
            margin-bottom: 12px;
        }}
        .dquote {{
            border-left: 2px solid {PRIMARY_YELLOW_DIM};
            padding-left: 12px;
            margin: 8px 0;
            font-style: italic;
            color: {TEXT_MAIN};
        }}
        .dbadge {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        </style>
        """)
    # A blank line inside a raw-HTML markdown block ends the HTML passthrough early —
    # everything after it gets rendered as literal escaped text instead of applied CSS.
    # Strip blank lines so the whole block stays one contiguous HTML block.
    css = "\n".join(line for line in css.splitlines() if line.strip())
    st.markdown(css, unsafe_allow_html=True)


def card_start(header: str = None):
    html = '<div class="dcard">'
    if header:
        html += f'<div class="dcard-header">{header}</div>'
    st.markdown(html, unsafe_allow_html=True)


def card_end():
    st.markdown("</div>", unsafe_allow_html=True)


def badge(text: str, kind: str = "medium") -> str:
    bg, fg = BADGE_COLORS.get(kind, BADGE_COLORS["medium"])
    return f'<span class="dbadge" style="background-color:{bg};color:{fg};">{text}</span>'


def quote_block(text: str, source: str = None) -> str:
    html = f'<div class="dquote">"{text}"'
    if source:
        html += f'<div style="font-style:normal;font-size:12px;color:{TEXT_MUTED};margin-top:4px;">— {source}</div>'
    html += "</div>"
    return html


def source_badge(source: str) -> str:
    bg, fg = SOURCE_COLORS.get(source, ("#e2e8f0", "#334155"))
    label = source.replace("_", " ").title()
    return f'<span class="dbadge" style="background-color:{bg};color:{fg};">{label}</span>'


def confidence_badge_kind(confidence: str) -> str:
    return {"high": "high", "medium": "medium", "single_source": "single_source", "low": "low"}.get(confidence, "medium")
