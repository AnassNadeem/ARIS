"""Pre-race Strat A/B/C cards."""

from __future__ import annotations

import streamlit as st

from aris.plan.prewrite import StratPlan, StratPlanSet
from aris.ui_text import format_race_clock


def render_strat_cards(plans: StratPlanSet) -> StratPlan | None:
    st.subheader("Pre-race strategy")
    if plans.weather:
        w = plans.weather
        st.caption(
            f"Weather — air {w.get('air_temp_c', '—')}°C · "
            f"track {w.get('track_temp_c', '—')}°C · "
            f"humidity {w.get('humidity_pct', '—')}%"
        )

    selected: StratPlan | None = None
    cols = st.columns(3)
    for col, plan in zip(cols, plans.plans, strict=False):
        with col:
            star = "★ " if plan.recommended else ""
            rec_cls = " recommended" if plan.recommended else ""
            st.markdown(
                f'<div class="aris-strat-card{rec_cls}">'
                f'<div class="name">{star}{plan.name}</div>'
                f'<div class="desc">{plan.description}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            st.metric("Est. race time", format_race_clock(plan.expected_race_time_s))
            pit_laps = st.text_input(
                "Pit laps",
                value=",".join(str(p) for p in plan.pit_laps),
                key=f"pit_laps_{plan.id}",
            )
            compounds = st.text_input(
                "Compounds",
                value=",".join(plan.pit_compounds),
                key=f"compounds_{plan.id}",
            )
            if st.button(f"Select {plan.id}", key=f"select_{plan.id}"):
                plan.pit_laps = [int(x.strip()) for x in pit_laps.split(",") if x.strip()]
                plan.pit_compounds = [x.strip().upper() for x in compounds.split(",") if x.strip()]
                selected = plan
    return selected
