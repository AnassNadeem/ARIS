"""ARIS V3 FastAPI data broker."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.paths import ROOT  # noqa: F401  # sys.path bootstrap
from backend.observability import init_sentry

init_sentry()

from backend.cache import (
    TTL_CALENDAR,
    TTL_CIRCUIT,
    TTL_COMPLETED,
    TTL_DRIVERS,
    TTL_LIVE,
    TTL_NEXT_RACE,
    TTL_SESSION,
    TTL_STANDINGS,
    TTL_STATS,
    cache,
    enable_fastf1_cache,
    get_memory_then_disk,
    put_both,
)
from backend.fastf1_guard import max_concurrent_loads
from backend.utils import prewarm_executor, run_light, run_prewarm, run_sync

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache", "fastf1")
try:
    os.makedirs(CACHE_DIR, exist_ok=True)
except OSError:
    pass
enable_fastf1_cache()
_log = logging.getLogger("aris.api")

from backend import analytics, aris_api, calendar, live, live_hub, sessions, standings  # noqa: E402
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
    CopilotChatRequest,
    CopilotChatResponse,
    AskRequest,
    DebriefResponse,
    DriverSeasonResponse,
    DriverStandingsResponse,
    DriversResponse,
    FastestLapEvolutionResponse,
    ForecastResponse,
    GapHistoryResponse,
    IngestStatusResponse,
    LapsResponse,
    LiveIntervalsResponse,
    LivePositionsResponse,
    LiveRaceControlResponse,
    LiveHubResponse,
    LiveStatus,
    LiveStintsResponse,
    LiveLapsResponse,
    LiveTelemetryResponse,
    LiveTimingResponse,
    LiveWeatherResponse,
    MessagesResponse,
    GhostRecomputeRequest,
    GhostRecomputeResponse,
    NextRaceResponse,
    PitStopsResponse,
    PositionHistoryResponse,
    PrewarmRequest,
    PrewarmResponse,
    RecentRaceCard,
    RecommendRequest,
    RecommendResponse,
    ReplayFrameResponse,
    ReplayInitRequest,
    ReplayInitResponse,
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
from aris.schemas import (  # noqa: E402
    DegradationCurveResponse,
    GhostVsRealResponse,
    RaceDebriefResponse,
)


# Race day: only the live weekend + last year's Zandvoort outline.
# Loading every 2025 quali in-process crashed uvicorn (Win access violation).
CIRCUITS_TO_PREWARM = [
    (2026, 12),
    (2024, 15),
]

# Lift these Race packs from diskcache into `_REPLAY_PACKS` at startup.
# Disk-only — never call FastF1 here (that has crashed uvicorn on Windows).
HOT_REPLAY_PACKS: list[tuple[int, int, str]] = [
    (2025, 15, "R"),  # Zandvoort
    (2024, 8, "R"),  # Monaco
    (2025, 8, "R"),  # Monaco
    (2024, 15, "R"),  # Zandvoort
    (2025, 12, "R"),  # Silverstone
    (2024, 12, "R"),  # Silverstone
    (2025, 16, "R"),  # Monza
    (2024, 16, "R"),  # Monza
]


def warmup_startup() -> dict[str, int]:
    """Preload calendar, driver lists, and hot replay packs into RAM.

    Called from the FastAPI lifespan before the first request is served.
    Replay packs are hydrated from memory/disk only — no FastF1.
    """
    years = sorted(calendar.ALLOWED_REPLAY_YEARS)
    calendars = 0
    drivers_n = 0
    packs = 0
    for year in years:
        try:
            cal = calendar.get_calendar(year)
            put_both(f"calendar_jolpica23st_{year}_now", cal, TTL_CALENDAR)
            calendars += 1
            print(f"[ARIS] Calendar {year} cached OK ({len(cal.rounds)} rounds)", flush=True)
        except Exception as e:
            print(f"[ARIS] Calendar {year} prewarm failed: {e}", flush=True)
        try:
            roster = standings.get_drivers(year)
            put_both(f"drivers_{year}", roster, TTL_DRIVERS)
            drivers_n += 1
            n = len(getattr(roster, "drivers", []) or [])
            print(f"[ARIS] Drivers {year} cached OK ({n})", flush=True)
        except Exception as e:
            print(f"[ARIS] Drivers {year} prewarm failed: {e}", flush=True)
    for year, rnd, stype in HOT_REPLAY_PACKS:
        try:
            key = live.synthetic_session_key(year, rnd, stype)
            pack, memory_hit, disk_hit = live.hydrate_replay_pack_cache(
                key, year, rnd, stype, log_hits=True
            )
            if pack is not None and (memory_hit or disk_hit):
                packs += 1
                print(
                    f"[ARIS] Hot pack {year} R{rnd} {stype} "
                    f"memory_hit={memory_hit} disk_hit={disk_hit}",
                    flush=True,
                )
            else:
                print(
                    f"[ARIS] Hot pack {year} R{rnd} {stype} skipped (not on disk)",
                    flush=True,
                )
        except Exception as e:
            print(f"[ARIS] Hot pack {year} R{rnd} {stype} failed: {e}", flush=True)
    msg = f"Warmup complete: calendar, drivers, {packs} hot packs loaded."
    _log.info(msg)
    print(f"[ARIS] {msg}", flush=True)
    return {"calendars": calendars, "drivers": drivers_n, "hot_packs": packs}


def _prewarm_catalog_extras() -> None:
    """Next-race, stats, and historical standings — not on the first-request path."""
    try:
        nxt = calendar.next_race()
        put_both("next_race_None_now", nxt, TTL_NEXT_RACE)
        print("[ARIS] Next race cached OK", flush=True)
    except Exception as e:
        print(f"[ARIS] Next race prewarm failed: {e}", flush=True)
    try:
        put_both("aris_stats", aris_api.model_stats(), TTL_STATS)
    except Exception as e:
        print(f"[ARIS] Stats prewarm failed: {e}", flush=True)
    for year in (2018, 2019, 2020, 2021, 2022, 2023):
        try:
            standings.driver_standings(year)
            print(f"[ARIS] Standings {year} cached OK", flush=True)
        except Exception as e:
            print(f"[ARIS] Standings {year} prewarm failed: {e}", flush=True)


def _prewarm_calendars() -> None:
    """Back-compat alias used by tests / scripts that expected the old name."""
    warmup_startup()
    _prewarm_catalog_extras()


def _recent_circuit_rounds(limit: int = 5) -> list[tuple[int, int]]:
    """Last 3–5 completed races (fill from previous season if needed)."""
    year = datetime.now(timezone.utc).year
    year = min(max(year, 2024), 2026)
    picks: list[tuple[int, int]] = []
    try:
        cal = calendar.get_calendar(year)
        completed = [r for r in cal.rounds if r.status == "COMPLETED"]
        completed.sort(key=lambda r: int(r.round_number))
        picks = [(year, int(r.round_number)) for r in completed[-limit:]]
    except Exception:
        picks = []
    if len(picks) < 3 and year > 2024:
        try:
            prev = calendar.get_calendar(year - 1)
            prev_c = [r for r in prev.rounds if r.status == "COMPLETED"]
            prev_c.sort(key=lambda r: int(r.round_number))
            need = limit - len(picks)
            extra = [(year - 1, int(r.round_number)) for r in prev_c[-need:]]
            picks = extra + picks
        except Exception:
            pass
    if not picks:
        return list(CIRCUITS_TO_PREWARM)
    return picks


def prewarm_enabled() -> bool:
    """Background FastF1 / ingest pre-warm. Off unless ARIS_ENABLE_PREWARM=true.

    Heroku Basic is 512MB. One GPS session is ~400MB; two concurrent loads
    trigger R15 (Memory quota vastly exceeded) and SIGKILL.
    """
    raw = (os.environ.get("ARIS_ENABLE_PREWARM") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


# Cap concurrent FastF1 session loads. Default 1 (see ARIS_MAX_CONCURRENT_LOADS).
_PREWARM_CONCURRENCY = asyncio.Semaphore(max_concurrent_loads())


async def _prewarm_weekend_packs() -> None:
    """Laps-only weekend warm. Never loads car_data or position_data (GPS).

    Circuit maps and full replay packs pull those channels (~400MB each).
    Two concurrent loads OOM a 512MB Heroku Basic dyno (R15).
    GPS fills lazily on the first user request instead.
    """
    await asyncio.sleep(1.5)
    try:
        nxt = await run_prewarm(calendar.next_race)
    except Exception as e:
        print(f"[ARIS] Weekend pack prewarm skipped: {e}", flush=True)
        return
    try:
        weekend = await run_prewarm(calendar.get_round_sessions, nxt.year, nxt.round_number)
    except Exception as e:
        print(f"[ARIS] Weekend sessions prewarm failed: {e}", flush=True)
        weekend = None
    if nxt.circuit_key:
        try:
            from backend.analytics import circuit_history

            hist = await run_prewarm(circuit_history, nxt.circuit_key)
            print(
                f"[ARIS] Circuit history cached: {nxt.circuit_key} "
                f"years={len(hist.years)} first_stop={hist.median_first_stop_lap} "
                f"stops={hist.typical_stop_count}",
                flush=True,
            )
        except Exception as e:
            print(f"[ARIS] Circuit history prewarm failed: {e}", flush=True)
    for sess in (weekend.sessions if weekend is not None else []):
        if sess.status != "COMPLETED":
            continue
        if sess.session_type != "R":
            continue
        async with _PREWARM_CONCURRENCY:
            try:
                # Laps + timing only: session_info, driver_info, session_status_data,
                # lap_count, track_status_data, timing_app_data. No car_data / position_data.
                await run_prewarm(
                    sessions.load_session,
                    nxt.year,
                    nxt.round_number,
                    sess.session_type,
                    telemetry=False,
                    weather=False,
                    messages=False,
                )
                print(
                    f"[ARIS] Laps-only session warm: {nxt.year} R{nxt.round_number} {sess.session_type}",
                    flush=True,
                )
            except Exception as e:
                print(f"[ARIS] Laps-only session warm failed {sess.session_type}: {e}", flush=True)
            try:
                from backend.ingest_jobs import ensure_session_ingested

                status = await run_prewarm(
                    ensure_session_ingested, nxt.year, nxt.round_number, "R"
                )
                print(
                    f"[ARIS] Ingest warm: {nxt.year} R{nxt.round_number} -> {status}",
                    flush=True,
                )
            except Exception as e:
                print(f"[ARIS] Ingest warm failed: {e}", flush=True)


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
    if prewarm_enabled():
        loop = asyncio.get_running_loop()
        # Calendar + drivers + disk-only hot packs, then background laps-only warm.
        # Never loads car_data / position_data at boot.
        try:
            await run_prewarm(warmup_startup)
        except Exception as e:
            print(f"[ARIS] Startup warmup failed: {e}", flush=True)
        loop.run_in_executor(prewarm_executor, _prewarm_catalog_extras)
        asyncio.create_task(_prewarm_weekend_packs(), name="weekend-pack-warm")
    else:
        print(
            "[ARIS] Startup prewarm disabled "
            "(set ARIS_ENABLE_PREWARM=true to enable). Cache fills on first request.",
            flush=True,
        )
    poller = asyncio.create_task(live.poll_openf1_forever(), name="openf1-poller")
    try:
        yield
    finally:
        poller.cancel()
        try:
            await poller
        except (asyncio.CancelledError, Exception):
            pass


app = FastAPI(title="ARIS V3 Data Broker", version="0.3.0", lifespan=lifespan)


@app.exception_handler(calendar.ReplayYearBlocked)
async def replay_year_blocked_handler(_request, extra: calendar.ReplayYearBlocked) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(extra)})


@app.exception_handler(calendar.ReplaySessionBlocked)
async def replay_session_blocked_handler(_request, extra: calendar.ReplaySessionBlocked) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(extra)})


@app.middleware("http")
async def _catalog_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/standings/") or path.startswith("/api/drivers/") or path.startswith("/api/teams/"):
        response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=600"
    elif "/api/calendar/" in path or path.endswith("/characteristics") or path.endswith("/history"):
        response.headers["Cache-Control"] = "no-store"
    elif path.endswith("/preview") or path.endswith("/map"):
        response.headers["Cache-Control"] = "public, max-age=300"
    elif path in {
        "/api/next-race",
        "/api/live/status",
        "/api/live/hub",
        "/api/live/next",
        "/health",
        "/api/health",
        "/api/status",
        "/api/aris/stats",
    }:
        response.headers["Cache-Control"] = "public, max-age=5"
    return response


from backend.cors_origins import cors_allow_origins  # noqa: E402
from backend.rate_limit import enforce_compute_quota  # noqa: E402

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(
        dict.fromkeys(
            [
                *cors_allow_origins(),
                "https://arisf1.tech",
                "https://www.arisf1.tech",
            ]
        )
    ),
    allow_origin_regex=(
        r"https://arisf1\.tech|"
        r"https://www\.arisf1\.tech|"
        r"https://aris-frontend-590\.pages\.dev|"
        r"https://[a-z0-9]+\.aris-frontend-590\.pages\.dev|"
        r"http://localhost:3000"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Resolve absolute path
ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static_replays"
os.makedirs(STATIC_DIR, exist_ok=True)

# 2. MOUNT FIRST: Ensure this is above all other @app.get routes
app.mount("/static_replays", StaticFiles(directory=str(STATIC_DIR)), name="static_replays")

# 3. Debug endpoint to verify paths — opt-in only (off in production).
# Set ARIS_DEBUG_ENDPOINTS=1 locally when you need the filesystem listing.
if os.getenv("ARIS_DEBUG_ENDPOINTS"):

    @app.get("/api/debug-static")
    def debug_static():
        test_file = STATIC_DIR / "2024_zandvoort_r" / "manifest.json"

        try:
            contents = os.listdir(STATIC_DIR) if STATIC_DIR.exists() else []
        except Exception as e:
            contents = [str(e)]

        return {
            "backend_file_path": str(Path(__file__).resolve()),
            "calculated_static_dir": str(STATIC_DIR),
            "static_dir_exists": STATIC_DIR.exists(),
            "manifest_exists": test_file.exists(),
            "files_in_static": contents,
        }


def _parse_as_of(
    as_of: datetime | None = Query(None, description="Override current time (ISO-8601 UTC)"),
    asOf: datetime | None = Query(None, description="Alias of as_of"),
) -> datetime | None:
    return asOf or as_of


AsOf = Annotated[datetime | None, Depends(_parse_as_of)]


def _http(exc: Exception, status: int = 404) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


def _require_replay_year(year: int) -> int:
    """400 before any FastF1 / background pack work for years outside 2024–2026."""
    try:
        return calendar.assert_replay_year(year)
    except calendar.ReplayYearBlocked as extra:
        raise HTTPException(status_code=400, detail=str(extra)) from extra


def _require_replay_session_type(session_type: str | None) -> str:
    """400 when Replay/ARIS is asked for FP / Sprint / Quali."""
    try:
        return calendar.assert_replay_session_type(session_type)
    except calendar.ReplaySessionBlocked as extra:
        raise HTTPException(status_code=400, detail=str(extra)) from extra


def _require_standings_year(year: int) -> int:
    try:
        return standings.assert_standings_year(year)
    except standings.StandingsYearBlocked as extra:
        raise HTTPException(status_code=400, detail=str(extra)) from extra


def _as_of_key(as_of: datetime | None) -> str:
    if as_of is None:
        return "now"
    return as_of.strftime("%Y-%m-%dT%H:%M:%SZ")


def _history_ttl(year: int) -> int:
    """Past seasons are frozen; keep this season at one day so today's race can fill."""
    return TTL_COMPLETED if year < datetime.now(timezone.utc).year else TTL_SESSION


