"""Blinkit Discovery Copilot — the Streamlit entrypoint (`streamlit run app/rag_chatbot.py`).

Four tabs, mirroring the Stitch-designed "Discovery Engine" product (see
data/stitch_blinkit_review_discovery_engine/): Overview, Analytics, Theme
Intelligence, Discovery Copilot. Each tab's rendering logic lives in its own
app/tab_*.py module; this file is the nav shell + page config + theme injection.
"""
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # so `from src....` / `from app....` work under `streamlit run`

from app import tab_analytics, tab_copilot, tab_overview, tab_themes  # noqa: E402
from app.theme import inject_theme  # noqa: E402

st.set_page_config(page_title="Discovery Engine", page_icon="🔍", layout="wide")
inject_theme()

PAGES = {
    "Overview": (" 📊", tab_overview),
    "Analytics": (" 📈", tab_analytics),
    "Theme Intelligence": (" 🧭", tab_themes),
    "Discovery Copilot": (" 💬", tab_copilot),
}

if "active_page" not in st.session_state:
    st.session_state.active_page = "Overview"

with st.sidebar:
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:12px; padding: 8px 0 16px 0;">
            <div style="width:40px;height:40px;background:#F9D507;border-radius:6px;
                        display:flex;align-items:center;justify-content:center;font-size:20px;">🔍</div>
            <div>
                <div style="font-weight:800;letter-spacing:-0.02em;color:#F9D507;text-transform:uppercase;">Discovery Engine</div>
                <div style="font-size:10px;letter-spacing:0.1em;color:#c8c6c5;text-transform:uppercase;">Blinkit Research Suite</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for page_name, (icon, _) in PAGES.items():
        is_active = st.session_state.active_page == page_name
        if st.button(
            f"{icon}  {page_name}",
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
    st.divider()
    st.caption(
        "Partial, in-progress corpus — some records are still pending enrichment "
        "due to the shared LLM daily quota. See Analytics for the live funnel."
    )

st.markdown("## Discovery Engine")
st.caption("Why Blinkit users stay inside familiar shopping categories — evidence-backed, not model priors.")
st.markdown(f"### {st.session_state.active_page}")

PAGES[st.session_state.active_page][1].render()
