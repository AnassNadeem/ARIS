"""Live / auto-replay dashboard. Starts itself when the official feed is up."""

from __future__ import annotations

import html
import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

try:
    for _key in ("ARIS_DB_URL", "OPENF1_USERNAME", "OPENF1_PASSWORD"):
        if _key in st.secrets:
            os.environ.setdefault(_key, str(st.secrets[_key]))
except (FileNotFoundError, KeyError):
    pass

from apps.components.recommend_panel import render_recommendation_callout  # noqa: E402
from apps.theme import inject_theme, render_disclaimer  # noqa: E402
from aris.live_feed import (  # noqa: E402
    DriverLive,
    LiveSnapshot,
    build_live_race_state,
    collect_live_snapshot,
    fmt_gap,
    fmt_ms,
    replay_snapshot,
    resolve_mode,
    start_live_ingest,
)
from aris.recommend import recommend  # noqa: E402
from aris.ui_text import PREFERRED_DRIVER_CODES  # noqa: E402

inject_theme()
start_live_ingest()

SPEEDS = [1, 2, 4, 10, 20, 50]

if "live_mode" not in st.session_state:
    st.session_state.live_mode = None
if "replay_wall0" not in st.session_state:
    st.session_state.replay_wall0 = None
if "replay_elapsed0" not in st.session_state:
    st.session_state.replay_elapsed0 = 0.0
if "replay_speed" not in st.session_state:
    st.session_state.replay_speed = 4
if "focus_code" not in st.session_state:
    st.session_state.focus_code = "VER"
if "aris_cache" not in st.session_state:
    st.session_state.aris_cache = None


