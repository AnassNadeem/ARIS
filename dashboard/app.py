"""ARIS dashboard entry point."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from dashboard.screens import screen1_selection, screen2_strategy, screen3_live, screen4_timing

SCREENS = ["Select race", "Strategy builder", "Live race", "Timing tower"]
_SCREEN_MODULES = [screen1_selection, screen2_strategy, screen3_live, screen4_timing]

_THEME_PATH = Path(__file__).parent / "styles" / "theme.css"


def _inject_theme() -> None:
    css = _THEME_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _render_step_bar(current: int) -> None:
    steps_html = []
    for i, name in enumerate(SCREENS):
        if i < current:
            cls = "aris-step done"
            num = "✓"
        elif i == current:
            cls = "aris-step active"
            num = str(i + 1)
        else:
            cls = "aris-step"
            num = str(i + 1)
        steps_html.append(f'<div class="{cls}"><span class="aris-step-num">{num}</span>{name}</div>')
    st.markdown(
        f"""
        <div class="aris-header">
            <div>
                <div class="aris-logo">ARIS</div>
                <div class="aris-tagline">Adaptive Race Intelligence System</div>
            </div>
        </div>
        <div class="aris-step-bar">{"".join(steps_html)}</div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="ARIS — Adaptive Race Intelligence System",
        page_icon="🏎️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_theme()

    if "screen" not in st.session_state:
        st.session_state["screen"] = 0

    current = st.session_state["screen"]
    current = max(0, min(current, len(SCREENS) - 1))
    st.session_state["screen"] = current

    _render_step_bar(current)

    # Sidebar quick nav
    with st.sidebar:
        st.markdown("### Navigation")
        for i, name in enumerate(SCREENS):
            if st.button(name, key=f"nav_{i}", type="primary" if i == current else "secondary"):
                st.session_state["screen"] = i
                st.rerun()

    _SCREEN_MODULES[current].render()


if __name__ == "__main__":
    main()
