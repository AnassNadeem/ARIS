"""Shared V3 session chrome — header, weather, tower, map."""

from __future__ import annotations

import html

import plotly.graph_objects as go
import streamlit as st

from aris.live_feed import DriverLive, LiveSnapshot, build_live_race_state, fmt_ms
from aris.recommend import recommend
from aris.ui_text import PREFERRED_DRIVER_CODES
from apps.components.recommend_panel import render_recommendation_callout

SESSION_LABEL = {
    "FP1": "FREE PRACTICE 1",
    "SQ": "SPRINT QUALIFYING",
    "S": "SPRINT",
    "Q": "QUALIFYING",
    "R": "RACE",
}


def clock(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def pick_focus(drivers: list[DriverLive], current: str) -> str:
    codes = [d.code for d in drivers]
    if current in codes:
        return current
    for pref in PREFERRED_DRIVER_CODES:
        if pref in codes:
            return pref
    return codes[0] if codes else current


def render_session(snap: LiveSnapshot, mode: str) -> None:
    quali = snap.session_type not in {"R", "S"}
    focus = pick_focus(snap.drivers, st.session_state.get("focus_code", "VER"))
    codes = [d.code for d in snap.drivers]
    if codes:
        focus = st.selectbox("FOCUS", codes, index=codes.index(focus) if focus in codes else 0)
        st.session_state.focus_code = focus
    _header(snap, mode)
    _weather(snap)
    _focus_car(next((d for d in snap.drivers if d.code == focus), None))
    _aris(snap, focus)
    left, right = st.columns([0.38, 0.62])
    with left:
        _tower(snap.drivers, focus, quali=quali)
    with right:
        _map(snap, focus)


def _header(snap: LiveSnapshot, mode: str) -> None:
    chip = "live" if mode == "live" else ("replay" if mode == "replay" else "")
    label = "LIVE" if mode == "live" else ("REPLAY" if mode == "replay" else "RACE WEEKEND")
    title = (snap.session_name or SESSION_LABEL.get(snap.session_type, "SESSION")).upper()
    extra = ""
    if mode == "live" and snap.remaining_s is not None:
        extra = f" · {clock(snap.remaining_s)}"
    if mode == "replay" and snap.elapsed_s is not None:
        extra = f" · {clock(snap.elapsed_s)}"
    src = html.escape((snap.source or "").upper())
    st.markdown(
        f"""
<div class="aris-v3-head">
  <span class="aris-chip {chip}">{label}</span>
  {f'<span class="aris-chip replay">{src}</span>' if src and mode == "replay" else ""}
  <span class="aris-title">{html.escape(title)}</span>
  <span style="font-family:IBM Plex Mono,monospace;font-size:11px;color:#7A8796">
    {html.escape((snap.circuit or "ZANDVOORT").upper())}{extra}
  </span>
  <span style="margin-left:auto;font-family:IBM Plex Mono,monospace;font-size:10px;color:#4A5560">
    {html.escape(snap.delay_note)}
  </span>
</div>
""",
        unsafe_allow_html=True,
    )


def _weather(snap: LiveSnapshot) -> None:
    def cell(label: str, value: str, alert: bool = False) -> str:
        cls = "val alert" if alert else "val"
        return f'<div><div class="lbl">{label}</div><div class="{cls}">{html.escape(value)}</div></div>'

    rain = "YES" if snap.rainfall else ("NO" if snap.rainfall is False else "—")
    air = "—" if snap.air_temp is None else f"{snap.air_temp:.1f}°"
    track = "—" if snap.track_temp is None else f"{snap.track_temp:.1f}°"
    humid = "—" if snap.humidity is None else f"{snap.humidity:.0f}%"
    press = "—" if snap.pressure is None else f"{snap.pressure:.1f} mb"
    wind = "—"
    if snap.wind_speed is not None:
        wind = f"{snap.wind_speed:.1f} m/s"
        if snap.wind_direction is not None:
            wind += f" {snap.wind_direction:.0f}°"
    st.markdown(
        '<div class="aris-wx">'
        + cell("AIR", air)
        + cell("TRACK", track)
        + cell("HUMID", humid)
        + cell("PRESS", press)
        + cell("WIND", wind)
        + cell("RAIN", rain, alert=bool(snap.rainfall))
        + cell("CARS", str(len(snap.drivers) or "—"))
        + "</div>",
        unsafe_allow_html=True,
    )


def _tower(drivers: list[DriverLive], focus: str, *, quali: bool) -> None:
    if not drivers:
        st.markdown(
            '<div class="aris-weekend" style="color:#7A8796">Waiting for the first timing frame…</div>',
            unsafe_allow_html=True,
        )
        return
    heads = ["P", "DRV", "BEST" if quali else "GAP", "LAST", "S1", "S2", "S3", "TYR"]
    body = []
    for i, d in enumerate(drivers):
        cls = []
        if d.code == focus:
            cls.append("focus")
        elif i % 2:
            cls.append("alt")
        if d.retired:
            cls.append("out")
        gap = (
            fmt_ms(d.best_lap_ms)
            if quali
            else (
                "LEADER"
                if d.position == 1
                else (f"+{d.gap_to_leader_s:.3f}" if d.gap_to_leader_s is not None else "—")
            )
        )
        reason = '<span style="margin-left:6px;color:#4A5560;font-weight:500">OUT</span>' if d.retired else ""
        fl = '<span class="aris-fl">FL</span>' if d.fastest_lap else ""
        tyre = (
            f'<span class="aris-badge {html.escape(d.compound or "")}">{html.escape(d.compound or "?")}</span>'
            f'<span style="color:#7A8796;font-size:10px;margin-left:5px">{d.tyre_life}L</span>'
            if d.compound
            else "—"
        )
        colour = "#9B72F0" if d.fastest_lap else ("#E8A33D" if d.code == focus else "#E8ECF0")
        body.append(
            f'<tr class="{" ".join(cls)}">'
            f'<td style="color:#7A8796">{d.position if d.position < 90 else "—"}</td>'
            f'<td style="font-weight:700;color:{colour}">{html.escape(d.code)}{reason}{fl}</td>'
            f'<td style="color:#7A8796;font-size:10px">{html.escape(gap)}</td>'
            f"<td>{html.escape(fmt_ms(d.last_lap_ms))}</td>"
            f'<td><span class="aris-dot {html.escape(d.s1_colour)}"></span></td>'
            f'<td><span class="aris-dot {html.escape(d.s2_colour)}"></span></td>'
            f'<td><span class="aris-dot {html.escape(d.s3_colour)}"></span></td>'
            f"<td>{tyre}</td>"
            "</tr>"
        )
    st.markdown(
        "<table class='aris-v3-tower'><thead><tr>"
        + "".join(f"<th>{h}</th>" for h in heads)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>",
        unsafe_allow_html=True,
    )


def _map(snap: LiveSnapshot, focus: str) -> None:
    fig = go.Figure()
    if snap.path_x and snap.path_y and len(snap.path_x) == len(snap.path_y):
        fig.add_trace(
            go.Scatter(
                x=snap.path_x,
                y=snap.path_y,
                mode="lines",
                line={"color": "#2A3545", "width": 12},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    px, py, colours, texts, sizes = [], [], [], [], []
    for d in snap.drivers:
        if d.gps_x is None or d.gps_y is None:
            continue
        px.append(d.gps_x)
        py.append(d.gps_y)
        colours.append(d.team_colour or ("#E8A33D" if d.code == focus else "#7A8796"))
        texts.append(d.code)
        sizes.append(15 if d.code == focus else 10)
    if px:
        fig.add_trace(
            go.Scatter(
                x=px,
                y=py,
                mode="markers+text",
                marker={"color": colours, "size": sizes, "line": {"width": 1, "color": "#070A0E"}},
                text=texts,
                textposition="top center",
                textfont={"size": 10, "color": "#E8ECF0", "family": "IBM Plex Mono"},
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            )
        )
    else:
        fig.add_annotation(
            text="GPS not in this frame yet — timing is live",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"color": "#7A8796", "size": 12, "family": "IBM Plex Mono"},
        )
    fig.update_layout(
        height=520,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="#0B0E12",
        plot_bgcolor="#0B0E12",
        xaxis={"visible": False, "scaleanchor": "y", "scaleratio": 1},
        yaxis={"visible": False},
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _focus_car(row: DriverLive | None) -> None:
    if row is None:
        return
    brake = row.brake
    if brake is not None and brake <= 1:
        brake = brake * 100
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("P", f"{row.position}" if row.position < 90 else "—")
    c2.metric("TYRE", f"{row.compound or '—'} {row.tyre_life if row.tyre_life is not None else '—'}L")
    c3.metric("LAST", fmt_ms(row.last_lap_ms))
    c4.metric("THR", "—" if row.throttle is None else f"{row.throttle:.0f}%")
    c5.metric("BRK", "—" if brake is None else f"{brake:.0f}%")
    c6.metric("SPD", "—" if row.speed_kph is None else f"{row.speed_kph:.0f}")


def _aris(snap: LiveSnapshot, focus: str) -> None:
    if snap.session_type not in {"R", "S"}:
        return
    state = build_live_race_state(snap, focus)
    if state is None:
        return
    key = (focus, state.lap_number, state.compound, state.tyre_life, state.position, snap.flag)
    cache = st.session_state.get("aris_cache")
    if cache and cache.get("key") == key:
        rec, err = cache.get("rec"), cache.get("err")
    else:
        rec, err = None, None
        try:
            result = recommend(state, top_k=3, mc_draws=12)
            rec = result.recommendations[0] if result.recommendations else None
        except Exception as extra:
            err = str(extra)
        st.session_state.aris_cache = {"key": key, "rec": rec, "err": err}
    if err:
        st.caption(f"ARIS: {err}")
        return
    render_recommendation_callout(
        rec,
        title=f"ARIS · {focus} · L{state.lap_number}/{state.total_laps}",
        extra_caveat=state.confidence_caveat,
        empty_body="Watching. A call appears when search beats stay-out.",
    )
