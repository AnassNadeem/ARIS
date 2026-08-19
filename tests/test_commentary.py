"""Commentary engine and driver-resolution helpers (no DB / FastF1)."""

from unittest.mock import MagicMock

from aris.commentary import DriverSnap, FieldSnapshot, events_for_transition
from backend.aris_api import ClientInputError, resolve_driver_code


def _snap(lap: int, drivers: list[DriverSnap], total: int = 72) -> FieldSnapshot:
    return FieldSnapshot(lap=lap, total_laps=total, drivers=drivers)


def test_pit_detection_emits_intel():
    prev = _snap(
        21,
        [
            DriverSnap(code="NOR", position=1, stint_number=1, compound="M", gap_to_leader_s=0),
            DriverSnap(code="VER", position=2, stint_number=1, compound="M", gap_to_leader_s=1.2),
        ],
    )
    curr = _snap(
        22,
        [
            DriverSnap(code="NOR", position=3, stint_number=2, compound="H", gap_to_leader_s=22.0),
            DriverSnap(code="VER", position=1, stint_number=1, compound="M", gap_to_leader_s=0),
        ],
    )
    msgs = events_for_transition(prev, curr, "VER")
    pits = [m for m in msgs if "pitted" in m.text.lower()]
    assert pits, msgs
    assert "NOR" in pits[0].text


def test_gap_alert_when_car_behind_under_1_5s():
    prev = _snap(
        10,
        [
            DriverSnap(code="NOR", position=1, gap_to_leader_s=0, gap_ahead_s=None),
            DriverSnap(code="VER", position=2, gap_to_leader_s=2.4, gap_ahead_s=2.4),
        ],
    )
    curr = _snap(
        11,
        [
            DriverSnap(code="NOR", position=1, gap_to_leader_s=0, gap_ahead_s=None),
            DriverSnap(code="VER", position=2, gap_to_leader_s=1.1, gap_ahead_s=1.1),
        ],
    )
    msgs = events_for_transition(prev, curr, "NOR")
    assert any("closing" in m.text.lower() or "mirror" in m.text.lower() for m in msgs)


def test_countdown_fires_once_at_10_to_go():
    prev = _snap(61, [DriverSnap(code="NOR", position=1, gap_to_leader_s=0)], total=72)
    curr = _snap(62, [DriverSnap(code="NOR", position=1, gap_to_leader_s=0)], total=72)
    msgs = events_for_transition(prev, curr, "NOR")
    assert any("10 laps remaining" in m.text for m in msgs)


def test_resolve_alpha_code_no_lookup():
    assert resolve_driver_code(2024, "nor", 15) == "NOR"


def test_resolve_unknown_numeric_id_raises(monkeypatch):
    fake = MagicMock()
    fake.drivers = []
    monkeypatch.setattr("backend.standings.get_drivers", lambda year: fake)
    try:
        resolve_driver_code(2024, "2430", 15)
    except ClientInputError as extra:
        assert "2430" in str(extra)
        assert "3-letter" in str(extra)
    else:
        raise AssertionError("expected ClientInputError")
