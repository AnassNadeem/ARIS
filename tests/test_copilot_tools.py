"""T11 — Copilot tool execution over a fixed Zandvoort replay state."""

from __future__ import annotations

import pytest

from aris.copilot.context import CopilotContext, FieldCar, set_context
from aris.copilot.tools import TOOL_SCHEMAS, execute_tool
from tests.test_circuit_deg import _zandvoort_state

CORE_TOOLS = (
    "get_gap",
    "get_undercut_window",
    "get_deg_slope",
    "simulate",
    "recommend",
    "get_sc_risk",
    "get_wet_state",
    "run_mc_comparison",
    "get_driver_style",
    "get_circuit_info",
)


def zandvoort_copilot_context() -> CopilotContext:
    state = _zandvoort_state().model_copy(
        update={
            "gap_to_leader_s": 0.0,
            "gap_ahead_s": None,
            "gap_behind_s": 1.8,
            "position": 1,
            "track_state": "DRY",
            "track_state_confidence": 0.95,
        }
    )
    return CopilotContext(
        state=state,
        field=[
            FieldCar(
                driver_code="VER",
                position=1,
                gap_to_leader_s=0.0,
                gap_behind_s=1.8,
                compound="MEDIUM",
                tyre_life=2,
                last_lap_s=74.0,
                name="Max Verstappen",
            ),
            FieldCar(
                driver_code="NOR",
                position=2,
                gap_to_leader_s=1.8,
                gap_ahead_s=1.8,
                compound="MEDIUM",
                tyre_life=18,
                last_lap_s=74.2,
                name="Lando Norris",
            ),
            FieldCar(
                driver_code="PIA",
                position=3,
                gap_to_leader_s=3.1,
                gap_ahead_s=1.3,
                compound="HARD",
                tyre_life=24,
                last_lap_s=74.5,
                name="Oscar Piastri",
            ),
        ],
        session_id="2025-15-R",
        use_llm=False,
    )


@pytest.fixture
def ctx() -> CopilotContext:
    context = zandvoort_copilot_context()
    set_context(context)
    return context


def test_schemas_cover_core_tools():
    names = {s["name"] for s in TOOL_SCHEMAS}
    assert names >= set(CORE_TOOLS)


@pytest.mark.parametrize(
    "name,args",
    [
        ("get_gap", {"driver": "VER"}),
        ("get_undercut_window", {"focus_driver": "VER", "rival_driver": "NOR"}),
        ("get_deg_slope", {"compound": "HARD"}),
        ("simulate", {"action": "PIT_NOW", "compound": "MEDIUM"}),
        ("recommend", {}),
        ("get_sc_risk", {"horizon": 5}),
        ("get_wet_state", {}),
        (
            "run_mc_comparison",
            {
                "actions": [
                    {"action": "PIT_NOW", "compound": "HARD"},
                    {"action": "STAY_OUT"},
                ],
                "n_scenarios": 40,
            },
        ),
        ("get_driver_style", {"driver": "HAM"}),
        ("get_circuit_info", {"circuit_id": "spa"}),
    ],
)
def test_each_tool_returns_without_error(ctx, name, args):
    result = execute_tool(name, args)
    assert isinstance(result, dict), result
    assert "error" not in result, result


def test_get_undercut_window_ver_nor_nonempty(ctx):
    result = execute_tool(
        "get_undercut_window",
        {"focus_driver": "VER", "rival_driver": "NOR"},
    )
    assert result.get("window_open") is True
    assert result.get("window_laps"), result
    assert result.get("focus_driver") == "VER"
    assert result.get("rival_driver") == "NOR"


def test_get_gap_includes_p3_tyres(ctx):
    result = execute_tool("get_gap", {"driver": "VER"})
    order = result.get("order") or []
    p3 = next((r for r in order if r.get("position") == 3), None)
    assert p3 is not None
    assert p3["driver"] == "PIA"
    assert p3["compound"] == "HARD"
    assert p3["tyre_life"] == 24


