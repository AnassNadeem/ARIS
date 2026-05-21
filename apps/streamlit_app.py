"""ARIS — F1 lap-time dashboard (Phase 2, Week 3 Day 4 skeleton).

Pick a season, a race, and a driver; see that driver's lap-time trace. Data
comes from the Postgres populated by `aris.io.ingest`, read through the
raw-SQL helpers in `aris.io.db`.

Run locally:
    streamlit run apps/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# apps/ sits beside src/; make `aris` importable without a package install.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

import streamlit as st  # noqa: E402

from aris.io import db  # noqa: E402

st.set_page_config(page_title="ARIS — lap times", page_icon="🏁", layout="wide")
st.title("🏁 ARIS — F1 lap-time explorer")

seasons = db.fetch_seasons()
if not seasons:
    st.warning("No sessions ingested yet — run `python scripts/ingest_season.py 2024`.")
    st.stop()

col_season, col_race, col_driver = st.columns(3)

with col_season:
    season = st.selectbox("Season", seasons)

races = db.fetch_races(season).set_index("session_id")
if races.empty:
    st.warning(f"No races ingested for {season}.")
    st.stop()

with col_race:
    session_id = st.selectbox(
        "Race",
        races.index.tolist(),
        format_func=lambda sid: f"R{races.at[sid, 'round_no']} — {races.at[sid, 'country']}",
    )

drivers = db.fetch_drivers(session_id).set_index("driver_id")
if drivers.empty:
    st.warning("No laps ingested for this race.")
    st.stop()

with col_driver:
    driver_id = st.selectbox(
        "Driver",
        drivers.index.tolist(),
        format_func=lambda did: f"{drivers.at[did, 'code']} — {drivers.at[did, 'full_name']}",
    )

# lap_time_s is NUMERIC in Postgres and comes back as Decimal — cast to float
# so the chart (and any later arithmetic) gets a plain numeric column.
laps = db.fetch_laps(session_id, driver_id)
timed = laps.dropna(subset=["lap_time_s"]).copy()
timed["lap_time_s"] = timed["lap_time_s"].astype(float)

if timed.empty:
    st.info("This driver has no timed laps in this race.")
    st.stop()

st.line_chart(timed, x="lap_number", y="lap_time_s")
