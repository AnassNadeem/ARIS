"""Tyre warm-up helpers (T9.1 wiring into simulate)."""

from aris.physics.tyre_warmup import apply_warmup, tyre_warmup_for_lap, tyre_warmup_penalty


def test_apply_warmup_lap1_and_lap2():
    base = 90.0
    hard_1 = apply_warmup(base, "HARD", 1, is_out_lap=True)
    hard_2 = apply_warmup(base, "HARD", 2, is_out_lap=False)
    hard_3 = apply_warmup(base, "HARD", 3, is_out_lap=False)
    assert hard_1 == 90.8
    assert hard_2 == 90.3
    assert hard_3 == 90.0
    assert apply_warmup(base, "SOFT", 1, True) < hard_1
    assert apply_warmup(base, "MEDIUM", 1, True) < hard_1
    assert apply_warmup(base, "MEDIUM", 1, True) > apply_warmup(base, "SOFT", 1, True)


def test_warmup_for_lap_zero_after_lap2():
    assert tyre_warmup_for_lap("HARD", 3) == 0.0
    assert tyre_warmup_for_lap("SOFT", 10) == 0.0


def test_total_penalty_is_lap1_plus_lap2():
    assert tyre_warmup_penalty("HARD") == 1.1
    assert tyre_warmup_penalty("MEDIUM") == 0.7
    assert tyre_warmup_penalty("SOFT") == 0.2