def _clock_label(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _tyre_html(letter: str | None) -> str:
    if not letter:
        return "—"
    return f'<span class="aris-tyre {html.escape(letter)}">{html.escape(letter)}</span>'


def _pos_delta_html(change: int | None) -> str:
    if change is None or change == 0:
        return "—"
    if change > 0:
        return f'<span class="aris-posup">▲{change}</span>'
    return f'<span class="aris-posdn">▼{abs(change)}</span>'


def _pick_focus(drivers: list[DriverLive], current: str) -> str:
    codes = [d.code for d in drivers]
    if current in codes:
        return current
    for pref in PREFERRED_DRIVER_CODES:
        if pref in codes:
            return pref
    return codes[0] if codes else current


def _render_tower(drivers: list[DriverLive], focus: str) -> None:
    if not drivers:
        st.markdown(
            '<div class="aris-empty"><strong>No timing yet</strong><br>'
            "The official feed is connected; rows appear at lights out / first lap.</div>",
            unsafe_allow_html=True,
        )
        return
    rows = []
    for d in drivers:
        fl = ' <span class="aris-fl">FL</span>' if d.fastest_lap else ""
        pit = " PIT" if d.in_pit else ""
        out = " OUT" if d.retired else ""
        code = html.escape(d.code)
        rows.append(
            "<tr>"
            f"<td>{d.position if d.position < 90 else '—'}</td>"
            f"<td><b>{code}</b>{fl}{pit}{out}</td>"
            f"<td>{_pos_delta_html(d.position_change)}</td>"
            f"<td>{html.escape(fmt_gap(d.gap_to_leader_s))}</td>"
            f"<td>{html.escape(fmt_ms(d.last_lap_ms))}</td>"
            f"<td>{html.escape(fmt_ms(d.best_lap_ms))}</td>"
            f'<td><span class="aris-sec {html.escape(d.s1_colour)}">{html.escape(fmt_ms(d.sector1_ms))}</span></td>'
            f'<td><span class="aris-sec {html.escape(d.s2_colour)}">{html.escape(fmt_ms(d.sector2_ms))}</span></td>'
            f'<td><span class="aris-sec {html.escape(d.s3_colour)}">{html.escape(fmt_ms(d.sector3_ms))}</span></td>'
            f"<td>{_tyre_html(d.compound)}</td>"
            f"<td>{d.tyre_life if d.tyre_life is not None else '—'}</td>"
            f"<td>{d.pit_count}</td>"
            "</tr>"
        )
    st.markdown(
        "<div class='aris-tower-wrap'><table class='aris-tower'>"
        "<tr><th>P</th><th>Drv</th><th>+/−</th><th>Gap</th><th>Last</th><th>Best</th>"
        "<th>S1</th><th>S2</th><th>S3</th><th>Tyre</th><th>Age</th><th>Pits</th></tr>"
        + "".join(rows)
        + "</table></div>"
        "<p class='aris-muted' style='font-size:0.75rem'>Purple sector = session best · "
        "green = personal best · FL = fastest lap · +/− vs grid</p>",
        unsafe_allow_html=True,
    )


def _render_map(snap: LiveSnapshot, focus: str) -> None:
    xs = [d.gps_x for d in snap.drivers if d.gps_x is not None and d.gps_y is not None]
    ys = [d.gps_y for d in snap.drivers if d.gps_x is not None and d.gps_y is not None]
    fig = go.Figure()
    if snap.path_x and snap.path_y and len(snap.path_x) == len(snap.path_y):
        fig.add_trace(
            go.Scatter(
                x=snap.path_x,
                y=snap.path_y,
                mode="lines",
                line={"color": "#3A4250", "width": 10},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    if xs:
        colours = []
        texts = []
        sizes = []
        px, py = [], []
        for d in snap.drivers:
            if d.gps_x is None or d.gps_y is None:
                continue
            px.append(d.gps_x)
            py.append(d.gps_y)
            colours.append(d.team_colour or ("#F5C518" if d.code == focus else "#8B93A1"))
            texts.append(d.code)
            sizes.append(16 if d.code == focus else 11)
        fig.add_trace(
            go.Scatter(
                x=px,
                y=py,
                mode="markers+text",
                marker={"color": colours, "size": sizes, "line": {"width": 1, "color": "#0B0D10"}},
                text=texts,
                textposition="top center",
                textfont={"size": 10, "color": "#F3F4F6"},
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            )
        )
    else:
        fig.add_annotation(
            text="GPS not in this frame yet — timing is live above",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"color": "#8B93A1", "size": 13},
        )
    fig.update_layout(
        height=420,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        paper_bgcolor="#0B0D10",
        plot_bgcolor="#0B0D10",
        xaxis={"visible": False, "scaleanchor": "y", "scaleratio": 1},
        yaxis={"visible": False},
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _aris_callout(snap: LiveSnapshot, focus: str) -> None:
    if snap.session_type not in {"R", "S"}:
        st.caption("ARIS strategy is armed for Sprint and Race. Practice / quali stay view-only.")
        return
    state = build_live_race_state(snap, focus)
    if state is None:
        render_recommendation_callout(None, title="ARIS is watching", empty_body="Waiting for the focus driver's first lap.")
        return
    cache = st.session_state.aris_cache
    key = (focus, state.lap_number, state.compound, state.tyre_life, state.position, snap.flag)
    if cache and cache.get("key") == key:
        rec = cache.get("rec")
        err = cache.get("err")
    else:
        rec = None
        err = None
        try:
            result = recommend(state, top_k=3, mc_draws=12)
            rec = result.recommendations[0] if result.recommendations else None
        except Exception as extra:
            err = str(extra)
        st.session_state.aris_cache = {"key": key, "rec": rec, "err": err}
    if err:
        st.warning(f"ARIS could not score this lap: {err}")
    extra = state.confidence_caveat
    render_recommendation_callout(
        rec,
        title=f"ARIS · {focus} · L{state.lap_number}/{state.total_laps}",
        extra_caveat=extra,
        empty_body="Watching tyre age, gaps, and SC/VSC. A call appears when the search finds a better action than stay-out.",
    )


def _focus_strip(row: DriverLive | None) -> None:
    if row is None:
        return
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Position", f"P{row.position}" if row.position < 90 else "—", _plain_pos(row.position_change))
    c2.metric("Tyre", f"{row.compound or '—'} · {row.tyre_life if row.tyre_life is not None else '—'} laps")
    c3.metric("Last lap", fmt_ms(row.last_lap_ms))
    c4.metric("Throttle", "—" if row.throttle is None else f"{row.throttle:.0f}%")
    brake = row.brake
    if brake is not None and brake <= 1:
        brake = brake * 100
    c5.metric("Brake", "—" if brake is None else f"{brake:.0f}%")
    c6.metric("Speed", "—" if row.speed_kph is None else f"{row.speed_kph:.0f} km/h")
    extras = []
    if row.rpm is not None:
        extras.append(f"RPM {row.rpm:.0f}")
    if row.gear is not None:
        extras.append(f"Gear {row.gear}")
    if row.drs is not None:
        extras.append(f"DRS {row.drs}")
    if extras:
        st.caption(" · ".join(extras))


def _plain_pos(change: int | None) -> str | None:
    if change is None or change == 0:
        return None
    return f"+{change}" if change > 0 else str(change)


def _header(snap: LiveSnapshot, mode: str) -> None:
    badge = {"live": "live", "replay": "replay", "waiting": "wait"}.get(mode, "wait")
    label = {"live": "LIVE", "replay": "REPLAY", "waiting": "STANDBY"}.get(mode, "STANDBY")
    lap = ""
    if snap.current_lap:
        total = f"/{snap.total_laps}" if snap.total_laps else ""
        lap = f" · Lap {snap.current_lap}{total}"
    st.markdown(
        f'<div class="aris-kicker">Race engineer</div>'
        f'<h1><span class="aris-live-badge {badge}">{label}</span>'
        f"{html.escape(snap.session_name or 'Session')}</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"{snap.circuit} · {snap.session_type or '—'} · flag {snap.flag} · "
        f"{snap.delay_note}{lap}"
    )


def _weather(snap: LiveSnapshot) -> None:
    cols = st.columns(7)
    cols[0].metric("Air", "—" if snap.air_temp is None else f"{snap.air_temp:.1f}°")
    cols[1].metric("Track", "—" if snap.track_temp is None else f"{snap.track_temp:.1f}°")
    cols[2].metric("Humid", "—" if snap.humidity is None else f"{snap.humidity:.0f}%")
    cols[3].metric("Rain", "YES" if snap.rainfall else ("NO" if snap.rainfall is False else "—"))
    cols[4].metric("Wind", "—" if snap.wind_speed is None else f"{snap.wind_speed:.1f} m/s")
    cols[5].metric(
        "Clock",
        _clock_label(snap.remaining_s if snap.mode != "replay" else snap.elapsed_s),
    )
    cols[6].metric("Cars", str(len(snap.drivers) or "—"))


def _enter_replay(auto: bool = True) -> None:
    st.session_state.live_mode = "replay"
    st.session_state.replay_wall0 = time.time()
    st.session_state.replay_elapsed0 = 0.0
    if auto and st.session_state.replay_speed < 2:
        st.session_state.replay_speed = 4


mode, window = resolve_mode()
prev = st.session_state.live_mode
if mode == "live":
    st.session_state.live_mode = "live"
elif mode == "replay" and prev != "live":
    if st.session_state.replay_wall0 is None:
        _enter_replay(auto=True)
    st.session_state.live_mode = "replay"
elif mode == "waiting" and prev == "live":
    _enter_replay(auto=True)
elif st.session_state.live_mode is None:
    st.session_state.live_mode = mode

ui_mode = st.session_state.live_mode

with st.sidebar:
    st.markdown("**Live feed**")
    st.caption(
        "Sprint and Race start themselves when SignalR / OpenF1 publish. "
        "After the feed drops this page switches to FastF1 / OpenF1 replay."
    )
    if ui_mode == "replay":
        st.session_state.replay_speed = st.select_slider(
            "Replay speed",
            options=SPEEDS,
            value=st.session_state.replay_speed,
        )
        if st.button("Restart replay"):
            _enter_replay(auto=False)
    st.caption("No Play click on a live session. Cars may jump — numbers stay real.")

if ui_mode == "waiting":
    snap = collect_live_snapshot()
    if snap.is_live and snap.drivers:
        st.session_state.live_mode = "live"
        ui_mode = "live"
    else:
        _header(snap, "waiting")
        nxt = snap.next_session_utc
        if nxt:
            left = int((nxt - snap.as_of).total_seconds())
            st.metric("Next session", snap.next_session_name or "—", _clock_label(left))
        st.info(
            "This tab keeps polling. When the official live feed starts, the "
            "tower, map, tyres, and ARIS call appear without a Start click."
        )
        render_disclaimer()
        time.sleep(8)
        st.rerun()
        st.stop()

if ui_mode == "live":
    snap = collect_live_snapshot()
    if not snap.is_live and not snap.drivers:
        if mode == "replay":
            _enter_replay(auto=True)
            st.rerun()
            st.stop()
        if mode == "waiting":
            st.session_state.live_mode = "waiting"
            st.rerun()
            st.stop()
        snap.session_name = snap.session_name or "Live session"
        snap.delay_note = "Connecting to SignalR / OpenF1 — page stays live, no Start click"
    focus = _pick_focus(snap.drivers, st.session_state.focus_code)
    codes = [d.code for d in snap.drivers]
    if codes:
        focus = st.sidebar.selectbox("Focus driver", codes, index=codes.index(focus) if focus in codes else 0)
        st.session_state.focus_code = focus
    _header(snap, "live")
    _weather(snap)
    row = next((d for d in snap.drivers if d.code == focus), None)
    _focus_strip(row)
    _aris_callout(snap, focus)
    left, right = st.columns([0.52, 0.48])
    with left:
        st.subheader("Timing")
        _render_tower(snap.drivers, focus)
    with right:
        st.subheader("Track map")
        _render_map(snap, focus)
    if snap.race_control:
        st.caption("Race control")
        for msg in snap.race_control[-6:]:
            st.write(f"· {msg}")
    if snap.error:
        st.caption(f"Feed note: {snap.error}")
    render_disclaimer()
    time.sleep(2)
    st.rerun()
    st.stop()

# Replay — auto-plays. Speed 1x–50x. FastF1 fills GPS when the cache is ready.
win = window or {}
year = int(win.get("year") or 2026)
stype = str(win.get("session_type") or "S")
circuit = str(win.get("circuit") or "Zandvoort")
event = "Netherlands"
elapsed = st.session_state.replay_elapsed0
if st.session_state.replay_wall0 is not None:
    elapsed = st.session_state.replay_elapsed0 + (time.time() - st.session_state.replay_wall0) * float(
        st.session_state.replay_speed
    )
snap = replay_snapshot(year=year, session_type=stype, circuit=circuit, event=event, elapsed_s=elapsed)
if snap is None:
    live_try = collect_live_snapshot()
    _header(live_try, "replay")
    st.warning(
        "Replay pack is still loading from OpenF1 / FastF1. "
        "A just-finished session can take several minutes the first time."
    )
    if live_try.drivers:
        _render_tower(live_try.drivers, _pick_focus(live_try.drivers, st.session_state.focus_code))
    render_disclaimer()
    time.sleep(4)
    st.rerun()

if snap.replay_duration_s and elapsed >= snap.replay_duration_s:
    elapsed = float(snap.replay_duration_s)
    st.session_state.replay_wall0 = time.time()
    st.session_state.replay_elapsed0 = 0.0

focus = _pick_focus(snap.drivers, st.session_state.focus_code)
codes = [d.code for d in snap.drivers]
if codes:
    focus = st.sidebar.selectbox("Focus driver", codes, index=codes.index(focus) if focus in codes else 0)
    st.session_state.focus_code = focus

_header(snap, "replay")
st.progress(min(1.0, elapsed / max(1, snap.replay_duration_s or 1)))
st.caption(f"{_clock_label(int(elapsed))} / {_clock_label(snap.replay_duration_s)} · {st.session_state.replay_speed}×")
_weather(snap)
row = next((d for d in snap.drivers if d.code == focus), None)
_focus_strip(row)
if snap.session_type in {"R", "S"}:
    _aris_callout(snap, focus)
left, right = st.columns([0.52, 0.48])
with left:
    st.subheader("Timing")
    _render_tower(snap.drivers, focus)
with right:
    st.subheader("Track map")
    _render_map(snap, focus)
render_disclaimer()
time.sleep(0.45)
st.rerun()