def _replay_feed_ttl(replay_session_key: int | None) -> int:
    """Replay of a finished session is static. Live timing must stay short."""
    return TTL_SESSION if replay_session_key is not None else TTL_LIVE


_REFRESHING: set[str] = set()
_PREWARM_INFLIGHT: set[tuple[int, int, str]] = set()


def _pack_memory_ready(session_key: int) -> bool:
    cached = live._REPLAY_PACKS.get(session_key)
    return bool(
        cached is not None
        and live._ff1_pack_ready(cached)
        and cached.get("path_traces")
        and cached.get("path_traces_v") == live._PATH_TRACES_V
    )


async def _prewarm_round_pack(year: int, round_number: int, session_type: str = "R") -> None:
    """Build the Race replay pack after round select. Never blocks the HTTP response."""
    if not calendar.replay_year_allowed(year):
        msg = f"Replay request for year {year} — blocked (not in 2024–2026)"
        _log.info(msg)
        print(f"[ARIS] {msg}", flush=True)
        return
    stype = str(session_type or "R").upper()
    if stype != "R":
        _log.info("Replay/ARIS prewarm skipped for non-Race session %s", stype)
        return
    token = (int(year), int(round_number), stype)
    if token in _PREWARM_INFLIGHT:
        return
    _PREWARM_INFLIGHT.add(token)
    try:
        from backend.sessions import _pack_cache_key

        key = live.synthetic_session_key(year, round_number, stype)
        cache_key = _pack_cache_key(year, round_number, stype)
        msg = f"[prewarm] started pack for {year} R{round_number} key={cache_key}"
        _log.info(msg)
        print(msg, flush=True)
        pack, memory_hit, disk_hit = live.hydrate_replay_pack_cache(
            key, year, round_number, stype, log_hits=True
        )
        _log.info("key=%s memory_hit=%s disk_hit=%s", cache_key, memory_hit, disk_hit)
        if _pack_memory_ready(key) or (
            pack is not None and live.replay_pack_stage(pack) == "full" and live._ff1_pack_ready(pack)
        ):
            skip = f"[prewarm] memory_hit={memory_hit} disk_hit={disk_hit} for {year} R{round_number} - skip reload"
            _log.info(skip)
            print(skip, flush=True)
            return
        await live._ensure_replay_pack(key, year, round_number, session_type=stype, wait_for="minimal")
        done = f"[prewarm] ready pack for {year} R{round_number} key={cache_key}"
        _log.info(done)
        print(done, flush=True)
    except Exception:
        _log.info("[prewarm] failed for %s R%s (replay will cold-load)", year, round_number, exc_info=True)
        print(f"[prewarm] failed for {year} R{round_number} (replay will cold-load)", flush=True)
    finally:
        _PREWARM_INFLIGHT.discard(token)


