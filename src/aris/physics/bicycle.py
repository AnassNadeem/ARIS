"""Single-track (bicycle) steady-state lap-time model. Rajamani Ch. 2; knowingly wrong.

The interpretable physics backbone for Phase 3: a grip-limited cornering speed per
corner (`v = sqrt(mu*g*R)`) plus a lumped trapezoidal straight-line profile. It omits
downforce, tyre thermal/degradation, and fuel mass on purpose — the residual against
real laps is the signal the Wk-6 ML learns. See `learning/notes/bicycle-model.md`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from aris.physics.tires import tire_pace_loss

G = 9.81  # m/s^2

# Empirical linear fuel penalty. Grip-limited cornering cancels mass (see notes), so the
# Day-2 physics is fuel-blind; fuel actually costs time on straight-line acceleration,
# which the grip-limited straight model also ignores. We add it back as a calibrated
# linear term — the long-standing F1 rule of thumb of ~0.03 s of lap time per kg of fuel.
FUEL_PENALTY_S_PER_KG = 0.03


@dataclass(frozen=True)
class Car:
    """F1-plausible single-track parameters. Defaults ≈ 2024 regs, no aero."""

    mass_kg: float = 798.0  # 2024 minimum weight incl. driver
    mu: float = 1.5  # mechanical tyre-road friction (no downforce — deliberately low)
    cog_height_m: float = 0.30
    wheelbase_m: float = 3.6
    max_speed_ms: float = 92.0  # ~331 km/h top speed ceiling


@dataclass(frozen=True)
class Corner:
    """One corner: a grip-limited arc of the given radius."""

    radius_m: float
    arc_length_m: float


@dataclass(frozen=True)
class Track:
    """A lap as a set of corners plus the total lumped straight distance."""

    corners: tuple[Corner, ...]
    straight_length_m: float
    name: str = ""
    pit_loss_s: float = 0.0  # time lost vs a green lap when this lap is an in/out (pit) lap
    # Optional per-compound deg slopes (s/lap). None → global DEFAULT_COMPOUND_SLOPE.
    compound_slopes: dict[str, float] | None = None


@dataclass(frozen=True)
class StintState:
    """Inputs to a single predicted lap. fuel_kg + pit_lap added Wk5 Day 3."""

    car: Car
    track: Track
    fuel_kg: float = 0.0  # current fuel load; heavier ⇒ slower via the linear penalty
    pit_lap: bool = False  # if this lap enters/exits the pits, add track.pit_loss_s
    compound: str = "MEDIUM"
    lap_in_stint: int = 1  # tyre life within stint (1 = out-lap)


def lateral_accel_limit(car: Car) -> float:
    """Maximum grip-limited lateral acceleration (m/s^2) — the friction circle radius."""
    return car.mu * G


def corner_speed(car: Car, radius_m: float) -> float:
    """Grip-limited cornering speed sqrt(mu*g*R), capped at the car's top speed."""
    if radius_m <= 0:
        raise ValueError(f"corner radius must be positive, got {radius_m}")
    return min(math.sqrt(lateral_accel_limit(car) * radius_m), car.max_speed_ms)


def longitudinal_load_transfer(car: Car, accel_ms2: float) -> float:
    """Axle load shift |m*a*h/L| under longitudinal accel; symmetric for accel/braking."""
    return abs(car.mass_kg * accel_ms2 * car.cog_height_m / car.wheelbase_m)


def _straight_time(
    distance_m: float, entry_speed_ms: float, max_speed_ms: float, accel_ms2: float
) -> float:
    """Time over a straight: accelerate from entry to v_max and brake back, grip-limited."""
    if distance_m <= 0:
        return 0.0
    # distance to reach v_max from entry (and the equal distance to brake back to it)
    ramp_dist = (max_speed_ms**2 - entry_speed_ms**2) / (2 * accel_ms2)
    if 2 * ramp_dist <= distance_m:
        # accelerate, cruise at v_max, brake: full trapezoid
        ramp_time = (max_speed_ms - entry_speed_ms) / accel_ms2
        cruise_time = (distance_m - 2 * ramp_dist) / max_speed_ms
        return 2 * ramp_time + cruise_time
    # straight too short to reach v_max: triangular profile peaking at v_peak
    v_peak = math.sqrt(entry_speed_ms**2 + accel_ms2 * distance_m)
    return 2 * (v_peak - entry_speed_ms) / accel_ms2


