"""ARIS V3 FastAPI data broker."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.paths import ROOT  # noqa: F401  # sys.path bootstrap
from backend.cache import (
    TTL_CALENDAR,
    TTL_CIRCUIT,
    TTL_DRIVERS,
    TTL_LIVE,
    TTL_NEXT_RACE,
    TTL_SESSION,
    TTL_STANDINGS,
    cache,
    enable_fastf1_cache,
)
from backend.utils import executor, run_sync

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache", "fastf1")
os.makedirs(CACHE_DIR, exist_ok=True)
enable_fastf1_cache()

from backend import analytics, aris_api, calendar, live, sessions, standings  # noqa: E402
from backend.models import (  # noqa: E402
    ArisStatsResponse,
    CalendarResponse,
    ChatResponse,
    CircuitCharacteristics,
    CircuitHistoryResponse,
    CircuitMapResponse,
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
    SessionEventsResponse,
    SessionPositionsAllResponse,
    SessionPositionsResponse,
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


CIRCUITS_TO_PREWARM = [
    (2025, 1),
    (2025, 2),
    (2025, 3),
    (2025, 4),
    (2025, 5),
    (2025, 6),
    (2025, 7),
    (2025, 8),
    (2025, 9),
    (2025, 10),
    (2025, 11),
    (2025, 12),
    (2025, 13),
    (2025, 14),
    (2025, 15),
    (2025, 16),
    (2025, 17),
    (2025, 18),
    (2025, 19),
    (2025, 20),
    (2025, 21),
    (2025, 22),
    (2025, 23),
    (2025, 24),
    (2024, 15),
]


def _prewarm_calendars() -> None:
    """Run at startup in a thread — calendars, next race, and cheap circuit profiles."""
    keys: set[str] = set()
    for year in [2024, 2025, 2026]:
        try:
            cal = calendar.get_calendar(year)
            print(f"[ARIS] Calendar {year} cached OK ({len(cal.rounds)} rounds)", flush=True)
            for rnd in cal.rounds:
                keys.add(rnd.circuit_key)
        except Exception as e:
            print(f"[ARIS] Calendar {year} prewarm failed: {e}", flush=True)
    try:
        calendar.next_race()
        print("[ARIS] Next race cached OK", flush=True)
    except Exception as e:
        print(f"[ARIS] Next race prewarm failed: {e}", flush=True)
    for key in keys:
        try:
            analytics.circuit_characteristics(key)
        except Exception:
            pass
    if keys:
        print(f"[ARIS] {len(keys)} circuit profiles cached OK", flush=True)


def _prewarm_circuit_previews() -> None:
    """Pre-compute 20-point circuit previews. Does not block startup."""
    for year, round_num in CIRCUITS_TO_PREWARM:
        cache_key = f"circuit_preview_{year}_{round_num}"
        if cache.get(cache_key, ttl_seconds=86400) is not None:
            continue
        try:
            preview = sessions.build_circuit_preview(year, round_num)
            if preview.available:
                cache.set(cache_key, preview)
                print(f"[ARIS] Circuit preview cached: {year} R{round_num}", flush=True)
            else:
                print(f"[ARIS] Circuit preview unavailable: {year} R{round_num}", flush=True)
        except Exception as e:
            print(f"[ARIS] Circuit preview failed {year} R{round_num}: {e}", flush=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    loop = asyncio.get_running_loop()
    loop.run_in_executor(executor, _prewarm_calendars)
    loop.run_in_executor(executor, _prewarm_circuit_previews)
    yield


app = FastAPI(title="ARIS V3 Data Broker", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_as_of(
    as_of: datetime | None = Query(None, description="Override current time (ISO-8601 UTC)"),
    asOf: datetime | None = Query(None, description="Alias of as_of"),
) -> datetime | None:
    return asOf or as_of


AsOf = Annotated[datetime | None, Depends(_parse_as_of)]


def _http(exc: Exception, status: int = 404) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


def _as_of_key(as_of: datetime | None) -> str:
    if as_of is None:
        return "now"
    return as_of.strftime("%Y-%m-%dT%H:%M:%SZ")


async def _cached_sync(key: str, ttl: int, fn, *args, **kwargs):
    hit = cache.get(key, ttl)
    if hit is not None:
        return hit
    value = await run_sync(fn, *args, **kwargs)
    cache.set(key, value)
    return value


async def _cached_await(key: str, ttl: int, factory):
    hit = cache.get(key, ttl)
    if hit is not None:
        return hit
    value = await factory()
    cache.set(key, value)
    return value


@app.get("/")
def root() -> dict[str, object]:
    return {"status": "ok", "service": "ARIS backend", "port": 8765}


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True)


@app.get("/api/calendar/{year}", response_model=CalendarResponse)
async def api_calendar(year: int, as_of: AsOf) -> CalendarResponse:
    if year not in {2024, 2025, 2026}:
        raise HTTPException(400, "year must be 2024, 2025, or 2026")
    return await _cached_sync(
        f"calendar_{year}_{_as_of_key(as_of)}",
        TTL_CALENDAR,
        calendar.get_calendar,
        year,
        as_of=as_of,
    )


@app.get("/api/calendar/{year}/{round_number}/sessions", response_model=RoundSessionsResponse)
async def api_round_sessions(year: int, round_number: int, as_of: AsOf) -> RoundSessionsResponse:
    try:
        return await _cached_sync(
            f"sessions_{year}_{round_number}_{_as_of_key(as_of)}",
            TTL_NEXT_RACE,
            calendar.get_round_sessions,
            year,
            round_number,
            as_of=as_of,
        )
    except KeyError as exc:
        raise _http(exc) from exc


@app.get("/api/next-race", response_model=NextRaceResponse)
async def api_next_race(as_of: AsOf, year: int | None = None) -> NextRaceResponse:
    try:
        return await _cached_sync(
            f"next_race_{year}_{_as_of_key(as_of)}",
            TTL_NEXT_RACE,
            calendar.next_race,
            as_of=as_of,
            year=year,
        )
    except Exception as exc:
        try:
            cal = calendar.get_calendar(2026)
            if cal.rounds:
                return calendar._next_from_round(
                    2026, cal.rounds[0], calendar.now_utc(as_of), off_season=True
                )
        except Exception:
            pass
        raise _http(exc, 503) from exc


@app.get("/api/drivers/{year}", response_model=DriversResponse)
async def api_drivers(year: int) -> DriversResponse:
    return await _cached_sync(f"drivers_{year}", TTL_DRIVERS, standings.get_drivers, year)


@app.get("/api/teams/{year}", response_model=TeamsResponse)
async def api_teams(year: int) -> TeamsResponse:
    return await _cached_sync(f"teams_{year}", TTL_DRIVERS, standings.get_teams, year)


@app.get("/api/standings/drivers/{year}", response_model=DriverStandingsResponse)
async def api_driver_standings(year: int) -> DriverStandingsResponse:
    return await _cached_sync(
        f"standings_drivers_{year}", TTL_STANDINGS, standings.driver_standings, year
    )


@app.get("/api/standings/constructors/{year}", response_model=ConstructorStandingsResponse)
async def api_constructor_standings(year: int) -> ConstructorStandingsResponse:
    return await _cached_sync(
        f"standings_constructors_{year}", TTL_STANDINGS, standings.constructor_standings, year
    )


@app.get("/api/session/{year}/{round_number}/{session_type}/laps", response_model=LapsResponse)
async def api_laps(year: int, round_number: int, session_type: str) -> LapsResponse:
    try:
        return await _cached_sync(
            f"laps_{year}_{round_number}_{session_type}",
            TTL_SESSION,
            sessions.session_laps,
            year,
            round_number,
            session_type,
        )
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/summary", response_model=SessionSummary)
async def api_summary(year: int, round_number: int, session_type: str) -> SessionSummary:
    try:
        return await _cached_sync(
            f"summary_{year}_{round_number}_{session_type}",
            TTL_SESSION,
            sessions.session_summary,
            year,
            round_number,
            session_type,
        )
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/stints", response_model=StintsResponse)
async def api_stints(year: int, round_number: int, session_type: str) -> StintsResponse:
    try:
        return await _cached_sync(
            f"stints_{year}_{round_number}_{session_type}",
            TTL_SESSION,
            sessions.session_stints,
            year,
            round_number,
            session_type,
        )
    except Exception as exc:
        raise _http(exc) from exc


@app.get(
    "/api/session/{year}/{round_number}/{session_type}/telemetry/{driver_code}",
    response_model=TelemetryResponse,
)
async def api_telemetry(
    year: int, round_number: int, session_type: str, driver_code: str, full: bool = False
) -> TelemetryResponse:
    try:
        return await _cached_sync(
            f"telemetry_{year}_{round_number}_{session_type}_{driver_code}_{full}",
            TTL_SESSION,
            sessions.session_telemetry,
            year,
            round_number,
            session_type,
            driver_code,
            full=full,
        )
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/weather", response_model=WeatherSeries)
async def api_weather(year: int, round_number: int, session_type: str) -> WeatherSeries:
    try:
        return await _cached_sync(
            f"weather_{year}_{round_number}_{session_type}",
            TTL_SESSION,
            sessions.session_weather,
            year,
            round_number,
            session_type,
        )
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/results", response_model=SessionResultsResponse)
async def api_results(year: int, round_number: int, session_type: str) -> SessionResultsResponse:
    try:
        return await _cached_sync(
            f"results_{year}_{round_number}_{session_type}",
            TTL_SESSION,
            sessions.session_results,
            year,
            round_number,
            session_type,
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/session/{year}/{round_number}/{session_type}/messages", response_model=MessagesResponse)
async def api_messages(year: int, round_number: int, session_type: str) -> MessagesResponse:
    try:
        return await _cached_sync(
            f"messages_{year}_{round_number}_{session_type}",
            TTL_SESSION,
            sessions.session_messages,
            year,
            round_number,
            session_type,
        )
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/timing", response_model=LiveTimingResponse)
async def api_replay_timing(
    year: int, round_number: int, session_type: str, lap: int = 1
) -> LiveTimingResponse:
    try:
        return await _cached_sync(
            f"timing_{year}_{round_number}_{session_type}_{lap}",
            TTL_SESSION,
            sessions.replay_timing,
            year,
            round_number,
            session_type,
            lap,
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/session/{year}/{round_number}/{session_type}/circuit-path", response_model=CircuitPathResponse)
async def api_circuit_path(year: int, round_number: int, session_type: str) -> CircuitPathResponse:
    return await _cached_sync(
        f"circuit_path_{year}_{round_number}_{session_type}",
        TTL_SESSION,
        sessions.circuit_path,
        year,
        round_number,
        session_type,
    )


@app.get("/api/circuit/{year}/{round_number}/map", response_model=CircuitMapResponse)
async def api_circuit_map(year: int, round_number: int) -> CircuitMapResponse:
    try:
        return await _cached_sync(
            f"circuit_map_{year}_{round_number}",
            TTL_SESSION,
            sessions.circuit_map,
            year,
            round_number,
        )
    except Exception:
        return CircuitMapResponse(
            year=year, round_number=round_number, available=False, fallback=True, error="Circuit map unavailable"
        )


@app.get("/api/circuit/{year}/{round_number}/preview", response_model=CircuitMapResponse)
async def api_circuit_preview(year: int, round_number: int) -> CircuitMapResponse:
    """Never triggers a live FastF1 load — cache only (startup pre-warm fills it)."""
    preview_key = f"circuit_preview_{year}_{round_number}"
    hit = cache.get(preview_key, TTL_SESSION)
    if hit is not None:
        return hit
    map_key = f"circuit_map_{year}_{round_number}"
    full = cache.get(map_key, TTL_SESSION)
    if full is not None:
        preview = sessions.circuit_preview_from_map(full)
        cache.set(preview_key, preview)
        return preview
    return CircuitMapResponse(
        year=year,
        round_number=round_number,
        available=False,
        fallback=True,
        error="Preview not cached yet",
    )


@app.get(
    "/api/session/{year}/{round_number}/{session_type}/positions/all",
    response_model=SessionPositionsAllResponse,
)
async def api_session_positions_all(
    year: int, round_number: int, session_type: str
) -> SessionPositionsAllResponse:
    try:
        return await _cached_sync(
            f"positions_all_{year}_{round_number}_{session_type}",
            TTL_SESSION,
            sessions.session_positions_all,
            year,
            round_number,
            session_type,
        )
    except Exception:
        return SessionPositionsAllResponse(
            year=year, round_number=round_number, session_type=session_type.upper(), laps={}
        )


@app.get(
    "/api/session/{year}/{round_number}/{session_type}/positions/{lap}",
    response_model=SessionPositionsResponse,
)
async def api_session_positions(
    year: int, round_number: int, session_type: str, lap: int
) -> SessionPositionsResponse:
    return await _cached_sync(
        f"positions_{year}_{round_number}_{session_type}_{lap}",
        TTL_SESSION,
        sessions.session_positions,
        year,
        round_number,
        session_type,
        lap,
    )


@app.get(
    "/api/session/{year}/{round_number}/{session_type}/events/{lap}",
    response_model=SessionEventsResponse,
)
async def api_session_events(
    year: int, round_number: int, session_type: str, lap: int, driver_code: str = "NOR"
) -> SessionEventsResponse:
    try:
        return await _cached_sync(
            f"events_{year}_{round_number}_{session_type}_{lap}_{driver_code}",
            TTL_SESSION,
            sessions.session_events,
            year,
            round_number,
            session_type,
            lap,
            driver_code,
        )
    except Exception:
        return SessionEventsResponse(
            year=year,
            round_number=round_number,
            session_type=session_type.upper(),
            lap=lap,
            events=[],
        )


@app.get("/api/race/{year}/{round_number}/gap-history", response_model=GapHistoryResponse)
async def api_gaps(year: int, round_number: int) -> GapHistoryResponse:
    try:
        return await _cached_sync(
            f"gaps_{year}_{round_number}", TTL_SESSION, analytics.gap_history, year, round_number
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/race/{year}/{round_number}/position-history", response_model=PositionHistoryResponse)
async def api_positions(year: int, round_number: int) -> PositionHistoryResponse:
    try:
        return await _cached_sync(
            f"positions_{year}_{round_number}",
            TTL_SESSION,
            analytics.position_history,
            year,
            round_number,
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/race/{year}/{round_number}/tyre-strategy", response_model=TyreStrategyResponse)
async def api_tyre_strategy(year: int, round_number: int) -> TyreStrategyResponse:
    try:
        return await _cached_sync(
            f"tyres_{year}_{round_number}", TTL_SESSION, analytics.tyre_strategy, year, round_number
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/race/{year}/{round_number}/pit-stops", response_model=PitStopsResponse)
async def api_pits(year: int, round_number: int) -> PitStopsResponse:
    try:
        return await _cached_sync(
            f"pits_{year}_{round_number}", TTL_SESSION, analytics.pit_stops, year, round_number
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/race/{year}/{round_number}/fastest-lap-evolution", response_model=FastestLapEvolutionResponse)
async def api_fl_evo(year: int, round_number: int) -> FastestLapEvolutionResponse:
    try:
        return await _cached_sync(
            f"fl_{year}_{round_number}",
            TTL_SESSION,
            analytics.fastest_lap_evolution,
            year,
            round_number,
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/race/{year}/{round_number}/results", response_model=SessionResultsResponse)
async def api_race_results(year: int, round_number: int) -> SessionResultsResponse:
    try:
        return await _cached_sync(
            f"race_results_{year}_{round_number}",
            TTL_SESSION,
            sessions.session_results,
            year,
            round_number,
            "R",
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/driver/{driver_code}/season/{year}", response_model=DriverSeasonResponse)
async def api_driver_season(driver_code: str, year: int) -> DriverSeasonResponse:
    return await _cached_sync(
        f"driver_season_{driver_code}_{year}",
        TTL_SESSION,
        analytics.driver_season,
        driver_code,
        year,
    )


@app.get("/api/circuit/{circuit_key}/history", response_model=CircuitHistoryResponse)
async def api_circuit_history(circuit_key: str) -> CircuitHistoryResponse:
    return await _cached_sync(
        f"circuit_history_v2_{circuit_key}", TTL_SESSION, analytics.circuit_history, circuit_key
    )


@app.get("/api/circuit/{circuit_key}/characteristics", response_model=CircuitCharacteristics)
async def api_circuit_chars(circuit_key: str, year: int | None = None) -> CircuitCharacteristics:
    return await _cached_sync(
        f"circuit_chars_{circuit_key}_{year}",
        TTL_CIRCUIT,
        analytics.circuit_characteristics,
        circuit_key,
        year=year,
    )


@app.get("/api/circuit/{circuit_key}/forecast", response_model=ForecastResponse)
async def api_forecast(circuit_key: str) -> ForecastResponse:
    return await _cached_sync(
        f"forecast_{circuit_key}", TTL_NEXT_RACE, analytics.forecast, circuit_key
    )


@app.get("/api/compare/drivers", response_model=CompareDriversResponse)
async def api_compare(
    driver_a: str, driver_b: str, year: int, round_number: int | None = None
) -> CompareDriversResponse:
    return await _cached_sync(
        f"compare_{driver_a}_{driver_b}_{year}_{round_number}",
        TTL_SESSION,
        analytics.compare_drivers,
        driver_a,
        driver_b,
        year,
        round_number,
    )


@app.get("/api/live/status", response_model=LiveStatus)
async def api_live_status(as_of: AsOf, replay_session_key: int | None = None) -> LiveStatus:
    try:
        if as_of is not None and replay_session_key is None:
            return await run_sync(live.simulated_status, as_of)
        return await _cached_await(
            f"live_status_{_as_of_key(as_of)}_{replay_session_key}",
            TTL_LIVE,
            lambda: live.live_status(as_of, replay_session_key=replay_session_key),
        )
    except Exception as extra:
        return LiveStatus(is_live=False, error=str(extra))


@app.get("/api/live/timing", response_model=LiveTimingResponse)
async def api_live_timing(as_of: AsOf, replay_session_key: int | None = None) -> LiveTimingResponse:
    try:
        return await _cached_await(
            f"live_timing_{_as_of_key(as_of)}_{replay_session_key}",
            TTL_LIVE,
            lambda: live.live_timing(as_of, replay_session_key=replay_session_key),
        )
    except Exception:
        return LiveTimingResponse(is_live=False, rows=[])


@app.get("/api/live/positions", response_model=LivePositionsResponse)
async def api_live_positions(as_of: AsOf, replay_session_key: int | None = None) -> LivePositionsResponse:
    try:
        return await _cached_await(
            f"live_positions_{_as_of_key(as_of)}_{replay_session_key}",
            TTL_LIVE,
            lambda: live.live_positions(
                as_of, replay_session_key=replay_session_key, simulated=as_of is not None
            ),
        )
    except Exception:
        return LivePositionsResponse(is_live=False, positions=[])


@app.get("/api/live/intervals", response_model=LiveIntervalsResponse)
async def api_live_intervals(as_of: AsOf, replay_session_key: int | None = None) -> LiveIntervalsResponse:
    return await _cached_await(
        f"live_intervals_{_as_of_key(as_of)}_{replay_session_key}",
        TTL_LIVE,
        lambda: live.live_intervals(as_of, replay_session_key=replay_session_key),
    )


@app.get("/api/live/race-control", response_model=LiveRaceControlResponse)
async def api_live_rc(as_of: AsOf, replay_session_key: int | None = None) -> LiveRaceControlResponse:
    try:
        return await _cached_await(
            f"live_rc_{_as_of_key(as_of)}_{replay_session_key}",
            TTL_LIVE,
            lambda: live.live_race_control(as_of, replay_session_key=replay_session_key),
        )
    except Exception:
        return LiveRaceControlResponse(is_live=False, messages=[])


@app.get("/api/live/stints", response_model=LiveStintsResponse)
async def api_live_stints(as_of: AsOf, replay_session_key: int | None = None) -> LiveStintsResponse:
    return await _cached_await(
        f"live_stints_{_as_of_key(as_of)}_{replay_session_key}",
        TTL_LIVE,
        lambda: live.live_stints(as_of, replay_session_key=replay_session_key),
    )


@app.get("/api/live/weather", response_model=LiveWeatherResponse)
async def api_live_weather(as_of: AsOf, replay_session_key: int | None = None) -> LiveWeatherResponse:
    return await _cached_await(
        f"live_weather_{_as_of_key(as_of)}_{replay_session_key}",
        TTL_LIVE,
        lambda: live.live_weather(as_of, replay_session_key=replay_session_key),
    )


@app.get("/api/live/stream")
async def api_live_stream(replay_session_key: int | None = None):
    return StreamingResponse(
        live.sse_generator(replay_session_key=replay_session_key),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/aris/recommend", response_model=RecommendResponse)
async def api_recommend(body: RecommendRequest) -> RecommendResponse:
    try:
        return await run_sync(aris_api.recommend, body)
    except aris_api.ClientInputError as extra:
        raise HTTPException(422, str(extra)) from extra
    except ValueError as extra:
        raise HTTPException(422, str(extra)) from extra
    except RuntimeError as extra:
        raise HTTPException(503, str(extra)) from extra
    except Exception as extra:
        return aris_api._fallback_recommend(body)


@app.post("/api/aris/simulate", response_model=SimulateResponse)
async def api_simulate(body: SimulateRequest) -> SimulateResponse:
    try:
        return await run_sync(aris_api.simulate, body)
    except aris_api.ClientInputError as extra:
        raise HTTPException(422, str(extra)) from extra
    except ValueError as extra:
        raise HTTPException(422, str(extra)) from extra
    except RuntimeError as extra:
        raise HTTPException(503, str(extra)) from extra
    except Exception as extra:
        raise HTTPException(503, str(extra)) from extra


@app.get("/api/aris/stats", response_model=ArisStatsResponse)
def api_aris_stats() -> ArisStatsResponse:
    return aris_api.model_stats()


@app.get("/api/aris/chat", response_model=ChatResponse)
async def api_chat(
    question: str,
    session_key: str | None = None,
    driver_code: str | None = None,
    year: int | None = None,
    round_number: int | None = None,
    current_lap: int | None = None,
) -> ChatResponse:
    return await run_sync(
        aris_api.chat, session_key, driver_code, question, year, round_number, current_lap
    )


@app.get("/api/aris/plans", response_model=StratPlansResponse)
async def api_plans(year: int, round_number: int, driver_code: str) -> StratPlansResponse:
    try:
        return await run_sync(aris_api.plans, year, round_number, driver_code)
    except aris_api.ClientInputError as extra:
        raise HTTPException(422, str(extra)) from extra
    except RuntimeError as extra:
        raise HTTPException(503, str(extra)) from extra
    except Exception as extra:
        raise HTTPException(503, str(extra)) from extra


@app.get("/api/aris/debrief", response_model=DebriefResponse)
async def api_debrief(year: int, round_number: int, driver_code: str) -> DebriefResponse:
    return await run_sync(aris_api.debrief, year, round_number, driver_code)
