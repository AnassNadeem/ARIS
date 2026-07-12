"""Pre-race Strat A/B/C generator."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aris.io import db
from aris.plan.weekend_form import DriverForm, weekend_form
from aris.simulate import simulate_full_race
from aris.state import RaceState
from aris.tracks import load_track_config


class StratPlan(BaseModel):
    id: str
    name: str
    pit_laps: list[int]
    pit_compounds: list[str]
    start_compound: str = "MEDIUM"
    expected_race_time_s: float | None = None
    description: str = ""
    recommended: bool = False
    editable: bool = True


class StratPlanSet(BaseModel):
    year: int
    round_no: int
    driver_code: str
    plans: list[StratPlan] = Field(default_factory=list)
    weather: dict | None = None


def _base_state(
    session_id: int, driver_id: int, year: int, round_no: int, country: str, total_laps: int
) -> RaceState:
    return RaceState(
        session_id=session_id,
        driver_id=driver_id,
        driver_code="",
        driver_name="",
        year=year,
        round_no=round_no,
        country=country,
        lap_number=1,
        compound="MEDIUM",
        tyre_life=1,
        fuel_kg=110.0,
        laps_remaining=total_laps - 1,
        total_laps=total_laps,
    )


def generate_strat_plans(
    session_id: int,
    driver_id: int,
    *,
    year: int,
    round_no: int,
    country: str,
    driver_code: str,
    form: DriverForm | None = None,
    weather: dict | None = None,
) -> StratPlanSet:
    track = load_track_config(country)
    total = track.total_laps
    if weather is None:
        try:
            weather = db.fetch_session_weather(session_id)
        except Exception:
            weather = None

    if form is None:
        try:
            forms = weekend_form(year, round_no)
            form = next((f for f in forms if f.driver_id == driver_id), None)
        except Exception:
            form = None

    high_deg = form is not None and form.deg_slope is not None and form.deg_slope > 0.05
    hot_track = weather and (weather.get("track_temp_c") or 0) > 40

    plans = [
        StratPlan(
            id="A",
            name="Strat A — One-stop early",
            pit_laps=[15],
            pit_compounds=["HARD"],
            start_compound="MEDIUM",
            description="Box lap 14-16 when deg is high from FP long runs",
        ),
        StratPlan(
            id="B",
            name="Strat B — One-stop late",
            pit_laps=[24],
            pit_compounds=["HARD"],
            start_compound="MEDIUM",
            description="Extend first stint when mediums hold from quali pace",
        ),
        StratPlan(
            id="C",
            name="Strat C — Two-stop aggressive",
            pit_laps=[14, 32],
            pit_compounds=["HARD", "MEDIUM"],
            start_compound="SOFT" if hot_track else "MEDIUM",
            description="Two-stop when track temp is high and deg is steep",
        ),
    ]

    if high_deg:
        plans[0].pit_laps = [14]
    if hot_track:
        plans[2].recommended = True

    base = _base_state(session_id, driver_id, year, round_no, country, total)
    base = base.model_copy(update={"driver_code": driver_code, "compound": plans[0].start_compound})

    scored: list[tuple[StratPlan, float]] = []
    for plan in plans:
        t = simulate_full_race(
            base.model_copy(update={"compound": plan.start_compound}),
            pit_laps=plan.pit_laps,
            pit_compounds=plan.pit_compounds,
        )
        plan.expected_race_time_s = round(t, 1)
        scored.append((plan, t))

    scored.sort(key=lambda x: x[1])
    for i, (plan, _) in enumerate(scored):
        plan.recommended = i == 0

    return StratPlanSet(
        year=year,
        round_no=round_no,
        driver_code=driver_code,
        plans=[p for p, _ in scored],
        weather=weather,
    )
