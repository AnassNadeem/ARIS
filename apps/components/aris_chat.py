"""ARIS conversational chat pane."""

from __future__ import annotations

import streamlit as st

from aris.ask.keyword_qa import answer_question
from aris.decisions.queue import DecisionKind, DecisionQueue
from aris.engine.session import RaceEngineSession


def render_chat(session: RaceEngineSession, queue: DecisionQueue) -> None:
    for turn in queue.history:
        with st.chat_message(turn.role):
            st.write(turn.text)
            if turn.role == "aris" and turn.options and turn is queue.pending:
                cols = st.columns(len(turn.options))
                for col, opt in zip(cols, turn.options, strict=False):
                    label = f"{'⭐ ' if opt.recommended else ''}{opt.label}"
                    if col.button(label, key=f"opt_{turn.kind}_{opt.id}_{turn.text[:20]}"):
                        if opt.id == "edit" and turn.editable_fields:
                            st.session_state["editing_decision"] = turn
                        else:
                            record = queue.resolve(
                                opt.id,
                                kind=turn.kind or DecisionKind.PIT,
                                lap=session.replay_index.lap_number,
                            )
                            session.record_decision(record)
                            st.rerun()

    if st.session_state.get("editing_decision"):
        turn = st.session_state["editing_decision"]
        st.subheader("Edit recommendation")
        pit_lap = st.number_input(
            "Pit lap",
            min_value=session.replay_index.lap_number,
            max_value=session.total_laps,
            value=int(turn.editable_fields.get("pit_lap", session.replay_index.lap_number + 1)),
        )
        compound = st.selectbox(
            "Compound",
            ["SOFT", "MEDIUM", "HARD"],
            index=["SOFT", "MEDIUM", "HARD"].index(
                str(turn.editable_fields.get("compound", "HARD"))
            ),
        )
        if st.button("Confirm edit"):
            record = queue.resolve(
                "edit",
                kind=turn.kind or DecisionKind.PIT,
                lap=session.replay_index.lap_number,
                edited_fields={"pit_lap": pit_lap, "compound": compound},
            )
            session.record_decision(record)
            st.session_state.pop("editing_decision", None)
            st.rerun()


def render_ask_mode(session: RaceEngineSession) -> None:
    st.subheader("Ask ARIS")
    if "ask_history" not in st.session_state:
        st.session_state.ask_history = []
    if not st.session_state.ask_history:
        st.markdown(
            '<div class="aris-empty">Ask about tyres, gaps, or whether to box. '
            "Example: <em>should we pit this lap?</em></div>",
            unsafe_allow_html=True,
        )
    for role, text in st.session_state.ask_history:
        with st.chat_message(role):
            st.write(text)
    question = st.chat_input("Ask about tyres, gaps, strategy…")
    if question:
        answer = answer_question(session, question, use_llm=False)
        st.session_state.ask_history.append(("user", question))
        st.session_state.ask_history.append(("assistant", answer))
        st.rerun()
