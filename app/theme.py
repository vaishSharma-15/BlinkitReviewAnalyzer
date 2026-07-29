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
# Sidebar carries a wash of the Blinkit brand yellow (#FFE141 in the official app
# icon) rather than the flat white of the Stitch source. Kept far lighter than the
# brand colour itself so 14px nav text still clears WCAG AA against it.
SIDEBAR_BG = "#ffefa8"
SIDEBAR_BG_FADE = "#fff8d6"
SIDEBAR_BORDER = "#e8cf5e"
SIDEBAR_HOVER = "#fff8d6"
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

        /* Sidebar: Blinkit-yellow gradient wash, defined edge against the main area */
        [data-testid="stSidebar"] {{
            /* Fade runs the full height, not out by 62% — stopping early left the lower
            half reading as plain white rather than a yellow panel. */
            background: linear-gradient(180deg, {SIDEBAR_BG} 0%, {SIDEBAR_BG_FADE} 100%);
            border-right: 2px solid {SIDEBAR_BORDER};
            box-shadow: 2px 0 10px rgba(16,24,40,0.05);
        }}
        [data-testid="stSidebar"] hr {{
            border-color: {SIDEBAR_BORDER};
            margin: 14px 0;
        }}
        /* Nav rows need breathing room now that the sidebar carries colour. */
        [data-testid="stSidebar"] .stButton {{ margin-bottom: 4px; }}

        /* Streamlit reserves a 78px band above the sidebar content for one collapse
        arrow, which read as a hole above the logo. Trimmed to what the arrow needs. */
        [data-testid="stSidebarHeader"] {{
            padding: 8px 14px 0 !important;
            height: auto !important;
            min-height: 0 !important;
        }}

        /* Push the account chip to the foot of the sidebar: make the sidebar's content
        column full-height, then let the chip's wrapper absorb the slack above it. */
        /* Tall enough to push the account chip to the foot, short enough that the
        sidebar never overflows into a scrollbar: Streamlit already reserves 96px of
        bottom padding below this block, and 7rem left the content ~16px too tall. */
        [data-testid="stSidebarUserContent"] {{
            padding-bottom: 1.5rem !important;
        }}
        /* Sized so the stretched block plus the flex gap below its last child still fits
        inside the sidebar. Nothing is clipped here: an earlier overflow:hidden cut the
        bottom off the account chip, and the scrollbar it was hiding came from the 96px
        of bottom padding trimmed just above, not from real overflow. */
        /* Path is spelled out from stSidebarUserContent so this hits *only* the sidebar's
        outermost block. `[data-testid="stSidebar"] ...` also matched every st.container
        with a key — the fetch panel's container inherited a 772px floor, which stretched
        the sidebar past the viewport and pushed the account chip out of sight. That looked
        like the review list scrolling the sidebar; it was this. */
        [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {{
            min-height: calc(100vh - 8rem);
        }}
        /* :has() is needed because the chip is wrapped in Streamlit's own
        stElementContainer — that wrapper, not .sb-user-foot itself, is the flex child
        that has to absorb the slack. */
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sb-user-foot) {{
            margin-top: auto;
        }}
        /* The live-scrape control is an action, not a fifth nav destination: it sits
        below the nav block with a rule above it, and unlike the transparent ghost nav
        rows it is filled, so it reads as something that *does* rather than navigates. */
        [data-testid="stSidebar"] .st-key-sb_fetch {{
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px solid {SIDEBAR_BORDER};
        }}
        [data-testid="stSidebar"] .st-key-sb_fetch [data-testid="stBaseButton-secondary"] {{
            background-color: rgba(255,255,255,0.72);
            border: 1px solid {SIDEBAR_BORDER};
            font-size: 12.5px;
            font-weight: 700;
            justify-content: center;
            text-align: center;
        }}
        [data-testid="stSidebar"] .st-key-sb_fetch [data-testid="stBaseButton-secondary"]:hover {{
            background-color: {CARD_BG};
            border-color: {ON_PRIMARY};
        }}

        /* Live-fetch panel. Every rule that sets a colour is both scoped to the sidebar
        and marked !important: the blanket `[data-testid="stSidebar"] *` rule below
        repaints all sidebar text one colour with !important, and an unscoped .lf-class
        ties it on specificity and loses on source order — which is what painted the
        first draft of the done chip black-on-black. */
        [data-testid="stSidebar"] .lf-log {{ margin: 10px 0 2px; }}
        [data-testid="stSidebar"] .lf-step {{
            display: flex; align-items: flex-start; gap: 7px;
            font-size: 11px; line-height: 1.45; margin-bottom: 5px;
            color: {TEXT_MAIN} !important;
        }}
        [data-testid="stSidebar"] .lf-step i {{
            width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; margin-top: 5px;
            background: {ON_PRIMARY};
            animation: lf-pulse 1s ease-in-out infinite;
        }}
        /* Finished steps stop pulsing and recede — the one still animating is the one
        the scrape is actually on. */
        [data-testid="stSidebar"] .lf-step.done {{ color: #6f6440 !important; }}
        [data-testid="stSidebar"] .lf-step.done i {{ background: #b9a94e; animation: none; }}
        @keyframes lf-pulse {{ 0%, 100% {{ opacity: 0.25; }} 50% {{ opacity: 1; }} }}
        @media (prefers-reduced-motion: reduce) {{ [data-testid="stSidebar"] .lf-step i {{ animation: none; }} }}

        [data-testid="stSidebar"] .lf-chip {{
            display: block; margin: 10px 0 8px; padding: 7px 10px; border-radius: 8px;
            background: {ON_PRIMARY}; color: {PRIMARY_YELLOW} !important;
            font-size: 11.5px; font-weight: 700;
        }}
        [data-testid="stSidebar"] .lf-chip.err {{ background: #fee2e2; color: #991b1b !important; }}
        [data-testid="stSidebar"] .lf-chip-sub {{ float: right; font-weight: 500; opacity: 0.7; color: inherit !important; }}
        [data-testid="stSidebar"] .lf-note {{
            font-size: 10px; letter-spacing: 0.04em; text-transform: uppercase;
            color: #6f6440 !important; margin-bottom: 7px;
        }}
        /* The review list is the only thing here that scrolls. It has to be capped
        somewhere: uncapped, eight cards push the account chip past the bottom of the
        sidebar, and then the *sidebar* scrolls to reach it — which is how the chip
        disappeared. Keeping the overflow inside this box means the panel occupies fixed
        vertical space no matter how many reviews come back. */
        [data-testid="stSidebar"] .lf-feed {{
            max-height: 230px; overflow-y: auto; padding-right: 3px;
            /* Hairline scrollbar — the default macOS overlay bar sits on top of the
            cards' right edge and reads as a stray border. */
            scrollbar-width: thin; scrollbar-color: {SIDEBAR_BORDER} transparent;
        }}

        /* The reviews, folded shut until asked for. */
        [data-testid="stSidebar"] .lf-fold {{ margin-bottom: 4px; }}
        [data-testid="stSidebar"] .lf-fold summary {{
            cursor: pointer; list-style: none; display: inline-block;
            font-size: 11px; font-weight: 700; letter-spacing: 0.04em;
            text-transform: uppercase; color: #6f6440 !important; padding: 4px 0 8px;
        }}
        [data-testid="stSidebar"] .lf-fold summary::-webkit-details-marker {{ display: none; }}
        [data-testid="stSidebar"] .lf-fold summary::after {{ content: " ▾"; }}
        [data-testid="stSidebar"] .lf-fold[open] summary::after {{ content: " ▴"; }}
        [data-testid="stSidebar"] .lf-fold summary:hover {{ color: {ON_PRIMARY} !important; }}

        /* "Open review ↗" — a whole clickable card is invisible without it. */
        [data-testid="stSidebar"] .lf-card-link {{
            font-size: 10px; font-weight: 700; letter-spacing: 0.03em;
            color: #8a6d1f !important; margin-top: 6px;
        }}
        [data-testid="stSidebar"] .lf-card:hover .lf-card-link {{ color: {ON_PRIMARY} !important; }}

        /* The step trace, shown only while a fetch is running. */
        [data-testid="stSidebar"] .lf-card {{
            display: block; text-decoration: none !important;
            background: rgba(255,255,255,0.72);
            border: 1px solid {SIDEBAR_BORDER}; border-radius: 9px;
            padding: 8px 10px; margin-bottom: 7px;
        }}
        [data-testid="stSidebar"] .lf-card:hover {{ background: {CARD_BG}; border-color: {ON_PRIMARY}; }}
        [data-testid="stSidebar"] .lf-card-head {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }}
        [data-testid="stSidebar"] .lf-stars {{ color: #b8860b !important; font-size: 11px; letter-spacing: 1px; }}
        [data-testid="stSidebar"] .lf-date {{ color: #6f6440 !important; font-size: 10px; }}
        [data-testid="stSidebar"] .lf-card-text {{ color: {TEXT_MAIN} !important; font-size: 11.5px; line-height: 1.45; }}

        /* Clear chat, now on the Insight Engine page itself: a quiet outline button, so
        it never competes with the yellow primary buttons around the chat.
        Selector is `button`, not `.stButton > button`: a button carrying a `help`
        tooltip is wrapped in Streamlit's stTooltipHoverTarget, so it is no longer the
        direct child .stButton expects. !important because the solid-yellow .stButton
        rule below ties on specificity and wins on source order. */
        /* Sticky, because a long conversation scrolls it off the top and clearing the
        chat is exactly what you want when there is a lot of it.

        The rule is on the columns *row*, not on the button: a sticky element can only
        travel within its own parent, and the button's column is no taller than the
        button, so sticking it there moved it nowhere. The row is a direct child of the
        tall block inside the scroll container, so it can ride the full length.

        pointer-events are off for the row and back on for the button — the row spans the
        full width, and as a solid strip floating over the answers it would have
        swallowed every click and text selection behind it. */
        /* Parked in the page's right margin, clear of the answer column.
        Sticky inside the column put it half over the card's right edge — the column ends
        at the page padding but the answer card stops short of it, so "right-aligned to
        the column" and "outside the card" are not the same place. Fixed to the viewport
        is, and it also means the button no longer travels at all.
        Its row is emptied of layout so the conversation starts where it used to. */
        [data-testid="stHorizontalBlock"]:has(.st-key-cp_clear) {{
            height: 0;
            overflow: visible;
            pointer-events: none;
        }}
        .st-key-cp_clear {{
            position: fixed;
            /* Clears Streamlit's 60px header and its ⋮ menu. */
            top: 74px;
            right: 26px;
            z-index: 20;
            margin: 0;
            pointer-events: auto;
            /* Without this the fixed box keeps the column's width and the button sits
            left-aligned inside it — 60px further left than `right: 26px` implies, i.e.
            back over the card. */
            width: max-content;
        }}
        /* max-content still resolves to the column's width here, so the button is pushed
        to the right edge of that box explicitly. */
        .st-key-cp_clear .stButton {{ display: flex; justify-content: flex-end; }}
        /* Narrow windows leave no margin to sit in, so the label goes and the icon
        stays — 40px fits a gutter that 125px cannot. */
        @media (max-width: 1360px) {{
            .st-key-cp_clear button [data-testid="stMarkdownContainer"] {{ display: none; }}
            .st-key-cp_clear button {{ padding: 8px 10px !important; }}
        }}
        .st-key-cp_clear button {{
            background-color: {CARD_BG} !important;
            border: 1px solid {CARD_BORDER_HOVER} !important;
            border-radius: 9px !important;
            color: {TEXT_MUTED} !important;
            font-size: 12px;
            font-weight: 600;
            padding: 7px 14px !important;
            box-shadow: 0 1px 2px rgba(16,24,40,0.04);
        }}
        .st-key-cp_clear button:hover {{
            border-color: {ON_PRIMARY} !important;
            color: {TEXT_MAIN} !important;
            box-shadow: 0 2px 6px rgba(16,24,40,0.09);
        }}
        /* Yellow rule above the account chip — the st.divider() that used to sit here
        went away when the chip was pinned to the foot. */
        .sb-user-foot {{
            padding-top: 18px;
            border-top: 1px solid {SIDEBAR_BORDER};
            margin-top: 18px;
        }}
        .sb-user {{
            display: flex; align-items: center; gap: 10px;
            background: rgba(255,255,255,0.72);
            border: 1px solid {SIDEBAR_BORDER};
            border-radius: 10px; padding: 9px 11px;
        }}
        /* Selector is scoped to the sidebar so it outranks the blanket
        `[data-testid="stSidebar"] *` colour rule above — an unscoped `.sb-user-av`
        ties on specificity, loses on source order, and paints the initials
        black on a black circle. */
        [data-testid="stSidebar"] .sb-user-av {{
            width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
            background: {ON_PRIMARY}; color: {PRIMARY_YELLOW} !important;
            display: flex; align-items: center; justify-content: center;
            font-size: 12px; font-weight: 800; letter-spacing: 0.02em;
        }}
        .sb-user-name {{ color: {TEXT_MAIN}; font-size: 13px; font-weight: 700; line-height: 1.2; }}
        .sb-user-role {{ color: #6f6440; font-size: 10.5px; letter-spacing: 0.04em; text-transform: uppercase; }}
        [data-testid="stSidebar"] * {{
            color: {TEXT_MAIN} !important;
        }}
        /* Warmer muted tone — plain grey reads as dirty against the yellow wash. */
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {{
            color: #6f6440 !important;
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
            background-color: {SIDEBAR_HOVER};
            color: {TEXT_MAIN} !important;
        }}
        /* Active nav row is now white-on-yellow: the old pale-yellow fill would
        disappear against the yellow sidebar. */
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {{
            background-color: {CARD_BG};
            color: {TEXT_MAIN} !important;
            border: none;
            border-left: 3px solid {ON_PRIMARY};
            box-shadow: 0 1px 2px rgba(16,24,40,0.10);
            border-radius: 8px;
            text-align: left;
            justify-content: flex-start;
            font-weight: 700;
        }}
        /* Keep the active row white on hover — the global yellow .stButton hover
        rule would otherwise repaint it solid brand yellow. */
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover,
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:focus,
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:active {{
            background-color: {CARD_BG} !important;
            border-left: 3px solid {ON_PRIMARY} !important;
            color: {TEXT_MAIN} !important;
        }}
        [data-testid="stSidebar"] .stButton > button {{
            width: 100%;
        }}

        /* Main-area buttons: Streamlit's per-widget emotion styles outrank the plain
        `.stButton > button` rule above once a button has ever been disabled, leaving it
        white. Scoping to the main block wins the specificity fight; :not(:disabled)
        keeps Streamlit's faded disabled state as a real affordance. */
        [data-testid="stMainBlockContainer"] [data-testid="stButton"] button:not(:disabled) {{
            background-color: {PRIMARY_YELLOW};
            border: 1px solid {PRIMARY_YELLOW_DIM};
            color: {ON_PRIMARY};
            font-weight: 600;
        }}
        [data-testid="stMainBlockContainer"] [data-testid="stButton"] button:not(:disabled):hover {{
            background-color: {PRIMARY_YELLOW_DIM};
            border-color: {PRIMARY_YELLOW_DIM};
        }}

        /* Text inputs: Streamlit's 16px text on a 22.4px line-height sits in a 22px
        content box with overflow:hidden, which shaves the descenders off "g/y/p".
        Smaller text plus real vertical padding gives the glyphs room. */
        [data-testid="stTextInput"] input {{
            font-size: 14px !important;
            line-height: 1.5 !important;
            padding-top: 10px !important;
            padding-bottom: 10px !important;
            height: auto !important;
            background-color: transparent !important;
            /* Magnifier drawn in the field itself — Streamlit's text_input has no icon
            slot, and without it the box reads as an empty panel rather than a search. */
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='17' height='17' viewBox='0 0 24 24' fill='none' stroke='%235f5e5e' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><circle cx='11' cy='11' r='8'/><path d='m21 21-4.3-4.3'/></svg>") !important;
            background-repeat: no-repeat !important;
            background-position: 13px center !important;
            padding-left: 40px !important;
        }}
        /* The field was a grey box with a same-colour border on a near-grey page. White
        fill plus a real border makes it read as an input at a glance. */
        [data-testid="stTextInput"] div[data-baseweb="input"],
        [data-testid="stTextInput"] div[data-baseweb="base-input"] {{
            background-color: {CARD_BG} !important;
            border: 1.5px solid {CARD_BORDER_HOVER} !important;
            border-radius: 9px !important;
            box-shadow: 0 1px 2px rgba(16,24,40,0.05);
        }}
        [data-testid="stTextInput"] div[data-baseweb="input"]:hover,
        [data-testid="stTextInput"] div[data-baseweb="base-input"]:hover {{
            border-color: {PRIMARY_YELLOW_DIM} !important;
        }}
        [data-testid="stTextInput"] input::placeholder {{
            color: #6b7280 !important;
            opacity: 1 !important;
        }}
        /* Selects get the same white fill and edge, so the filter row reads as one
        control group rather than a white box beside two grey ones. */
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
            background-color: {CARD_BG} !important;
            border: 1.5px solid {CARD_BORDER_HOVER} !important;
            border-radius: 9px !important;
            box-shadow: 0 1px 2px rgba(16,24,40,0.05);
        }}
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {{
            border-color: {PRIMARY_YELLOW_DIM} !important;
        }}
        /* Focus ring in brand yellow instead of Streamlit's default red. */
        [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
        [data-testid="stTextInput"] div[data-baseweb="base-input"]:focus-within {{
            border-color: {PRIMARY_YELLOW} !important;
            box-shadow: 0 0 0 2px rgba(249, 213, 7, 0.38) !important;
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
