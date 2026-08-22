"""V3 shell — GlobalNav matching frontend/src/components/GlobalNav.tsx."""

from __future__ import annotations

import streamlit as st

from apps.theme import inject_v3

_NAV = (
    ("pages/00_Home.py", "HOME", "home"),
    ("pages/04_Replay.py", "REPLAY", "replay"),
    ("pages/03_Live.py", "LIVE", "live"),
    ("pages/05_Standings.py", "STANDINGS", "standings"),
    ("pages/06_Calendar.py", "CIRCUITS", "calendar"),
)


def render_nav(active: str) -> None:
    inject_v3()
    brand, *links = st.columns([1.4, 1, 1, 1, 1.2, 1.2])
    with brand:
        st.markdown('<div class="aris-v3-brand">ARIS</div>', unsafe_allow_html=True)
    for col, (path, label, key) in zip(links, _NAV):
        with col:
            if key == active:
                st.markdown('<div class="aris-nav-active">', unsafe_allow_html=True)
            st.page_link(path, label=label)
            if key == active:
                st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div style="border-bottom:1px solid #1E2630;margin:4px 0 16px 0"></div>', unsafe_allow_html=True)
