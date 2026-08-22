"""ARIS entrypoint — landing + Strategy + lap explorer.

Run locally:
    streamlit run apps/streamlit_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402

try:
    for _key in (
        "ARIS_DB_URL",
        "OPENF1_USERNAME",
        "OPENF1_PASSWORD",
        "OPENF1_API_KEY",
        "OPENF1_TOKEN",
        "OPENF1_ACCESS_TOKEN",
        "OPENF1_KEY",
    ):
        if _key in st.secrets:
            os.environ.setdefault(_key, str(st.secrets[_key]))
except (FileNotFoundError, KeyError):
    pass

st.set_page_config(page_title="ARIS", page_icon="🏁", layout="wide")

live = st.Page(
    "pages/03_Live.py",
    title="Live",
    icon="🔴",
    url_path="Live",
    default=True,
)
home = st.Page("pages/00_Home.py", title="Home", icon="🏁")
strategy = st.Page(
    "pages/01_Strategy.py",
    title="Strategy",
    icon="📡",
    url_path="Strategy",
)
explorer = st.Page(
    "pages/02_Lap_Explorer.py",
    title="Lap explorer",
    icon="📈",
    url_path="Lap_explorer",
)

# Explicit links — client.showSidebarNavigation is off so pages/ is not auto-listed.
with st.sidebar:
    st.page_link(live, label="Live", icon="🔴")
    st.page_link(home, label="Home", icon="🏁")
    st.page_link(strategy, label="Strategy", icon="📡")
    st.page_link(explorer, label="Lap explorer", icon="📈")

pg = st.navigation([live, home, strategy, explorer])
pg.run()
