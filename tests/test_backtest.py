"""Tests for walk-forward backtest helpers (no DB / no full race walk)."""

import pandas as pd

from aris.eval.backtest import (
    Inflection,
    extract_inflections,
    last_year_matches_pit,
    match_rate,
    matches_team_pit,
    rec_is_stay,
    rec_pit_calls,
    rolling_mean,
    stay_out_baseline_rate,
)
from aris.recommend import Recommendation
from aris.simulate import ActionKind, StrategyAction


def _rec(**kwargs) -> Recommendation:
    defaults = dict(
        rank=1,
        label="x",
        action=StrategyAction(kind=ActionKind.STAY_OUT),
        delta_vs_stay_out_s=0.0,
        mean_race_time_s=5000.0,
        confidence_std_s=0.0,
        p10_delta_s=0.0,
        p90_delta_s=0.0,
        evidence="",
        narration_context={},
    )
    defaults.update(kwargs)
    return Recommendation(**defaults)


def test_extract_inflections_pits_sc_compound():
    laps = pd.DataFrame(
        [
            {
                "lap_number": 1, "compound": "SOFT", "pit_in": False,
                "track_status": "1",
            },
            {
                "lap_number": 10, "compound": "SOFT", "pit_in": False,
                "track_status": "4",
            },
            {
                "lap_number": 11, "compound": "SOFT", "pit_in": False,
                "track_status": "4",
            },
            {
                "lap_number": 18, "compound": "SOFT", "pit_in": True,
                "track_status": "1",
            },
            {
                "lap_number": 19, "compound": "HARD", "pit_in": False,
                "track_status": "1",
            },
        ]
    )
    inf = extract_inflections(laps)
    kinds = [i.kind for i in inf]
    assert "sc" in kinds
    assert "pit" in kinds
    pit = next(i for i in inf if i.kind == "pit")
    assert pit.lap == 18
    assert pit.compound == "HARD"
    sc = next(i for i in inf if i.kind == "sc")
    assert sc.lap == 10


def test_matches_team_pit_within_tolerance_and_compound():
    rec = _rec(
        action=StrategyAction(
            kind=ActionKind.PIT_LAP, pit_lap=20, pit_compound="HARD"
        )
    )
    assert matches_team_pit(rec, 18, "HARD")
    assert not matches_team_pit(rec, 18, "SOFT")
    assert not matches_team_pit(rec, 30, "HARD")


def test_stay_out_and_line_actions_count_as_stay():
    assert rec_is_stay(_rec())
    lift = _rec(
        action=StrategyAction(kind=ActionKind.LIFT, corner_index=1, distance_m=30)
    )
    assert not rec_is_stay(lift)
    pit = _rec(
        action=StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="HARD")
    )
    assert not rec_is_stay(pit)
    assert rec_pit_calls(pit, 12) == [(12, "HARD")]


def test_rolling_mean_window_five():
    vals = [1.0, 3.0, 5.0, 7.0, 9.0, 11.0]
    rolled = rolling_mean(vals, window=5)
    assert rolled[0] == 1.0
    assert rolled[4] == (1 + 3 + 5 + 7 + 9) / 5
    assert rolled[5] == (3 + 5 + 7 + 9 + 11) / 5


def test_rolling_calendar_keeps_holes():
    from types import SimpleNamespace

    from aris.eval.backtest import rolling_calendar

    races = [SimpleNamespace(round_no=i, gp=str(i)) for i in range(1, 7)]
    match = [0.0, float("nan"), 0.5, 0.0, 1.0, 0.0]
    delta = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    rows = rolling_calendar(races, match, delta, window=5)
    assert len(rows) == 6
    assert rows[1]["end_round"] == 2
    assert rows[1]["rolling_match_rate"] == 0.0  # only race 1 finite in window
    assert rows[2]["rolling_match_rate"] == 0.25  # (0 + 0.5) / 2
    assert rows[5]["rolling_position_delta"] == (2 + 3 + 4 + 5 + 6) / 5


def test_match_rate_excludes_insufficient_info():
    from aris.eval.backtest import DecisionScore

    inf = Inflection(kind="pit", lap=10, compound="HARD", team_pitted=True)
    scores = [
        DecisionScore(
            gp="A", year=2024, round_no=1, driver_code="X",
            inflection=inf, aris_label="p", classification="match",
            stay_out_match=False,
        ),
        DecisionScore(
            gp="A", year=2024, round_no=1, driver_code="X",
            inflection=inf, aris_label="p",
            classification="divergence_team_hindsight",
            stay_out_match=False,
        ),
        DecisionScore(
            gp="A", year=2024, round_no=1, driver_code="X",
            inflection=inf, aris_label="p",
            classification="divergence_insufficient_info",
            stay_out_match=False,
        ),
    ]
    rate, n_match, n_scored = match_rate(scores)
    assert n_scored == 2
    assert n_match == 1
    assert rate == 0.5
    stay_rate, _, _ = stay_out_baseline_rate(scores)
    assert stay_rate == 0.0


def test_last_year_baseline_window():
    assert last_year_matches_pit([(16, "HARD"), (40, "SOFT")], 18) is True
    assert last_year_matches_pit([(16, "HARD")], 30) is False
    assert last_year_matches_pit(None, 18) is None
