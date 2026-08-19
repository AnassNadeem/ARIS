"""ARIS V3 FastAPI data broker."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.paths import ROOT  # noqa: F401  # sys.path bootstrap

from backend import analytics, aris_api, calendar, live, sessions, standings
from backend.models import (
    CalendarResponse,
    ChatResponse,
    CircuitCharacteristics,
    CircuitHistoryResponse,
    CircuitPathResponse,
    CompareDriversResponse,
    ConstructorStandingsResponse,
    DebriefResponse,
    DriverSeasonResponse,
    DriverStandingsResponse,
    DriversResponse,
    FastestLapEvolutionResponse,
    ForecastResponse,
    GapHistoryResponse,
    HealthResponse,
    LapsResponse,
    LiveIntervalsResponse,
    LivePositionsResponse,
    LiveRaceControlResponse,
    LiveStatus,
    LiveStintsResponse,
    LiveTimingResponse,
    LiveWeatherResponse,
    MessagesResponse,
    NextRaceResponse,
    PitStopsResponse,
    PositionHistoryResponse,
    RecommendRequest,
    RecommendResponse,
    RoundSessionsResponse,
    SessionResultsResponse,
    SessionSummary,
    SimulateRequest,
    SimulateResponse,
    StintsResponse,
    StratPlansResponse,
    TeamsResponse,
    TelemetryResponse,
    TyreStrategyResponse,
    WeatherSeries,
)

app = FastAPI(title="ARIS V3 Data Broker", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AsOf = Annotated[datetime | None, Query(description="Override current time (ISO-8601 UTC) for state testing")]


def _http(exc: Exception, status: int = 404) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True)


@app.get("/api/calendar/{year}", response_model=CalendarResponse)
def api_calendar(year: int, as_of: AsOf = None) -> CalendarResponse:
    if year not in {2024, 2025, 2026}:
        raise HTTPException(400, "year must be 2024, 2025, or 2026")
    return calendar.get_calendar(year, as_of=as_of)


@app.get("/api/calendar/{year}/{round_number}/sessions", response_model=RoundSessionsResponse)
def api_round_sessions(year: int, round_number: int, as_of: AsOf = None) -> RoundSessionsResponse:
    try:
        return calendar.get_round_sessions(year, round_number, as_of=as_of)
    except KeyError as exc:
        raise _http(exc) from exc


@app.get("/api/next-race", response_model=NextRaceResponse)
def api_next_race(as_of: AsOf = None, year: int | None = None) -> NextRaceResponse:
    try:
        return calendar.next_race(as_of=as_of, year=year)
    except Exception as exc:
        raise _http(exc, 500) from exc


@app.get("/api/drivers/{year}", response_model=DriversResponse)
def api_drivers(year: int) -> DriversResponse:
    return standings.get_drivers(year)


@app.get("/api/teams/{year}", response_model=TeamsResponse)
def api_teams(year: int) -> TeamsResponse:
    return standings.get_teams(year)


@app.get("/api/standings/drivers/{year}", response_model=DriverStandingsResponse)
def api_driver_standings(year: int) -> DriverStandingsResponse:
    return standings.driver_standings(year)


@app.get("/api/standings/constructors/{year}", response_model=ConstructorStandingsResponse)
def api_constructor_standings(year: int) -> ConstructorStandingsResponse:
    return standings.constructor_standings(year)


@app.get("/api/session/{year}/{round_number}/{session_type}/laps", response_model=LapsResponse)
def api_laps(year: int, round_number: int, session_type: str) -> LapsResponse:
    try:
        return sessions.session_laps(year, round_number, session_type)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/summary", response_model=SessionSummary)
def api_summary(year: int, round_number: int, session_type: str) -> SessionSummary:
    try:
        return sessions.session_summary(year, round_number, session_type)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/stints", response_model=StintsResponse)
def api_stints(year: int, round_number: int, session_type: str) -> StintsResponse:
    try:
        return sessions.session_stints(year, round_number, session_type)
    except Exception as exc:
        raise _http(exc) from exc


@app.get(
    "/api/session/{year}/{round_number}/{session_type}/telemetry/{driver_code}",
    response_model=TelemetryResponse,
)
def api_telemetry(
    year: int, round_number: int, session_type: str, driver_code: str, full: bool = False
) -> TelemetryResponse:
    try:
        return sessions.session_telemetry(year, round_number, session_type, driver_code, full=full)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/weather", response_model=WeatherSeries)
def api_weather(year: int, round_number: int, session_type: str) -> WeatherSeries:
    try:
        return sessions.session_weather(year, round_number, session_type)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/results", response_model=SessionResultsResponse)
def api_results(year: int, round_number: int, session_type: str) -> SessionResultsResponse:
    try:
        return sessions.session_results(year, round_number, session_type)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/messages", response_model=MessagesResponse)
def api_messages(year: int, round_number: int, session_type: str) -> MessagesResponse:
    try:
        return sessions.session_messages(year, round_number, session_type)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/timing", response_model=LiveTimingResponse)
def api_replay_timing(
    year: int, round_number: int, session_type: str, lap: int = 1
) -> LiveTimingResponse:
    try:
        return sessions.replay_timing(year, round_number, session_type, lap)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/circuit-path", response_model=CircuitPathResponse)
def api_circuit_path(year: int, round_number: int, session_type: str) -> CircuitPathResponse:
    return sessions.circuit_path(year, round_number, session_type)


@app.get("/api/race/{year}/{round_number}/gap-history", response_model=GapHistoryResponse)
def api_gaps(year: int, round_number: int) -> GapHistoryResponse:
    try:
        return analytics.gap_history(year, round_number)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/race/{year}/{round_number}/position-history", response_model=PositionHistoryResponse)
def api_positions(year: int, round_number: int) -> PositionHistoryResponse:
    try:
        return analytics.position_history(year, round_number)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/race/{year}/{round_number}/tyre-strategy", response_model=TyreStrategyResponse)
def api_tyre_strategy(year: int, round_number: int) -> TyreStrategyResponse:
    try:
        return analytics.tyre_strategy(year, round_number)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/race/{year}/{round_number}/pit-stops", response_model=PitStopsResponse)
def api_pits(year: int, round_number: int) -> PitStopsResponse:
    try:
        return analytics.pit_stops(year, round_number)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/race/{year}/{round_number}/fastest-lap-evolution", response_model=FastestLapEvolutionResponse)
def api_fl_evo(year: int, round_number: int) -> FastestLapEvolutionResponse:
    try:
        return analytics.fastest_lap_evolution(year, round_number)
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/race/{year}/{round_number}/results", response_model=SessionResultsResponse)
def api_race_results(year: int, round_number: int) -> SessionResultsResponse:
    try:
        return sessions.session_results(year, round_number, "R")
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/driver/{driver_code}/season/{year}", response_model=DriverSeasonResponse)
def api_driver_season(driver_code: str, year: int) -> DriverSeasonResponse:
    return analytics.driver_season(driver_code, year)


@app.get("/api/circuit/{circuit_key}/history", response_model=CircuitHistoryResponse)
def api_circuit_history(circuit_key: str) -> CircuitHistoryResponse:
    return analytics.circuit_history(circuit_key)


@app.get("/api/circuit/{circuit_key}/characteristics", response_model=CircuitCharacteristics)
def api_circuit_chars(circuit_key: str, year: int | None = None) -> CircuitCharacteristics:
    return analytics.circuit_characteristics(circuit_key, year=year)


@app.get("/api/circuit/{circuit_key}/forecast", response_model=ForecastResponse)
def api_forecast(circuit_key: str) -> ForecastResponse:
    return analytics.forecast(circuit_key)


@app.get("/api/compare/drivers", response_model=CompareDriversResponse)
def api_compare(
    driver_a: str, driver_b: str, year: int, round_number: int | None = None
) -> CompareDriversResponse:
    return analytics.compare_drivers(driver_a, driver_b, year, round_number)


@app.get("/api/live/status", response_model=LiveStatus)
def api_live_status(as_of: AsOf = None, replay_session_key: int | None = None) -> LiveStatus:
    return live.live_status(as_of, replay_session_key=replay_session_key)


@app.get("/api/live/timing", response_model=LiveTimingResponse)
def api_live_timing(as_of: AsOf = None, replay_session_key: int | None = None) -> LiveTimingResponse:
    return live.live_timing(as_of, replay_session_key=replay_session_key)


@app.get("/api/live/positions", response_model=LivePositionsResponse)
def api_live_positions(as_of: AsOf = None, replay_session_key: int | None = None) -> LivePositionsResponse:
    return live.live_positions(as_of, replay_session_key=replay_session_key)


@app.get("/api/live/intervals", response_model=LiveIntervalsResponse)
def api_live_intervals(as_of: AsOf = None, replay_session_key: int | None = None) -> LiveIntervalsResponse:
    return live.live_intervals(as_of, replay_session_key=replay_session_key)


@app.get("/api/live/race-control", response_model=LiveRaceControlResponse)
def api_live_rc(as_of: AsOf = None, replay_session_key: int | None = None) -> LiveRaceControlResponse:
    return live.live_race_control(as_of, replay_session_key=replay_session_key)


@app.get("/api/live/stints", response_model=LiveStintsResponse)
def api_live_stints(as_of: AsOf = None, replay_session_key: int | None = None) -> LiveStintsResponse:
    return live.live_stints(as_of, replay_session_key=replay_session_key)


@app.get("/api/live/weather", response_model=LiveWeatherResponse)
def api_live_weather(as_of: AsOf = None, replay_session_key: int | None = None) -> LiveWeatherResponse:
    return live.live_weather(as_of, replay_session_key=replay_session_key)


@app.get("/api/live/stream")
async def api_live_stream(replay_session_key: int | None = None):
    return StreamingResponse(
        live.sse_generator(replay_session_key=replay_session_key),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/aris/recommend", response_model=RecommendResponse)
def api_recommend(body: RecommendRequest) -> RecommendResponse:
    try:
        return aris_api.recommend(body)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/aris/simulate", response_model=SimulateResponse)
def api_simulate(body: SimulateRequest) -> SimulateResponse:
    try:
        return aris_api.simulate(body)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.get("/api/aris/chat", response_model=ChatResponse)
def api_chat(
    question: str,
    session_key: str | None = None,
    driver_code: str | None = None,
) -> ChatResponse:
    return aris_api.chat(session_key, driver_code, question)


@app.get("/api/aris/plans", response_model=StratPlansResponse)
def api_plans(year: int, round_number: int, driver_code: str) -> StratPlansResponse:
    try:
        return aris_api.plans(year, round_number, driver_code)
    except RuntimeError as extra:
        raise HTTPException(503, str(extra)) from extra
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.get("/api/aris/debrief", response_model=DebriefResponse)
def api_debrief(year: int, round_number: int, driver_code: str) -> DebriefResponse:
    return aris_api.debrief(year, round_number, driver_code)
