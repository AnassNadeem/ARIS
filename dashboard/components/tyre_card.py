"""Reusable tyre visualisation component."""

from __future__ import annotations

import streamlit as st

COMPOUND_COLORS = {
    "SOFT": "#E8002D",
    "MEDIUM": "#F5A623",
    "HARD": "#888884",
    "INTERMEDIATE": "#4CAF50",
    "WET": "#2196F3",
}
COMPOUND_LETTER = {"SOFT": "S", "MEDIUM": "M", "HARD": "H", "INTERMEDIATE": "I", "WET": "W"}


def render_tyre_card(
    compound: str,
    stint_num: int,
    laps_on: int,
    max_life: int = 34,
    deg_rate: float = 0.05,
    cliff_lap: int | None = None,
) -> None:
    color = COMPOUND_COLORS.get(compound.upper(), "#888884")
    letter = COMPOUND_LETTER.get(compound.upper(), "?")
    fill_pct = min(100, int(100 * laps_on / max(max_life, 1)))
    bar_color = "#F5A623" if fill_pct < 75 else "#E8002D"
    cliff_txt = f"Cliff L{cliff_lap}+" if cliff_lap else ""

    st.markdown(
        f"""
        <div class="aris-card" style="text-align:center;padding:1rem;">
            <div style="width:48px;height:48px;border-radius:50%;background:{color};
                        display:flex;align-items:center;justify-content:center;
                        margin:0 auto 0.5rem;font-weight:bold;font-size:1.2rem;color:#0D0D0D;">
                {letter}
            </div>
            <div style="color:#FAFAF8;font-size:0.85rem;">{compound.title()} / Stint {stint_num}</div>
            <div style="color:#888884;font-size:0.7rem;margin-bottom:0.5rem;">{laps_on} laps old</div>
            <div style="background:#1e1e1e;border-radius:2px;height:6px;margin:0.5rem 0;">
                <div style="background:{bar_color};width:{fill_pct}%;height:6px;border-radius:2px;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:0.6rem;color:#888884;">
                <span>0</span><span>{max_life} lap max</span>
            </div>
            <div style="color:#888884;font-size:0.65rem;margin-top:0.4rem;">
                Deg: {deg_rate:.2f}s/lap {cliff_txt}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tyre_dot(compound: str, age: int) -> str:
    color = COMPOUND_COLORS.get(compound.upper(), "#888884")
    letter = COMPOUND_LETTER.get(compound.upper(), "?")
    return (
        f'<span style="display:inline-flex;align-items:center;gap:4px;">'
        f'<span style="width:14px;height:14px;border-radius:50%;background:{color};'
        f'display:inline-block;text-align:center;font-size:0.5rem;line-height:14px;color:#0D0D0D;">{letter}</span>'
        f'<span style="color:#888884;">{age}L</span></span>'
    )


def render_pit_window(current_lap: int, total_laps: int, window_open: int, window_close: int, optimal: int) -> None:
    pct = lambda lap: int(100 * lap / total_laps)
    st.markdown(
        f"""
        <div class="aris-card" style="padding:0.75rem;">
            <div style="font-size:0.65rem;color:#888884;margin-bottom:0.5rem;">PIT WINDOW</div>
            <div style="position:relative;background:#1e1e1e;height:20px;border-radius:2px;">
                <div style="position:absolute;left:{pct(window_open)}%;width:{pct(window_close)-pct(window_open)}%;
                            height:20px;background:#E8002D33;border-radius:2px;"></div>
                <div style="position:absolute;left:{pct(optimal)}%;width:2px;height:20px;background:#E8002D;"></div>
                <div style="position:absolute;left:{pct(current_lap)}%;width:2px;height:20px;background:#FAFAF8;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:0.55rem;color:#888884;margin-top:0.3rem;">
                <span>L{window_open}</span>
                <span style="color:#E8002D;">Optimal: pit lap {optimal}</span>
                <span>L{total_laps}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
