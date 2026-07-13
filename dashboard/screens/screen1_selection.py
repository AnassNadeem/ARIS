"""Screen 1 — Race & driver selection."""

from __future__ import annotations

import streamlit as st

from dashboard.utils.fastf1_loader import (
    DRIVERS_2025,
    check_session_available,
    get_event_schedule,
)


def _weather_badge(weather: str) -> str:
    cls = {"Dry": "aris-badge-dry", "Wet": "aris-badge-wet", "Mixed": "aris-badge-mixed"}.get(weather, "aris-badge-dry")
    return f'<span class="{cls}">{weather}</span>'


def render() -> None:
    st.markdown(
        '<div style="text-align:right;font-size:0.65rem;color:#888884;">SESSION SETUP</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 1], gap="large")

    # --- Driver panel ---
    with left:
        st.markdown('<div style="font-size:0.7rem;color:#888884;margin-bottom:0.5rem;">CHOOSE DRIVER</div>', unsafe_allow_html=True)
        search = st.text_input("Search driver", placeholder="Search driver…", label_visibility="collapsed", key="driver_search")
        query = search.strip().lower()
        drivers = [
            d for d in DRIVERS_2025
            if not query or query in d["name"].lower() or query in d["code"].lower() or query in d["team"].lower()
        ]
        selected_driver = st.session_state.get("selected_driver")
        for i in range(0, len(drivers), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(drivers):
                    break
                d = drivers[idx]
                is_sel = selected_driver and selected_driver.get("code") == d["code"]
                border = "1.5px solid #E8002D" if is_sel else "0.5px solid #1e1e1e"
                badge = f'<span style="background:#E8002D33;color:#E8002D;font-size:0.55rem;padding:1px 4px;border-radius:2px;">{d["badge"]}</span>' if d.get("badge") else ""
                col.markdown(
                    f"""
                    <div class="aris-card" style="border:{border};margin-bottom:0.5rem;cursor:pointer;">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                            <span style="color:{d['color']};font-size:1.1rem;font-weight:bold;">{d['number']}</span>
                            {badge}
                        </div>
                        <div style="color:#FAFAF8;font-size:0.85rem;margin-top:0.3rem;">{d['name']}</div>
                        <div style="color:#888884;font-size:0.65rem;">{d['team']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if col.button(f"Select {d['code']}", key=f"drv_{d['code']}"):
                    st.session_state["selected_driver"] = d
                    st.rerun()

    # --- Race panel ---
    with right:
        st.markdown('<div style="font-size:0.7rem;color:#888884;margin-bottom:0.5rem;">CHOOSE RACE</div>', unsafe_allow_html=True)
        season_tabs = st.columns(3)
        seasons = [2025, 2024, 2023]
        if "selected_season" not in st.session_state:
            st.session_state["selected_season"] = 2025
        for col, yr in zip(season_tabs, seasons, strict=True):
            style = "primary" if st.session_state["selected_season"] == yr else "secondary"
            if col.button(str(yr), key=f"season_{yr}", type=style):
                st.session_state["selected_season"] = yr
                st.rerun()

        year = st.session_state["selected_season"]
        try:
            schedule = get_event_schedule(year)
        except Exception as exc:
            st.warning(f"Could not load {year} schedule: {exc}")
            schedule = get_event_schedule(2024)

        selected_race = st.session_state.get("selected_race")
        for _, race in schedule.iterrows():
            is_sel = selected_race and selected_race.get("round") == race["round"] and selected_race.get("year") == year
            border = "1.5px solid #E8002D" if is_sel else "0.5px solid #1e1e1e"
            temp_extra = ' · <span style="color:#F5A623;">38°C</span>' if is_sel else ""
            wbadge = _weather_badge(race["weather"])
            date_short = race["date"][5:].replace("-", " ") if race["date"] else ""
            if len(date_short) >= 5:
                parts = race["date"].split("-")
                if len(parts) == 3:
                    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    date_short = f"{int(parts[2])} {months[int(parts[1])]}"

            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"""
                    <div class="aris-card" style="border:{border};margin-bottom:0.4rem;padding:0.5rem 0.75rem;">
                        <div style="display:flex;align-items:center;gap:0.75rem;font-size:0.75rem;">
                            <span style="color:#888884;">R{race['round']:02d}</span>
                            <span>{race['flag']}</span>
                            <span style="color:#FAFAF8;">{race['name']}</span>
                            <span style="color:#888884;">{date_short}</span>
                            {wbadge}{temp_extra}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("Pick", key=f"race_{year}_{race['round']}"):
                    from aris.tracks import load_track_config

                    try:
                        cfg = load_track_config(str(race["country"]))
                        laps = cfg.total_laps
                        circuit = cfg.name
                    except Exception:
                        laps = 57
                        circuit = str(race["country"])
                    st.session_state["selected_race"] = {
                        "year": year,
                        "round": int(race["round"]),
                        "country": str(race["country"]),
                        "name": str(race["name"]),
                        "weather": str(race["weather"]),
                        "flag": str(race["flag"]),
                        "total_laps": laps,
                        "circuit": circuit,
                        "date": str(race["date"]),
                    }
                    st.rerun()

    # --- Bottom confirmation bar ---
    st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
    driver = st.session_state.get("selected_driver")
    race = st.session_state.get("selected_race")

    if driver and race:
        ok, status = check_session_available(race["year"], race["round"])
        status_color = "#4CAF50" if ok else "#F5A623"
        status_txt = "ready" if ok else status[:30]
        cond_color = "#F5A623" if race.get("weather") == "Dry" else "#64B5F6"
        bar = st.container()
        with bar:
            bcol1, bcol2, bcol3 = st.columns([4, 1, 1])
            with bcol1:
                st.markdown(
                    f"""
                    <div style="background:#111;border-top:0.5px solid #1e1e1e;padding:0.75rem 0;font-size:0.75rem;">
                        <span style="color:#888884;">Driver:</span> <span style="color:#FAFAF8;">{driver['name']} · #{driver['number']}</span>
                        &nbsp;&nbsp;
                        <span style="color:#888884;">Race:</span> <span style="color:#FAFAF8;">{race['year']} {race['name']} · R{race['round']:02d}</span>
                        &nbsp;&nbsp;
                        <span style="color:#888884;">Circuit:</span> <span style="color:#FAFAF8;">{race.get('circuit', race['country'])} · {race.get('total_laps', 57)} laps</span>
                        &nbsp;&nbsp;
                        <span style="color:#888884;">Conditions:</span> <span style="color:{cond_color};">{race.get('weather', 'Dry')} · 38°C track</span>
                        &nbsp;&nbsp;
                        <span style="color:#888884;">Data:</span> <span style="color:{status_color};">FastF1 {status_txt}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with bcol2:
                if st.button("Change session"):
                    st.session_state.pop("selected_driver", None)
                    st.session_state.pop("selected_race", None)
                    st.rerun()
            with bcol3:
                st.markdown('<div class="aris-btn-primary">', unsafe_allow_html=True)
                if st.button("Build strategy →", type="primary", key="goto_strategy"):
                    st.session_state["screen"] = 1
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    elif not driver:
        st.info("Select a driver to continue.")
    elif not race:
        st.info("Select a race to continue.")
