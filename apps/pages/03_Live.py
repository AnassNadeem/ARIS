"""V3 live — LivePage + LiveSessionView. Auto-starts. No Play click."""

from __future__ import annotations

import html
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

import streamlit as st  # noqa: E402

_SECRET_KEYS = (
    "ARIS_DB_URL",
    "OPENF1_USERNAME",
    "OPENF1_PASSWORD",
    "OPENF1_API_KEY",
    "OPENF1_TOKEN",
    "OPENF1_ACCESS_TOKEN",
    "OPENF1_KEY",
)
try:
    for _key in _SECRET_KEYS:
        if _key in st.secrets:
            os.environ.setdefault(_key, str(st.secrets[_key]))
except (FileNotFoundError, KeyError):
    pass

from apps.components.v3_session import clock, render_session  # noqa: E402
from apps.v3_chrome import render_nav  # noqa: E402
from aris.live_feed import (  # noqa: E402
    ZANDVOORT_2026_WINDOWS,
    collect_live_snapshot,
    matching_window,
    next_window,
    parse_dt,
    replay_snapshot,
    resolve_mode,
    start_live_ingest,
)

render_nav("live")
start_live_ingest()

SPEEDS = [1, 2, 5, 10, 25, 50]


def _secrets_ok() -> bool:
    return any(os.getenv(k) for k in _SECRET_KEYS if k != "ARIS_DB_URL")


if "live_mode" not in st.session_state:
    st.session_state.live_mode = None
if "replay_wall0" not in st.session_state:
    st.session_state.replay_wall0 = None
if "replay_elapsed0" not in st.session_state:
    st.session_state.replay_elapsed0 = 0.0
if "replay_speed" not in st.session_state:
    st.session_state.replay_speed = 2
if "focus_code" not in st.session_state:
    st.session_state.focus_code = "VER"
if "aris_cache" not in st.session_state:
    st.session_state.aris_cache = None


def _enter_replay() -> None:
    st.session_state.live_mode = "replay"
    st.session_state.replay_wall0 = time.time()
    st.session_state.replay_elapsed0 = 0.0


def _session_board() -> None:
    now = datetime.now(timezone.utc)
    live = matching_window(now)
    nxt = next_window(now)
    rows = []
    for stype, name, start_iso, hours in ZANDVOORT_2026_WINDOWS:
        start = parse_dt(start_iso)
        if start is None:
            continue
        end = start + timedelta(hours=hours)
        if live and live["session_type"] == stype:
            status, tone = "LIVE", "live"
        elif now > end:
            status, tone = "COMPLETED", "green"
        else:
            status, tone = "UPCOMING", ""
        count = clock(int((start - now).total_seconds())) if status == "UPCOMING" else ""
        rows.append(
            f'<div class="aris-weekend-row"><span>{html.escape(name)}</span>'
            f'<span style="color:#7A8796">{count}</span>'
            f'<span class="aris-chip {tone}">{status}</span></div>'
        )
    headline = "DUTCH GRAND PRIX"
    sub = "Circuit Zandvoort · Sprint weekend"
    if live:
        sub = f"Circuit Zandvoort · {live['session_name'].upper()} IN PROGRESS"
    elif nxt:
        sub = f"Circuit Zandvoort · {nxt['session_name'].upper()} NEXT · {clock(int((nxt['start'] - now).total_seconds()))}"
    st.markdown(
        f'<span class="aris-chip {"live" if live else "signal"}">{"LIVE SESSION" if live else "RACE WEEKEND"}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="aris-title" style="font-size:36px;margin:12px 0">{headline}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-family:IBM Plex Mono,monospace;font-size:12px;color:#7A8796;margin-bottom:16px">{sub}</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="aris-weekend">' + "".join(rows) + "</div>", unsafe_allow_html=True)
    if not _secrets_ok():
        st.caption("OpenF1 account is in Streamlit secrets — SignalR still runs without a key.")


mode, window = resolve_mode()
prev = st.session_state.live_mode
if mode == "live":
    st.session_state.live_mode = "live"
elif mode == "replay" and prev != "live":
    if st.session_state.replay_wall0 is None:
        _enter_replay()
    st.session_state.live_mode = "replay"
elif mode == "waiting" and prev == "live":
    _enter_replay()
elif st.session_state.live_mode is None:
    st.session_state.live_mode = mode

ui_mode = st.session_state.live_mode

if ui_mode == "replay":
    st.session_state.replay_speed = st.select_slider(
        "SPEED", options=SPEEDS, value=st.session_state.replay_speed
    )

if ui_mode == "waiting":
    snap = collect_live_snapshot()
    if snap.is_live and snap.drivers:
        st.session_state.live_mode = "live"
        st.rerun()
        st.stop()
    _session_board()
    time.sleep(8)
    st.rerun()
    st.stop()

if ui_mode == "live":
    snap = collect_live_snapshot()
    if not snap.is_live and not snap.drivers:
        if mode == "replay":
            _enter_replay()
            st.rerun()
            st.stop()
        if mode == "waiting":
            st.session_state.live_mode = "waiting"
            st.rerun()
            st.stop()
        snap.delay_note = "Connecting to SignalR / OpenF1 — no Start click"
    render_session(snap, "live")
    time.sleep(2)
    st.rerun()
    st.stop()

win = window or {}
elapsed = st.session_state.replay_elapsed0
if st.session_state.replay_wall0 is not None:
    elapsed = st.session_state.replay_elapsed0 + (time.time() - st.session_state.replay_wall0) * float(
        st.session_state.replay_speed
    )
snap = replay_snapshot(
    year=int(win.get("year") or 2026),
    session_type=str(win.get("session_type") or "S"),
    circuit=str(win.get("circuit") or "Zandvoort"),
    event="Netherlands",
    elapsed_s=elapsed,
)
if snap is None:
    st.markdown('<span class="aris-chip replay">REPLAY</span>', unsafe_allow_html=True)
    st.markdown('<div class="aris-title" style="font-size:28px;margin:12px 0">LOADING SESSION DATA…</div>', unsafe_allow_html=True)
    st.caption("OpenF1 / FastF1 pack — first load after a session can take a few minutes.")
    time.sleep(4)
    st.rerun()
    st.stop()
if snap.replay_duration_s and elapsed >= snap.replay_duration_s:
    st.session_state.replay_wall0 = time.time()
    st.session_state.replay_elapsed0 = 0.0
render_session(snap, "replay")
if snap.replay_duration_s:
    st.progress(min(1.0, elapsed / max(1, snap.replay_duration_s)))
time.sleep(0.45)
st.rerun()
