"""Timing tower leaderboard with F1 sector colors."""

from __future__ import annotations

import streamlit as st

from aris.field.sectors import SectorColor
from aris.field.state import FieldState

_COLOR_CSS = {
    SectorColor.PURPLE: "background-color:#b400ff;color:white;",
    SectorColor.GREEN: "background-color:#00ff00;color:black;",
    SectorColor.YELLOW: "background-color:#ffff00;color:black;",
    SectorColor.NONE: "",
}


def _fmt_sector(val: float | None, color: SectorColor) -> str:
    if val is None:
        return "—"
    style = _COLOR_CSS.get(color, "")
    return f'<span style="padding:2px 6px;{style}">{val:.3f}</span>'


def render_leaderboard(field: FieldState | None) -> None:
    if field is None or not field.driver_views:
        st.info("Waiting for race data…")
        return

    st.caption(
        f"Lap {field.index.lap_number}/{field.total_laps} · "
        f"Sector {field.index.sector_idx}/3"
    )

    rows_html = []
    for view in field.driver_views[:20]:
        s = view.standing
        last = f"{s.last_lap_s:.3f}s" if s.last_lap_s else "—"
        rows_html.append(
            f"<tr>"
            f"<td>{s.position}</td>"
            f"<td><b>{s.code}</b></td>"
            f"<td>{s.team or ''}</td>"
            f"<td>{s.gap_to_leader_s:.1f}s</td>"
            f"<td>{_fmt_sector(s.sector_1_s, view.s1_color)}</td>"
            f"<td>{_fmt_sector(s.sector_2_s, view.s2_color)}</td>"
            f"<td>{_fmt_sector(s.sector_3_s, view.s3_color)}</td>"
            f"<td>{last}</td>"
            f"</tr>"
        )

    html = (
        "<table style='width:100%;font-size:0.85em;border-collapse:collapse'>"
        "<tr><th>Pos</th><th>Driver</th><th>Team</th><th>Gap</th>"
        "<th>S1</th><th>S2</th><th>S3</th><th>Last</th></tr>"
        + "".join(rows_html)
        + "</table>"
    )
    st.markdown(html, unsafe_allow_html=True)

    fastest = field.fastest_sectors
    if fastest:
        badges = " · ".join(f"S{k}: {v}" for k, v in fastest.items())
        st.caption(f"Fastest sectors — {badges}")