def predict_lap_time(state: StintState) -> float:
    """Predicted lap time (s): grip-limited corner times + one lumped straight profile."""
    car, track = state.car, state.track
    if not track.corners:
        raise ValueError("track has no corners")

    speeds = [corner_speed(car, c.radius_m) for c in track.corners]
    corner_time = sum(c.arc_length_m / v for c, v in zip(track.corners, speeds, strict=True))

    # Distribute the straight distance across one inter-corner segment per corner, so the
    # car must brake and re-accelerate at every corner exit — a real lap cannot do all its
    # braking in one place. Each segment runs from the mean corner speed up toward v_max
    # and back. (Lumping it into a single straight makes the lap implausibly fast.)
    mean_corner_speed = sum(speeds) / len(speeds)
    n = len(track.corners)
    segment_time = _straight_time(
        track.straight_length_m / n,
        entry_speed_ms=mean_corner_speed,
        max_speed_ms=car.max_speed_ms,
        accel_ms2=lateral_accel_limit(car),  # longitudinal grip == lateral grip (friction circle)
    )
    physics_time = corner_time + n * segment_time

    fuel_time = FUEL_PENALTY_S_PER_KG * state.fuel_kg
    pit_time = track.pit_loss_s if state.pit_lap else 0.0
    tire_time = tire_pace_loss(
        state.compound, state.lap_in_stint, slopes=track.compound_slopes
    )
    return physics_time + fuel_time + pit_time + tire_time


def approach_delta_s(
    track: Track,
    *,
    corner_index: int,
    distance_m: float,
    mode: str,
    car: Car | None = None,
) -> float:
    """Lap-time cost of lifting or braking ``distance_m`` earlier into a corner.

    ``corner_index`` is 1-based (T1…Tn). Extends the existing per-corner straight
    segments: the final ``distance_m`` of the approach to that corner is covered
    at corner speed instead of the grip-limited accel/cruise profile.

    - ``mode="lift"``: throttle lift / early coast into the corner.
    - ``mode="brake"``: brake point moved earlier by ``distance_m`` (same
      kinematic cost under this lumped model; kept as a distinct action so
      callers can narrate intent separately).

    Returns a non-negative delta in seconds (earlier lift/brake ⇒ slower lap).
    """
    if distance_m <= 0:
        return 0.0
    if mode not in {"lift", "brake"}:
        raise ValueError(f"mode must be 'lift' or 'brake', got {mode!r}")
    c = car or Car()
    corners = track.corners
    if not corners:
        raise ValueError("track has no corners")
    if corner_index < 1 or corner_index > len(corners):
        raise ValueError(
            f"corner_index {corner_index} out of range for {len(corners)}-corner track"
        )
    idx = corner_index - 1
    n = len(corners)
    segment_m = track.straight_length_m / n
    d = min(float(distance_m), segment_m)

    speeds = [corner_speed(c, corner.radius_m) for corner in corners]
    # Entry to this approach: previous corner speed (or this corner if first).
    entry = speeds[idx - 1] if idx > 0 else speeds[idx]
    v_corner = speeds[idx]
    accel = lateral_accel_limit(c)

    baseline = _straight_time(
        segment_m,
        entry_speed_ms=entry,
        max_speed_ms=c.max_speed_ms,
        accel_ms2=accel,
    )
    # Early lift/brake: cover (segment - d) with the normal profile, then the
    # last d metres at corner speed (already slowed / coasting).
    shortened = _straight_time(
        max(0.0, segment_m - d),
        entry_speed_ms=entry,
        max_speed_ms=c.max_speed_ms,
        accel_ms2=accel,
    )
    coast = d / max(v_corner, 1e-6)
    modified = shortened + coast
    return max(0.0, modified - baseline)


def predict_lap_time_with_line_action(
    state: StintState,
    *,
    corner_index: int,
    distance_m: float,
    mode: str,
) -> float:
    """Baseline ``predict_lap_time`` plus a single-corner lift/brake delta."""
    return predict_lap_time(state) + approach_delta_s(
        state.track,
        corner_index=corner_index,
        distance_m=distance_m,
        mode=mode,
        car=state.car,
    )


def bahrain_2024() -> Track:
    """Bahrain International Circuit ≈ 5.412 km, 15 corners. Radii eyeballed off the map."""
    # (radius_m, arc_length_m) — approximate, not surveyed. See notes for the caveat.
    corners = (
        Corner(70, 90),    # T1
        Corner(40, 50),    # T2-3 complex
        Corner(120, 80),   # T4
        Corner(55, 60),    # T5
        Corner(90, 70),    # T6-7
        Corner(45, 55),    # T8
        Corner(160, 90),   # T9-10
        Corner(50, 60),    # T11
        Corner(110, 80),   # T12
        Corner(35, 45),    # T13
        Corner(200, 100),  # T14 (fast)
        Corner(60, 65),    # T15
        Corner(80, 70),    # extra esses
        Corner(140, 85),   # sweeper
        Corner(48, 55),    # final
    )
    arc_total = sum(c.arc_length_m for c in corners)
    lap_length_m = 5412.0
    return Track(
        corners=corners,
        straight_length_m=lap_length_m - arc_total,
        name="Bahrain",
        pit_loss_s=21.0,  # ≈ pit-lane time loss vs a green lap at Bahrain
    )
