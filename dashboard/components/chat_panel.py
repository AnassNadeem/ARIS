"""ARIS persistent chat panel."""

from __future__ import annotations

import streamlit as st

from dashboard.utils.aris_chat import get_aris_response


def _init_chat_state() -> None:
    if "chat_sessions" not in st.session_state:
        st.session_state["chat_sessions"] = {"Race #1": []}
    if "active_chat" not in st.session_state:
        st.session_state["active_chat"] = "Race #1"
    if "new_chat_name" not in st.session_state:
        st.session_state["new_chat_name"] = ""


def render_chat_panel(race_state: dict, current_lap: int) -> None:
    _init_chat_state()
    sessions: dict = st.session_state["chat_sessions"]
    active: str = st.session_state["active_chat"]

    # Header
    hcol1, hcol2 = st.columns([3, 1])
    with hcol1:
        st.markdown(
            '<div style="font-size:0.9rem;color:#FAFAF8;">ARIS chat</div>'
            '<div style="font-size:0.65rem;color:#888884;">Ask anything · full race knowledge</div>',
            unsafe_allow_html=True,
        )
    with hcol2:
        if st.button("+ New chat", key="chat_new_btn"):
            st.session_state["show_new_chat"] = True

    # New chat expander
    if st.session_state.get("show_new_chat"):
        with st.expander("Create new chat", expanded=True):
            name = st.text_input("Chat name", key="new_chat_input", placeholder="Tyre strategy")
            if st.button("Create", key="chat_create_btn") and name.strip():
                sessions[name.strip()] = []
                st.session_state["active_chat"] = name.strip()
                st.session_state["show_new_chat"] = False
                st.rerun()

    # Tab row
    tab_cols = st.columns(min(len(sessions) + 1, 6))
    for i, chat_name in enumerate(list(sessions.keys())[:5]):
        with tab_cols[i]:
            is_active = chat_name == active
            border = "border-top: 2px solid #E8002D;" if is_active else ""
            if st.button(chat_name, key=f"chat_tab_{chat_name}"):
                st.session_state["active_chat"] = chat_name
                st.rerun()

    # Messages
    messages = sessions.get(active, [])
    msg_container = st.container(height=320)
    with msg_container:
        for msg in messages:
            role = msg.get("role", "aris")
            lap = msg.get("lap", current_lap)
            text = msg.get("text", "")
            if role == "user":
                st.markdown(
                    f'<div class="aris-chat-user">'
                    f'<div class="aris-chat-label">You (L{lap})</div>'
                    f'<div style="color:#FAFAF8;">{text}</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="aris-chat-aris">'
                    f'<div class="aris-chat-label">ARIS (L{lap})</div>'
                    f'<div style="color:#FAFAF8;">{text}</div></div>',
                    unsafe_allow_html=True,
                )

    # Input row
    icol1, icol2 = st.columns([5, 1])
    with icol1:
        user_input = st.text_input("Ask ARIS…", key=f"chat_input_{active}", label_visibility="collapsed")
    with icol2:
        send = st.button("→", key=f"chat_send_{active}")

    if send and user_input.strip():
        sessions[active].append({"role": "user", "text": user_input.strip(), "lap": current_lap})
        response = get_aris_response(user_input.strip(), race_state)
        sessions[active].append({"role": "aris", "text": response, "lap": current_lap})
        st.session_state["chat_sessions"] = sessions
        st.rerun()
