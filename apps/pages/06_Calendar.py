"""V3 calendar — CircuitsView grid of rounds."""

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

render_nav("calendar")
st.markdown('<div class="aris-kicker-gold">FIA CALENDAR</div>', unsafe_allow_html=True)
st.markdown('<div class="aris-title" style="font-size:42px;margin:8px 0 20px">CIRCUITS</div>', unsafe_allow_html=True)

year = st.radio("YEAR", [2026, 2025, 2024], horizontal=True, index=0)


@st.cache_data(ttl=180)
def _rounds(year: int):
    from backend.calendar import get_calendar

    cal = get_calendar(year)
    return [
        {
            "round": r.round_number,
            "name": r.name,
            "circuit": r.circuit_name,
            "city": r.city,
            "country": r.country,
            "status": r.status,
            "sprint": r.is_sprint_weekend,
            "race": r.date_race.isoformat() if r.date_race else None,
        }
        for r in cal.rounds
    ]


try:
    rows = _rounds(year)
except Exception as extra:
    st.error(f"Could not load calendar. {extra}")
    st.stop()

if not rows:
    st.info("No rounds for this year.")
    st.stop()

cards = []
for r in rows:
    tone = "live" if r["status"] == "LIVE" else ("green" if r["status"] == "COMPLETED" else "")
    sprint = " · SPRINT" if r["sprint"] else ""
    when = (r["race"] or "")[:10]
    cards.append(
        f"""<div class="aris-card">
  <div class="l">R{r['round']}{sprint}</div>
  <div style="font-family:Big Shoulders Display,sans-serif;font-size:22px;font-weight:800;color:#E8ECF0;margin:6px 0">
    {r['name'].upper()}
  </div>
  <div class="l">{r['circuit']} · {r['city']}</div>
  <div style="margin-top:10px"><span class="aris-chip {tone}">{r['status']}</span>
  <span class="l" style="margin-left:8px">{when}</span></div>
</div>"""
    )
st.markdown('<div class="aris-grid3">' + "".join(cards) + "</div>", unsafe_allow_html=True)
