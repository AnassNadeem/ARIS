"""Screen 4 — Timing tower."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from aris.field.sectors import SectorColor, color_sector_time, driver_personal_bests
from dashboard.components.lap_chart import plot_gap_chart
from dashboard.components.tyre_card import render_tyre_dot
from dashboard.utils.fastf1_loader import format_lap_time, load_race_session
from dashboard.utils.race_state import compute_standings_at_lap

SECTOR_CSS = {
    SectorColor.PURPLE: "#9B85FF",
    SectorColor.GREEN: "#4CAF50",
    SectorColor.YELLOW: "#F5A623",
    SectorColor.NONE: "#888884",
}

TEAM_COLORS = {
    "VER": "#3671C6", "PER": "#3671C6", "LEC": "#E8002D", "SAI": "#E8002D",
    "HAM": "#27F4D2", "RUS": "#27F4D2", "NOR": "#FF8000", "PIA": "#FF8000",
    "ALO": "#229971", "STR": "#229971",
}


def _session_sector_bests(laps_df: pd.DataFrame, through_lap: int) -> dict[int, float]:
    bests: dict[int, float] = {}
    subset = laps_df[laps_df["lap_number"] <= through_lap]
    for sector in (1, 2, 3):
        col = f"sector_{sector}_s"
        if col in subset.columns:
            vals = subset[col].dropna()
            if not vals.empty:
                bests[sector] = float(vals.min())
    return bests


def render() -> None:
    driver = st.session_state.get("selected_driver")
    race = st.session_state.get("selected_race")
    if not driver or not race:
        st.warning("Complete session setup first.")
        return

    total_laps = race.get("total_laps", 57)
    current_lap = st.session_state.get("current_lap", min(38, total_laps))

    session_data = load_race_session(race["year"], race["round"])
    laps_df = session_data.get("laps")
    if laps_df is None or laps_df.empty:
        st.error("No lap data.")
        return

    # Header
    h1, h2 = st.columns([2, 2])
    with h2:
        st.markdown(
            f"""
            <div style="display:flex;gap:0.5rem;justify-content:flex-end;align-items:center;">
                <span class="aris-badge-live">● LIVE</span>
                <span style="background:#111;padding:0.25rem 0.6rem;border-radius:4px;font-size:0.75rem;">
                    LAP {current_lap} / {total_laps}
                </span>
                <span style="background:#111;padding:0.25rem 0.6rem;border-radius:4px;font-size:0.75rem;">
                    {race['name'].upper()} {race['year']}
                </span>
                <span style="background:#4CAF5033;color:#4CAF50;padding:0.25rem 0.6rem;border-radius:4px;font-size:0.7rem;">
                    DRS OPEN
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    standings = compute_standings_at_lap(laps_df, current_lap)
    session_bests = _session_sector_bests(laps_df, current_lap)
    my_code = driver["code"]

    # Fastest lap
    fastest_lap = None
    fastest_driver = None
    fastest_lap_no = None
    for drv, grp in laps_df.groupby("driver"):
        valid = grp["lap_time_s"].dropna()
        if valid.empty:
            continue
        best = valid.min()
        if fastest_lap is None or best < fastest_lap:
            fastest_lap = best
            fastest_driver = drv
            fastest_lap_no = int(grp.loc[grp["lap_time_s"].idxmin(), "lap_number"])

    # Best sectors
    best_sector_holders: dict[int, tuple[str, float]] = {}
    for sector in (1, 2, 3):
        col = f"sector_{sector}_s"
        if col not in laps_df.columns:
            continue
        subset = laps_df[laps_df["lap_number"] <= current_lap]
        idx = subset[col].idxmin()
        if pd.notna(idx):
            row = subset.loc[idx]
            best_sector_holders[sector] = (str(row["driver"]), float(row[col]))

    main_col, side_col = st.columns([3, 1])

    with main_col:
        # Table header
        st.markdown(
            """
            <div style="display:grid;grid-template-columns:40px 50px 1fr 80px 70px 70px 70px 90px 90px;
                        font-size:0.6rem;color:#888884;padding:0.4rem 0;border-bottom:0.5px solid #1e1e1e;">
                <span>POS</span><span>CAR</span><span>DRIVER</span><span>INTERVAL</span>
                <span>S1</span><span>S2</span><span>S3</span><span>TYRE · AGE</span><span>LAST LAP</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for row in standings[:10]:
            is_me = row["driver"] == my_code
            bg = "background:#E8002D08;" if is_me else ""
            border = "border-left:2px solid #E8002D;" if is_me else ""
            interval = "LEADER" if row["pos"] == 1 else f"+{row['gap_s']:.1f}s"
            interval_color = "#FAFAF8" if row["pos"] == 1 else ("#F5A623" if row["gap_s"] < 5 else "#888884")

            lap_row = laps_df[
                (laps_df["driver"] == row["driver"]) & (laps_df["lap_number"] == current_lap)
            ]
            drv_laps = laps_df[laps_df["driver"] == row["driver"]].sort_values("lap_number")
            personal_bests = driver_personal_bests(
                drv_laps.rename(columns={"lap_number": "lap_number"}),
                current_lap + 1,
            )

            if lap_row.empty:
                s1_html = s2_html = s3_html = '<span style="color:#888884;">—</span>'
            else:
                lr = lap_row.iloc[0]
                sector_spans = []
                for si in (1, 2, 3):
                    val = lr.get(f"sector_{si}_s")
                    if val is not None and not pd.isna(val):
                        c = color_sector_time(
                            float(val), sector_idx=si,
                            session_bests=session_bests, personal_bests=personal_bests,
                        )
                        sector_spans.append(f'<span style="color:{SECTOR_CSS[c]};">{float(val):.3f}</span>')
                    else:
                        sector_spans.append('<span style="color:#888884;">—</span>')
                s1_html, s2_html, s3_html = sector_spans

            compound = row.get("compound", "MEDIUM")
            tyre_age = row.get("tyre_life", 0)
            tyre_html = render_tyre_dot(compound, tyre_age)
            last_lap = row.get("last_lap_s")
            last_fmt = format_lap_time(last_lap)
            fl_badge = ""
            if fastest_driver == row["driver"] and last_lap and abs(last_lap - fastest_lap) < 0.001:
                fl_badge = ' <span style="color:#9B85FF;font-size:0.55rem;">FL</span>'

            st.markdown(
                f"""
                <div style="display:grid;grid-template-columns:40px 50px 1fr 80px 70px 70px 70px 90px 90px;
                            font-size:0.7rem;padding:0.35rem 0;border-bottom:0.5px solid #1e1e1e;{bg}{border}">
                    <span style="color:{'#E8002D' if is_me else '#FAFAF8'};">{row['pos']}</span>
                    <span style="color:#888884;">{row['driver']}</span>
                    <span style="color:#FAFAF8;">{row['driver']}</span>
                    <span style="color:{interval_color};">{interval}</span>
                    <span>{s1_html}</span>
                    <span>{s2_html}</span>
                    <span>{s3_html}</span>
                    <span>{tyre_html}</span>
                    <span style="color:#FAFAF8;">{last_fmt}{fl_badge}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div style="font-size:0.6rem;color:#888884;margin-top:0.5rem;">'
            '● Purple = fastest · ● Green = personal best · ● S=Soft M=Med H=Hard</div>'
            '<div style="font-size:0.6rem;color:#888884;">P11-P20 hidden · scroll to expand</div>',
            unsafe_allow_html=True,
        )

    with side_col:
        # Fastest lap card
        if fastest_lap:
            fl_row = laps_df[
                (laps_df["driver"] == fastest_driver) & (laps_df["lap_number"] == fastest_lap_no)
            ]
            s1 = s2 = s3 = "—"
            if not fl_row.empty:
                fr = fl_row.iloc[0]
                s1 = f"{fr.get('sector_1_s', 0):.3f}" if pd.notna(fr.get("sector_1_s")) else "—"
                s2 = f"{fr.get('sector_2_s', 0):.3f}" if pd.notna(fr.get("sector_2_s")) else "—"
                s3 = f"{fr.get('sector_3_s', 0):.3f}" if pd.notna(fr.get("sector_3_s")) else "—"
            st.markdown(
                f'<div class="aris-card" style="padding:0.75rem;margin-bottom:0.75rem;">'
                f'<div style="font-size:0.6rem;color:#888884;">FASTEST LAP</div>'
                f'<div style="font-size:1.4rem;color:#9B85FF;">{format_lap_time(fastest_lap)}</div>'
                f'<div style="font-size:0.65rem;color:#888884;">{fastest_driver} Lap {fastest_lap_no}</div>'
                f'<div style="font-size:0.6rem;color:#9B85FF;margin-top:0.3rem;">S1 {s1} · S2 {s2} · S3 {s3}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div style="font-size:0.6rem;color:#888884;">BEST SECTORS</div>', unsafe_allow_html=True)
        for si in (1, 2, 3):
            if si in best_sector_holders:
                code, t = best_sector_holders[si]
                st.markdown(
                    f'<div style="font-size:0.65rem;"><span style="color:#888884;">S{si}</span> '
                    f'<span style="color:#9B85FF;">{code}</span> <span style="color:#9B85FF;">{t:.3f}</span></div>',
                    unsafe_allow_html=True,
                )

        # Tyre age extremes
        oldest = max(standings, key=lambda r: r.get("tyre_life", 0), default=None)
        freshest = min(standings, key=lambda r: r.get("tyre_life", 99), default=None)
        my_tyre = next((r for r in standings if r["driver"] == my_code), None)
        st.markdown('<div style="font-size:0.6rem;color:#888884;margin-top:0.75rem;">TYRE AGE LEADERS</div>', unsafe_allow_html=True)
        if oldest:
            st.markdown(f'<div style="font-size:0.65rem;color:#888884;">Oldest: {oldest["driver"]} {oldest["tyre_life"]}L {oldest["compound"][:1]}</div>', unsafe_allow_html=True)
        if freshest:
            st.markdown(f'<div style="font-size:0.65rem;color:#888884;">Freshest: {freshest["driver"]} {freshest["tyre_life"]}L {freshest["compound"][:1]}</div>', unsafe_allow_html=True)
        if my_tyre:
            st.markdown(f'<div style="font-size:0.65rem;color:#888884;">Your tyre: {my_tyre["driver"]} {my_tyre["tyre_life"]}L {my_tyre["compound"][:1]}</div>', unsafe_allow_html=True)

        # Gap chart
        top5 = [(r["driver"], r["gap_s"], TEAM_COLORS.get(r["driver"], "#888884")) for r in standings[:5]]
        if top5:
            fig = plot_gap_chart(top5)
            st.pyplot(fig, use_container_width=True)

        st.markdown(
            '<div class="aris-card" style="padding:0.5rem;margin-top:0.5rem;">'
            '<span style="color:#4CAF50;font-size:0.7rem;">● Clear</span><br>'
            '<span style="font-size:0.6rem;color:#888884;">SC prob remaining: 14%</span></div>',
            unsafe_allow_html=True,
        )

    # Bottom nav
    nav1, nav2 = st.columns([1, 4])
    with nav1:
        if st.button("← Live race"):
            st.session_state["screen"] = 2
            st.rerun()
