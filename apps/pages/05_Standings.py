"""V3 standings — StandingsView (Jolpica + OpenF1 extras)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

import streamlit as st  # noqa: E402

try:
    for _key in ("OPENF1_USERNAME", "OPENF1_PASSWORD", "OPENF1_API_KEY"):
        if _key in st.secrets:
            os.environ.setdefault(_key, str(st.secrets[_key]))
except (FileNotFoundError, KeyError):
    pass

from apps.v3_chrome import render_nav  # noqa: E402

render_nav("standings")
st.markdown('<div class="aris-kicker-gold">CHAMPIONSHIP</div>', unsafe_allow_html=True)
st.markdown('<div class="aris-title" style="font-size:42px;margin:8px 0 20px">STANDINGS</div>', unsafe_allow_html=True)

year = st.radio("YEAR", [2024, 2025, 2026], horizontal=True, index=2, format_func=lambda y: f"{y} ▶ LIVE" if y == 2026 else str(y))
tab = st.radio("TABLE", ["DRIVERS", "CONSTRUCTORS"], horizontal=True)


@st.cache_data(ttl=300)
def _drivers(year: int):
    from backend.standings import driver_standings

    return driver_standings(year)


@st.cache_data(ttl=300)
def _teams(year: int):
    from backend.standings import constructor_standings

    return constructor_standings(year)


@st.cache_data(ttl=180)
def _progress(year: int) -> tuple[int, int]:
    from backend.calendar import get_calendar

    cal = get_calendar(year)
    done = sum(1 for r in cal.rounds if r.status == "COMPLETED")
    return done, len(cal.rounds)


try:
    done, total = _progress(year)
    st.caption(f"SEASON IN PROGRESS — ROUND {done} OF {total or 24}" if year == 2026 else f"{year} · {done} rounds classified")
except Exception:
    pass

try:
    if tab == "DRIVERS":
        data = _drivers(year)
        rows = [
            {
                "POS": r.position,
                "DRIVER": f"{r.full_name} ({r.driver_code})",
                "TEAM": r.team_name,
                "PTS": r.points,
                "WINS": r.wins,
                "POD": r.podiums or 0,
                "FL": r.fastest_laps or 0,
                "DNF": r.dnfs or 0,
                "GAP": r.gap_to_leader,
            }
            for r in data.standings
        ]
    else:
        data = _teams(year)
        rows = [
            {
                "POS": r.position,
                "TEAM": r.team_name,
                "PTS": r.points,
                "WINS": r.wins,
                "POD": r.podiums or 0,
                "DRIVERS": " / ".join(r.drivers or []),
            }
            for r in data.standings
        ]
except Exception as extra:
    st.error(f"Could not load standings. {extra}")
    st.stop()

if not rows:
    st.info("Jolpica has no table for this year yet.")
else:
    st.dataframe(rows, use_container_width=True, hide_index=True)
