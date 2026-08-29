"""H.4 — grounding contract: cited numbers match logged records exactly."""

import json

from aris.ask.grounded import ABSTAIN, answer_question
from aris.ask.retrieve import AskIndex
from aris.ask.sources import collect_documents, json_number, load_decision_documents


def _index() -> AskIndex:
    return AskIndex.from_documents(collect_documents())


def _cases() -> list[tuple[str, dict]]:
    """One question per fixture decision record (14 real JSONL proposes)."""
    docs = load_decision_documents()
    cases: list[tuple[str, dict]] = []
    for doc in docs:
        f = doc.facts
        if f.get("source_file") == "decisions.jsonl":
            # Fixtures keep the original filename in _source_file when dumped.
            pass
        q = (
            f"What did ARIS recommend for {f['driver_code']} at the "
            f"{f['year']} {f['country']} race on lap {f['lap']}?"
        )
        if f.get("country") == "United States":
            q = (
                f"What did ARIS recommend for {f['driver_code']} at "
                f"{f['year']} United States round {f['round_no']} lap {f['lap']}?"
            )
        if f.get("country") == "Italy":
            q = (
                f"What did ARIS recommend for {f['driver_code']} at "
                f"{f['year']} Italy round {f['round_no']} lap {f['lap']}?"
            )
        cases.append((q, f))
    return cases


def test_grounding_ten_plus_logged_decisions():
    index = _index()
    cases = _cases()
    # Aimed: >= 10 questions over real logged proposes. Actual n below.
    assert len(cases) >= 10, f"aimed >= 10 grounding cases, actual {len(cases)}"
    failures: list[str] = []
    for question, facts in cases:
        answer = answer_question(None, question, index=index)
        delta = json_number(facts["delta_vs_stay_out_s"])
        label = facts["label"]
        event_id = facts["event_id"]
        if ABSTAIN in answer:
            failures.append(f"ABSTAIN on {question!r}")
            continue
        if delta not in answer:
            failures.append(
                f"delta mismatch for {question!r}: aimed {delta} in answer, actual {answer[:240]!r}"
            )
        if label not in answer:
            failures.append(f"label mismatch for {question!r}: aimed {label!r}")
        if event_id not in answer and "Cited:" not in answer:
            failures.append(f"missing citation for {question!r}")
        if "Cited:" not in answer:
            failures.append(f"no Cited: block for {question!r}")
        # mean_race_time_s must also be the record's number when present
        mean = facts.get("mean_race_time_s")
        if mean is not None and json_number(mean) not in answer:
            failures.append(
                f"mean_race_time_s mismatch for {question!r}: aimed {json_number(mean)}"
            )
    assert not failures, "aimed 0 grounding mismatches, actual:\n" + "\n".join(failures)


def test_grounding_does_not_guess_when_nothing_retrieved():
    index = _index()
    unanswered = [
        "What is the capital of France?",
        "What did ARIS recommend for SAI at the 2024 Netherlands race on lap 9999?",
        "Who won the 1998 FIFA World Cup?",
    ]
    for question in unanswered:
        answer = answer_question(None, question, index=index)
        assert answer == ABSTAIN, (
            f"aimed ABSTAIN for {question!r}, actual {answer[:240]!r}"
        )


def test_grounding_does_not_mix_another_lap_delta():
    index = _index()
    answer = answer_question(
        None,
        "What did ARIS recommend for SAI at the 2024 Netherlands race on lap 21?",
        index=index,
    )
    # Aimed: L21 delta -72.72805747985858, not the L2 delta -45.83318244933962.
    assert json_number(-72.72805747985858) in answer
    assert json_number(-45.83318244933962) not in answer
    assert json.dumps("Pit now for HARD") in answer or "Pit now for HARD" in answer


def test_who_won_here_last_year_does_not_dump_fia_tyre_doc():
    index = _index()
    answer = answer_question(None, "who won here last year", index=index)
    low = answer.lower()
    assert "fia" not in low
    assert "cited:" not in low
    assert "dry-tyres" not in low
    assert "article 30" not in low
    assert not answer.lstrip().startswith("#")
    assert "won't guess" in low or "no relevant source" in low or "no classified" in low


def test_who_won_2024_netherlands_returns_winner_not_sar():
    index = _index()
    answer = answer_question(None, "Who won the 2024 Netherlands race?", index=index)
    low = answer.lower()
    assert "cited:" not in low
    assert "sar" not in low
    assert "p16" not in low
    assert "NOR" in answer or "Norris" in answer
    assert "won" in low
