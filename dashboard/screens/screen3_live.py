"""Screen 3 — Live race cockpit."""

from __future__ import annotations

import streamlit as st

from aris.field.sectors import SectorColor, color_sector_time
from aris.physics.tires import DEFAULT_COMPOUND_SLOPE
from dashboard.components.chat_panel import render_chat_panel
from dashboard.components.lap_chart import plot_stint_bars
from dashboard.components.tyre_card import render_pit_window, render_tyre_card
from dashboard.utils.fastf1_loader import format_lap_time, get_driver_laps, load_race_session
from dashboard.utils.monte_carlo import TYRE_LIFE_ESTIMATE
from dashboard.utils.race_state import (
    build_race_state,
    compute_standings_at_lap,
    get_stint_info,
    predict_for_lap,
)

SECTOR_COLOR_MAP = {
    SectorColor.PURPLE: "#9B85FF",
    SectorColor.GREEN: "#4CAF50",
    SectorColor.YELLOW: "#F5A623",
    SectorColor.NONE: "#888884",
}


def _format_gap(gap: float | None, leader: bool = False) -> str:
    if leader:
        return "LEADER"
    if gap is None:
        return "—"
    return f"+{gap:.1f}s"


def render() -> None:
    driver = st.session_state.get("selected_driver")
    race = st.session_state.get("selected_race")
    strategy = st.session_state.get("selected_strategy")
    if not driver or not race:
        st.warning("Complete setup and strategy first.")
        if st.button("← Back"):
            st.session_state["screen"] = 0
            st.rerun()
        return

    total_laps = race.get("total_laps", 57)
    session_data = load_race_session(race["year"], race["round"])
    laps_df = session_data.get("laps")
    if laps_df is None or laps_df.empty:
        st.error("No lap data available.")
        return

    if "current_lap" not in st.session_state:
        st.session_state["current_lap"] = min(38, total_laps)
    if "pit_decisions" not in st.session_state:
        st.session_state["pit_decisions"] = []

    current_lap = st.session_state["current_lap"]
    driver_code = driver["code"]
    driver_laps = get_driver_laps(laps_df, driver_code)
    max_lap = int(driver_laps["lap_number"].max()) if not driver_laps.empty else total_laps
    current_lap = min(current_lap, max_lap, total_laps)

    weather = session_data.get("weather", {})
    mc_probs = {
        "p1": strategy.get("p1_prob", 0.68) if strategy else 0.68,
        "p2": strategy.get("p2_prob", 0.24) if strategy else 0.24,
        "p3_plus": strategy.get("p3_plus_prob", 0.08) if strategy else 0.08,
    }
    race_state = build_race_state(
        laps_df=laps_df,
        driver_code=driver_code,
        current_lap=current_lap,
        total_laps=total_laps,
        country=race.get("country", "Bahrain"),
        strategy=strategy,
        mc_probs=mc_probs,
        weather=weather,
    )
    stint = get_stint_info(strategy, current_lap)
    preds = predict_for_lap(driver_laps, current_lap, total_laps=total_laps)
    standings = compute_standings_at_lap(laps_df, current_lap)
    my_row = next((r for r in standings if r["driver"] == driver_code), None)

    # --- Top bar ---
    t1, t2, t3 = st.columns([2, 3, 1])
    with t2:
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:1rem;justify-content:center;">
                <span class="aris-badge-live">● LIVE</span>
                <span style="background:#111;padding:0.3rem 0.8rem;border-radius:4px;font-size:0.8rem;">
                    LAP {current_lap} / {total_laps}
                </span>
                <span style="background:#111;padding:0.3rem 0.8rem;border-radius:4px;font-size:0.8rem;color:#888884;">
                    {race['name'].upper()} {race['year']}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with t3:
        st.markdown('<div class="aris-pit-now">', unsafe_allow_html=True)
        if st.button("PIT NOW", key="pit_now"):
            st.session_state["pit_decisions"].append({"lap": current_lap, "compound": "HARD"})
            st.toast(f"Pit recorded at lap {current_lap}")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Status bar ---
    pos = my_row["pos"] if my_row else 1
    gap_behind_drv = "—"
    if my_row and my_row.get("gap_behind_s"):
        behind_idx = pos
        if behind_idx < len(standings):
            gap_behind_drv = standings[pos]["driver"] if pos < len(standings) else "LEC"
    gap_behind = my_row.get("gap_behind_s") if my_row else 4.2
    from aris.models.features import estimate_fuel_kg

    fuel = estimate_fuel_kg(current_lap, total_laps=total_laps)
    track_temp = weather.get("track_temp_c", 42)
    st.markdown(
        f"""
        <div class="aris-card" style="display:flex;gap:2rem;padding:0.5rem 1rem;margin:0.5rem 0;font-size:0.75rem;flex-wrap:wrap;">
            <span><span style="color:#888884;">Pos</span> <span style="color:#E8002D;font-weight:bold;">P{pos}</span></span>
            <span><span style="color:#888884;">Gap ahead</span> <span style="color:#FAFAF8;">LEADER</span></span>
            <span><span style="color:#888884;">Gap behind</span> <span style="color:#F5A623;">+{gap_behind:.1f}s {gap_behind_drv}</span></span>
            <span><span style="color:#888884;">Tyre</span> <span style="color:#F5A623;">{stint['compound'].title()} · {stint['laps_on_tyre']} laps</span></span>
            <span><span style="color:#888884;">Fuel</span> <span style="color:#FAFAF8;">~{fuel:.0f} kg</span></span>
            <span><span style="color:#888884;">Track temp</span> <span style="color:#F5A623;">{track_temp:.0f}°C</span></span>
            <span><span style="color:#888884;">Strategy</span> <span style="color:#4CAF50;">On plan</span></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Lap controls
    lcol1, lcol2, lcol3, lcol4 = st.columns([1, 1, 1, 3])
    with lcol1:
        if st.button("◀ Lap", disabled=current_lap <= 1):
            st.session_state["current_lap"] = current_lap - 1
            st.rerun()
    with lcol2:
        if st.button("Lap ▶", disabled=current_lap >= max_lap):
            st.session_state["current_lap"] = current_lap + 1
            st.rerun()
    with lcol3:
        st.caption(f"Replay lap {current_lap}/{max_lap}")

    # --- Three columns ---
    left_col, center_col, right_col = st.columns([1, 2, 1.2])

    compound = stint["compound"]
    deg_rate = DEFAULT_COMPOUND_SLOPE.get(compound, 0.05)
    max_life = TYRE_LIFE_ESTIMATE.get(compound, 34)
    pit_laps = strategy.get("pit_laps", [41, 44]) if strategy else [41, 44]
    pw_open = pit_laps[0] if pit_laps else 40
    pw_close = pit_laps[-1] + 3 if pit_laps else 44

    with left_col:
        render_tyre_card(compound, stint["stint_num"], stint["laps_on_tyre"], max_life, deg_rate, cliff_lap=45)
        render_pit_window(current_lap, total_laps, pw_open, pw_close, pw_open)

        st.markdown('<div style="font-size:0.65rem;color:#888884;margin-top:0.75rem;">KEY METRICS</div>', unsafe_allow_html=True)
        aris_pred = preds.get("aris_pred")
        actual = preds.get("actual")
        ml_res = preds.get("ml_residual", 0)
        race_mae = race_state.get("race_mae")
        metrics = [
            ("ARIS pred", format_lap_time(aris_pred), "#FAFAF8"),
            ("Actual", format_lap_time(actual), "#FAFAF8"),
            ("ML residual", f"{ml_res:+.3f}s", "#4CAF50" if ml_res and ml_res < 0 else "#F5A623"),
            ("Race MAE", f"{race_mae:.2f}s" if race_mae else "—", "#F5A623"),
            ("P1 prob", f"{mc_probs['p1']:.0%}", "#4CAF50"),
        ]
        for label, val, color in metrics:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;font-size:0.7rem;padding:0.2rem 0;">'
                f'<span style="color:#888884;">{label}</span>'
                f'<span style="color:{color};">{val}</span></div>',
                unsafe_allow_html=True,
            )

    with center_col:
        hero_time = format_lap_time(aris_pred) if aris_pred else "—"
        ml_txt = f"ML correction {ml_res:+.3f}s" if ml_res else ""
        st.markdown(
            f'<div style="text-align:center;margin:1rem 0;">'
            f'<div style="font-size:2.8rem;color:#FAFAF8;font-weight:bold;">{hero_time}</div>'
            f'<div style="font-size:0.65rem;color:#888884;">ARIS prediction · {ml_txt}</div></div>',
            unsafe_allow_html=True,
        )

        # Sectors
        lap_row = driver_laps[driver_laps["lap_number"] == current_lap]
        session_bests = {}
        for sector in (1, 2, 3):
            col = f"sector_{sector}_s"
            if col in laps_df.columns:
                subset = laps_df[laps_df["lap_number"] <= current_lap][col].dropna()
                if not subset.empty:
                    session_bests[sector] = float(subset.min())

        personal_bests = {}
        prior = driver_laps[driver_laps["lap_number"] < current_lap]
        for sector in (1, 2, 3):
            col = f"sector_{sector}_s"
            if col in prior.columns:
                vals = prior[col].dropna()
                if not vals.empty:
                    personal_bests[sector] = float(vals.min())

        scols = st.columns(3)
        sector_times = []
        if not lap_row.empty:
            lr = lap_row.iloc[0]
            sector_times = [
                lr.get("sector_1_s"), lr.get("sector_2_s"), lr.get("sector_3_s"),
            ]
        for i, scol in enumerate(scols, start=1):
            st_val = sector_times[i - 1] if i - 1 < len(sector_times) else None
            color_enum = color_sector_time(
                st_val, sector_idx=i,
                session_bests=session_bests, personal_bests=personal_bests,
            )
            color = SECTOR_COLOR_MAP[color_enum]
            pb_label = '<div style="font-size:0.55rem;color:#9B85FF;">personal best</div>' if color_enum == SectorColor.PURPLE else ""
            st_val_fmt = f"{st_val:.3f}" if st_val else "—"
            scol.markdown(
                f'<div class="aris-card" style="text-align:center;padding:0.5rem;">'
                f'<div style="font-size:0.6rem;color:#888884;">S{i}</div>'
                f'<div style="color:{color};font-size:1rem;">{st_val_fmt}</div>{pb_label}</div>',
                unsafe_allow_html=True,
            )

        # Stint lap chart
        stint_start = stint.get("stint_start", 1)
        stint_laps_df = driver_laps[
            (driver_laps["lap_number"] >= stint_start) & (driver_laps["lap_number"] <= current_lap)
        ]
        actual_laps = stint_laps_df["lap_number"].tolist()
        actual_times = stint_laps_df["lap_time_s"].dropna().tolist()
        fig = plot_stint_bars(actual_laps, actual_times, title=f"LAP HISTORY — STINT {stint['stint_num']}")
        st.pyplot(fig, use_container_width=True)

        # Strategy strip
        if strategy:
            pills_html = []
            compounds = strategy.get("compounds", [])
            stint_laps_list = strategy.get("stint_laps", [])
            colors = {"SOFT": "#E8002D", "MEDIUM": "#F5A623", "HARD": "#888884"}
            for idx, (comp, laps_count) in enumerate(zip(compounds, stint_laps_list, strict=False)):
                c = colors.get(comp, "#888884")
                highlight = "border:2px solid #F5A623;" if idx + 1 == stint["stint_num"] else ""
                check = " ✓" if idx + 1 < stint["stint_num"] else (" → NOW" if idx + 1 == stint["stint_num"] else "")
                pills_html.append(
                    f'<span style="background:{c}22;border:1px solid {c};{highlight}'
                    f'padding:4px 10px;border-radius:3px;font-size:0.65rem;margin-right:6px;color:{c};">'
                    f'{comp[:1]} x {laps_count}{check}</span>'
                )
            st.markdown(
                f'<div style="font-size:0.65rem;color:#888884;margin:0.5rem 0;">RACE STRATEGY — LIVE</div>'
                f'<div>{"".join(pills_html)}</div>',
                unsafe_allow_html=True,
            )

        # MC strip
        remaining = total_laps - current_lap
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.75rem;font-size:0.7rem;">'
            f'<span style="color:#888884;">Monte Carlo · remaining {remaining} laps</span>'
            f'<span><span style="color:#4CAF50;">P1: {mc_probs["p1"]:.0%}</span> · '
            f'<span style="color:#F5A623;">P2: {mc_probs["p2"]:.0%}</span> · '
            f'<span style="color:#888884;">P3+: {mc_probs["p3_plus"]:.0%}</span></span>'
            f'<span style="color:#E8002D;">Undercut risk / LEC in 3 laps</span></div>',
            unsafe_allow_html=True,
        )

    with right_col:
        render_chat_panel(race_state, current_lap)

    # Bottom nav
    st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
    nav1, nav2, nav3 = st.columns([1, 1, 4])
    with nav1:
        if st.button("← Strategy"):
            st.session_state["screen"] = 1
            st.rerun()
    with nav2:
        if st.button("Timing tower →"):
            st.session_state["screen"] = 3
            st.rerun()

    st.markdown(
        '<div style="font-size:0.55rem;color:#888884;text-align:center;margin-top:1rem;">'
        'MODEL: XGBoost residual + bicycle physics · NARRATION: Llama 3.1 local · '
        'DATA: FastF1 live · BUILD: v0.3-predictor</div>',
        unsafe_allow_html=True,
    )
