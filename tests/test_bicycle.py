"""Physical-sanity tests for aris.physics.bicycle. The model is wrong; the physics isn't."""

import math

import pytest

from aris.physics.bicycle import (
    FUEL_PENALTY_S_PER_KG,
    Car,
    Corner,
    StintState,
    Track,
    bahrain_2024,
    corner_speed,
    lateral_accel_limit,
    longitudinal_load_transfer,
    predict_lap_time,
)


class TestCornerSpeed:
    def test_matches_friction_circle_formula(self):
        car = Car(mu=1.5, max_speed_ms=1000.0)  # cap high so it never clips
        r = 100.0
        assert corner_speed(car, r) == pytest.approx(math.sqrt(1.5 * 9.81 * r))

    def test_tighter_radius_is_slower(self):
        car = Car(max_speed_ms=1000.0)
        assert corner_speed(car, 30.0) < corner_speed(car, 200.0)

    def test_capped_at_max_speed(self):
        car = Car(max_speed_ms=50.0)
        assert corner_speed(car, 10_000.0) == pytest.approx(50.0)

    def test_more_grip_is_faster(self):
        slick = Car(mu=1.8, max_speed_ms=1000.0)
        greasy = Car(mu=0.9, max_speed_ms=1000.0)
        assert corner_speed(slick, 100.0) > corner_speed(greasy, 100.0)

    def test_nonpositive_radius_raises(self):
        with pytest.raises(ValueError, match="radius must be positive"):
            corner_speed(Car(), 0.0)


class TestLoadTransfer:
    def test_zero_accel_zero_transfer(self):
        assert longitudinal_load_transfer(Car(), 0.0) == 0.0

    def test_monotonic_in_accel(self):
        car = Car()
        assert (
            longitudinal_load_transfer(car, 5.0)
            < longitudinal_load_transfer(car, 10.0)
            < longitudinal_load_transfer(car, 20.0)
        )

    def test_symmetric_accel_vs_braking(self):
        car = Car()
        assert longitudinal_load_transfer(car, 8.0) == pytest.approx(
            longitudinal_load_transfer(car, -8.0)
        )

    def test_heavier_car_transfers_more(self):
        light = Car(mass_kg=700.0)
        heavy = Car(mass_kg=900.0)
        assert longitudinal_load_transfer(heavy, 10.0) > longitudinal_load_transfer(light, 10.0)


class TestPredictLapTime:
    def test_positive_and_finite(self):
        t = predict_lap_time(StintState(Car(), bahrain_2024()))
        assert math.isfinite(t)
        assert t > 0

    def test_order_of_magnitude_plausible(self):
        # no-downforce model: far slower than the real ~93 s pole, but order-right
        t = predict_lap_time(StintState(Car(), bahrain_2024()))
        assert 60.0 < t < 240.0

    def test_more_grip_gives_shorter_lap(self):
        track = bahrain_2024()
        fast = predict_lap_time(StintState(Car(mu=1.8), track))
        slow = predict_lap_time(StintState(Car(mu=1.0), track))
        assert fast < slow

    def test_invariant_to_mass_in_day2_model(self):
        # mass cancels in grip-limited cornering — a known, documented Day-2 limitation
        track = bahrain_2024()
        t_light = predict_lap_time(StintState(Car(mass_kg=700.0), track))
        t_heavy = predict_lap_time(StintState(Car(mass_kg=900.0), track))
        assert t_light == pytest.approx(t_heavy)

    def test_no_corners_raises(self):
        with pytest.raises(ValueError, match="no corners"):
            predict_lap_time(StintState(Car(), Track(corners=(), straight_length_m=1000.0)))

    def test_lateral_accel_limit_is_mu_g(self):
        assert lateral_accel_limit(Car(mu=1.5)) == pytest.approx(1.5 * 9.81)

    def test_longer_straight_takes_more_time(self):
        car = Car()
        short = predict_lap_time(StintState(car, Track((Corner(80, 70),), 1000.0)))
        long = predict_lap_time(StintState(car, Track((Corner(80, 70),), 3000.0)))
        assert long > short


class TestFuelAndPitLoss:
    def test_fuel_adds_time_linearly(self):
        track = bahrain_2024()
        dry = predict_lap_time(StintState(Car(), track, fuel_kg=0.0))
        loaded = predict_lap_time(StintState(Car(), track, fuel_kg=100.0))
        assert loaded - dry == pytest.approx(FUEL_PENALTY_S_PER_KG * 100.0)

    def test_more_fuel_is_slower(self):
        track = bahrain_2024()
        light = predict_lap_time(StintState(Car(), track, fuel_kg=10.0))
        heavy = predict_lap_time(StintState(Car(), track, fuel_kg=90.0))
        assert heavy > light

    def test_zero_fuel_recovers_pure_physics(self):
        track = bahrain_2024()
        with_default = predict_lap_time(StintState(Car(), track))
        with_zero = predict_lap_time(StintState(Car(), track, fuel_kg=0.0))
        assert with_default == pytest.approx(with_zero)

    def test_pit_lap_adds_exactly_pit_loss(self):
        track = bahrain_2024()
        green = predict_lap_time(StintState(Car(), track, fuel_kg=30.0, pit_lap=False))
        pit = predict_lap_time(StintState(Car(), track, fuel_kg=30.0, pit_lap=True))
        assert pit - green == pytest.approx(track.pit_loss_s)

    def test_no_pit_loss_when_track_has_none(self):
        plain = Track((Corner(80, 70),), 2000.0)  # pit_loss_s defaults to 0
        green = predict_lap_time(StintState(Car(), plain, pit_lap=False))
        pit = predict_lap_time(StintState(Car(), plain, pit_lap=True))
        assert pit == pytest.approx(green)
