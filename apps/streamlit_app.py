"""ARIS V3 — React shell on Streamlit Cloud.

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

home = st.Page("pages/00_Home.py", title="Home", url_path="home", default=True)
replay = st.Page("pages/04_Replay.py", title="Replay", url_path="replay")
live = st.Page("pages/03_Live.py", title="Live", url_path="live")
standings = st.Page("pages/05_Standings.py", title="Standings", url_path="standings")
calendar = st.Page("pages/06_Calendar.py", title="Calendar", url_path="calendar")

try:
    pg = st.navigation([home, replay, live, standings, calendar], position="hidden")
except TypeError:
    pg = st.navigation([home, replay, live, standings, calendar])
pg.run()