async def _cached_sync(key: str, ttl: int, fn, *args, **kwargs):
    refresh = bool(kwargs.pop("refresh", False))
    if refresh:
        cache.delete(key)
        _log.info("HTTP cache BYPASS key=%s", key)
        value = await run_sync(fn, *args, **kwargs)
        cache.set(key, value)
        return value
    hit = get_memory_then_disk(key, ttl)
    if hit is not None:
        _log.debug("HTTP cache HIT key=%s", key)
        return hit
    stale = cache.peek(key)
    if stale is not None:
        if key not in _REFRESHING:
            _REFRESHING.add(key)

            async def _refresh() -> None:
                try:
                    value = await run_sync(fn, *args, **kwargs)
                    cache.set(key, value)
                except Exception:
                    pass
                finally:
                    _REFRESHING.discard(key)

            asyncio.create_task(_refresh())
        _log.debug("HTTP cache STALE key=%s", key)
        return stale
    _log.info("HTTP cache MISS key=%s", key)
    value = await run_sync(fn, *args, **kwargs)
    put_both(key, value, ttl)
    return value


async def _cached_await(key: str, ttl: int, factory, *, refresh: bool = False):
    if refresh:
        cache.delete(key)
        _log.info("HTTP cache BYPASS key=%s", key)
        value = await factory()
        cache.set(key, value)
        return value
    hit = get_memory_then_disk(key, ttl)
    if hit is not None:
        _log.debug("HTTP cache HIT key=%s", key)
        return hit
    stale = cache.peek(key)
    if stale is not None:
        if key not in _REFRESHING:
            _REFRESHING.add(key)

            async def _refresh() -> None:
                try:
                    value = await factory()
                    cache.set(key, value)
                except Exception:
                    pass
                finally:
                    _REFRESHING.discard(key)

            asyncio.create_task(_refresh())
        _log.debug("HTTP cache STALE key=%s", key)
        return stale
    _log.info("HTTP cache MISS key=%s", key)
    value = await factory()
    put_both(key, value, ttl)
    return value


@app.get("/")
def root() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "ARIS backend",
        "port": int(os.environ.get("PORT", "8765")),
    }


@app.get("/health")
def health_probe():
    from backend.health import build_health

    payload = build_health()
    return JSONResponse(status_code=200 if payload["ok"] else 503, content=payload)


@app.get("/api/health")
def health():
    from backend.health import build_health

    payload = build_health()
    return JSONResponse(status_code=200 if payload["ok"] else 503, content=payload)


