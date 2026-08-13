"""Landing page — what ARIS is, honest numbers, where to go next."""

from __future__ import annotations

import streamlit as st

from apps.theme import inject_theme, render_disclaimer
from aris.ui_text import (
    HEADLINE_CALENDAR_AIMED_S,
    HEADLINE_CALENDAR_BLEND_MAE_S,
    HEADLINE_CALENDAR_PASS,
    HEADLINE_CHINA_AIMED_S,
    HEADLINE_CHINA_MAE_S,
    HEADLINE_CHINA_MISS_S,
    HEADLINE_NL_2024_AIMED_S,
    HEADLINE_NL_2024_MAE_S,
    HEADLINE_NL_2025_AIMED_S,
    HEADLINE_NL_2025_MAE_S,
)

inject_theme()

st.markdown('<div class="aris-kicker">Always-on race strategy</div>', unsafe_allow_html=True)
st.markdown(
    """
<div class="aris-hero">
  <h1>ARIS</h1>
  <p>A race engineer that watches a Formula 1 race, predicts the next lap,
  and proposes the next pit call with a lap-time delta. You decide.</p>
  <p class="aris-muted">Hybrid physics + residual model, scored on held-out
  races — not a marketing MAE. Unofficial fan project.</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="aris-stat-row">
  <div class="aris-stat pass">
    <div class="lbl">2024 calendar blend MAE</div>
    <div class="val">{HEADLINE_CALENDAR_BLEND_MAE_S:.3f}s</div>
    <div class="sub">aimed ≤ {HEADLINE_CALENDAR_AIMED_S:.3f}s · {HEADLINE_CALENDAR_PASS} races</div>
  </div>
  <div class="aris-stat pass">
    <div class="lbl">Dutch GP (Zandvoort)</div>
    <div class="val">{HEADLINE_NL_2024_MAE_S:.3f}s</div>
    <div class="sub">2024 pass (≤ {HEADLINE_NL_2024_AIMED_S:.3f}) · 2025 {HEADLINE_NL_2025_MAE_S:.3f}s (≤ {HEADLINE_NL_2025_AIMED_S:.3f})</div>
  </div>
  <div class="aris-stat miss">
    <div class="lbl">China 2024 — still a miss</div>
    <div class="val">{HEADLINE_CHINA_MAE_S:.3f}s</div>
    <div class="sub">aimed ≤ {HEADLINE_CHINA_AIMED_S:.3f}s · short by {HEADLINE_CHINA_MISS_S:.3f}s</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.caption(
    "Numbers from the Phase E.3 / E.4 lock-in (held-out 2024 calendar, 1.5× MA(2) "
    "bar). Monte Carlo P10/P90 bands are not calibrated coverage. Physics alone is "
    "still ~10–26 s slow on many circuits; residual + blend is what you see above."
)

left, right = st.columns(2)
with left:
    st.markdown("**Strategy**")
    st.write(
        "Replay a race as the engineer. ARIS recommends; you accept, reject, or "
        "edit. Watch, Ask, What-if, then a post-race comparison."
    )
    st.page_link("pages/01_Strategy.py", label="Open the Strategy tool", icon="📡")
with right:
    st.markdown("**Lap explorer**")
    st.write(
        "Pick a season, race, and driver. Lap-time trace, sector stack, and the "
        "MA(2) baseline a model has to beat."
    )
    st.page_link("pages/02_Lap_Explorer.py", label="Open the lap explorer", icon="📈")

st.markdown("---")
render_disclaimer()
