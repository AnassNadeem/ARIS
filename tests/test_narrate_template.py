"""Ask ARIS keyword templates must not hijack strategy questions via 'lap'."""

from aris.narrate import FieldDriver, RadioField, generate_template_response

FIELD = RadioField(
    drivers=[
        FieldDriver(
            code="VER",
            name="Max Verstappen",
            compound="MEDIUM",
            tyre_life=8,
            position=1,
            gap_to_leader=0.0,
        ),
        FieldDriver(
            code="NOR",
            name="Lando Norris",
            compound="SOFT",
            tyre_life=12,
            position=2,
            gap_to_leader=1.8,
        ),
    ]
)


def _ask(q: str) -> str:
    return generate_template_response(q, FIELD, "NOR", 14, 57)


def test_laps_remaining_still_answers_count():
    text = _ask("How many laps remaining?")
    assert "Lap 14 of 57" in text
    assert "43 laps remaining" in text


def test_how_many_laps_left():
    assert "43 laps remaining" in _ask("How many laps left?")


def test_why_recommend_lap_does_not_return_lap_count():
    text = _ask("Why did ARIS recommend pitting on lap 28?")
    assert "laps remaining" not in text.lower()
    assert "recommend button" not in text.lower()


def test_what_lap_did_aris_recommend_does_not_return_lap_count():
    text = _ask("What lap did ARIS recommend pitting?")
    assert "laps remaining" not in text.lower()
    assert "recommend button" not in text.lower()