@app.get("/api/calendar/{year}", response_model=CalendarResponse)
async def api_calendar(
    year: int,
    as_of: AsOf,
    replay: bool = Query(False, description="If true, only 2024–2026 are served (no FastF1 for older seasons)."),
) -> CalendarResponse:
    now_year = datetime.now(timezone.utc).year
    if year < 2018 or year > max(now_year, 2026):
        raise HTTPException(400, f"year must be 2018–{max(now_year, 2026)}")
    if replay:
        _require_replay_year(year)
    key = f"calendar_jolpica23st_{year}_{_as_of_key(as_of)}_{'replay' if replay else 'full'}"
    try:
        cal = await asyncio.wait_for(
            _cached_sync(key, TTL_CALENDAR, calendar.get_calendar, year, as_of=as_of, for_replay=replay),
            timeout=20.0,
        )
    except Exception:
        stale = cache.peek(key) or cache.peek(f"calendar_jolpica23st_{year}_now")
        if stale is not None:
            cal = stale
        else:
            try:
                cal = calendar.get_calendar(year, as_of=as_of, for_replay=replay)
            except Exception:
                raise HTTPException(503, "Calendar is warming up. Retry in a moment.")
    if replay:
        playable = [
            r
            for r in cal.rounds
            if str(getattr(r, "status", "")).upper() not in {"CANCELLED", "UPCOMING"}
        ]
        if hasattr(cal, "model_copy"):
            return cal.model_copy(update={"rounds": playable})
        cal.rounds = playable
        return cal
    return cal


@app.get("/api/calendar/{year}/{round_number}/sessions", response_model=RoundSessionsResponse)
async def api_round_sessions(
    year: int,
    round_number: int,
    as_of: AsOf,
    background_tasks: BackgroundTasks,
    session_type: str | None = Query(
        None, description="Unused for Replay/ARIS (Race-only). Kept for older callers."
    ),
    replay: bool = Query(
        False,
        description="If true, only Race sessions are returned (Replay/ARIS).",
    ),
) -> RoundSessionsResponse:
    # Round select already hits this path — start a pack now, don't wait for Start Replay.
    # Live OpenF1 weekends are unchanged; FastF1 replay packs are Race-only for 2024–2026.
    if calendar.replay_year_allowed(year):
        background_tasks.add_task(_prewarm_round_pack, year, round_number, "R")
    try:
        return await _cached_sync(
            f"sessions_{year}_{round_number}_{_as_of_key(as_of)}_{int(replay)}",
            TTL_NEXT_RACE,
            calendar.get_round_sessions,
            year,
            round_number,
            as_of=as_of,
            replay=replay,
        )
    except KeyError as extra:
        raise _http(extra) from extra


@app.get(
    "/api/session/{year}/{round_number}/{session_type}/ingest",
    response_model=IngestStatusResponse,
)
async def api_ingest_status(year: int, round_number: int, session_type: str) -> IngestStatusResponse:
    from backend.ingest_jobs import peek_ingest_status

    status = await run_sync(peek_ingest_status, year, round_number, session_type)
    return IngestStatusResponse(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        status=status,
    )


@app.post(
    "/api/session/{year}/{round_number}/{session_type}/ingest",
    response_model=IngestStatusResponse,
)
async def api_ingest_start(year: int, round_number: int, session_type: str) -> IngestStatusResponse:
    from backend.ingest_jobs import ensure_session_ingested

    status = await run_sync(ensure_session_ingested, year, round_number, session_type)
    return IngestStatusResponse(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        status=status,
    )


@app.post("/api/prewarm", response_model=PrewarmResponse)
async def api_prewarm(
    background_tasks: BackgroundTasks,
    year: int | None = Query(None),
    round_alias: int | None = Query(None, alias="round"),
    round_number: int | None = Query(None),
    session_type: str = Query("R"),
    body: PrewarmRequest | None = Body(default=None),
) -> PrewarmResponse:
    """Called when a round is selected. Returns immediately; the pack builds in the background."""
    y = body.year if body is not None else year
    rnd = body.round_number if body is not None else (round_number if round_number is not None else round_alias)
    st = str((body.session_type if body is not None else session_type) or "R").upper()
    if y is None or rnd is None:
        raise HTTPException(422, "year and round are required")
    _require_replay_year(int(y))
    st = _require_replay_session_type(st)
    key = live.synthetic_session_key(int(y), int(rnd), st)
    background_tasks.add_task(_prewarm_round_pack, int(y), int(rnd), st)

    def _bg() -> None:
        try:
            sessions.circuit_preview_safe(int(y), int(rnd))
        except Exception as exc:
            print(f"[ARIS] prewarm preview failed: {exc}", flush=True)
        try:
            from backend.ingest_jobs import ensure_session_ingested

            ensure_session_ingested(int(y), int(rnd), st)
        except Exception as extra:
            print(f"[ARIS] prewarm ingest failed: {extra}", flush=True)

    asyncio.get_running_loop().run_in_executor(prewarm_executor, _bg)
    return PrewarmResponse(
        year=int(y),
        round_number=int(rnd),
        session_type=st,
        session_key=key,
        status="ready" if _pack_memory_ready(key) else "warming",
        tasks=["session_pack", "circuit_preview", "ingest"],
    )


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
            pick = next((r for r in cal.rounds if r.status in {"LIVE", "UPCOMING"}), None)
            if pick is not None:
                return calendar._next_from_round(
                    2026, pick, calendar.now_utc(as_of), off_season=False
                )
        except Exception:
            pass
        raise _http(exc, 503) from exc


@app.get("/api/live/next", response_model=NextRaceResponse)
async def api_live_next(as_of: AsOf, year: int | None = None) -> NextRaceResponse:
    """Alias of /api/next-race — current or next weekend."""
    return await api_next_race(as_of, year)


def _r2_public_base() -> str:
    return (
        os.environ.get("R2_PUBLIC_BASE_URL")
        or os.environ.get("NEXT_PUBLIC_R2_BASE_URL")
        or ""
    ).rstrip("/")


def _r2_field_exists(year: int, round_number: int) -> bool:
    base = _r2_public_base()
    if not base:
        return False
    url = f"{base}/replay/{int(year)}/{int(round_number)}/race_field.json"
    try:
        import urllib.request

        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=4) as resp:
            return 200 <= int(getattr(resp, "status", 200)) < 400
    except Exception:
        return False


def _race_winner(year: int, round_number: int) -> tuple[str | None, str | None]:
    """Winner code from ingested Postgres results. Never loads FastF1."""
    try:
        from aris.io import db as aris_db
        from sqlalchemy import text as _sql

        eng = aris_db.engine()
        with eng.connect() as conn:
            row = conn.execute(
                _sql(
                    "SELECT d.code FROM results r "
                    "JOIN sessions s ON s.session_id = r.session_id "
                    "JOIN drivers d ON d.driver_id = r.driver_id "
                    "WHERE s.year=:y AND s.round_no=:n AND s.session_type='R' "
                    "AND r.position = 1 LIMIT 1"
                ),
                {"y": int(year), "n": int(round_number)},
            ).fetchone()
        if row and row[0]:
            code = str(row[0])
            return code, code
    except Exception:
        pass
    return None, None


