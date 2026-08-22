"""V3 replay — SetupView year / race / session, then LiveSessionView clock."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

import streamlit as st  # noqa: E402

try:
    for _key in ("ARIS_DB_URL", "OPENF1_USERNAME", "OPENF1_PASSWORD", "OPENF1_API_KEY"):
        if _key in st.secrets:
            os.environ.setdefault(_key, str(st.secrets[_key]))
except (FileNotFoundError, KeyError):
    pass

from apps.components.v3_session import render_session  # noqa: E402
from apps.v3_chrome import render_nav  # noqa: E402
from aris.live_feed import replay_snapshot  # noqa: E402

render_nav("replay")

if "rp_playing" not in st.session_state:
    st.session_state.rp_playing = False
if "rp_wall0" not in st.session_state:
    st.session_state.rp_wall0 = None
if "rp_speed" not in st.session_state:
    st.session_state.rp_speed = 5
if "focus_code" not in st.session_state:
    st.session_state.focus_code = "VER"
if "aris_cache" not in st.session_state:
    st.session_state.aris_cache = None


@st.cache_data(ttl=180)
def _rounds(year: int):
    from backend.calendar import get_calendar

    cal = get_calendar(year)
    return [
        {
            "round": r.round_number,
            "name": r.name,
            "circuit": r.circuit_name,
            "status": r.status,
            "sprint": r.is_sprint_weekend,
        }
        for r in cal.rounds
    ]


if not st.session_state.rp_playing:
    st.markdown('<div class="aris-kicker-gold">MISSION SETUP</div>', unsafe_allow_html=True)
    st.markdown('<div class="aris-title" style="font-size:42px;margin:8px 0 20px">REPLAY</div>', unsafe_allow_html=True)
    year = st.radio("01 — SELECT YEAR", [2024, 2025, 2026], horizontal=True, index=1)
    try:
        rows = _rounds(year)
    except Exception as extra:
        st.warning(f"Calendar: {extra}")
        rows = []
    completed = [r for r in rows if r["status"] == "COMPLETED"]
    upcoming = [r for r in rows if r["status"] != "COMPLETED"]
    options = completed or rows
    if not options:
        st.info("No rounds loaded yet.")
        st.stop()
    st.caption("02 — SELECT RACE")
    labels = [f"R{r['round']}  {r['name'].upper()}  ·  {r['circuit']}" for r in options]
    pick = st.selectbox("Race", labels, label_visibility="collapsed")
    chosen = options[labels.index(pick)]
    session = st.radio(
        "03 — SESSION",
        ["R", "S", "Q", "FP1"] if chosen.get("sprint") else ["R", "Q", "FP1"],
        horizontal=True,
        format_func=lambda s: {"R": "RACE", "S": "SPRINT", "Q": "QUALIFYING", "FP1": "FP1"}[s],
    )
    speed = st.select_slider("SPEED", options=[1, 2, 5, 10, 25, 50], value=st.session_state.rp_speed)
    if upcoming:
        st.caption("UPCOMING")
        st.markdown(
            "".join(
                f'<div class="aris-round" style="margin:6px 0;opacity:.55">R{r["round"]} {r["name"].upper()}</div>'
                for r in upcoming[:8]
            ),
            unsafe_allow_html=True,
        )
    if st.button("▶ START REPLAY", type="primary"):
        st.session_state.rp_playing = True
        st.session_state.rp_wall0 = time.time()
        st.session_state.rp_speed = speed
        st.session_state.rp_year = year
        st.session_state.rp_session = session
        st.session_state.rp_circuit = chosen["circuit"]
        st.session_state.rp_event = chosen["name"]
        st.rerun()
    st.stop()

st.session_state.rp_speed = st.select_slider(
    "SPEED", options=[1, 2, 5, 10, 25, 50], value=st.session_state.rp_speed
)
if st.button("← BACK TO SETUP"):
    st.session_state.rp_playing = False
    st.session_state.rp_wall0 = None
    st.rerun()
    st.stop()

elapsed = (time.time() - (st.session_state.rp_wall0 or time.time())) * float(st.session_state.rp_speed)
snap = replay_snapshot(
    year=int(st.session_state.get("rp_year") or 2025),
    session_type=str(st.session_state.get("rp_session") or "R"),
    circuit=str(st.session_state.get("rp_circuit") or "Zandvoort"),
    event=str(st.session_state.get("rp_event") or "Netherlands"),
    elapsed_s=elapsed,
)
if snap is None:
    st.markdown('<span class="aris-chip replay">REPLAY</span>', unsafe_allow_html=True)
    st.markdown('<div class="aris-title" style="font-size:28px;margin:12px 0">LOADING SESSION DATA…</div>', unsafe_allow_html=True)
    st.caption("First OpenF1 / FastF1 pack can take a few minutes.")
    time.sleep(4)
    st.rerun()
    st.stop()
if snap.replay_duration_s and elapsed >= snap.replay_duration_s:
    st.session_state.rp_wall0 = time.time()
render_session(snap, "replay")
if snap.replay_duration_s:
    st.progress(min(1.0, elapsed / max(1, snap.replay_duration_s)))
time.sleep(0.45)
st.rerun()