def test_get_gap_to_named_driver_is_interval_not_gap_to_leader(ctx):
    """From PIA, gap to NOR is 1.3s (interval), not NOR's 1.8s to the leader."""
    from aris.copilot.context import set_context

    pia = zandvoort_copilot_context()
    pia.state = pia.state.model_copy(update={"driver_code": "PIA", "position": 3, "gap_to_leader_s": 3.1})
    set_context(pia)
    result = execute_tool("get_gap", {"driver": "PIA", "vs_driver": "NOR"})
    assert result.get("vs_driver") == "NOR"
    gap = result.get("gap_to_target_s")
    assert gap is not None
    assert abs(float(gap) - 1.3) < 0.05
    assert abs(float(gap) - 1.8) > 0.05


def test_fastf1_race_state_populates_gap_to_leader():
    from datetime import datetime, timedelta
    from types import SimpleNamespace

    import pandas as pd

    from backend.aris_api import build_race_state_from_fastf1_session

    t0 = timedelta(seconds=1800.0)
    laps = pd.DataFrame(
        [
            {
                "Driver": "VER",
                "LapNumber": 24,
                "Compound": "MEDIUM",
                "TyreLife": 24,
                "Position": 1,
                "Time": t0,
                "LapTime": timedelta(seconds=74.0),
                "TrackStatus": "1",
                "Stint": 1,
            },
            {
                "Driver": "NOR",
                "LapNumber": 24,
                "Compound": "MEDIUM",
                "TyreLife": 24,
                "Position": 2,
                "Time": t0 + timedelta(seconds=1.8),
                "LapTime": timedelta(seconds=74.2),
                "TrackStatus": "1",
                "Stint": 1,
            },
            {
                "Driver": "PIA",
                "LapNumber": 23,
                "Compound": "HARD",
                "TyreLife": 23,
                "Position": 3,
                "Time": t0 - timedelta(seconds=74.5),
                "LapTime": timedelta(seconds=74.5),
                "TrackStatus": "1",
                "Stint": 1,
            },
            {
                "Driver": "PIA",
                "LapNumber": 24,
                "Compound": "HARD",
                "TyreLife": 24,
                "Position": 3,
                "Time": t0 + timedelta(seconds=3.1),
                "LapTime": timedelta(seconds=74.5),
                "TrackStatus": "1",
                "Stint": 1,
            },
        ]
    )
    session = SimpleNamespace(
        laps=laps,
        event={
            "Country": "Netherlands",
            "Location": "Zandvoort",
            "EventDate": datetime(2025, 8, 31),
            "RoundNumber": 15,
        },
        date=datetime(2025, 8, 31),
        weather_data=None,
        race_control_messages=None,
        results=None,
        get_driver=lambda code: {"FullName": "Oscar Piastri", "TeamName": "McLaren"},
    )
    state = build_race_state_from_fastf1_session(session, "PIA", 25)
    assert state is not None
    assert state.gap_to_leader_s is not None
    assert abs(float(state.gap_to_leader_s) - 3.1) < 0.05


def test_simulate_pit_now_differs_from_stay(ctx):
    stay = execute_tool("simulate", {"action": "STAY_OUT"})
    pit = execute_tool("simulate", {"action": "PIT_NOW", "compound": "MEDIUM"})
    assert stay["delta_vs_stay_out_s"] == 0.0
    assert pit["delta_vs_stay_out_s"] != 0.0


def test_recommend_returns_top_three(ctx):
    result = execute_tool("recommend", {})
    assert len(result.get("top_3") or []) == 3


def test_spa_circuit_info_is_high_deg(ctx):
    result = execute_tool("get_circuit_info", {"circuit_id": "spa"})
    assert result.get("deg") == "high"
    assert "high-deg" in str(result.get("text") or "").lower()