def _recent_races(limit: int) -> list[RecentRaceCard]:
    picks = _recent_circuit_rounds(limit)
    out: list[RecentRaceCard] = []
    for year, rnd in reversed(picks):
        try:
            card = calendar.get_round(int(year), int(rnd))
        except Exception:
            continue
        winner_name, winner_code = _race_winner(int(year), int(rnd))
        date = getattr(card, "date_race", None)
        out.append(
            RecentRaceCard(
                year=int(year),
                round=int(rnd),
                circuitName=str(card.circuit_name or card.name or ""),
                countryFlag=calendar.country_flag(card.country, card.circuit_key),
                raceName=str(card.name or card.circuit_name or ""),
                date=date.isoformat() if hasattr(date, "isoformat") else date,
                winner=winner_name,
                winnerCode=winner_code,
                sessionType="R",
                r2_available=_r2_field_exists(int(year), int(rnd)),
            )
        )
        if len(out) >= limit:
            break
    return out[:limit]


@app.get("/api/recent-races", response_model=list[RecentRaceCard])
async def api_recent_races(limit: int = 3) -> list[RecentRaceCard]:
    """Last N completed races for homepage replay badges."""
    n = max(1, min(int(limit or 3), 12))
    return await run_sync(_recent_races, n)


@app.get("/api/live/hub", response_model=LiveHubResponse)
async def api_live_hub(as_of: AsOf) -> LiveHubResponse:
    try:
        return await asyncio.wait_for(live_hub.build_live_hub(as_of), timeout=6.0)
    except Exception:
        try:
            return await run_sync(live_hub.build_live_hub_fast, as_of)
        except Exception as extra:
            raise _http(extra, 503) from extra


@app.get("/api/drivers/{year}", response_model=DriversResponse)
async def api_drivers(year: int) -> DriversResponse:
    return await _cached_sync(f"drivers_{year}", TTL_DRIVERS, standings.get_drivers, year)


@app.get("/api/teams/{year}", response_model=TeamsResponse)
async def api_teams(year: int) -> TeamsResponse:
    return await _cached_sync(f"teams_{year}", TTL_DRIVERS, standings.get_teams, year)


@app.get("/api/standings/drivers/{year}", response_model=DriverStandingsResponse)
async def api_driver_standings(year: int) -> DriverStandingsResponse:
    _require_standings_year(year)
    ttl = TTL_COMPLETED if year < datetime.now(timezone.utc).year else TTL_STANDINGS
    return await _cached_sync(
        f"standings_drivers_{year}", ttl, standings.driver_standings, year
    )


@app.get("/api/standings/constructors/{year}", response_model=ConstructorStandingsResponse)
async def api_constructor_standings(year: int) -> ConstructorStandingsResponse:
    _require_standings_year(year)
    ttl = TTL_COMPLETED if year < datetime.now(timezone.utc).year else TTL_STANDINGS
    return await _cached_sync(
        f"standings_constructors_{year}", ttl, standings.constructor_standings, year
    )


@app.get("/api/session/{year}/{round_number}/{session_type}/laps", response_model=LapsResponse)
async def api_laps(
    year: int, round_number: int, session_type: str, refresh: bool = False
) -> LapsResponse:
    try:
        if refresh:
            sessions.clear_session_cache(year, round_number, session_type)
        return await _cached_sync(
            f"laps_{year}_{round_number}_{session_type}",
            _history_ttl(year),
            sessions.session_laps,
            year,
            round_number,
            session_type,
            refresh=refresh,
        )
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/summary", response_model=SessionSummary)
async def api_summary(
    year: int, round_number: int, session_type: str, refresh: bool = False
) -> SessionSummary:
    try:
        if refresh:
            sessions.clear_session_cache(year, round_number, session_type)
        return await _cached_sync(
            f"summary_{year}_{round_number}_{session_type}",
            _history_ttl(year),
            sessions.session_summary,
            year,
            round_number,
            session_type,
            refresh=refresh,
        )
    except Exception as exc:
        raise _http(exc) from exc


@app.get("/api/session/{year}/{round_number}/{session_type}/stints", response_model=StintsResponse)
async def api_stints(
    year: int, round_number: int, session_type: str, refresh: bool = False
) -> StintsResponse:
    try:
        if refresh:
            sessions.clear_session_cache(year, round_number, session_type)
        return await _cached_sync(
            f"stints_{year}_{round_number}_{session_type}",
            _history_ttl(year),
            sessions.session_stints,
            year,
            round_number,
            session_type,
            refresh=refresh,
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
            _history_ttl(year),
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
            _history_ttl(year),
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
            _history_ttl(year),
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
            _history_ttl(year),
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
            _history_ttl(year),
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
        _history_ttl(year),
        sessions.circuit_path,
        year,
        round_number,
        session_type,
    )


@app.get("/api/circuit/{year}/{round_number}/map", response_model=CircuitMapResponse)
async def api_circuit_map(year: int, round_number: int) -> CircuitMapResponse:
    try:
        raw = await _cached_sync(
            f"circuit_map_v6_{year}_{round_number}",
            _history_ttl(year),
            sessions.circuit_map_quick,
            year,
            round_number,
        )
        return sessions.ensure_sector_paths(raw)
    except Exception:
        return CircuitMapResponse(
            year=year, round_number=round_number, available=False, fallback=True, error="Circuit map unavailable"
        )


