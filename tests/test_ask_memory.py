"""H.5 — multi-turn memory is in-session only."""

from aris.ask.grounded import ABSTAIN, answer_question
from aris.ask.memory import ConversationMemory
from aris.ask.retrieve import AskIndex
from aris.ask.sources import collect_documents, json_number


def test_follow_up_uses_session_memory_not_a_new_guess():
    index = AskIndex.from_documents(collect_documents())
    memory = ConversationMemory()
    q1 = "What did ARIS recommend for SAI at the 2024 Netherlands race on lap 21?"
    a1 = answer_question(None, q1, index=index, memory=memory)
    memory.add("user", q1)
    memory.add("assistant", a1)
    assert json_number(-72.72805747985858) in a1

    q2 = "What was the delta_vs_stay_out_s on that call?"
    a2 = answer_question(None, q2, index=index, memory=memory)
    assert json_number(-72.72805747985858) in a2, (
        f"aimed L21 delta in follow-up, actual {a2[:300]!r}"
    )
    assert "Cited:" in a2


def test_memory_is_not_persisted_across_instances():
    first = ConversationMemory()
    first.add("user", "hello")
    first.add("assistant", "nope")
    # A new object (new Streamlit session) must start empty — no disk store.
    second = ConversationMemory()
    assert second.turns == []
    assert second.last_decision_docs == []
    assert second.query_with_context("x") == "x"


def test_follow_up_without_memory_does_not_invent_the_delta():
    index = AskIndex.from_documents(collect_documents())
    answer = answer_question(None, "What was the delta_vs_stay_out_s on that call?", index=index)
    # No session memory and no identifiers → abstain, don't pick a random record.
    assert answer == ABSTAIN, f"aimed ABSTAIN, actual {answer[:240]!r}"
