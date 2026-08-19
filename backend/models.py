"""Pydantic response models for every V3 API endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RoundStatus = Literal["COMPLETED", "LIVE", "UPCOMING", "CANCELLED"]
SessionStatus = Literal["COMPLETED", "LIVE", "UPCOMING"]
SessionFlag = Literal["GREEN", "SC", "VSC", "RED", "UNKNOWN"]
SectorColour = Literal["purple", "green", "yellow", "grey"]
ArisAction = Literal["STAY_OUT", "BOX", "PIT_SOON", "MANAGE_PACE", "PUSH"]
CompoundCode = Literal["S", "M", "H", "I", "W"]
StandingsSource = Literal["jolpica", "unavailable", "estimated"]
DriversSource = Literal["openf1", "fastf1", "estimated"]


class CalendarRound(BaseModel):
    round_number: int
    name: str
    circuit_name: str
    circuit_key: str
    country: str
    city: str
    date_fp1: datetime | None = None
    date_fp2: datetime | None = None
    date_fp3: datetime | None = None
    date_sprint_quali: datetime | None = None
    date_sprint: datetime | None = None
    date_quali: datetime | None = None
    date_race: datetime | None = None
    status: RoundStatus
    is_sprint_weekend: bool
    cancelled_reason: str | None = None
    notes: list[str] = Field(default_factory=list)
    estimated: bool = False
    official_event_name: str | None = None


class CalendarResponse(BaseModel):
    year: int
    rounds: list[CalendarRound]
    source: Literal["fastf1", "estimated"]
    as_of: datetime


class SessionInfo(BaseModel):
    session_type: str
    session_name: str
    status: SessionStatus
    datetime_utc: datetime | None = None
    fastf1_key: str | None = None


class RoundSessionsResponse(BaseModel):
    year: int
    round_number: int
    name: str
    is_sprint_weekend: bool
    sessions: list[SessionInfo]


class WeekendSession(BaseModel):
    session_type: str
    session_name: str
    datetime_utc: datetime | None = None
    status: SessionStatus


class NextRaceResponse(BaseModel):
    year: int
    round_number: int
    name: str
    circuit_name: str
    circuit_key: str
    country: str
    city: str
    date_race: datetime | None
    status: RoundStatus
    is_sprint_weekend: bool
    is_this_weekend: bool
    countdown_seconds: int
    days_until: int
    hours_until: int
    next_session_name: str | None
    next_session_datetime: datetime | None
    sessions_this_weekend: list[WeekendSession]
    notes: list[str] = Field(default_factory=list)
    as_of: datetime
    off_season: bool = False


class Driver(BaseModel):
    driver_code: str
    full_name: str
    team_name: str
    team_colour: str | None = None
    driver_number: int | None = None
    country_code: str | None = None
    headshot_url: str | None = None
    estimated: bool = False


class DriversResponse(BaseModel):
    year: int
    drivers: list[Driver]
    source: DriversSource
    estimated_label: str | None = None


class Team(BaseModel):
    team_name: str
    team_colour: str | None = None
    logo_url: str | None = None
    position: int | None = None
    points: float | None = None
    estimated: bool = False


class TeamsResponse(BaseModel):
    year: int
    teams: list[Team]
    source: StandingsSource


class DriverStanding(BaseModel):
    position: int
    driver_code: str
    full_name: str
    team_name: str
    team_colour: str | None = None
    points: float
    wins: int
    podiums: int = 0
    fastest_laps: int = 0
    dnfs: int = 0
    gap_to_leader: float


class ConstructorStanding(BaseModel):
    position: int
    team_name: str
    team_colour: str | None = None
    points: float
    wins: int
    gap_to_leader: float


class DriverStandingsResponse(BaseModel):
    year: int
    standings: list[DriverStanding]
    source: StandingsSource
    champion_code: str | None = None
    leader_code: str | None = None


class ConstructorStandingsResponse(BaseModel):
    year: int
    standings: list[ConstructorStanding]
    source: StandingsSource
    champion_name: str | None = None


class LapRow(BaseModel):
    driver_code: str
    lap_number: int
    lap_time_ms: int | None = None
    sector1_ms: int | None = None
    sector2_ms: int | None = None
    sector3_ms: int | None = None
    compound: str | None = None
    tyre_life: int | None = None
    is_personal_best: bool = False
    pit_in_lap: bool = False
    pit_out_lap: bool = False
    track_status: str | None = None
    speed_i1: float | None = None
    speed_i2: float | None = None
    speed_fl: float | None = None
    speed_st: float | None = None
    s1_colour: SectorColour = "grey"
    s2_colour: SectorColour = "grey"
    s3_colour: SectorColour = "grey"
    team: str | None = None


class LapsResponse(BaseModel):
    year: int
    round_number: int
    session_type: str
    laps: list[LapRow]


class DriverFastest(BaseModel):
    driver_code: str
    lap_time_ms: int
    lap_number: int
    compound: str | None = None


class SectorRecord(BaseModel):
    driver_code: str
    time_ms: int


class WeatherSummary(BaseModel):
    avg_air_temp: float | None = None
    min_air_temp: float | None = None
    max_air_temp: float | None = None
    avg_track_temp: float | None = None
    min_track_temp: float | None = None
    max_track_temp: float | None = None
    rainfall: bool | None = None


class SessionSummary(BaseModel):
    year: int
    round_number: int
    session_type: str
    fastest_laps: list[DriverFastest]
    sector1_record: SectorRecord | None = None
    sector2_record: SectorRecord | None = None
    sector3_record: SectorRecord | None = None
    top_speed_kph: float | None = None
    top_speed_driver: str | None = None
    laps_completed: int
    weather: WeatherSummary
    wet_reduced_confidence: bool = False


class StintRow(BaseModel):
    driver_code: str
    stint_number: int
    compound: str | None = None
    fresh_tyre: bool | None = None
    lap_start: int
    lap_end: int
    total_laps: int
    average_lap_ms: float | None = None
    deg_rate_ms_per_lap: float | None = None


class StintsResponse(BaseModel):
    year: int
    round_number: int
    session_type: str
    stints: list[StintRow]


class TelemetryResponse(BaseModel):
    year: int
    round_number: int
    session_type: str
    driver_code: str
    sampled: bool
    distance: list[float]
    speed: list[float]
    throttle: list[float]
    brake: list[float]
    drs: list[int]
    rpm: list[float]
    gear: list[int]
    x: list[float]
    y: list[float]


class WeatherSeries(BaseModel):
    year: int
    round_number: int
    session_type: str
    timestamp: list[str]
    air_temp: list[float | None]
    track_temp: list[float | None]
    humidity: list[float | None]
    rainfall: list[bool | None]
    wind_speed: list[float | None]
    wind_direction: list[float | None]


class SessionResultRow(BaseModel):
    position: int | None
    driver_code: str
    team: str | None = None
    time_ms: int | None = None
    gap_to_winner_ms: int | None = None
    points: float | None = None
    fastest_lap: bool = False
    laps_completed: int | None = None
    status: str
    grid: int | None = None


class SessionResultsResponse(BaseModel):
    year: int
    round_number: int
    session_type: str
    results: list[SessionResultRow]


class RaceControlMessage(BaseModel):
    utc_time: str | None = None
    lap: int | None = None
    flag: str | None = None
    category: str | None = None
    message: str


class MessagesResponse(BaseModel):
    year: int
    round_number: int
    session_type: str
    messages: list[RaceControlMessage]


class CircuitPathPoint(BaseModel):
    x: float
    y: float


class CircuitPathResponse(BaseModel):
    year: int
    round_number: int
    session_type: str
    view_box: str = "0 0 440 280"
    points: list[CircuitPathPoint]
    estimated: bool = False
    corners: list[CircuitPathPoint] = Field(default_factory=list)


class GapLap(BaseModel):
    lap: int
    gaps: dict[str, float]


class GapHistoryResponse(BaseModel):
    year: int
    round_number: int
    laps: list[GapLap]


class PositionLap(BaseModel):
    lap: int
    positions: dict[str, int]


class PositionHistoryResponse(BaseModel):
    year: int
    round_number: int
    laps: list[PositionLap]


class TyreStrategyStint(BaseModel):
    driver_code: str
    lap_start: int
    lap_end: int
    compound: str | None = None
    fresh: bool | None = None
    tyre_life_at_end: int | None = None


class TyreStrategyResponse(BaseModel):
    year: int
    round_number: int
    stints: list[TyreStrategyStint]


class PitStopRow(BaseModel):
    driver_code: str
    lap: int
    duration_ms: int | None = None
    new_compound: str | None = None


class PitStopsResponse(BaseModel):
    year: int
    round_number: int
    stops: list[PitStopRow]


class FastestLapPoint(BaseModel):
    lap: int
    driver: str
    time_ms: int


class FastestLapEvolutionResponse(BaseModel):
    year: int
    round_number: int
    points: list[FastestLapPoint]


class DriverSeasonRace(BaseModel):
    round_number: int
    name: str
    finish_position: int | None = None
    qualifying_position: int | None = None
    fastest_lap: bool = False
    dnf: bool = False
    points: float | None = None
    avg_lap_ms: float | None = None


class DriverSeasonResponse(BaseModel):
    driver_code: str
    year: int
    races: list[DriverSeasonRace]
    average_finish: float | None = None
    dnf_count: int = 0
    wins: int = 0
    poles: int = 0
    fastest_laps: int = 0
    tyre_usage: dict[str, int] = Field(default_factory=dict)


class CircuitHistoryYear(BaseModel):
    year: int
    winner: str | None = None
    winner_team: str | None = None
    pole: str | None = None
    fastest_lap: str | None = None
    weather: str | None = None
    incident_notes: list[str] = Field(default_factory=list)


class CircuitHistoryResponse(BaseModel):
    circuit_key: str
    years: list[CircuitHistoryYear]


class CircuitCharacteristics(BaseModel):
    circuit_key: str
    name: str
    country: str
    lap_length_km: float | None = None
    turns: int | None = None
    drs_zones: int | None = None
    pit_loss_seconds: float | None = None
    total_laps: int | None = None
    sector_descriptions: list[str] = Field(default_factory=list)
    similar_circuits: list[str] = Field(default_factory=list)
    corner_types: list[str] = Field(default_factory=list)
    known_deg_compounds: dict[str, float] = Field(default_factory=dict)
    estimated: bool = False
    reg_note_2026: bool = False


class ForecastResponse(BaseModel):
    circuit_key: str
    source: Literal["open-meteo", "unavailable"]
    temperature_c: float | None = None
    precipitation_probability: float | None = None
    wind_speed_kmh: float | None = None
    as_of: datetime | None = None


class CompareDriversResponse(BaseModel):
    driver_a: str
    driver_b: str
    year: int
    round_number: int | None = None
    quali_wins_a: int = 0
    quali_wins_b: int = 0
    race_wins_a: int = 0
    race_wins_b: int = 0
    avg_lap_delta_ms: float | None = None
    sector1_delta_ms: float | None = None
    sector2_delta_ms: float | None = None
    sector3_delta_ms: float | None = None


class LiveStatus(BaseModel):
    is_live: bool
    year: int | None = None
    round_number: int | None = None
    session_type: str | None = None
    session_name: str | None = None
    session_key: int | None = None
    gp_name: str | None = None
    current_lap: int | None = None
    total_laps: int | None = None
    session_elapsed_seconds: int | None = None
    session_flag: SessionFlag = "UNKNOWN"
    last_success_utc: datetime | None = None
    replay_mode: bool = False


class LiveTimingRow(BaseModel):
    position: int
    driver_code: str
    gap_to_leader_s: float | None = None
    gap_to_ahead_s: float | None = None
    last_lap_ms: int | None = None
    best_lap_ms: int | None = None
    sector1_ms: int | None = None
    sector2_ms: int | None = None
    sector3_ms: int | None = None
    s1_colour: SectorColour = "grey"
    s2_colour: SectorColour = "grey"
    s3_colour: SectorColour = "grey"
    compound: str | None = None
    tyre_life: int | None = None
    stint_number: int | None = None
    pit_count: int = 0
    drs_open: bool = False
    speed_trap_kph: float | None = None
    team_colour: str | None = None


class LiveTimingResponse(BaseModel):
    is_live: bool
    session_key: int | None = None
    rows: list[LiveTimingRow]
    last_success_utc: datetime | None = None
    current_lap: int | None = None
    replay: bool = False


class LivePosition(BaseModel):
    driver_code: str
    x: float
    y: float
    team_colour: str | None = None


class LivePositionsResponse(BaseModel):
    is_live: bool
    positions: list[LivePosition]
    last_success_utc: datetime | None = None


class LiveInterval(BaseModel):
    driver_code: str
    gap_to_leader_s: float | None = None
    gap_to_ahead_s: float | None = None


class LiveIntervalsResponse(BaseModel):
    is_live: bool
    intervals: list[LiveInterval]


class LiveRaceControlResponse(BaseModel):
    is_live: bool
    messages: list[RaceControlMessage]


class LiveStintsResponse(BaseModel):
    is_live: bool
    stints: list[StintRow]


class LiveWeatherResponse(BaseModel):
    is_live: bool
    air_temp: float | None = None
    track_temp: float | None = None
    humidity: float | None = None
    rainfall: bool | None = None
    wind_speed: float | None = None
    wind_direction: float | None = None
    last_success_utc: datetime | None = None


class RecommendRequest(BaseModel):
    session_key: str | None = None
    year: int
    round_number: int
    session_type: str = "R"
    driver_code: str
    current_lap: int
    mode: Literal["live", "replay"] = "replay"


class RecommendAlternative(BaseModel):
    action: ArisAction
    compound: str | None = None
    net_delta_s: float
    note: str


class RecommendResponse(BaseModel):
    action: ArisAction
    compound_recommendation: CompoundCode | None = None
    reasoning: str
    pace_gain_s: float
    pit_cost_s: float
    net_delta_s: float
    confidence: float
    decision_record_id: str
    alternatives: list[RecommendAlternative]
    wet_reduced_confidence: bool = False
    reg_note_2026: bool = False


class SimulateRequest(BaseModel):
    session_key: str | None = None
    year: int
    round_number: int
    session_type: str = "R"
    driver_code: str
    current_lap: int = 1
    pit_lap: int | None = None
    compound: str | None = None
    sc_probability: float = 0.0
    rain_lap: int | None = None
    deg_factor: float = 1.0


class ProjectedPit(BaseModel):
    lap: int
    compound: str


class SimulateResponse(BaseModel):
    projected_finish_position: int | None = None
    total_race_time_delta_s: float
    projected_pit_stops: list[ProjectedPit]
    risk_level: Literal["Low", "Medium", "Higher"]
    baseline_delta_s: float = 0.0
    wet_reduced_confidence: bool = False
    note: str | None = None


class ChatResponse(BaseModel):
    answer: str
    cited_ids: list[str] = Field(default_factory=list)
    abstained: bool = False


class StratPlanOut(BaseModel):
    id: str
    name: str
    pit_laps: list[int]
    pit_compounds: list[str]
    start_compound: str
    expected_race_time_s: float | None = None
    description: str = ""
    recommended: bool = False
    pace_gain_s: float | None = None
    pit_cost_s: float | None = None
    risk: str = "Low"


class StratPlansResponse(BaseModel):
    year: int
    round_number: int
    driver_code: str
    plans: list[StratPlanOut]
    pit_loss_s: float | None = None


class DebriefDecision(BaseModel):
    lap: int
    aris_call: str
    actual_call: str
    outcome: str
    net_delta_s: float | None = None


class DebriefResponse(BaseModel):
    year: int
    round_number: int
    driver_code: str
    actual_position: int | None = None
    aris_projected_position: int | None = None
    actual_pits: list[int]
    decisions: list[DebriefDecision]
    summary: str
    podium: list[SessionResultRow] = Field(default_factory=list)


class HealthResponse(BaseModel):
    ok: bool
    service: str = "aris-v3-broker"
