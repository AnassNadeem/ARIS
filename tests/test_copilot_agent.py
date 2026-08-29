"""T11 — end-to-end Copilot agent on ten standard questions."""

from __future__ import annotations

from aris.copilot.agent import run_copilot, word_count
from aris.copilot.retrieval import index_corpus, reset_index
from tests.test_copilot_tools import zandvoort_copilot_context

STANDARD = [
    ("What's the gap to NOR?", {"get_gap"}),
    ("Who's in P3 and what's their tyre life?", {"get_gap"}),
    ("If we pit now for MEDIUM, what's the delta vs stay?", {"simulate"}),
    ("What's the best strategy from here?", {"recommend"}),
    ("What's the undercut window for VER vs NOR?", {"get_undercut_window"}),
    ("If NOR pits next lap, should we cover?", {"simulate"}),
    ("What happened at Zandvoort 2024 lap 33?", {"recommend"}),
    ("How does Hamilton manage tyres compared to Verstappen?", {"get_driver_style"}),
    ("Do drivers have to use two compounds in a dry race?", set()),
    ("Is Spa high-deg?", {"get_circuit_info"}),
]


def setup_module() -> None:
    reset_index()
    index_corpus()


def _run(question: str):
    return run_copilot(question, zandvoort_copilot_context(), use_llm=False)


def test_ten_standard_questions():
    failures: list[str] = []
    for question, expected_tools in STANDARD:
        result = _run(question)
        called = {c["name"] for c in result.tool_calls}
        if expected_tools and not expected_tools.issubset(called):
            failures.append(f"{question!r} expected {expected_tools}, called {called}")
        if word_count(result.response) > 150:
            failures.append(f"{question!r} too long ({word_count(result.response)} words)")
        if not result.response.strip():
            failures.append(f"{question!r} empty response")
        if question.lower().startswith("do drivers") or "spa" in question.lower() or "hamilton" in question.lower():
            blob = " ".join(c.get("text") or "" for c in result.retrieved_chunks).lower()
            q_terms = [t for t in question.lower().split() if len(t) > 3]
            if q_terms and not any(t.strip("?,") in blob or t.strip("?,") in result.response.lower() for t in q_terms):
                failures.append(f"{question!r} retrieval/response overlap failed")
        for call in result.tool_calls:
            if isinstance(call.get("result"), dict) and call["result"].get("error"):
                failures.append(f"{question!r} tool {call['name']} error {call['result']}")
    assert not failures, "\n".join(failures)


def test_recommend_surfaces_top3_and_approval():
    result = _run("What's the best strategy from here?")
    assert len(result.recommendations) == 3
    assert result.needs_approval is True


def test_two_compounds_cites_fia_chunk():
    result = _run("Do drivers have to use two compounds in a dry race?")
    ids = [c.get("chunk_id") for c in result.retrieved_chunks]
    assert any(str(i).startswith("fia_reg:two-compounds-dry") for i in ids), ids
    low = result.response.lower()
    assert "cite:" in low
    assert "30.5" in result.response or "two different specifications" in low


def _assert_clean_factual(response: str) -> None:
    low = response.lower()
    assert "cite:" not in low
    assert "aris_doc:" not in low
    assert not response.lstrip().startswith("#")
    assert "|" not in response or "P" in response


def test_who_is_the_leader_is_plain_language():
    result = _run("who is the leader")
    called = {c["name"] for c in result.tool_calls}
    assert "get_gap" in called, called
    _assert_clean_factual(result.response)
    assert "VER" in result.response
    assert "leader" in result.response.lower()


def test_who_won_here_last_year_is_plain_language():
    result = _run("who won here last year")
    called = {c["name"] for c in result.tool_calls}
    assert "get_session_result" in called, called
    _assert_clean_factual(result.response)
    assert "NOR" in result.response or "Norris" in result.response
    assert "Cite:" not in result.response


def test_gap_to_nor_from_pia_is_interval():
    from aris.copilot.agent import run_copilot
    from tests.test_copilot_tools import zandvoort_copilot_context

    ctx = zandvoort_copilot_context()
    ctx.state = ctx.state.model_copy(
        update={"driver_code": "PIA", "position": 3, "gap_to_leader_s": 3.1}
    )
    result = run_copilot("What's the gap to NOR?", ctx, use_llm=False)
    low = result.response.lower()
    assert "1.3" in result.response or "1.3s" in low
    assert "1.8" not in result.response
    assert "cite:" not in low
