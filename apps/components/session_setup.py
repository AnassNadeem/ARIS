"""Session setup — team / driver / race selectors."""

from __future__ import annotations

import streamlit as st

from apps.theme import empty_state
from aris.io import db
from aris.ui_text import PREFERRED_DRIVER_CODES


def _default_race_index(races) -> int:
    default_idx = 0
    bahrain_idx = 0
    for i, sid in enumerate(races.index):
        country = str(races.at[sid, "country"]).lower()
        if "nether" in country:
            return i
        if "bahrain" in country:
            bahrain_idx = i
    return bahrain_idx if bahrain_idx else default_idx


def _default_team_index(teams: list[str], session_id: int) -> int:
    all_drv = db.fetch_drivers(session_id)
    if all_drv.empty:
        return 0
    for code in PREFERRED_DRIVER_CODES:
        hit = all_drv[all_drv["code"] == code]
        if hit.empty:
            continue
        team = str(hit.iloc[0].get("team") or "")
        if team in teams:
            return teams.index(team)
    return 0


def render_setup() -> dict | None:
    seasons = db.fetch_seasons()
    if not seasons:
        empty_state(
            "No sessions ingested",
            "Run the FastF1 ingest against Postgres, then refresh.",
        )
        return None

    default_year = 2025 if 2025 in seasons else seasons[0]
    year = st.selectbox("Season", seasons, index=seasons.index(default_year))

    races = db.fetch_races(year).set_index("session_id")
    if races.empty:
        empty_state(
            f"No races for {year}",
            f"Ingest that season, then refresh. Race-only data is enough to start a replay.",
        )
        return None

    session_id = st.selectbox(
        "Race",
        races.index.tolist(),
        index=_default_race_index(races),
        format_func=lambda sid: f"R{races.at[sid, 'round_no']} — {races.at[sid, 'country']}",
    )

    teams = db.fetch_teams(int(session_id))
    if not teams:
        empty_state("No teams found", "This session has no drivers with laps.")
        return None

    team = st.selectbox(
        "Team",
        teams,
        index=_default_team_index(teams, int(session_id)),
    )
    drivers = db.fetch_drivers_by_team(int(session_id), team).set_index("driver_id")
    if drivers.empty:
        empty_state("No drivers for team", "Pick another team.")
        return None

    preferred_idx = 0
    codes = list(drivers["code"])
    for code in PREFERRED_DRIVER_CODES:
        if code in codes:
            preferred_idx = codes.index(code)
            break

    driver_id = st.selectbox(
        "Driver",
        drivers.index.tolist(),
        index=preferred_idx,
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
