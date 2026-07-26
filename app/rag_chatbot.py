"""Blinkit Discovery Copilot — the Streamlit entrypoint (`streamlit run app/rag_chatbot.py`).

Four tabs, mirroring the Stitch-designed "Discovery Engine" product (see
data/stitch_blinkit_review_discovery_engine/): Overview, Analytics, Theme
Intelligence, Insight Engine. Each tab's rendering logic lives in its own
app/tab_*.py module; this file is the nav shell + page config + theme injection.
"""
import base64
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # so `from src....` / `from app....` work under `streamlit run`

from app import tab_analytics, tab_copilot, tab_overview, tab_themes, ui  # noqa: E402
from app.theme import inject_theme  # noqa: E402
from app.ui import inject_ui  # noqa: E402

LOGO_PATH = ROOT / "app" / "assets" / "blinkit-logo.svg"


@st.cache_data
def _logo_data_uri() -> str:
    """The real Blinkit app icon as a data: URI (see app/assets/README.md for licence).

    Inlined rather than served via st.image so it can sit inside the sidebar's
    flex header markup alongside the wordmark.
    """
    b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return f"data:image/svg+xml;base64,{b64}"


st.set_page_config(page_title="Blinkit Reviews Analyzer", page_icon=str(LOGO_PATH), layout="wide")
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

    st.divider()
    manifest_path = ROOT / "data" / "index" / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        st.caption(f"Evidence indexed: {manifest['n_evidence']}")
        st.caption(f"Themes indexed: {manifest['n_themes']}")

st.markdown('<div class="ui-wrap">', unsafe_allow_html=True)
PAGES[st.session_state.active_page][1].render()
st.markdown("</div>", unsafe_allow_html=True)
