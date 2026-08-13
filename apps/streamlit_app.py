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
    if "ARIS_DB_URL" in st.secrets:
        os.environ.setdefault("ARIS_DB_URL", st.secrets["ARIS_DB_URL"])
except (FileNotFoundError, KeyError):
    pass

st.set_page_config(page_title="ARIS", page_icon="🏁", layout="wide")

home = st.Page("pages/00_Home.py", title="Home", icon="🏁", default=True)
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
    st.page_link(home, label="Home", icon="🏁")
    st.page_link(strategy, label="Strategy", icon="📡")
    st.page_link(explorer, label="Lap explorer", icon="📈")

pg = st.navigation([home, strategy, explorer])
pg.run()
