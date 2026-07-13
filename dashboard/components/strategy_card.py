"""Strategy option card for Screen 2."""

from __future__ import annotations

import streamlit as st

from dashboard.utils.monte_carlo import StrategyResult, format_race_time

COMPOUND_COLORS = {"SOFT": "#E8002D", "MEDIUM": "#F5A623", "HARD": "#888884"}
COMPOUND_SHORT = {"SOFT": "S", "MEDIUM": "M", "HARD": "H"}


def _stint_pills(compounds: list[str], stint_laps: list[int]) -> str:
    pills = []
    for compound, laps in zip(compounds, stint_laps, strict=False):
        c = COMPOUND_COLORS.get(compound, "#888884")
        s = COMPOUND_SHORT.get(compound, "?")
        pills.append(
            f'<span style="background:{c}22;border:1px solid {c};color:{c};'
            f'padding:2px 8px;border-radius:3px;font-size:0.7rem;margin-right:4px;">'
            f'{s} x{laps}</span>'
        )
    return "".join(pills)


def _prob_bar(p1: float, p2: float, p3: float) -> str:
    return (
        f'<div style="display:flex;height:6px;border-radius:2px;overflow:hidden;margin:0.5rem 0;">'
        f'<div style="width:{p1*100:.0f}%;background:#E8002D;"></div>'
        f'<div style="width:{p2*100:.0f}%;background:#888884;"></div>'
        f'<div style="width:{p3*100:.0f}%;background:#2a2a2a;"></div></div>'
    )


def render_strategy_card(
    result: StrategyResult,
    index: int,
    selected_id: str | None,
) -> bool:
    """Render strategy card. Returns True if user clicked Select."""
    strat = result.strategy
    is_rec = result.recommended
    is_selected = selected_id == strat.id
    border = "1.5px solid #E8002D" if (is_rec or is_selected) else "0.5px solid #1e1e1e"
    rec_badge = (
        '<span style="color:#E8002D;font-size:0.65rem;">● RECOMMENDED</span><br>'
        if is_rec else ""
    )
    compound_str = " → ".join(c.title() for c in strat.compounds)
    pit_str = ", ".join(str(p) for p in strat.pit_laps)
    pills = _stint_pills(strat.compounds, strat.stint_laps)
    prob_bar = _prob_bar(result.p1_prob, result.p2_prob, result.p3_plus_prob)

    st.markdown(
        f"""
        <div class="aris-card" style="border:{border};min-height:280px;">
            {rec_badge}
            <div style="font-size:0.95rem;color:#FAFAF8;font-weight:bold;margin-bottom:0.3rem;">
                {strat.name}
            </div>
            <div style="font-size:0.7rem;color:#888884;margin-bottom:0.5rem;">{compound_str}</div>
            <div>{pills}</div>
            <div style="font-size:0.65rem;color:#888884;margin-top:0.75rem;line-height:1.6;">
                Pit laps: {pit_str}<br>
                Pit loss: ~{result.pit_loss_s:.0f}s<br>
                <span style="color:#4CAF50;">P1 prob: {result.p1_prob:.0%}</span><br>
                Total time: {format_race_time(result.total_time_s)}
            </div>
            {prob_bar}
            <div style="font-size:0.6rem;color:#888884;">
                P1 {result.p1_prob:.0%} · P2 {result.p2_prob:.0%} · P3+ {result.p3_plus_prob:.0%}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    btn_label = "Selected ✓" if is_selected else "Select strategy"
    btn_type = "primary" if is_selected else "secondary"
    clicked = st.button(btn_label, key=f"strat_select_{index}", type=btn_type)
    return clicked
