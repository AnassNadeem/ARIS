"""Timing tower leaderboard with F1 sector colors."""

from __future__ import annotations

import streamlit as st

from apps.theme import empty_state
from aris.field.sectors import SectorColor
from aris.field.state import FieldState

_COLOR_CLASS = {
    SectorColor.PURPLE: "purple",
    SectorColor.GREEN: "green",
    SectorColor.YELLOW: "yellow",
    SectorColor.NONE: "none",
}


def _fmt_sector(val: float | None, color: SectorColor) -> str:
    cls = _COLOR_CLASS.get(color, "none")
    if val is None:
        return f'<span class="aris-sec {cls}">—</span>'
    return f'<span class="aris-sec {cls}">{val:.3f}</span>'


def render_leaderboard(field: FieldState | None) -> None:
    if field is None or not field.driver_views:
        empty_state("Waiting for race data…", "Start the session, then lock a strategy to run the tower.")
        return

    st.caption(
        f"Lap {field.index.lap_number}/{field.total_laps} · "
        f"Sector {field.index.sector_idx}/3"
    )

    rows_html = []
    for view in field.driver_views[:20]:
        s = view.standing
        last = f"{s.last_lap_s:.3f}s" if s.last_lap_s else "—"
        team = s.team or ""
        rows_html.append(
            "<tr>"
            f"<td>{s.position}</td>"
            f"<td><b>{s.code}</b></td>"
            f"<td>{team}</td>"
            f"<td>{s.gap_to_leader_s:.1f}s</td>"
            f"<td>{_fmt_sector(s.sector_1_s, view.s1_color)}</td>"
            f"<td>{_fmt_sector(s.sector_2_s, view.s2_color)}</td>"
            f"<td>{_fmt_sector(s.sector_3_s, view.s3_color)}</td>"
            f"<td>{last}</td>"
            "</tr>"
        )

    html = (
        "<div class='aris-tower-wrap'><table class='aris-tower'>"
        "<tr><th>Pos</th><th>Driver</th><th>Team</th><th>Gap</th>"
        "<th>S1</th><th>S2</th><th>S3</th><th>Last</th></tr>"
        + "".join(rows_html)
        + "</table></div>"
        "<p class='aris-muted' style='font-size:0.75rem;margin:0.2rem 0 0.6rem 0'>"
        "Purple = session best · green = personal best · yellow = slower</p>"
    )
    st.markdown(html, unsafe_allow_html=True)

    fastest = field.fastest_sectors
    if fastest:
        badges = " · ".join(f"S{k}: {v}" for k, v in fastest.items())
        st.caption(f"Fastest sectors — {badges}")