@app.get("/api/circuit/{year}/{round_number}/preview", response_model=CircuitMapResponse)
async def api_circuit_preview(year: int, round_number: int) -> CircuitMapResponse:
    """Never triggers a live FastF1 load — memory/disk only."""
    return await run_sync(sessions.circuit_preview_safe, year, round_number)


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
            _history_ttl(year),
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
        _history_ttl(year),
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
            _history_ttl(year),
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
            f"gaps_{year}_{round_number}", _history_ttl(year), analytics.gap_history, year, round_number
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/race/{year}/{round_number}/position-history", response_model=PositionHistoryResponse)
async def api_positions(year: int, round_number: int) -> PositionHistoryResponse:
    try:
        return await _cached_sync(
            f"positions_{year}_{round_number}",
            _history_ttl(year),
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
            f"tyres_{year}_{round_number}", _history_ttl(year), analytics.tyre_strategy, year, round_number
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/race/{year}/{round_number}/pit-stops", response_model=PitStopsResponse)
async def api_pits(year: int, round_number: int) -> PitStopsResponse:
    try:
        return await _cached_sync(
            f"pits_{year}_{round_number}", _history_ttl(year), analytics.pit_stops, year, round_number
        )
    except Exception as extra:
        raise _http(extra) from extra


@app.get("/api/race/{year}/{round_number}/fastest-lap-evolution", response_model=FastestLapEvolutionResponse)
async def api_fl_evo(year: int, round_number: int) -> FastestLapEvolutionResponse:
    try:
        return await _cached_sync(
            f"fl_{year}_{round_number}",
            _history_ttl(year),
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
            _history_ttl(year),
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
        _history_ttl(year),
        analytics.driver_season,
        driver_code,
        year,
    )


@app.get("/api/circuit/{circuit_key}/history", response_model=CircuitHistoryResponse)
async def api_circuit_history(circuit_key: str) -> CircuitHistoryResponse:
    return await _cached_sync(
        f"circuit_history_v5_{circuit_key}", TTL_SESSION, analytics.circuit_history, circuit_key
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
        _history_ttl(year),
        analytics.compare_drivers,
        driver_a,
        driver_b,
        year,
        round_number,
    )


@app.get("/api/live/session-key")
async def api_live_session_key(
    year: int, round_number: int, session_type: str, refresh: bool = False
) -> dict[str, object]:
    from backend.sessions import _pack_cache_key, quali_windows_for_session_type

    key = live.synthetic_session_key(year, round_number, session_type)
    cache_key = _pack_cache_key(year, round_number, session_type)
    start, end = live.calendar_session_window(year, round_number, session_type)
    pack, memory_hit, disk_hit = live.hydrate_replay_pack_cache(
        key, year, round_number, session_type, log_hits=False
    )
    _log.info("key=%s memory_hit=%s disk_hit=%s", cache_key, memory_hit, disk_hit)
    # fix-pass item 13: this endpoint is polled repeatedly while a replay is open,
    # so guard the task spawn — a no-op once the pack is warm or already building,
    # instead of creating (and immediately discarding) a task on every call.
    existing_lock = live._REPLAY_LOCKS.get(key)
    pack_in_flight = existing_lock is not None and existing_lock.locked()
    if refresh or (not _pack_memory_ready(key) and not pack_in_flight):
        live._kick_pack_job(key, year, round_number, session_type, refresh=refresh)
    pack = live._REPLAY_PACKS.get(key) or pack
    green = None
    if isinstance(pack, dict):
        green = (
            live._race_start_s(pack)
            if session_type.upper() in {"R", "S"}
            else pack.get("green_flag_s")
        )
        pack_start = pack.get("date_start")
        pack_end = pack.get("date_end")
        if pack_start is not None:
            start = pack_start
        if pack_end is not None:
            end = pack_end
    _log.info(
        "session-key FastF1 year=%s round=%s type=%s key=%s cache=%s",
        year,
        round_number,
        session_type,
        key,
        cache_key,
    )
    return {
        "session_key": key,
        "year": year,
        "round_number": round_number,
        "session_type": session_type,
        "date_start": start.isoformat() if hasattr(start, "isoformat") else start,
        "date_end": end.isoformat() if hasattr(end, "isoformat") else end,
        "session_name": session_type,
        "quali_windows": quali_windows_for_session_type(session_type),
        "green_flag_s": green,
        "source": "fastf1",
    }


@app.get("/api/live/replay-ready")
async def api_live_replay_ready(
    session_key: int,
    year: int | None = None,
    round_number: int | None = None,
    refresh: bool = False,
    driver: str | None = None,
) -> dict[str, object]:
    return await live.replay_ready(session_key, year, round_number, refresh=refresh, driver=driver)


@app.get("/api/live/replay-pack-status")
async def api_live_replay_pack_status(
    session_key: int | None = None,
    session_id: int | None = None,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
    refresh: bool = False,
    outline: bool = False,
) -> dict[str, object]:
    """Non-blocking cold-load peek. Returns immediately with stage/flags.

    Additive endpoint — does not change `/api/live/replay-ready`. Ready means
    stage >= minimal so the UI can start before full GPS.
    """
    key = session_key if session_key is not None else session_id
    if key is None:
        raise HTTPException(status_code=422, detail="session_key or session_id is required")
    return await live.peek_replay_pack_status(
        int(key),
        year,
        round_number,
        session_type,
        refresh=refresh,
        outline=outline,
    )


@app.post("/api/replay/init", response_model=ReplayInitResponse)
async def api_replay_init(req: ReplayInitRequest) -> ReplayInitResponse:
    """Return calendar metadata immediately and start staged FastF1 in the background."""
    _require_replay_year(req.year)
    session_type = _require_replay_session_type(req.session_type)
    payload = await live.init_replay(req.year, req.round_number, session_type)
    return ReplayInitResponse.model_validate(payload)


@app.get("/api/replay/pack-status")
async def api_replay_pack_status(
    session_key: int | None = None,
    session_id: int | None = None,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
    refresh: bool = False,
    outline: bool = False,
) -> dict[str, object]:
    """Alias of /api/live/replay-pack-status with session_id accepted."""
    key = session_key if session_key is not None else session_id
    if key is None:
        raise HTTPException(status_code=422, detail="session_key or session_id is required")
    return await live.peek_replay_pack_status(
        int(key),
        year,
        round_number,
        session_type,
        refresh=refresh,
        outline=outline,
    )


@app.get("/api/replay/pos-chunk")
async def api_replay_pos_chunk(
    session_key: int | None = None,
    session_id: int | None = None,
    lap: int = 1,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
) -> dict[str, object]:
    """Prefetch a 10-lap GPS window. Disk only — never FastF1 car_data or position_data."""
    key = session_key if session_key is not None else session_id
    if key is None:
        raise HTTPException(status_code=422, detail="session_key or session_id is required")
    return await live.peek_replay_pos_chunk(
        int(key), int(lap), year, round_number, session_type
    )


@app.get("/api/live/replay-path")
async def api_live_replay_path(
    session_key: int, year: int | None = None, round_number: int | None = None
) -> dict[str, object]:
    return await live.replay_path(session_key, year, round_number)


@app.get("/api/live/replay-frame", response_model=ReplayFrameResponse)
async def api_live_replay_frame(
    session_key: int,
    as_of: datetime = Query(..., description="Replay clock (ISO-8601 UTC)"),
    year: int | None = None,
    round_number: int | None = None,
    driver: str | None = None,
    refresh: bool = False,
    prev_as_of: datetime | None = Query(None, description="Previous applied frame clock for deltas"),
    full: bool = Query(False, description="Force a full snapshot (seek / first frame)"),
) -> ReplayFrameResponse:
    return await live.serve_replay_frame(
        session_key,
        as_of,
        year=year,
        round_number=round_number,
        driver=driver,
        refresh=refresh,
        prev_as_of=prev_as_of,
        force_full=full,
    )


@app.get("/api/aris/ghost")
async def api_aris_ghost(
    year: int,
    round_number: int,
    driver: str,
    lap: int = 1,
    session_key: int | None = None,
) -> dict[str, object]:
    """Live/replay ghost tick for the selected driver. Does not change recommend()/simulate()."""
    return await live.ghost_for_driver(
        year=year,
        round_number=round_number,
        driver=driver,
        lap=lap,
        session_key=session_key,
    )


@app.get("/api/aris/ghost-pack")
async def api_aris_ghost_pack(year: int, round_number: int, driver: str) -> dict[str, object]:
    """Full R2-shaped ghost for any driver who raced this weekend.

    Race-pack 404s stay ``Race data unavailable``. A driver who did not race
    is a 422, not an empty ghost. Computation is synchronous: recommend()
    with mc_draws=0 plus per-lap simulate is typically a few seconds.
    """
    from aris.ghost_pack import GhostPackError

    try:
        return await run_sync(aris_api.ghost_pack, year, round_number, driver)
    except GhostPackError as extra:
        raise HTTPException(status_code=extra.status, detail=extra.as_detail()) from extra
    except Exception as extra:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ghost_data_gap",
                "message": f"Could not compute a ghost for {str(driver).upper()}: {extra}",
            },
        ) from extra


