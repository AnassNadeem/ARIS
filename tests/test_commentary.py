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


def test_sc_message_includes_reduced_pit_loss():
    prev = _snap(10, [DriverSnap(code="NOR", position=1, gap_to_leader_s=0)])
    curr = _snap(
        11,
        [DriverSnap(code="NOR", position=1, gap_to_leader_s=0)],
    )
    curr.messages = [{"flag": "SC", "category": "SafetyCar", "message": "SAFETY CAR DEPLOYED"}]
    msgs = events_for_transition(prev, curr, "NOR", pit_loss_s=18.5)
    sc = [m for m in msgs if "SC deployed" in m.text or "SAFETY CAR" in m.text]
    assert sc, msgs
    assert "Pit loss now ~6s" in sc[0].text
    assert sc[0].text.count("SC deployed") == 1


def test_countdown_fires_once_at_10_to_go():
    prev = _snap(61, [DriverSnap(code="NOR", position=1, gap_to_leader_s=0)], total=72)
    curr = _snap(62, [DriverSnap(code="NOR", position=1, gap_to_leader_s=0)], total=72)
    msgs = events_for_transition(prev, curr, "NOR")
    assert any("10 laps remaining" in m.text for m in msgs)


def test_approaching_window_at_tyre_life_13():
    from aris.commentary import CommentaryEngine

    prev = _snap(
        13,
        [DriverSnap(code="NOR", position=1, gap_to_leader_s=0, tyre_life=12, compound="MEDIUM")],
        total=72,
    )
    curr = _snap(
        14,
        [DriverSnap(code="NOR", position=1, gap_to_leader_s=0, tyre_life=13, compound="MEDIUM")],
        total=72,
    )
    msgs = events_for_transition(prev, curr, "NOR", deg_rate_s=0.05)
    hits = [m for m in msgs if "Pit window opens in ~5 laps" in m.text]
    assert hits, msgs
    assert "Current deg rate 0.050s/lap." in hits[0].text

    later = _snap(
        15,
        [DriverSnap(code="NOR", position=1, gap_to_leader_s=0, tyre_life=14, compound="MEDIUM")],
        total=72,
    )
    skipped = events_for_transition(curr, later, "NOR", deg_rate_s=0.05)
    assert not any("Pit window opens" in m.text for m in skipped)

    engine = CommentaryEngine()
    engine.prev_field = prev
    first = engine.generate(curr, "NOR", 14, 72, [], deg_rate_s=0.05)
    second = engine.generate(later, "NOR", 15, 72, [], deg_rate_s=0.05)
    assert sum("Pit window opens" in m.text for m in first) == 1
    assert not any("Pit window opens" in m.text for m in second)


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


def _field_drivers(*, life: int = 18) -> list[DriverSnap]:
    return [
        DriverSnap(code="NOR", position=1, gap_to_leader_s=0.0, compound="MEDIUM", tyre_life=life, stint_number=1),
        DriverSnap(code="VER", position=2, gap_to_leader_s=1.2, compound="MEDIUM", tyre_life=life, stint_number=1),
        DriverSnap(code="PIA", position=3, gap_to_leader_s=2.4, compound="MEDIUM", tyre_life=life + 3, stint_number=1),
        DriverSnap(code="LEC", position=4, gap_to_leader_s=3.1, compound="HARD", tyre_life=6, stint_number=2),
        DriverSnap(code="HAM", position=5, gap_to_leader_s=4.0, compound="MEDIUM", tyre_life=life + 5, stint_number=1),
        DriverSnap(code="RUS", position=6, gap_to_leader_s=5.2, compound="MEDIUM", tyre_life=life + 1, stint_number=1),
    ]


def test_field_board_fires_at_lap_10_and_20_not_11():
    from aris.commentary import CommentaryEngine

    engine = CommentaryEngine()
    engine.prev_field = _snap(9, _field_drivers())
    at10 = engine.generate(_snap(10, _field_drivers()), "NOR", 10, 72, [])
    field10 = [m for m in at10 if m.type == "FIELD"]
    assert field10, at10
    assert field10[0].text.startswith("FIELD:")
    for code in ("VER", "PIA", "LEC", "HAM"):
        assert code in field10[0].text
    assert "NOR" not in field10[0].text.split("FIELD:", 1)[-1]
    assert "already pitted" in field10[0].text

    at11 = engine.generate(_snap(11, _field_drivers()), "NOR", 11, 72, [])
    assert not any(m.type == "FIELD" for m in at11), at11

    at20 = engine.generate(_snap(20, _field_drivers()), "NOR", 20, 72, [])
    assert any(m.type == "FIELD" for m in at20), at20


def test_field_board_on_first_lap():
    from aris.commentary import CommentaryEngine

    engine = CommentaryEngine()
    msgs = engine.generate(_snap(1, _field_drivers(life=1)), "NOR", 1, 72, [])
    assert any(m.type == "FIELD" for m in msgs), msgs


def test_rain_onset_emits_wet_heuristic_alert():
    prev = _snap(20, [DriverSnap(code="LEC", position=1, compound="MEDIUM")])
    curr = _snap(21, [DriverSnap(code="LEC", position=1, compound="MEDIUM")])
    prev.rainfall = False
    curr.rainfall = True
    msgs = events_for_transition(prev, curr, "LEC")
    rain = [m for m in msgs if "RAIN DETECTED" in m.text]
    assert rain, msgs
    assert rain[0].type == "ALERT"
    assert "WET HEURISTIC" in rain[0].text


def test_rain_clearing_emits_info():
    prev = _snap(24, [DriverSnap(code="LEC", position=1, compound="INTER")])
    curr = _snap(25, [DriverSnap(code="LEC", position=1, compound="INTER")])
    prev.rainfall = True
    curr.rainfall = False
    msgs = events_for_transition(prev, curr, "LEC")
    assert any("Rain easing" in m.text for m in msgs), msgs


def test_hold_inter_every_five_laps_while_wet():
    prev = _snap(24, [DriverSnap(code="LEC", position=1, compound="INTER")])
    curr = _snap(25, [DriverSnap(code="LEC", position=1, compound="INTER")])
    prev.rainfall = True
    curr.rainfall = True
    msgs = events_for_transition(prev, curr, "LEC")
    assert any("Hold INTER" in m.text for m in msgs), msgs


def test_field_board_should_fire_cadence():
    from aris.engine.clock import SectorEvent
    from aris.engine.triggers import field_board_should_fire
    from aris.field.state import FieldState, ReplayIndex

    session = MagicMock()

    def ev(lap: int, new_lap: bool = True) -> SectorEvent:
        return SectorEvent(
            index=ReplayIndex(lap, 0),
            field=MagicMock(spec=FieldState),
            is_new_lap=new_lap,
            is_race_complete=False,
        )

    assert field_board_should_fire(session, ev(1)) is True
    assert field_board_should_fire(session, ev(10)) is True
    assert field_board_should_fire(session, ev(20)) is True
    assert field_board_should_fire(session, ev(11)) is False
    assert field_board_should_fire(session, ev(10, new_lap=False)) is False

