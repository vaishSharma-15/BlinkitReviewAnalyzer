"""Blinkit Discovery Copilot — the Streamlit entrypoint (`streamlit run app/rag_chatbot.py`).

Four tabs, mirroring the Stitch-designed "Discovery Engine" product (see
data/stitch_blinkit_review_discovery_engine/): Overview, Analytics, Theme
Intelligence, Insight Engine. Each tab's rendering logic lives in its own
app/tab_*.py module; this file is the nav shell + page config + theme injection.
"""
import base64
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # so `from src....` / `from app....` work under `streamlit run`

from app import live_fetch, tab_analytics, tab_copilot, tab_overview, tab_themes, ui  # noqa: E402
from app.theme import inject_theme  # noqa: E402
from app.ui import inject_ui  # noqa: E402

LOGO_PATH = ROOT / "app" / "assets" / "blinkit-logo.svg"
# Same mark, rasterised (see app/assets/README.md). The favicon has to be the PNG:
# Streamlit hands page_icon straight to the browser as the tab icon, and an SVG passed
# there is ignored — which is why the tab showed Streamlit's own logo instead.
FAVICON_PATH = ROOT / "app" / "assets" / "blinkit-logo.png"


@st.cache_data
def _logo_data_uri() -> str:
    """The real Blinkit app icon as a data: URI (see app/assets/README.md for licence).

    Inlined rather than served via st.image so it can sit inside the sidebar's
    flex header markup alongside the wordmark.
    """
    b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return f"data:image/svg+xml;base64,{b64}"


# The cart is load-bearing, not decoration: Safari drops a leading word that repeats the
# site name, and the deployed URL contains "blinkit" — so a plain "Blinkit Analyst" showed
# up in the tab strip as "Analyst". A glyph in front breaks that match.
st.set_page_config(page_title="🛒 Blinkit Analyst", page_icon=str(FAVICON_PATH), layout="wide")


def _claim_favicon():
    """Make our icon the only one on the page.

    page_icon sets <link rel="icon">, and locally that is the only icon tag there is. A
    Community Cloud deployment serves the app inside its own wrapper, which adds
    rel="mask-icon" and rel="apple-touch-icon" pointing at Streamlit's logo — and Safari
    prefers those, which is why the deployed tab kept showing a red Streamlit mark beside
    our title while Chrome showed ours.

    st.markdown strips <script>, so this runs from a zero-height components iframe and
    reaches into the parent document(s): the app frame, and the wrapper above it when the
    two are same-origin (they are — one host). Streamlit's own icon href is read first and
    reused, since its /media/ path is content-hashed and not knowable from here.

    Best-effort by design: every step is guarded, and a browser that blocks the reach-up
    simply keeps the platform's icon rather than losing the page.
    """
    components.html(
        """
        <script>
        (function () {
          const docs = [];
          try { if (window.parent && window.parent.document) docs.push(window.parent.document); } catch (e) {}
          try { if (window.top && window.top.document && !docs.includes(window.top.document)) docs.push(window.top.document); } catch (e) {}

          let href = null;
          for (const d of docs) {
            const own = d.querySelector('link[rel="shortcut icon"], link[rel="icon"]');
            if (own && own.href.indexOf('/media/') !== -1) { href = own.href; break; }
          }
          if (!href) return;

          for (const d of docs) {
            d.querySelectorAll('link[rel="mask-icon"], link[rel="apple-touch-icon"], link[rel~="icon"]')
             .forEach(function (l) { l.remove(); });
            ['icon', 'shortcut icon', 'apple-touch-icon'].forEach(function (rel) {
              const link = d.createElement('link');
              link.rel = rel;
              link.type = 'image/png';
              // Cache-buster: Safari keeps a favicon database keyed by URL and will not
              // refetch one it already has, so a browser that saw Streamlit's icon for
              // this page keeps showing it. A URL it has never seen is a new lookup.
              // Streamlit's media handler ignores the parameter (verified: same 6,176
              // bytes, same content-type, with and without it).
              link.href = href + (href.indexOf('?') === -1 ? '?' : '&') + 'v=blinkit1';
              d.head.appendChild(link);
            });
          }
        })();
        </script>
        """,
        height=0,
    )


_claim_favicon()
inject_theme()
inject_ui()

# Clean Material Symbols (via Streamlit's icon param) instead of emoji.
PAGES = {
    "Overview": (":material/dashboard:", tab_overview),
    "Analytics": (":material/bar_chart:", tab_analytics),
    "Theme Intelligence": (":material/layers:", tab_themes),
    "Insight Engine": (":material/forum:", tab_copilot),
}

if "active_page" not in st.session_state:
    st.session_state.active_page = "Overview"

with st.sidebar:
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:11px; padding: 6px 0 14px 0;">
            <img src="{_logo_data_uri()}" alt="Blinkit" width="38" height="38"
                 style="border-radius:9px;display:block;flex-shrink:0;
                        box-shadow:0 1px 3px rgba(16,24,40,0.14);" />
            <div>
                <div style="font-weight:800;letter-spacing:-0.01em;color:#16181d;font-size:14px;">Blinkit Reviews Analyzer</div>
                <div style="font-size:10px;letter-spacing:0.08em;color:#8a7c4a;text-transform:uppercase;">Voice of Customer</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for page_name, (icon, _) in PAGES.items():
        is_active = st.session_state.active_page == page_name
        if st.button(
            page_name,
            icon=icon,
            key=f"nav_{page_name}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.active_page = page_name
            st.rerun()

    # Live scrape. Its own container so the CSS can set it apart from the nav rows above,
    # which are otherwise the identical transparent secondary button. Clicking only parks
    # a flag and reruns: the fetch then runs inside render_panel() on the next pass, with
    # the button already repainted and any previous result cleared, so the panel below is
    # only ever showing the run that is actually in flight.
    with st.container(key="sb_fetch"):
        # No `help`: Streamlit's tooltip is positioned for the main area and gets clipped
        # against the sidebar's edge, so it arrived as a half-visible box over the nav.
        # The button says what it does.
        if st.button("Fetch new reviews", icon=":material/cloud_download:",
                     use_container_width=True, key="fetch_reviews"):
            st.session_state.live_fetch_run = True
            st.session_state.pop("live_fetch", None)
            st.rerun()
        live_fetch.render_panel()

    # Demo account chip, pinned to the foot of the sidebar by .sb-user-foot's
    # margin-top:auto. Not authentication — the app has no login; this stands in
    # for the signed-in user in walkthroughs.
    st.markdown(
        """
        <div class="sb-user-foot">
        <div class="sb-user">
            <div class="sb-user-av">GP</div>
            <div style="min-width:0;">
                <div class="sb-user-name">Growth PM</div>
                <div class="sb-user-role">Blinkit · India</div>
            </div>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown('<div class="ui-wrap">', unsafe_allow_html=True)
PAGES[st.session_state.active_page][1].render()
st.markdown("</div>", unsafe_allow_html=True)
