"""ARIS Strategy page — replay snapshot + overrides → top-3 recommendations + narration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))

import streamlit as st

try:
    if "ARIS_DB_URL" in st.secrets:
        os.environ.setdefault("ARIS_DB_URL", st.secrets["ARIS_DB_URL"])
except (FileNotFoundError, KeyError):
    pass

from aris.io import db
from aris.narrate import narrate_result
from aris.recommend import recommend
from aris.state import RaceStateOverrides, build_race_state

st.title("ARIS — Race Strategy")
st.caption(
    "Replay a historical lap snapshot, optionally override conditions, and get "
    "top-3 pit/stay-out recommendations with a narrated radio call."
)

with st.sidebar:
    st.markdown("[← Lap explorer](streamlit_app)")

try:
    seasons = db.fetch_seasons()
except RuntimeError as exc:
    st.error(f"Database not configured: {exc}")
    st.stop()

if not seasons:
    st.warning("No sessions ingested — run `python scripts/ingest_season.py 2024`.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
with col1:
    season = st.selectbox("Season", seasons, key="strat_season")
races = db.fetch_races(season).set_index("session_id")
if races.empty:
    st.warning(f"No races for {season}.")
    st.stop()

with col2:
    session_id = st.selectbox(
        "Race",
        races.index.tolist(),
        format_func=lambda sid: f"R{races.at[sid, 'round_no']} — {races.at[sid, 'country']}",
        key="strat_race",
    )
drivers = db.fetch_drivers(session_id).set_index("driver_id")
if drivers.empty:
    st.warning("No drivers for this race.")
    st.stop()

with col3:
    driver_id = st.selectbox(
        "Driver",
        drivers.index.tolist(),
        format_func=lambda did: f"{drivers.at[did, 'code']} — {drivers.at[did, 'full_name']}",
        key="strat_driver",
    )

laps_df = db.fetch_laps(session_id, driver_id)
lap_numbers = laps_df["lap_number"].tolist() if not laps_df.empty else [1]
with col4:
    lap_number = st.selectbox("Replay lap", lap_numbers, key="strat_lap")

with st.expander("Manual overrides (optional)"):
    o_col1, o_col2, o_col3 = st.columns(3)
    with o_col1:
        override_compound = st.selectbox(
            "Compound",
            ["(none)", "SOFT", "MEDIUM", "HARD"],
            key="strat_compound",
        )
    with o_col2:
        override_tyre_life = st.number_input(
            "Tyre life (0 = auto)", min_value=0, value=0, key="strat_tyre_life"
        )
    with o_col3:
        override_fuel = st.number_input(
            "Fuel kg (0 = auto)", min_value=0.0, value=0.0, key="strat_fuel"
        )
    override_pit_compound = st.selectbox(
        "Pit compound", ["HARD", "MEDIUM"], key="strat_pit_compound"
    )
    use_llm = st.toggle("Use Ollama narration", value=False, key="strat_llm")

if st.button("Get Strategy", type="primary"):
    overrides = RaceStateOverrides()
    if override_compound != "(none)":
        overrides.compound = override_compound
    if override_tyre_life > 0:
        overrides.tyre_life = int(override_tyre_life)
    if override_fuel > 0:
        overrides.fuel_kg = float(override_fuel)
    overrides.pit_compound = override_pit_compound

    state = build_race_state(session_id, driver_id, lap_number, overrides=overrides)
    result = recommend(state, top_k=3, mc_draws=100)
    narration = narrate_result(result, use_llm=use_llm)

    st.subheader("Radio call")
    st.info(narration)

    st.subheader("Top recommendations")
    for rec in result.recommendations:
        with st.container(border=True):
            st.markdown(f"**#{rec.rank}** — {rec.label}")
            st.caption(
                f"Delta vs stay out: **{rec.delta_vs_stay_out_s:+.2f}s** · "
                f"sigma {rec.confidence_std_s:.2f}s · {rec.evidence}"
            )

    with st.expander("Raw JSON"):
        st.json(result.model_dump(mode="json"))
