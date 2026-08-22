"""Pydantic response models for every V3 API endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RoundStatus = Literal["COMPLETED", "LIVE", "UPCOMING", "CANCELLED"]
SessionStatus = Literal["COMPLETED", "LIVE", "UPCOMING"]
SessionFlag = Literal["GREEN", "SC", "VSC", "RED", "UNKNOWN"]
SectorColour = Literal["purple", "green", "yellow", "grey"]
ArisAction = Literal["STAY_OUT", "BOX", "PIT_SOON", "MANAGE_PACE", "PUSH"]
CompoundCode = Literal["S", "M", "H", "I", "W"]
StandingsSource = Literal["jolpica", "unavailable", "estimated"]
DriversSource = Literal["openf1", "fastf1", "estimated"]


class CalendarSessionWindow(BaseModel):
    type: str
    date_start: datetime
    date_end: datetime
    key: str | None = None


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
    sessions: list[CalendarSessionWindow] = Field(default_factory=list)


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
    is_live: bool = False


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
    podiums: int = 0
    drivers: list[str] = Field(default_factory=list)
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


class CircuitCorner(BaseModel):
    number: int
    letter: str = ""
    angle: float | None = None
    distance: float | None = None
    x: float
    y: float
    description: str | None = None


class CircuitMarker(BaseModel):
    kind: str
    x: float
    y: float
    label: str


class CircuitMapBounds(BaseModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class CircuitMapResponse(BaseModel):
    year: int
    round_number: int
    x: list[float] = Field(default_factory=list)
    y: list[float] = Field(default_factory=list)
    corners: list[CircuitCorner] = Field(default_factory=list)
    markers: list[CircuitMarker] = Field(default_factory=list)
    drs_segments: list[list[int]] = Field(default_factory=list)
    pit_lane_x: list[float] = Field(default_factory=list)
    pit_lane_y: list[float] = Field(default_factory=list)
    pit_stalls: list[list[float]] = Field(default_factory=list)
    bounds: CircuitMapBounds | None = None
    available: bool = True
    fallback: bool = False
    error: str | None = None
    view_box: str = "0 0 440 280"


class SessionCarPosition(BaseModel):
    driver_code: str
    x: float
    y: float
    team_colour: str | None = None
    is_pitted: bool = False
    is_dnf: bool = False
    path_frac: float = 0.0
    speed_ms: float | None = None


class SessionPositionsResponse(BaseModel):
    year: int
    round_number: int
    session_type: str
    lap: int
    positions: list[SessionCarPosition] = Field(default_factory=list)


class CircuitPathXY(BaseModel):
    x: list[float] = Field(default_factory=list)
    y: list[float] = Field(default_factory=list)


class SessionPositionsAllResponse(BaseModel):
    year: int
    round_number: int
    session_type: str
    laps: dict[str, list[SessionCarPosition]] = Field(default_factory=dict)
    circuit_path: CircuitPathXY | None = None


class CommentaryEvent(BaseModel):
    type: str
    text: str


class SessionEventsResponse(BaseModel):
    year: int
    round_number: int
    session_type: str = "R"
    lap: int
    events: list[CommentaryEvent] = Field(default_factory=list)


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
    winner_grid: int | None = None
    race_name: str | None = None


class CircuitHistoryResponse(BaseModel):
    circuit_key: str
    years: list[CircuitHistoryYear]
    from_year: int = 2018
    typical_stop_count: float | None = None
    median_first_stop_lap: int | None = None
    most_common_winner: str | None = None
    analysis: str = ""


class ArisCircuitNotes(BaseModel):
    undercut_effectiveness: str = ""
    tyre_compound_tendencies: str = ""
    overtaking_difficulty: str = ""
    sc_probability_history: str = ""
    summary: str = ""


class CircuitCharacteristics(BaseModel):
    circuit_key: str
    name: str
    country: str
    lap_length_km: float | None = None
    turns: int | None = None
    drs_zones: int | None = None
    pit_loss_seconds: float | None = None
    total_laps: int | None = None
    tyre_stress_rating: str | None = None
    track_evolution_rating: str | None = None
    sector_descriptions: list[str] = Field(default_factory=list)
    similar_circuits: list[str] = Field(default_factory=list)
    corner_types: list[str] = Field(default_factory=list)
    known_deg_compounds: dict[str, float] = Field(default_factory=dict)
    aris_notes: ArisCircuitNotes | None = None
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
    race_pace_median_delta_ms: float | None = None
    fastest_lap_a_ms: int | None = None
    fastest_lap_b_ms: int | None = None


class LiveStatus(BaseModel):
    is_live: bool
    year: int | None = None
    round_number: int | None = None
    session_type: str | None = None
    session_name: str | None = None
    session_key: int | None = None
    gp_name: str | None = None
    circuit: str | None = None
    current_lap: int | None = None
    total_laps: int | None = None
    session_elapsed_seconds: int | None = None
    session_remaining_seconds: int | None = None
    session_flag: SessionFlag = "UNKNOWN"
    last_success_utc: datetime | None = None
    replay_mode: bool = False
    simulated: bool = False
    as_of: datetime | None = None
    session: dict[str, Any] | None = None
    error: str | None = None
    source: str | None = None
    view_only: bool = False
    aris_ready: bool = False


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
    eliminated: bool = False
    in_pit: bool = False
    fastest_lap: bool = False
    reason: str | None = None
    q1_ms: int | None = None
    q2_ms: int | None = None
    q3_ms: int | None = None


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
    is_pitted: bool = False
    is_dnf: bool = False
    path_frac: float = 0.0
    speed_ms: float | None = None
    reason: str | None = None


class LivePositionsResponse(BaseModel):
    is_live: bool
    positions: list[LivePosition]
    last_success_utc: datetime | None = None
    circuit_path: CircuitPathXY | None = None


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
    pressure: float | None = None
    last_success_utc: datetime | None = None


class QualiWindow(BaseModel):
    id: str
    label: str
    start_s: int
    end_s: int


class ReplayFrameResponse(BaseModel):
    session_key: int
    as_of: datetime
    elapsed_s: int
    duration_s: int
    date_start: datetime | None = None
    date_end: datetime | None = None
    timing: LiveTimingResponse
    weather: LiveWeatherResponse
    positions: LivePositionsResponse
    source: str = "openf1"
    quali_phase: str | None = None
    quali_windows: list[QualiWindow] = Field(default_factory=list)


class RecommendRequest(BaseModel):
    session_key: str | None = None
    year: int
    round_number: int
    session_type: str = "R"
    driver_code: str
    current_lap: int
    mode: Literal["live", "replay", "pre_race"] = "replay"


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
    data_source: str | None = None
    lap_note: str | None = None
    ingest_status: str | None = None


class CustomPitStop(BaseModel):
    lap: int
    compound: str


class SimulateRequest(BaseModel):
    session_key: str | None = None
    year: int
    round_number: int
    session_type: str = "R"
    driver_code: str
    current_lap: int = 1
    pit_lap: int | None = None
    compound: str | None = None
    pit_stops: list[CustomPitStop] = Field(default_factory=list)
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
    delta_vs_aris_s: float | None = None
    delta_vs_actual_s: float | None = None
    pace_gain_s: float | None = None
    pit_cost_s: float | None = None
    wet_reduced_confidence: bool = False
    note: str | None = None
    data_source: str | None = None


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
    reasoning: str | None = None
    user_override: str | None = None
    pace_gain_s: float | None = None
    pit_cost_s: float | None = None


class StrategyColumn(BaseModel):
    label: str
    position: int | None = None
    plan_name: str | None = None
    pits: list[ProjectedPit] = Field(default_factory=list)


class DebriefStats(BaseModel):
    laps_led: int = 0
    pit_time_s: float | None = None
    compounds_used: list[str] = Field(default_factory=list)
    positions_gained: int | None = None
    fastest_lap_ms: int | None = None
    field_fastest_lap_ms: int | None = None
    deg_rate_ms: float | None = None
    field_deg_rate_ms: float | None = None
    aris_correct: int = 0
    aris_total: int = 0
    sc_events: int = 0
    sc_handled: int = 0


class DebriefDeltaPoint(BaseModel):
    lap: int
    aris_vs_actual_s: float = 0.0
    optimal_vs_actual_s: float = 0.0


class DebriefResponse(BaseModel):
    year: int
    round_number: int
    driver_code: str
    actual_position: int | None = None
    aris_projected_position: int | None = None
    optimal_position: int | None = None
    actual_pits: list[int]
    decisions: list[DebriefDecision]
    summary: str
    podium: list[SessionResultRow] = Field(default_factory=list)
    aris_strategy: StrategyColumn | None = None
    actual_strategy: StrategyColumn | None = None
    optimal_strategy: StrategyColumn | None = None
    stats: DebriefStats | None = None
    delta_series: list[DebriefDeltaPoint] = Field(default_factory=list)


class ArisStatsResponse(BaseModel):
    lap_time_mae_s: float
    decision_match_rate: float
    never_pit_baseline: float
    avg_position_delta: float
    clean_delta: float
    disrupted_delta: float


class HealthResponse(BaseModel):
    ok: bool
    service: str = "aris-v3-broker"
