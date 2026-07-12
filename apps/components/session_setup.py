"""Session setup — team / driver / race selectors."""

from __future__ import annotations

import streamlit as st

from aris.io import db


def render_setup() -> dict | None:
    seasons = db.fetch_seasons()
    if not seasons:
        st.warning("No sessions ingested.")
        return None

    default_year = 2025 if 2025 in seasons else seasons[0]
    year = st.selectbox("Season", seasons, index=seasons.index(default_year))

    races = db.fetch_races(year).set_index("session_id")
    if races.empty:
        st.warning(f"No races for {year}.")
        return None

    default_idx = 0
    for i, sid in enumerate(races.index):
        if "bahrain" in str(races.at[sid, "country"]).lower():
            default_idx = i
            break

    session_id = st.selectbox(
        "Race",
        races.index.tolist(),
        index=default_idx,
        format_func=lambda sid: f"R{races.at[sid, 'round_no']} — {races.at[sid, 'country']}",
    )

    teams = db.fetch_teams(int(session_id))
    if not teams:
        st.warning("No teams found.")
        return None

    team = st.selectbox("Team", teams)
    drivers = db.fetch_drivers_by_team(int(session_id), team).set_index("driver_id")
    if drivers.empty:
        st.warning("No drivers for team.")
        return None

    driver_id = st.selectbox(
        "Driver",
        drivers.index.tolist(),
        format_func=lambda did: f"{drivers.at[did, 'code']} — {drivers.at[did, 'full_name']}",
    )

    return {
        "year": year,
        "session_id": int(session_id),
        "round_no": int(races.at[session_id, "round_no"]),
        "country": str(races.at[session_id, "country"]),
        "team": team,
        "driver_id": int(driver_id),
        "driver_code": str(drivers.at[driver_id, "code"]),
        "driver_name": str(drivers.at[driver_id, "full_name"]),
    }