@app.get("/api/live/status", response_model=LiveStatus)
async def api_live_status(as_of: AsOf, replay_session_key: int | None = None) -> LiveStatus:
    try:
        if as_of is not None and replay_session_key is None:
            return await run_sync(live.simulated_status, as_of)
        return await asyncio.wait_for(
            live.live_status(as_of, replay_session_key=replay_session_key),
            timeout=8.0,
        )
    except Exception:
        ended = live._STATE.get("ended_session")
        return LiveStatus(
            is_live=False,
            session_ended=isinstance(ended, dict),
            error=None,
            replay_preparing=True,
        )


@app.get("/api/live/timing", response_model=LiveTimingResponse)
async def api_live_timing(as_of: AsOf, replay_session_key: int | None = None) -> LiveTimingResponse:
    try:
        return await _cached_await(
            f"live_timing_{_as_of_key(as_of)}_{replay_session_key}",
            1,
            lambda: live.live_timing(as_of, replay_session_key=replay_session_key),
        )
    except Exception:
        return LiveTimingResponse(is_live=False, rows=[])


@app.get("/api/telemetry/cars", response_model=LivePositionsResponse)
async def api_telemetry_cars(as_of: AsOf, replay_session_key: int | None = None) -> LivePositionsResponse:
    """Alias of /api/live/positions — GPS car dots for the map."""
    return await api_live_positions(as_of, replay_session_key)


@app.get("/api/circuits/{circuit_id}/layout", response_model=CircuitMapResponse)
async def api_circuit_layout(
    circuit_id: str, year: int | None = None, round_number: int | None = None
) -> CircuitMapResponse:
    try:
        return await run_sync(live_hub.circuit_layout, circuit_id, year, round_number)
    except KeyError as extra:
        raise HTTPException(404, str(extra)) from extra
    except Exception:
        return CircuitMapResponse(
            year=year or 0,
            round_number=round_number or 0,
            available=False,
            fallback=True,
            error="Circuit layout unavailable",
        )


@app.get("/api/live/positions", response_model=LivePositionsResponse)
async def api_live_positions(as_of: AsOf, replay_session_key: int | None = None) -> LivePositionsResponse:
    try:
        return await _cached_await(
            f"live_positions_{_as_of_key(as_of)}_{replay_session_key}",
            1,
            lambda: live.live_positions(
                as_of, replay_session_key=replay_session_key, simulated=as_of is not None and replay_session_key is None
            ),
        )
    except Exception:
        return LivePositionsResponse(is_live=False, positions=[])


@app.get("/api/live/intervals", response_model=LiveIntervalsResponse)
async def api_live_intervals(as_of: AsOf, replay_session_key: int | None = None) -> LiveIntervalsResponse:
        return await _cached_await(
            f"live_intervals_{_as_of_key(as_of)}_{replay_session_key}",
            _replay_feed_ttl(replay_session_key),
            lambda: live.live_intervals(as_of, replay_session_key=replay_session_key),
        )


@app.get("/api/live/race-control", response_model=LiveRaceControlResponse)
async def api_live_rc(as_of: AsOf, replay_session_key: int | None = None) -> LiveRaceControlResponse:
    try:
        return await _cached_await(
            f"live_rc_{_as_of_key(as_of)}_{replay_session_key}",
            _replay_feed_ttl(replay_session_key),
            lambda: live.live_race_control(as_of, replay_session_key=replay_session_key),
        )
    except Exception:
        return LiveRaceControlResponse(is_live=False, messages=[])


@app.get("/api/live/stints", response_model=LiveStintsResponse)
async def api_live_stints(as_of: AsOf, replay_session_key: int | None = None) -> LiveStintsResponse:
    return await _cached_await(
        f"live_stints_{_as_of_key(as_of)}_{replay_session_key}",
        _replay_feed_ttl(replay_session_key),
        lambda: live.live_stints(as_of, replay_session_key=replay_session_key),
    )


@app.get("/api/live/weather", response_model=LiveWeatherResponse)
async def api_live_weather(as_of: AsOf, replay_session_key: int | None = None) -> LiveWeatherResponse:
    return await _cached_await(
        f"live_weather_{_as_of_key(as_of)}_{replay_session_key}",
        _replay_feed_ttl(replay_session_key),
        lambda: live.live_weather(as_of, replay_session_key=replay_session_key),
    )


@app.get("/api/live/laps", response_model=LiveLapsResponse)
async def api_live_laps(as_of: AsOf, replay_session_key: int | None = None) -> LiveLapsResponse:
    try:
        return await live.live_laps(as_of, replay_session_key=replay_session_key)
    except Exception:
        return LiveLapsResponse(is_live=False, laps=[])


@app.get("/api/live/telemetry", response_model=LiveTelemetryResponse)
async def api_live_telemetry(
    driver: str, as_of: AsOf, replay_session_key: int | None = None
) -> LiveTelemetryResponse:
    try:
        return await live.live_telemetry(driver, as_of, replay_session_key=replay_session_key)
    except Exception:
        return LiveTelemetryResponse(is_live=False, driver_code=driver.upper())


@app.get("/api/live/stream")
async def api_live_stream(replay_session_key: int | None = None):
    return StreamingResponse(
        live.sse_generator(replay_session_key=replay_session_key),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _live_rainfall_override(body: RecommendRequest) -> RecommendRequest:
    """Overlay OpenF1 rainfall onto live recommend. Debug override_rainfall wins."""
    if body.override_rainfall is not None or body.mode != "live":
        return body
    key = None
    if body.session_key:
        try:
            key = int(str(body.session_key).strip())
        except (TypeError, ValueError):
            key = None
    if key is None:
        try:
            sess = await live.peek_live_session()
            if isinstance(sess, dict) and sess.get("session_key") is not None:
                key = int(sess["session_key"])
        except Exception:
            key = None
    if key is None:
        return body
    try:
        raining = await live.get_live_rainfall(key)
    except Exception:
        return body
    return body.model_copy(update={"override_rainfall": raining})


GHOST_RECOMPUTE_TIMEOUT_S = 20


def _ghost_recompute_http_error(extra: BaseException) -> HTTPException:
    message = str(extra) or extra.__class__.__name__
    lower = message.lower()
    if "not warm" in lower:
        return HTTPException(
            status_code=503,
            detail={
                "error": message,
                "code": "replay_pack_not_warm",
            },
        )
    if "no laps" in lower or "no ticks" in lower or "did not race" in lower:
        return HTTPException(
            status_code=422,
            detail={
                "error": message,
                "code": "ghost_uncomputable",
            },
        )
    return HTTPException(
        status_code=500,
        detail={
            "error": message,
            "code": "ghost_recompute_failed",
        },
    )


@app.post(
    "/api/aris/recommend",
    response_model=RecommendResponse,
    dependencies=[Depends(enforce_compute_quota)],
)
async def api_recommend(body: RecommendRequest) -> RecommendResponse:
    try:
        body = await _live_rainfall_override(body)
        # fix-pass item 1: recommend runs on its own small pool so a slow cold
        # replay load on the general pool can never queue-block a live recommendation.
        return await run_light(aris_api.recommend, body)
    except aris_api.ClientInputError as extra:
        raise HTTPException(422, str(extra)) from extra
    except ValueError as extra:
        raise HTTPException(422, str(extra)) from extra
    except RuntimeError as extra:
        raise HTTPException(503, str(extra)) from extra
    except Exception as extra:
        return aris_api._fallback_recommend(body)


@app.post(
    "/api/aris/ghost-recompute",
    response_model=GhostRecomputeResponse,
    dependencies=[Depends(enforce_compute_quota)],
)
async def api_ghost_recompute(
    body: GhostRecomputeRequest,
) -> GhostRecomputeResponse:
    driver = str(body.driver or "").strip()
    if not driver:
        raise HTTPException(
            status_code=422,
            detail={"error": "driver is required", "code": "ghost_uncomputable"},
        )
    try:
        payload = await asyncio.wait_for(
            run_light(
                lambda: live.recompute_ghost_from_plan(
                    year=int(body.year),
                    round_number=int(body.round),
                    driver=driver,
                    current_lap=int(body.current_lap),
                    pit_laps=list(body.pit_laps),
                    compounds=list(body.compounds),
                    session_key=body.session_key,
                    label=str(body.label or ""),
                )
            ),
            timeout=GHOST_RECOMPUTE_TIMEOUT_S,
        )
        return GhostRecomputeResponse.model_validate(payload)
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail={
                "error": "ghost recompute timed out",
                "code": "ghost_recompute_timeout",
                "timeout_s": GHOST_RECOMPUTE_TIMEOUT_S,
            },
        ) from None
    except aris_api.ClientInputError as extra:
        raise HTTPException(
            status_code=422,
            detail={"error": str(extra), "code": "ghost_uncomputable"},
        ) from extra
    except RuntimeError as extra:
        raise _ghost_recompute_http_error(extra) from extra
    except ValueError as extra:
        raise HTTPException(
            status_code=422,
            detail={"error": str(extra), "code": "ghost_uncomputable"},
        ) from extra
    except Exception as extra:
        raise _ghost_recompute_http_error(extra) from extra


