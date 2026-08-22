"""CQL helpers that must import without torch (CI / physics path)."""

from aris.models.cql import (
    ACTION_STAY_OUT,
    STATE_DIM,
    build_state_vector,
    load_cql_model,
    map_recommendation_to_action,
    raw_state_vector,
)
from aris.recommend import recommend
from aris.simulate import ActionKind, StrategyAction
from aris.state import RaceState


def _state() -> RaceState:
    return RaceState(
        session_id=1,
        driver_id=1,
        driver_code="VER",
        driver_name="Max Verstappen",
        year=2025,
        round_no=15,
        country="Netherlands",
        lap_number=25,
        compound="MEDIUM",
        tyre_life=2,
        fuel_kg=70.0,
        laps_remaining=47,
        total_laps=72,
        lag1_pace=74.0,
        lag2_pace=74.0,
        stint_roll3=74.0,
        gap_ahead_s=3.0,
        gap_ahead_history=[3.4, 3.2, 3.0],
        position=5,
        stint_number=1,
        track_status="1",
        rainfall=False,
        pit_compound="HARD",
    )


def test_raw_state_vector_is_18():
    vec = raw_state_vector(_state())
    assert vec.shape == (STATE_DIM,)
    assert vec[1] == 1.0  # MEDIUM
    assert vec[12] == 1.0  # green


def test_build_state_vector_applies_zscore():
    norm = {
        "cont_indices": [4],
        "means": [0.0],
        "stds": [1.0],
    }
    vec = build_state_vector(_state(), norm)
    assert vec.shape == (STATE_DIM,)
    assert abs(vec[4]) <= 3.0


def test_map_stay_and_pit():
    class _Rec:
        def __init__(self, action):
            self.action = action
            self.label = ""

    stay = _Rec(StrategyAction(kind=ActionKind.STAY_OUT))
    assert map_recommendation_to_action(stay) == ACTION_STAY_OUT
    pit = _Rec(StrategyAction(kind=ActionKind.PIT_LAP, pit_lap=33, pit_compound="HARD"))
    assert map_recommendation_to_action(pit) == 3
    unknown = _Rec(StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="UNKNOWN"))
    assert map_recommendation_to_action(unknown) is None


def test_load_cql_model_missing_is_none(tmp_path):
    q_net, norm = load_cql_model(
        model_path=tmp_path / "missing.pt",
        norm_path=tmp_path / "missing.json",
    )
    assert q_net is None and norm is None


def test_recommend_cql_without_model_does_not_crash():
    result = recommend(_state(), mc_draws=0, scoring="cql")
    assert result.recommendations
    assert result.recommendations[0].action.kind in {
        ActionKind.PIT_LAP,
        ActionKind.PIT_NOW,
        ActionKind.STAY_OUT,
        ActionKind.LIFT,
        ActionKind.BRAKE,
    }
