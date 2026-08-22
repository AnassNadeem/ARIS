"""V3 home — same layout as frontend/src/pages/HomePage.tsx."""

from __future__ import annotations

import os
import sys
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

from apps.v3_chrome import render_nav  # noqa: E402
from aris.ui_text import HEADLINE_CALENDAR_BLEND_MAE_S  # noqa: E402

render_nav("home")


@st.cache_data(ttl=90)
def _next_race() -> dict:
    from backend.calendar import next_race

    nxt = next_race()
    return {
        "name": nxt.name,
        "off_season": nxt.off_season,
        "next_session_name": nxt.next_session_name,
        "countdown_seconds": nxt.countdown_seconds,
    }


live_label = "⬤ LIVE: DUTCH GRAND PRIX"
next_line = "DUTCH GRAND PRIX WEEKEND"
try:
    nxt = _next_race()
    name = (nxt.get("name") or "Dutch Grand Prix").upper()
    sess = (nxt.get("next_session_name") or "Sprint").upper()
    live_label = "⬤ LIVE: OFF SEASON" if nxt.get("off_season") else f"⬤ LIVE: {name}"
    left = int(nxt.get("countdown_seconds") or 0)
    h, rem = divmod(max(0, left), 3600)
    m, _s = divmod(rem, 60)
    d, h = divmod(h, 24)
    next_line = f"🏁 {name} WEEKEND · {sess} IN {d}D {h}H {m}M"
except Exception:
    nxt = None

st.markdown('<div class="aris-hero-word">ARIS</div>', unsafe_allow_html=True)
st.markdown('<div class="aris-kicker-gold">Always-on Race Intelligence System</div>', unsafe_allow_html=True)
st.markdown(
    """
<p style="font-family:IBM Plex Sans,sans-serif;font-size:16px;color:#7A8796;line-height:1.7;max-width:720px;margin-top:20px">
ARIS is a digital race engineer that watches a Grand Prix and makes the decisions a real
strategist makes — tyre choice, pit timing, Safety Car reactions — aimed at the best
realistic outcome for your driver. Every recommendation shows its reasoning. Nothing is
blindly decided.
</p>
""",
    unsafe_allow_html=True,
)

c1, c2, _ = st.columns([1.1, 1.3, 1.6])
with c1:
    if st.button("▶ REPLAY A RACE", type="primary"):
        st.switch_page("pages/04_Replay.py")
with c2:
    if st.button(live_label):
        st.switch_page("pages/03_Live.py")

st.markdown(
    f"""
<div style="margin-top:28px;padding:10px 14px;border:1px solid #E8A33D55;background:#1F1A0D;border-radius:4px;
font-family:IBM Plex Mono,monospace;font-size:11px;color:#E8ECF0">{next_line}</div>
""",
    unsafe_allow_html=True,
)

mae = HEADLINE_CALENDAR_BLEND_MAE_S
st.markdown(
    f"""
<div class="aris-grid3" style="margin-top:40px">
  <div class="aris-card"><div class="n">{mae:.3f}s</div><div class="l">Calendar-wide lap time MAE</div></div>
  <div class="aris-card"><div class="n">32.5%</div><div class="l">Decision match-rate 2024</div>
    <div class="l" style="color:#4A5560">vs 25.0% never-pit baseline</div></div>
  <div class="aris-card"><div class="n">−1.73</div><div class="l">Average position delta</div>
    <div class="l" style="color:#4A5560">−1.49 clean / −2.38 disrupted</div></div>
</div>
<div class="aris-grid2" style="margin-top:28px">
  <div class="aris-card"><div class="l" style="color:#E8A33D;letter-spacing:0.1em">LAP-BY-LAP STRATEGY</div>
    <div style="font-size:13px;color:#7A8796;margin-top:8px">pit timing, compound choice, pace targets</div></div>
  <div class="aris-card"><div class="l" style="color:#E8A33D;letter-spacing:0.1em">FULL REASONING</div>
    <div style="font-size:13px;color:#7A8796;margin-top:8px">every call shows pace gained vs pit cost</div></div>
  <div class="aris-card"><div class="l" style="color:#E8A33D;letter-spacing:0.1em">REPLAY ANY RACE</div>
    <div style="font-size:13px;color:#7A8796;margin-top:8px">2024, 2025, 2026 with 1× to 50× speed</div></div>
  <div class="aris-card"><div class="l" style="color:#E8A33D;letter-spacing:0.1em">LIVE RACE MODE</div>
    <div style="font-size:13px;color:#7A8796;margin-top:8px">real OpenF1 data, ARIS recommends in real time</div></div>
</div>
""",
    unsafe_allow_html=True,
)
