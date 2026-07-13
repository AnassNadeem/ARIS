"""Screen 2 — Strategy builder."""

from __future__ import annotations

import streamlit as st

from dashboard.components.lap_chart import plot_lap_trace, plot_temp_forecast
from dashboard.components.strategy_card import render_strategy_card
from dashboard.utils.fastf1_loader import load_race_session
from dashboard.utils.monte_carlo import (
    SAFETY_CAR_PROB,
    run_strategy_mc,
    tyre_info_table,
    predict_lap_trace,
)


def render() -> None:
    driver = st.session_state.get("selected_driver")
    race = st.session_state.get("selected_race")
    if not driver or not race:
        st.warning("Complete session setup first.")
        if st.button("← Back to selection"):
            st.session_state["screen"] = 0
            st.rerun()
        return

    total_laps = race.get("total_laps", 57)
    country = race.get("country", "Bahrain")

    # Load session
    session_data = load_race_session(race["year"], race["round"])
    weather = session_data.get("weather", {})
    track_temp = weather.get("track_temp_c", 38)
    humidity = weather.get("humidity_pct", 22)
    wind = weather.get("wind_speed", 8)
    rain_risk = 2 if not weather.get("rainfall") else 35
    temps = weather.get("track_temps", [])

    # Context strip
    st.markdown(
        f"""
        <div class="aris-card" style="padding:0.5rem 0.75rem;margin-bottom:1rem;font-size:0.7rem;">
            <span style="color:#888884;">{driver['code']} — {driver['team']}</span> &nbsp;|&nbsp;
            <span style="color:#FAFAF8;">{race['name']} · {total_laps} Laps</span> &nbsp;|&nbsp;
            Start tyre: <span style="color:#E8002D;">● Soft</span> &nbsp;|&nbsp;
            Track temp: <span style="color:#F5A623;">{track_temp:.0f}°C</span> &nbsp;|&nbsp;
            Rain risk: <span style="background:#4CAF5033;color:#4CAF50;padding:1px 6px;border-radius:3px;">{rain_risk}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Weather strip
    st.markdown('<div style="font-size:0.65rem;color:#888884;">WEATHER FORECAST · RACE WINDOW</div>', unsafe_allow_html=True)
    wcol1, wcol2, wcol3 = st.columns([2, 4, 1])
    with wcol1:
        st.markdown(
            f'<div style="font-size:0.75rem;color:#FAFAF8;">☀ {track_temp:.0f}°C Track<br>'
            f'<span style="color:#888884;">Humidity {humidity:.0f}% · Wind {wind:.0f} km/h NE</span></div>',
            unsafe_allow_html=True,
        )
    with wcol2:
        fig = plot_temp_forecast(temps, total_laps)
        st.pyplot(fig, use_container_width=True)
    with wcol3:
        risk_color = "#4CAF50" if rain_risk < 10 else "#F5A623"
        st.markdown(
            f'<div style="background:{risk_color}33;color:{risk_color};padding:0.4rem;border-radius:4px;'
            f'font-size:0.65rem;text-align:center;">{"Low rain risk" if rain_risk < 10 else "Rain risk"}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="font-size:0.65rem;color:#888884;margin:1rem 0 0.5rem;">TOP 3 STRATEGIES · ARIS RECOMMENDED</div>', unsafe_allow_html=True)

    # MC simulation
    if "mc_results" not in st.session_state or st.session_state.get("mc_race_key") != f"{race['year']}_{race['round']}":
        with st.spinner("Running 1000 Monte Carlo simulations…"):
            results = run_strategy_mc(total_laps=total_laps, country=country, n_sims=1000)
        st.session_state["mc_results"] = results
        st.session_state["mc_race_key"] = f"{race['year']}_{race['round']}"

    results = st.session_state["mc_results"]
    selected_id = st.session_state.get("selected_strategy", {}).get("id") if st.session_state.get("selected_strategy") else None

    cols = st.columns(3)
    for i, (col, result) in enumerate(zip(cols, results, strict=False)):
        with col:
            if render_strategy_card(result, i, selected_id):
                st.session_state["selected_strategy"] = {
                    "id": result.strategy.id,
                    "name": result.strategy.name,
                    "compounds": result.strategy.compounds,
                    "pit_laps": result.strategy.pit_laps,
                    "stint_laps": result.strategy.stint_laps,
                    "p1_prob": result.p1_prob,
                    "p2_prob": result.p2_prob,
                    "p3_plus_prob": result.p3_plus_prob,
                }
                st.rerun()

    # Default select recommended if none chosen
    if not st.session_state.get("selected_strategy") and results:
        top = results[0]
        st.session_state["selected_strategy"] = {
            "id": top.strategy.id,
            "name": top.strategy.name,
            "compounds": top.strategy.compounds,
            "pit_laps": top.strategy.pit_laps,
            "stint_laps": top.strategy.stint_laps,
            "p1_prob": top.p1_prob,
            "p2_prob": top.p2_prob,
            "p3_plus_prob": top.p3_plus_prob,
        }

    selected = st.session_state.get("selected_strategy", {})
    sel_result = next((r for r in results if r.strategy.id == selected.get("id")), results[0])

    # Main content: chart + sidebar
    main_col, side_col = st.columns([3, 1])
    with main_col:
        st.markdown(
            f'<div style="font-size:0.65rem;color:#888884;">PREDICTED LAP TIME TRACE · {total_laps} LAPS · {selected.get("name", "").upper()}</div>',
            unsafe_allow_html=True,
        )
        laps, times, pit_markers = predict_lap_trace(sel_result.strategy, total_laps)
        fig = plot_lap_trace(laps, times, pit_markers, title="")
        st.pyplot(fig, use_container_width=True)

    with side_col:
        st.markdown('<div style="font-size:0.65rem;color:#888884;">TYRE INFO — BAHRAIN</div>', unsafe_allow_html=True)
        for row in tyre_info_table():
            st.markdown(
                f'<div style="font-size:0.65rem;color:#888884;margin:0.3rem 0;">'
                f'<span style="color:#FAFAF8;">{row["compound"].title()}</span> life: {row["life_laps"]} · '
                f'Deg: {row["deg_rate"]}</div>',
                unsafe_allow_html=True,
            )
        st.markdown('<div style="font-size:0.65rem;color:#888884;margin-top:1rem;">SAFETY CAR RISK</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:0.75rem;color:#FAFAF8;">{SAFETY_CAR_PROB:.0%} per race</div>'
            f'<div style="background:#1e1e1e;height:4px;border-radius:2px;margin:0.3rem 0;">'
            f'<div style="background:#F5A623;width:{SAFETY_CAR_PROB*100:.0f}%;height:4px;"></div></div>'
            f'<div style="font-size:0.6rem;color:#888884;">Simulation accounts for SC probability</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="font-size:0.65rem;color:#888884;margin-top:1rem;">UNDERCUT WINDOW</div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:0.65rem;color:#888884;">vs Leclerc (P2 · S)<br>'
            'Gap &lt; 3s on L15-20<br>Undercut viable if gap ≤ pit delta</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="font-size:0.65rem;color:#888884;margin-top:1rem;">MODEL INFO</div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:0.6rem;color:#888884;">XGBoost residual on bicycle model · '
            '1000 MC sims · race-CV MAE 0.38s</div>',
            unsafe_allow_html=True,
        )

    # Bottom bar
    st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)
    pit_str = ", ".join(str(p) for p in selected.get("pit_laps", []))
    compounds_str = " → ".join(selected.get("compounds", []))
    b1, b2, b3 = st.columns([4, 1, 1])
    with b1:
        st.markdown(
            f'<div style="font-size:0.75rem;color:#888884;">Strategy selected — '
            f'<span style="color:#FAFAF8;">{selected.get("name", "")} · {compounds_str} · Pit laps {pit_str}</span></div>',
            unsafe_allow_html=True,
        )
    with b2:
        if st.button("← Back"):
            st.session_state["screen"] = 0
            st.rerun()
    with b3:
        if st.button("Start race →", type="primary"):
            st.session_state["screen"] = 2
            st.session_state["current_lap"] = 1
            st.session_state["pit_decisions"] = []
            st.rerun()