@app.post(
    "/api/aris/simulate",
    response_model=SimulateResponse,
    dependencies=[Depends(enforce_compute_quota)],
)
async def api_simulate(body: SimulateRequest) -> SimulateResponse:
    try:
        return await run_light(aris_api.simulate, body)
    except aris_api.ClientInputError as extra:
        raise HTTPException(422, str(extra)) from extra
    except ValueError as extra:
        raise HTTPException(422, str(extra)) from extra
    except RuntimeError as extra:
        raise HTTPException(503, str(extra)) from extra
    except Exception as extra:
        raise HTTPException(503, str(extra)) from extra


def _aris_stats() -> ArisStatsResponse:
    hit = cache.get("aris_stats", TTL_STATS)
    if hit is not None:
        return hit
    value = aris_api.model_stats()
    put_both("aris_stats", value, TTL_STATS)
    return value


@app.get("/api/aris/stats", response_model=ArisStatsResponse)
def api_aris_stats() -> ArisStatsResponse:
    return _aris_stats()


@app.get("/api/status", response_model=ArisStatsResponse)
def api_status() -> ArisStatsResponse:
    """Fast alias of `/api/aris/stats` — Hero (`getStatus`) hits this path."""
    return _aris_stats()


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


@app.post(
    "/api/ask",
    response_model=ChatResponse,
    dependencies=[Depends(enforce_compute_quota)],
)
async def api_ask(body: AskRequest) -> ChatResponse:
    """Ask ARIS — factual questions hit field lookups via chat(); not a RAG dump."""
    return await run_sync(
        aris_api.chat,
        None,
        body.driver_code,
        body.question,
        body.year,
        body.round_number,
        body.current_lap,
    )


@app.post(
    "/api/copilot/chat",
    response_model=CopilotChatResponse,
    dependencies=[Depends(enforce_compute_quota)],
)
async def api_copilot_chat(body: CopilotChatRequest) -> CopilotChatResponse:
    try:
        return await run_sync(aris_api.copilot_chat, body)
    except Exception as extra:
        raise HTTPException(503, str(extra)) from extra


@app.get(
    "/api/aris/plans",
    response_model=StratPlansResponse,
    dependencies=[Depends(enforce_compute_quota)],
)
async def api_plans(year: int, round_number: int, driver_code: str) -> StratPlansResponse:
    try:
        return await run_sync(aris_api.plans, year, round_number, driver_code)
    except aris_api.ClientInputError as extra:
        raise HTTPException(422, str(extra)) from extra
    except RuntimeError as extra:
        raise HTTPException(503, str(extra)) from extra
    except Exception as extra:
        raise HTTPException(503, str(extra)) from extra


@app.get("/api/aris/quick-analysis", response_model=StratPlansResponse)
async def api_quick_analysis(year: int, round_number: int, driver_code: str) -> StratPlansResponse:
    """Pre-race top-3 strategies. Wraps plans(); does not change recommend()/simulate()."""
    try:
        return await run_sync(aris_api.quick_analysis, year, round_number, driver_code)
    except aris_api.ClientInputError as extra:
        raise HTTPException(422, str(extra)) from extra
    except RuntimeError as extra:
        raise HTTPException(503, str(extra)) from extra
    except Exception as extra:
        raise HTTPException(503, str(extra)) from extra


@app.get("/api/aris/debrief", response_model=DebriefResponse)
async def api_debrief(year: int, round_number: int, driver_code: str) -> DebriefResponse:
    return await run_sync(aris_api.debrief, year, round_number, driver_code)


@app.get("/api/explain/degradation", response_model=DegradationCurveResponse)
async def api_explain_degradation(
    session_id: str | None = None,
    driver: str = "VER",
    stint_id: int | None = None,
    start_lap: int | None = None,
    end_lap: int | None = None,
    year: int | None = None,
    round_number: int | None = None,
) -> DegradationCurveResponse:
    try:
        payload = await run_sync(
            aris_api.explain_degradation,
            session_id,
            driver,
            stint_id,
            start_lap,
            end_lap,
            year,
            round_number,
        )
        return DegradationCurveResponse.model_validate(payload)
    except Exception as extra:
        raise HTTPException(503, str(extra)) from extra


@app.get("/api/explain/ghost", response_model=GhostVsRealResponse)
async def api_explain_ghost(
    session_id: str | None = None,
    driver: str = "VER",
    year: int | None = None,
    round_number: int | None = None,
) -> GhostVsRealResponse:
    try:
        payload = await run_sync(
            aris_api.explain_ghost, session_id, driver, year, round_number
        )
        return GhostVsRealResponse.model_validate(payload)
    except Exception as extra:
        raise HTTPException(503, str(extra)) from extra


@app.get("/api/explain/debrief")
async def api_explain_debrief(
    session_id: str | None = None,
    driver: str | None = None,
    focus_driver: str | None = None,
    year: int | None = None,
    round_number: int | None = None,
    format: str = Query("json"),
):
    try:
        payload = await run_sync(
            aris_api.explain_debrief,
            session_id,
            focus_driver or driver,
            year,
            round_number,
        )
    except Exception as extra:
        raise HTTPException(503, str(extra)) from extra
    if str(format).lower() == "parquet":
        from aris.explain.debrief import debrief_to_parquet_bytes

        body, media, filename = debrief_to_parquet_bytes(payload)
        return Response(
            content=body,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return RaceDebriefResponse.model_validate(payload)
