"""OpenF1 live polling (async httpx), SSE stream, and FastF1 replay-as-if-live."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

_log = logging.getLogger("aris.live")

from backend.cache import TTL_LIVE, TTL_RAINFALL, TTL_REPLAY, TTL_WEATHER_LIVE, cache
from backend.calendar import now_utc
from backend.http_client import aopenf1
from backend.models import (
    CircuitMarker,
    LapRow,
    LiveInterval,
    LiveIntervalsResponse,
    LiveLapsResponse,
    LivePosition,
    LivePositionsResponse,
    LiveRaceControlResponse,
    LiveStatus,
    LiveStintsResponse,
    LiveTelemetryResponse,
    LiveTimingResponse,
    LiveTimingRow,
    LiveWeatherResponse,
    QualiWindow,
    RaceControlMessage,
    ReplayFrameResponse,
    StintRow,
)
from backend.utils import executor as _sync_pool
from backend.utils import prewarm_executor as _prewarm_pool
from backend.utils import run_on, run_sync

OPENF1_BASE = "https://api.openf1.org/v1"


def _pool_name(pool: Any) -> str:
    if pool is _prewarm_pool:
        return "prewarm"
    if pool is _sync_pool:
        return "sync"
    return "sync"


async def _run_pack_blocking(executor: Any, fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run pack-building blocking work on `executor` (default: general sync pool).

    Lets prewarm callers pass the dedicated prewarm pool so a background weekend-
    pack warm never competes with a live user's replay/recommend request for a
    worker on the general pool (fix-pass item 1/2).
    """
    pool = executor or _sync_pool
    return await run_on(pool, _pool_name(pool), fn, *args, **kwargs)

_STATE: dict[str, Any] = {
    "status": None,
    "timing": None,
    "positions": None,
    "intervals": None,
    "race_control": None,
    "stints": None,
    "weather": None,
    "last_success": None,
    "session": None,
    "drivers": {},
    "laps": [],
    "latest_pos": {},
    "locations": {},
    "eliminated": set(),
    "error": None,
}

# T6: ghost pre-computation cache.
# Keys: "{year}_{round}_{driver_code}" (per-driver lookup) and
# "{year}_{round}_{session_key}" (legacy alias used by replay_frame).
# Values: {lap_number: ghost_to_dict() output | None}
_GHOST_CACHE: dict[str, dict[int, dict | None]] = {}
_GHOST_INFLIGHT: set[str] = set()
# fix-pass item 5/9: same keys as _GHOST_CACHE, records *why* a key resolved to
# an empty map so `_ghost_at_lap` can report a real reason instead of silence.
# "ok" (DB data found, just no divergence yet) | "session_not_ingested" (no
# usable ARIS-DB rows for this driver/session).
_GHOST_STATUS: dict[str, str] = {}
# Selected-plan override for ghost precompute: "{year}_{round}_{DRIVER}" → GhostPlan-like dict.
_GHOST_PLAN: dict[str, dict[str, Any]] = {}

GhostReason = str  # "no_driver_selected" | "session_not_ingested" | "no_divergence"


def _ghost_driver_key(year: int | None, round_number: int | None, driver: str) -> str:
    return f"{int(year or 0)}_{int(round_number or 0)}_{str(driver).upper()}"


def _row_float(row: Any, key: str, default: float | None) -> float | None:
    try:
        val = row[key] if key in getattr(row, "index", []) else row.get(key)
    except Exception:
        val = None
    if val is None:
        return default
    try:
        num = float(val)
        if math.isnan(num):
            return default
        return num
    except (TypeError, ValueError):
        return default


def _store_ghost_map(
    year: Any,
    round_num: Any,
    session_key: int,
    driver_code: str,
    ghost_map: dict,
    status: str = "ok",
) -> None:
    per_driver_key = _ghost_driver_key(year, round_num, driver_code)
    replay_frame_key = f"{year}_{round_num}_{session_key}"
    _GHOST_CACHE[per_driver_key] = ghost_map
    _GHOST_CACHE[replay_frame_key] = ghost_map
    _GHOST_STATUS[per_driver_key] = status
    _GHOST_STATUS[replay_frame_key] = status


def _explain_ghost_ticks(driver: str, year: Any, round_num: Any) -> dict[int, dict | None]:
    from aris.explain.ghost import get_ghost_lap_ticks

    return get_ghost_lap_ticks(str(driver).upper(), year=int(year), round_number=int(round_num))


def _try_explain_ghost(year: Any, round_num: Any, session_key: int, focus: str) -> bool:
    if not year or not round_num or not focus:
        return False
    try:
        ticks = _explain_ghost_ticks(focus, year, round_num)
    except Exception:
        return False
    if not ticks:
        return False
    _store_ghost_map(year, round_num, session_key, focus, ticks)
    _log.info(
        "ghost precompute via explain: session_key=%s driver=%s laps=%s",
        session_key,
        focus,
        len(ticks),
    )
    return True


def _field_cum_from_pack(pack: dict | None) -> dict[int, dict[str, float]]:
    """Cumulative classified lap times from a replay pack, keyed by lap then driver."""
    from aris.ghost import field_cumulative_by_lap

    per: dict[str, dict[int, float]] = {}
    for row in (pack or {}).get("laps") or []:
        if not isinstance(row, dict):
            continue
        code = str(row.get("driver_code") or "").upper()
        lap = int(row.get("lap_number") or 0)
        if not code or lap < 1:
            continue
        raw = row.get("lap_duration")
        if raw is None:
            raw = row.get("lap_time_s")
        try:
            t = float(raw)
        except (TypeError, ValueError):
            continue
        if t <= 0:
            continue
        per.setdefault(code, {})[lap] = t
    return field_cumulative_by_lap(per)


def _ghost_on_track(ghost: dict | None, positions: list, driver: str | None) -> dict | None:
    """Copy ghost tick and place it along the real car's path_frac."""
    if not ghost or not isinstance(ghost, dict):
        return ghost
    out = dict(ghost)
    typical = float(out.get("typical_lap_s") or 90.0) or 90.0
    delta = float(out.get("ghost_cumulative_delta") or 0.0)
    real_frac = 0.0
    code = str(driver or out.get("driver_code") or "").upper()
    for pos in positions or []:
        pos_code = str(getattr(pos, "driver_code", "") or "").upper()
        if pos_code == code:
            real_frac = float(getattr(pos, "path_frac", 0.0) or 0.0)
            break
    offset = delta / typical
    out["ghost_position_on_track"] = ((real_frac + offset) % 1.0 + 1.0) % 1.0
    if not out.get("ghost_compound"):
        out["ghost_compound"] = out.get("ghost_tyre")
    if not out.get("driver_code"):
        out["driver_code"] = code
    return out


def _ghost_at_lap(
    year: int | None,
    round_number: int | None,
    session_key: int,
    lap: int | None,
    driver: str | None = None,
) -> tuple[dict | None, GhostReason | None]:
    """Return (ghost_to_dict() output, reason).

    `reason` is populated whenever the ghost is None so the frontend can
    explain the empty state instead of showing a silent "no active ghost"
    (fix-pass item 5/9): "no_driver_selected", "session_not_ingested", or
    "no_divergence" (DB data exists, this driver just never diverged from
    ARIS's recommendation, or a ghost precompute hasn't landed yet).
    """
    if not driver:
        return None, "no_driver_selected"
    lap_n = int(lap) if lap else 1

    def _lookup(mapping: dict | None) -> dict | None:
        if not isinstance(mapping, dict):
            return None
        if lap_n in mapping and mapping[lap_n] is not None:
            return mapping[lap_n]
        if lap in mapping and mapping[lap] is not None:
            return mapping[lap]
        prev = [
            int(k)
            for k, v in mapping.items()
            if v is not None and str(k).isdigit() and int(k) <= lap_n
        ]
        if prev:
            return mapping.get(max(prev)) or mapping.get(str(max(prev)))
        return None

    dkey = _ghost_driver_key(year, round_number, driver)
    legacy_key = f"{year}_{round_number}_{session_key}"
    if dkey in _GHOST_CACHE:
        checked_key = dkey
        ghost = _lookup(_GHOST_CACHE.get(dkey))
    else:
        checked_key = legacy_key if legacy_key in _GHOST_CACHE else None
        ghost = _lookup(_GHOST_CACHE.get(legacy_key))
    if ghost is not None:
        return ghost, None
    if checked_key is None:
        # Not computed yet — precompute is scheduled/in-flight (or this session
        # type doesn't support ghost). Benign "nothing to show yet".
        return None, "no_divergence"
    status = _GHOST_STATUS.get(checked_key, "ok")
    if status == "session_not_ingested":
        return None, "session_not_ingested"
    return None, "no_divergence"


def _schedule_ghost_precompute(
    pack: dict, session_key: int, driver: str | None = None, plan: dict | None = None
) -> None:
    session_type_str = str(pack.get("session_type") or "")
    if session_type_str not in ("R", "S"):
        return
    year = pack.get("year")
    round_num = pack.get("round_number")
    focus = str(driver).upper() if driver else ""
    cache_key = (
        _ghost_driver_key(year, round_num, focus)
        if focus
        else f"{year}_{round_num}_{session_key}"
    )
    if plan and focus:
        _GHOST_PLAN[cache_key] = plan
    if cache_key in _GHOST_CACHE or cache_key in _GHOST_INFLIGHT:
        return
    _GHOST_INFLIGHT.add(cache_key)

    async def _run() -> None:
        try:
            await asyncio.to_thread(_precompute_ghost_sync, pack, session_key, driver, plan)
        finally:
            _GHOST_INFLIGHT.discard(cache_key)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        _precompute_ghost_sync(pack, session_key, driver, plan)
        _GHOST_INFLIGHT.discard(cache_key)


def _precompute_ghost_sync(
    pack: dict,
    session_key: int,
    driver_code: str | None = None,
    plan: dict | None = None,
) -> None:
    """Sync helper (runs in thread pool) — build ghost cache from ARIS DB.

    Fetches laps for the requested driver (or the first pack driver),
    infers ``real_action`` from the ``pit_in`` column, then scores the ghost
    against the selected plan when supplied, otherwise ``recommend()`` at lap 1.

    Fails silently when the ARIS DB has no data for this session (common for
    live sessions that haven't been ingested yet).
    """
    import logging
    _log = logging.getLogger(__name__)
    try:
        session_type = str(pack.get("session_type") or "")
        if session_type not in ("R", "S"):
            return
        year = pack.get("year")
        round_num = pack.get("round_number")
        if not year or not round_num:
            return

        codes: dict = pack.get("codes") or {}
        driver_codes = [str(c) for c in codes.values() if c]
        focus = str(driver_code).upper() if driver_code else (
            driver_codes[0] if driver_codes else ""
        )
        if not focus:
            return
        per_driver_key = _ghost_driver_key(year, round_num, focus)
        if plan:
            _GHOST_PLAN[per_driver_key] = plan
        else:
            plan = _GHOST_PLAN.get(per_driver_key)
        if per_driver_key in _GHOST_CACHE and not plan:
            return

        from aris.io import db as aris_db
        from sqlalchemy import text as _sql

        db_eng = aris_db.engine()
        with db_eng.connect() as conn:
            sess_row = conn.execute(
                _sql(
                    "SELECT session_id FROM sessions "
                    "WHERE year=:y AND round_no=:r AND session_type='R' LIMIT 1"
                ),
                {"y": int(year), "r": int(round_num)},
            ).fetchone()
        if not sess_row:
            if _try_explain_ghost(year, round_num, session_key, focus):
                return
            _GHOST_CACHE[per_driver_key] = {}
            _GHOST_STATUS[per_driver_key] = "session_not_ingested"
            return
        db_session_id = int(sess_row[0])
        driver_code = focus
        with db_eng.connect() as conn:
            drv_row = conn.execute(
                _sql(
                    "SELECT driver_id FROM drivers WHERE code=:c "
                    "AND driver_id IN (SELECT DISTINCT driver_id FROM laps WHERE session_id=:s)"
                ),
                {"c": driver_code, "s": db_session_id},
            ).fetchone()
        if not drv_row:
            if _try_explain_ghost(year, round_num, session_key, focus):
                return
            _GHOST_CACHE[per_driver_key] = {}
            _GHOST_STATUS[per_driver_key] = "session_not_ingested"
            return
        driver_id = int(drv_row[0])

        laps_df = aris_db.fetch_laps(db_session_id, driver_id)
        if laps_df.empty:
            if _try_explain_ghost(year, round_num, session_key, focus):
                return
            _GHOST_CACHE[per_driver_key] = {}
            _GHOST_STATUS[per_driver_key] = "session_not_ingested"
            return

        total_laps_val = int(laps_df["lap_number"].max())

        # Build laps_data with real_action inferred from pit_in flag.
        laps_data: list[dict] = []
        for _, row in laps_df.iterrows():
            lap_num = int(row["lap_number"])
            pit_in_flag = bool(row.get("pit_in") or False)
            compound = str(row.get("compound") or "HARD")
            if pit_in_flag:
                next_laps = laps_df[laps_df["lap_number"] > lap_num]
                next_compound = (
                    str(next_laps.iloc[0]["compound"] or "HARD")
                    if not next_laps.empty
                    else "HARD"
                )
                real_action = f"PIT_NOW_{next_compound.upper()}"
            else:
                real_action = "STAY_OUT"
            laps_data.append(
                {
                    "lap_number": lap_num,
                    "real_action": real_action,
                    "compound": compound,
                    "tyre_life": int(row.get("tyre_life") or 1),
                    "fuel_kg": _row_float(row, "fuel_kg", 30.0),
                    "position": int(_row_float(row, "position", 10)),
                    "lap_time_s": _row_float(row, "lap_time_s", None),
                    "track_status": str(row.get("track_status") or "1"),
                }
            )

        # Lights-out plan: selected strategy if supplied, else recommend() at lap 1.
        aris_recs: list[dict] = []
        explicit = plan if isinstance(plan, dict) and plan.get("pit_laps") is not None else None
        if explicit is not None:
            pits = [int(x) for x in (explicit.get("pit_laps") or [])]
            compounds = [
                str(c)
                for c in (explicit.get("compounds") or explicit.get("pit_compounds") or [])
            ]
            aris_recs.append(
                {
                    "lap": 1,
                    "label": str(explicit.get("label") or explicit.get("name") or ""),
                    "action": {
                        "kind": "stay_out" if not pits else "pit_lap",
                        "pit_laps": pits,
                        "pit_compounds": compounds,
                        "pit_lap": pits[0] if pits else None,
                        "pit_compound": compounds[0] if compounds else "HARD",
                    },
                }
            )
        else:
            from aris.recommend import recommend as aris_recommend
            from aris.state import build_race_state

            for check_lap in (1, 2):
                if check_lap > total_laps_val:
                    continue
                try:
                    state = build_race_state(db_session_id, driver_id, check_lap)
                    rec_result = aris_recommend(state, top_k=3, mc_draws=0)
                    from aris.ghost import pick_strategy_recommendation

                    top = pick_strategy_recommendation(rec_result)
                    if top and str(top.get("label") or "") != "STRATEGY_RESET":
                        aris_recs.append(
                            {
                                "lap": check_lap,
                                "label": top.get("label") or "",
                                "action": top.get("action") or {},
                            }
                        )
                        break
                except Exception:
                    continue

        country = str(pack.get("country") or pack.get("circuit") or "")
        if not country:
            try:
                from backend.calendar import get_round as _gr

                country = str(_gr(int(year), int(round_num)).country or "")
            except Exception:
                country = ""
        session_data = {
            "session_key": session_key,
            "session_type": session_type,
            "year": int(year),
            "round_no": int(round_num),
            "country": country,
            "laps": laps_data,
            "total_laps": total_laps_val,
            "driver_id": driver_id,
            "field_cum_by_lap": _field_cum_from_pack(pack),
            "plan": explicit,
        }

        ghost_map = precompute_ghost_for_session(
            session_data=session_data,
            driver_code=driver_code,
            aris_recommendations=aris_recs,
        )
        if not ghost_map and _try_explain_ghost(year, round_num, session_key, driver_code):
            return
        latest_plan = _GHOST_PLAN.get(per_driver_key)
        if latest_plan and not explicit:
            # Selected plan arrived while recommend() was running — don't clobber.
            return
        _store_ghost_map(year, round_num, session_key, driver_code, ghost_map)
        _log.info(
            "ghost precompute done: session_key=%s driver=%s laps=%s plan_recs=%s",
            session_key,
            driver_code,
            len(ghost_map),
            aris_recs,
        )
    except Exception:
        try:
            year = pack.get("year")
            round_num = pack.get("round_number")
            focus = str(driver_code).upper() if driver_code else ""
            if year and round_num and focus:
                if _try_explain_ghost(year, round_num, session_key, focus):
                    return
                fallback_key = _ghost_driver_key(year, round_num, focus)
                _GHOST_CACHE[fallback_key] = {}
                _GHOST_STATUS[fallback_key] = "session_not_ingested"
        except Exception:
            pass
        logging.getLogger(__name__).debug(
            "ghost precompute skipped (no DB data): session_key=%s", session_key, exc_info=True
        )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _session_type_map(name: str, stype: str) -> str:
    blob = f"{name} {stype}".lower()
    if "race" in blob and "sprint" not in blob:
        return "R"
    if "sprint quali" in blob or "sprint shootout" in blob:
        return "SQ"
    if "sprint" in blob:
        return "S"
    if "quali" in blob:
        return "Q"
    if "practice 1" in blob or "fp1" in blob:
        return "FP1"
    if "practice 2" in blob or "fp2" in blob:
        return "FP2"
    if "practice 3" in blob or "fp3" in blob:
        return "FP3"
    return (stype or name or "UNKNOWN")[:4].upper()


async def _openf1(path: str, params: dict[str, Any] | None = None, *, timeout: float | None = None) -> Any:
    try:
        data = await aopenf1(path, params, timeout=timeout)
        _STATE["error"] = None
        return data if data is not None else []
    except Exception as extra:
        msg = str(extra)
        if "404" in msg:
            return []
        _STATE["error"] = msg
        return []


async def get_live_timing_raw(session_key: int) -> list[dict]:
    data = await _openf1("intervals", {"session_key": session_key})
    return data if isinstance(data, list) else []


async def get_live_positions_raw(session_key: int) -> list[dict]:
    data = await _openf1("position", {"session_key": session_key})
    return data if isinstance(data, list) else []


def _chequered_at() -> datetime | None:
    rc = _STATE.get("race_control") or []
    if not isinstance(rc, list):
        return None
    last: datetime | None = None
    for row in rc:
        if not isinstance(row, dict):
            continue
        blob = f"{row.get('flag') or ''} {row.get('message') or ''} {row.get('category') or ''}".upper()
        if "CHEQUERED" not in blob and "CHECKERED" not in blob:
            continue
        dt = _parse_dt(row.get("date"))
        if dt is not None:
            last = dt
    return last


def _remember_ended(sess: dict[str, Any] | None) -> None:
    if not isinstance(sess, dict) or sess.get("session_key") is None:
        return
    prev = _STATE.get("ended_session")
    if isinstance(prev, dict) and prev.get("session_key") == sess.get("session_key"):
        return
    _STATE["ended_session"] = sess
    _STATE["session"] = None


def _session_window_live(sess: dict[str, Any], as_of: datetime) -> bool:
    start = _parse_dt(sess.get("date_start"))
    end = _parse_dt(sess.get("date_end"))
    if start is None:
        return False
    if end is None:
        end = start + timedelta(hours=2)
    flag = _chequered_at()
    if flag is not None and as_of >= flag + timedelta(minutes=2):
        return False
    name = str(sess.get("session_name") or sess.get("session_type") or "").lower()
    lead_min = 75 if name in {"race", "r"} else 20
    grace_min = 3
    if "practice" in name or name in {"fp1", "fp2", "fp3"}:
        # Official FP is 60 min; keep the feed through the 90-min calendar LIVE window.
        grace_min = 20
        end = max(end, start + timedelta(minutes=90))
    return start - timedelta(minutes=lead_min) <= as_of <= end + timedelta(minutes=grace_min)


async def peek_live_session(as_of: datetime | None = None) -> dict[str, Any] | None:
    as_of = now_utc(as_of)
    cached = _STATE.get("session")
    if isinstance(cached, dict):
        if _session_window_live(cached, as_of):
            return cached
        _remember_ended(cached)
    try:
        data = await _openf1("sessions", {"session_key": "latest"})
    except Exception:
        data = []
    latest = None
    if isinstance(data, list) and data:
        latest = data[0] if isinstance(data[0], dict) else None
    elif isinstance(data, dict):
        latest = data
    if latest and _session_window_live(latest, as_of):
        _STATE["session"] = latest
        return latest
    if latest:
        _remember_ended(latest)
    year = as_of.year
    cache_key = f"openf1:sessions:{year}"
    sessions = cache.get(cache_key, 180)
    if sessions is None:
        try:
            raw = await _openf1("sessions", {"year": year})
            sessions = raw if isinstance(raw, list) else []
            cache.set(cache_key, sessions)
        except Exception:
            sessions = []
    hits: list[tuple[float, dict[str, Any]]] = []
    for sess in sessions:
        if not isinstance(sess, dict):
            continue
        if _session_window_live(sess, as_of):
            start = _parse_dt(sess.get("date_start"))
            end = _parse_dt(sess.get("date_end")) or (start + timedelta(hours=2) if start else as_of)
            hits.append(((end - start).total_seconds(), sess))
    hits.sort(key=lambda x: x[0])
    if hits:
        _STATE["session"] = hits[0][1]
        return hits[0][1]
    if latest and _session_window_live(latest, as_of):
        return latest
    cal = await _session_from_weekend_calendar(as_of)
    if cal is not None:
        _STATE["session"] = cal
        return cal
    return None


async def _session_from_weekend_calendar(as_of: datetime) -> dict[str, Any] | None:
    """Attach the live (or imminent) weekend session even when OpenF1 `latest` is stale."""
    try:
        from backend.calendar import get_round_sessions, next_race

        nxt = next_race(as_of=as_of)
    except Exception:
        return None
    mapped: str | None = None
    try:
        weekend = get_round_sessions(int(nxt.year), int(nxt.round_number), as_of=as_of)
        live_match = next((s for s in weekend.sessions if s.status == "LIVE"), None)
        if live_match is not None:
            mapped = str(live_match.session_type)
        elif any(s.status == "COMPLETED" for s in weekend.sessions) and not any(
            s.status in {"LIVE", "UPCOMING"} for s in weekend.sessions
        ):
            return None
    except Exception:
        weekend = None
    if not mapped:
        start = nxt.next_session_datetime
        if start is None:
            return None
        mapped_guess = _session_type_map(str(nxt.next_session_name or ""), "")
        is_race = (mapped_guess or "").upper() == "R" or "race" in str(nxt.next_session_name or "").lower()
        lead_min = 75 if is_race else 20
        after_h = {
            "R": 2.5,
            "Q": 1.75,
            "SQ": 1.0,
            "S": 1.25,
            "FP1": 1.6,
            "FP2": 1.6,
            "FP3": 1.6,
        }.get((mapped_guess or "").upper(), 1.6)
        if as_of < start - timedelta(minutes=lead_min) or as_of > start + timedelta(hours=after_h):
            return None
        mapped = mapped_guess
        if not mapped:
            raw = str(nxt.next_session_name or "").upper()
            if "SPRINT QUALI" in raw or "SHOOTOUT" in raw:
                mapped = "SQ"
            elif "SPRINT" in raw:
                mapped = "S"
            elif "QUALI" in raw:
                mapped = "Q"
            elif raw.startswith("FP") or "PRACTICE" in raw:
                mapped = "FP1"
            else:
                mapped = "R"
        if weekend is not None:
            match = next((s for s in weekend.sessions if s.session_type == mapped), None)
            if match is not None and match.status == "COMPLETED":
                return None
    try:
        return await resolve_openf1_session(int(nxt.year), int(nxt.round_number), mapped)
    except Exception:
        return None


_OPENF1_SESSION_NAMES = {
    "FP1": ("Practice 1",),
    "FP2": ("Practice 2",),
    "FP3": ("Practice 3",),
    "SQ": ("Sprint Qualifying", "Sprint Shootout"),
    "S": ("Sprint",),
    "Q": ("Qualifying",),
    "R": ("Race",),
}

_SYNTHETIC_SESSION_KIND = {"FP1": 1, "FP2": 2, "FP3": 3, "Q": 4, "S": 5, "SQ": 6, "R": 7}


_SYNTHETIC_KIND_BY_ID = {v: k for k, v in _SYNTHETIC_SESSION_KIND.items()}
_SESSION_DISPLAY = {
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
    "SQ": "Sprint Qualifying",
    "S": "Sprint",
    "Q": "Qualifying",
    "R": "Race",
}
_SESSION_HOURS = {"FP1": 1.5, "FP2": 1.5, "FP3": 1.5, "SQ": 0.8, "S": 1.0, "Q": 1.5, "R": 2.25}


def synthetic_session_key(year: int, round_number: int, session_type: str) -> int:
    """Stable FastF1 replay key (OpenF1 keys are live-only)."""
    kind = _SYNTHETIC_SESSION_KIND.get(str(session_type or "R").upper(), 0)
    return 800_000_000 + int(year) * 1000 + int(round_number) * 10 + kind


def is_synthetic_session_key(session_key: int) -> bool:
    return int(session_key) >= 800_000_000


def decode_synthetic_session_key(session_key: int) -> tuple[int, int, str] | None:
    key = int(session_key)
    if key < 800_000_000:
        return None
    rem = key - 800_000_000
    year = rem // 1000
    rest = rem % 1000
    round_number = rest // 10
    kind = rest % 10
    stype = _SYNTHETIC_KIND_BY_ID.get(kind)
    if not stype or year < 2018 or year > 2100 or round_number < 1:
        return None
    return year, round_number, stype


def calendar_session_window(
    year: int, round_number: int, session_type: str | None = None
) -> tuple[datetime | None, datetime | None]:
    from backend.calendar import get_round, get_round_sessions

    st = str(session_type or "").upper() or None
    if st:
        try:
            weekend = get_round_sessions(year, round_number)
            match = next((s for s in weekend.sessions if s.session_type == st), None)
            if match is not None and match.datetime_utc is not None:
                hours = _SESSION_HOURS.get(st, 1.5)
                return match.datetime_utc, match.datetime_utc + timedelta(hours=hours)
        except Exception:
            pass
    rnd = get_round(year, round_number)
    start = rnd.date_fp1 or rnd.date_race
    end = rnd.date_race
    if end is not None:
        end = end + timedelta(hours=2, minutes=15)
    return start, end


def _norm_match_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return text.encode("ascii", "ignore").decode("ascii").lower().strip()


def _circuit_match(sess: dict[str, Any], rnd: Any) -> bool:
    blob = _norm_match_text(
        f"{sess.get('circuit_short_name') or ''} {sess.get('location') or ''} "
        f"{sess.get('country_name') or ''} {sess.get('country_code') or ''}"
    )
    if not blob:
        return False
    country = _norm_match_text(getattr(rnd, "country", None))
    tokens: list[str] = []
    for raw in (
        getattr(rnd, "city", None),
        getattr(rnd, "circuit_name", None),
        getattr(rnd, "name", None),
        getattr(rnd, "circuit_key", None),
    ):
        token = _norm_match_text(raw)
        if not token or (country and token == country):
            continue
        tokens.append(token)
        word = token.replace("-", " ").split()[-1]
        if word and word != token:
            tokens.append(word)
    blob_words = set(blob.replace("-", " ").split())
    for token in tokens:
        if len(token) >= 4 and token in blob:
            return True
        if len(token) >= 3 and token in blob_words:
            return True
    return False


async def resolve_openf1_session(year: int, round_number: int, session_type: str) -> dict[str, Any] | None:
    from backend.calendar import get_round

    rnd = get_round(year, round_number)
    names = _OPENF1_SESSION_NAMES.get(session_type.upper(), (session_type,))
    cache_key = f"openf1:sessions:{year}"
    sessions = cache.get(cache_key, 120)
    if sessions is None:
        raw = await _openf1("sessions", {"year": year})
        sessions = raw if isinstance(raw, list) else []
        cache.set(cache_key, sessions)
    for sess in sessions:
        if not isinstance(sess, dict):
            continue
        if str(sess.get("session_name") or "") not in names:
            continue
        if _circuit_match(sess, rnd) and sess.get("session_key") is not None:
            return sess
    named = [
        sess
        for sess in sessions
        if isinstance(sess, dict)
        and str(sess.get("session_name") or "") in names
        and sess.get("session_key") is not None
    ]
    named.sort(key=lambda row: str(row.get("date_start") or ""))
    idx = int(round_number) - 1
    if 0 <= idx < len(named):
        _log.info(
            "OpenF1 session matched by round index year=%s round=%s type=%s session_key=%s",
            year,
            round_number,
            session_type,
            named[idx].get("session_key"),
        )
        return named[idx]
    return None


async def resolve_openf1_session_key(year: int, round_number: int, session_type: str) -> int | None:
    sess = await resolve_openf1_session(year, round_number, session_type)
    if sess is None or sess.get("session_key") is None:
        return None
    return int(sess["session_key"])


def _feed_session_key() -> int | None:
    sess = _STATE.get("session")
    if isinstance(sess, dict) and sess.get("session_key") is not None:
        try:
            return int(sess["session_key"])
        except (TypeError, ValueError):
            return None
    return None


async def peek_live_round(as_of: datetime | None = None) -> tuple[int, int] | None:
    """Best-effort (year, round) for a live OpenF1 session, else None."""
    sess = await peek_live_session(as_of)
    if not sess:
        return None
    year = int(sess.get("year") or now_utc(as_of).year)
    meeting_key = sess.get("meeting_key")
    mkey = f"openf1:meetings:{year}"
    meetings = cache.get(mkey, TTL_LIVE * 20)
    if meetings is None:
        try:
            meetings = await _openf1("meetings", {"year": year}) or []
            cache.set(mkey, meetings)
        except Exception:
            meetings = []
    name = ""
    for m in meetings if isinstance(meetings, list) else []:
        if m.get("meeting_key") == meeting_key:
            name = str(m.get("meeting_name") or m.get("circuit_short_name") or "")
            break
    circuit = str(sess.get("circuit_short_name") or sess.get("location") or "").lower()
    needle = (circuit or name.lower()).strip()
    if not needle:
        return None
    try:
        from backend.calendar import get_calendar

        cal = await run_sync(get_calendar, year)
        for rnd in cal.rounds:
            blob = " ".join(
                [
                    str(rnd.circuit_key or ""),
                    str(rnd.circuit_name or ""),
                    str(rnd.city or ""),
                    str(rnd.name or ""),
                    str(rnd.country or ""),
                ]
            ).lower()
            if circuit and (circuit in blob or any(p in blob for p in circuit.split() if len(p) > 3)):
                return year, int(rnd.round_number)
            if "zandvoort" in (circuit + " " + name.lower()) and (
                "nether" in blob or "zandvoort" in blob or "dutch" in blob
            ):
                return year, int(rnd.round_number)
            if name and name.lower() in blob:
                return year, int(rnd.round_number)
    except Exception:
        return None
    return None


async def _driver_rows(session_key: int) -> list[dict[str, Any]]:
    cached = _STATE.get("drivers")
    if isinstance(cached, dict) and cached.get("_session_key") == session_key:
        return list(cached.get("rows") or [])
    key = f"openf1:drivers:{session_key}"
    rows = cache.get(key, 3600)
    if rows is None:
        data = await _openf1("drivers", {"session_key": session_key})
        rows = data if isinstance(data, list) else []
        cache.set(key, rows)
    _STATE["drivers"] = {"_session_key": session_key, "rows": rows}
    return rows


async def _driver_code_map(session_key: int) -> dict[int, str]:
    out: dict[int, str] = {}
    colours: dict[int, str] = {}
    for row in await _driver_rows(session_key):
        num = row.get("driver_number")
        code = row.get("name_acronym") or row.get("broadcast_name")
        if num is None or not code:
            continue
        n = int(num)
        out[n] = str(code)[:3].upper()
        colour = row.get("team_colour")
        if colour:
            colours[n] = f"#{str(colour).lstrip('#')}"
    _STATE["driver_colours"] = colours
    return out


def _compound_letter(raw: str | None) -> str | None:
    if not raw:
        return None
    u = str(raw).upper()
    if u.startswith("SOFT"):
        return "S"
    if u.startswith("MED"):
        return "M"
    if u.startswith("HARD"):
        return "H"
    if u.startswith("INTER"):
        return "I"
    if u.startswith("WET") or u.startswith("FULL"):
        return "W"
    if u in {"S", "M", "H", "I", "W"}:
        return u
    return u[:1]


def _fastf1_window_live(as_of: datetime) -> LiveStatus | None:
    """If OpenF1 has no overlapping session, use FastF1 calendar session windows."""
    from backend.calendar import get_calendar, get_round_sessions

    for year in (as_of.year, as_of.year - 1):
        if year < 2024 or year > 2026:
            continue
        try:
            cal = get_calendar(year, as_of=as_of)
        except Exception:
            continue
        for rnd in cal.rounds:
            if rnd.status != "LIVE":
                continue
            try:
                weekend = get_round_sessions(year, rnd.round_number, as_of=as_of)
            except Exception:
                continue
            live_s = next((s for s in weekend.sessions if s.status == "LIVE"), None)
            if live_s is None:
                continue
            elapsed = None
            if live_s.datetime_utc is not None:
                elapsed = max(0, int((as_of - live_s.datetime_utc).total_seconds()))
            openf1_names = {
                "FP1": "Practice 1",
                "FP2": "Practice 2",
                "FP3": "Practice 3",
                "Q": "Qualifying",
                "SQ": "Sprint Qualifying",
                "S": "Sprint",
                "R": "Race",
            }
            stype = live_s.session_type
            pretty = openf1_names.get(stype, live_s.session_name or stype)
            return LiveStatus(
                is_live=True,
                year=year,
                round_number=rnd.round_number,
                session_type=stype,
                session_name=live_s.session_name or pretty,
                gp_name=rnd.name,
                session_elapsed_seconds=elapsed,
                last_success_utc=_STATE.get("last_success"),
                replay_mode=False,
                session={
                    "session_type": stype,
                    "session_name": live_s.session_name or stype,
                    "year": year,
                    "round_number": rnd.round_number,
                },
            )
    return None


def simulated_status(as_of: datetime) -> LiveStatus:
    """Pure local asOf simulation — calendar session windows only, no OpenF1."""
    as_of = now_utc(as_of)
    from backend.calendar import get_calendar

    years = [as_of.year]
    if as_of.year < 2024:
        years = [2024]
    if as_of.year > 2026:
        years = [2026]

    for year in years:
        if year < 2024 or year > 2026:
            continue
        try:
            # Use the pre-warmed calendar (no as_of) so this is date arithmetic only.
            cal = get_calendar(year)
        except Exception:
            continue
        for rnd in cal.rounds:
            for sess in rnd.sessions:
                start = sess.date_start
                end = sess.date_end
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                if start <= as_of <= end:
                    elapsed = max(0, int((as_of - start).total_seconds()))
                    return LiveStatus(
                        is_live=True,
                        year=year,
                        round_number=rnd.round_number,
                        session_type=sess.type,
                        session_name=sess.type,
                        gp_name=rnd.name,
                        circuit=rnd.circuit_name,
                        session_elapsed_seconds=elapsed,
                        last_success_utc=_STATE.get("last_success"),
                        replay_mode=False,
                        simulated=True,
                        as_of=as_of,
                        session={
                            "session_type": sess.type,
                            "session_name": sess.type,
                            "year": year,
                            "round_number": rnd.round_number,
                            "circuit": rnd.circuit_name,
                        },
                    )
    return LiveStatus(
        is_live=False,
        session=None,
        simulated=True,
        as_of=as_of,
        last_success_utc=_STATE.get("last_success"),
    )


async def live_status(
    as_of: datetime | None = None,
    *,
    replay_session_key: int | None = None,
    simulated: bool = False,
) -> LiveStatus:
    as_of = now_utc(as_of)
    if replay_session_key:
        mapped = "R"
        raw_name = "Replay"
        year = None
        rnd_no = None
        gp = None
        pack = _REPLAY_PACKS.get(replay_session_key)
        if not isinstance(pack, dict):
            pack = load_replay_pack_disk(replay_session_key)
        if isinstance(pack, dict):
            mapped = str(pack.get("session_type") or mapped)
            try:
                year = int(pack["year"]) if pack.get("year") is not None else year
            except (TypeError, ValueError):
                year = year
            try:
                rnd_no = int(pack["round_number"]) if pack.get("round_number") is not None else rnd_no
            except (TypeError, ValueError):
                rnd_no = rnd_no
        decoded = decode_synthetic_session_key(replay_session_key)
        if decoded is not None:
            year = year or decoded[0]
            rnd_no = rnd_no or decoded[1]
            if not isinstance(pack, dict):
                mapped = decoded[2]
        raw_name = _SESSION_DISPLAY.get(mapped, mapped)
        if year and rnd_no:
            try:
                from backend.calendar import get_round

                rnd = get_round(int(year), int(rnd_no))
                gp = str(rnd.circuit_name or rnd.name or "")
            except Exception:
                gp = None
        return LiveStatus(
            is_live=True,
            year=year,
            round_number=rnd_no,
            session_key=replay_session_key,
            session_type=mapped,
            session_name=raw_name,
            gp_name=gp,
            circuit=gp,
            replay_mode=True,
            view_only=mapped not in {"R", "S"},
            last_success_utc=_STATE.get("last_success"),
            source="fastf1",
            session={"session_key": replay_session_key, "session_type": mapped, "year": year, "round_number": rnd_no},
        )
    if simulated:
        return await run_sync(simulated_status, as_of)

    openf1_error: str | None = None
    sess = None
    try:
        sess = await asyncio.wait_for(peek_live_session(as_of), timeout=4.0)
    except Exception as extra:
        sess = None
        if not isinstance(extra, TimeoutError):
            openf1_error = str(extra)

    # FastF1 calendar scan is only a fallback. Running it on every live tick
    # added ~1 s even when OpenF1 already attached a session.
    local = None
    if not sess:
        try:
            local = await asyncio.wait_for(run_sync(_fastf1_window_live, as_of), timeout=2.5)
        except Exception:
            local = None

    if not sess:
        nxt = None
        weekend_open = False
        try:
            from backend.calendar import next_race

            nxt = next_race(as_of=as_of)
            weekend_open = any(
                getattr(s, "status", None) in {"UPCOMING", "LIVE"}
                for s in (nxt.sessions_this_weekend or [])
            ) or (
                nxt.next_session_datetime is not None and nxt.next_session_datetime > as_of
            )
        except Exception:
            nxt = None
        ended = _STATE.get("ended_session")
        if isinstance(ended, dict) and ended.get("session_key") is not None and not weekend_open:
            ended_place = str(ended.get("circuit_short_name") or ended.get("location") or "").lower()
            nxt_place = str(getattr(nxt, "name", "") or getattr(nxt, "circuit_name", "") or "").lower()
            same_weekend = bool(
                ended_place
                and nxt_place
                and (
                    ended_place in nxt_place
                    or nxt_place in ended_place
                    or ("zandvoort" in ended_place and "nether" in nxt_place)
                    or ("nether" in ended_place and "zandvoort" in nxt_place)
                )
            )
            if nxt is not None and not same_weekend:
                ended = None
        if isinstance(ended, dict) and ended.get("session_key") is not None and not weekend_open:
            raw_name = str(ended.get("session_name") or "")
            mapped_end = _session_type_map(raw_name, str(ended.get("session_type") or ""))
            return LiveStatus(
                is_live=False,
                year=int(ended["year"]) if ended.get("year") is not None else as_of.year,
                session_type=mapped_end,
                session_name=raw_name or mapped_end,
                session_key=int(ended["session_key"]),
                gp_name=str(ended.get("circuit_short_name") or ended.get("location") or ""),
                last_success_utc=_STATE.get("last_success"),
                session_ended=True,
                ended_session_name=raw_name or mapped_end,
                ended_session_type=mapped_end,
                replay_preparing=True,
                error=None,
            )
        if local is not None:
            return local
        if nxt is not None:
            mapped = _session_type_map(str(nxt.next_session_name or ""), "") or "R"
            return LiveStatus(
                is_live=False,
                year=nxt.year,
                round_number=nxt.round_number,
                session_type=mapped,
                session_name=nxt.next_session_name,
                gp_name=nxt.name,
                session_remaining_seconds=nxt.countdown_seconds,
                last_success_utc=_STATE.get("last_success"),
                session_ended=False,
                error=openf1_error,
            )
        return LiveStatus(
            is_live=False,
            session=None,
            last_success_utc=_STATE.get("last_success"),
            error=openf1_error,
        )
    year = int(sess.get("year") or as_of.year)
    try:
        rnd = await asyncio.wait_for(peek_live_round(as_of), timeout=2.0)
    except Exception:
        rnd = None
    raw_name = str(sess.get("session_name") or "")
    mapped = _session_type_map(raw_name, str(sess.get("session_type") or ""))
    start = _parse_dt(sess.get("date_start"))
    end = _parse_dt(sess.get("date_end"))
    elapsed = None
    remaining = None
    if start is not None:
        elapsed = max(0, int((as_of - start).total_seconds()))
    if end is not None:
        remaining = max(0, int((end - as_of).total_seconds()))
    flag: str = "GREEN"
    try:
        stored = _STATE.get("race_control")
        if isinstance(stored, list) and stored:
            flag = _flag_from_rc(stored)
        else:
            key = sess.get("session_key")
            rc_key = f"openf1:rc-flag:{key}"
            rc = cache.get(rc_key, TTL_LIVE)
            if isinstance(rc, list) and rc:
                flag = _flag_from_rc(rc)
    except Exception:
        pass
    view_only = mapped in {"SQ", "Q", "FP1", "FP2", "FP3"}
    round_number = (rnd[1] if rnd else None) or (local.round_number if local else None)
    if round_number is None:
        try:
            from backend.calendar import next_race

            nxt = next_race(as_of=as_of)
            place = str(sess.get("circuit_short_name") or sess.get("location") or "").lower()
            nxt_blob = " ".join(
                [
                    str(nxt.circuit_key or ""),
                    str(nxt.circuit_name or ""),
                    str(nxt.name or ""),
                    str(nxt.city or ""),
                    str(nxt.country or ""),
                ]
            ).lower()
            tokens = [p for p in place.split() if len(p) > 3]
            if place and (place in nxt_blob or any(p in nxt_blob for p in tokens)):
                round_number = nxt.round_number
                year = nxt.year or year
        except Exception:
            pass
    return LiveStatus(
        is_live=True,
        year=year,
        round_number=round_number,
        session_type=mapped,
        session_name=raw_name or mapped,
        session_key=int(sess["session_key"]) if sess.get("session_key") is not None else None,
        gp_name=str(sess.get("circuit_short_name") or sess.get("location") or ""),
        circuit=str(sess.get("circuit_short_name") or sess.get("location") or ""),
        session_elapsed_seconds=elapsed,
        session_remaining_seconds=remaining,
        session_flag=flag,  # type: ignore[arg-type]
        last_success_utc=_STATE.get("last_success"),
        replay_mode=False,
        session=sess,
        source="openf1",
        view_only=view_only,
        aris_ready=mapped in {"R", "S"},
        error=_STATE.get("error"),
        total_laps=_status_total_laps(year, round_number),
    )


def _status_total_laps(year: int | None, round_number: int | None) -> int | None:
    if not year or not round_number:
        return None
    try:
        from backend.calendar import get_round, scheduled_laps

        rnd = get_round(int(year), int(round_number))
        return scheduled_laps(int(year), int(round_number), rnd.country, rnd.circuit_key)
    except Exception:
        return None


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _drs_open(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None or value == "":
        return False
    try:
        return float(value) >= 8
    except (TypeError, ValueError):
        return False


def _sector_colour_from_segments(segments: Any, fallback: str = "grey") -> str:
    if not isinstance(segments, list) or not segments:
        return fallback
    codes = [int(v) for v in segments if v is not None]
    if 2051 in codes:
        return "purple"
    if 2049 in codes:
        return "green"
    if 2048 in codes:
        return "yellow"
    return fallback


def _sector_tone(ms: int | None, personal_best: int | None, session_best: int | None, segments: Any) -> str:
    from_seg = _sector_colour_from_segments(segments, "")
    if from_seg:
        return from_seg
    if ms is None:
        return "grey"
    if session_best is not None and ms <= session_best + 1:
        return "purple"
    if personal_best is not None and ms <= personal_best + 1:
        return "green"
    return "yellow"


def _unique_positions(raw: dict[int, int]) -> dict[int, int]:
    ranked = sorted(raw.items(), key=lambda kv: (kv[1], kv[0]))
    out: dict[int, int] = {}
    used: set[int] = set()
    next_p = 1
    for num, pos in ranked:
        p = int(pos) if pos and pos > 0 else next_p
        while p in used:
            p += 1
        used.add(p)
        out[num] = p
        next_p = max(next_p, p + 1)
    return out


def _ms(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value) * 1000))
    except (TypeError, ValueError):
        return None


_REPLAY_PACKS: dict[int, dict[str, Any]] = {}
_REPLAY_LOCKS: dict[int, asyncio.Lock] = {}
# fix-pass item 3: non-blocking pack-status peeks report these without waiting
# on FastF1. `_ensure_replay_pack` still does the real work in the background.
_PACK_LOAD_ERROR: dict[int, str] = {}
_PACK_LOAD_STARTED: dict[int, float] = {}
_REPLAY_LOCK = asyncio.Lock()
_FF1_UPGRADE_INFLIGHT: set[int] = set()
_FF1_UPGRADE_LAST: dict[int, float] = {}
_PACK_JOBS: dict[int, asyncio.Task] = {}
_REPLAY_PACK_DISK_PREFIX = "replay_pack_v1:"
_LOC_BUCKETS: dict[tuple[int, int], list[Any]] = {}
_CAR_BUCKETS: dict[tuple[int, int], list[Any]] = {}
_LOC_BUCKET_S = 30
_LOC_BUCKET_KEEP = 80


def replay_pack_disk_key(
    session_key: int,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
) -> str:
    """Diskcache key for a replay pack. Prefer year/round/type; fall back to session_key."""
    from backend.sessions import _pack_cache_key

    y, r, t = year, round_number, session_type
    decoded = decode_synthetic_session_key(session_key)
    if decoded is not None:
        y = y or decoded[0]
        r = r or decoded[1]
        t = t or decoded[2]
    if y and r:
        return _pack_cache_key(int(y), int(r), t or "R")
    return f"{_REPLAY_PACK_DISK_PREFIX}{int(session_key)}"


def _legacy_pack_disk_key(session_key: int) -> str:
    return f"{_REPLAY_PACK_DISK_PREFIX}{int(session_key)}"


def replay_pack_is_complete(pack: dict[str, Any], as_of: datetime | None = None) -> bool:
    """True once the session window has closed — official results will not change."""
    end = pack.get("date_end")
    if not isinstance(end, datetime):
        end = _parse_dt(end)
    if end is None:
        return False
    return now_utc(as_of) > end + timedelta(minutes=5)


def pack_matches_request(
    pack: dict[str, Any], year: int | None, round_number: int | None
) -> bool:
    """Reject a cached pack that belongs to a different race."""
    if year is not None and pack.get("year") is not None and int(pack["year"]) != int(year):
        return False
    if (
        round_number is not None
        and pack.get("round_number") is not None
        and int(pack["round_number"]) != int(round_number)
    ):
        return False
    return True


def invalidate_replay_pack(session_key: int) -> None:
    """Drop memory + disk replay pack so the next load hits FastF1 only."""
    pack = _REPLAY_PACKS.pop(int(session_key), None)
    _FF1_UPGRADE_INFLIGHT.discard(int(session_key))
    _FF1_UPGRADE_LAST.pop(int(session_key), None)
    _PACK_JOBS.pop(int(session_key), None)
    _PACK_LOAD_ERROR.pop(int(session_key), None)
    _PACK_LOAD_STARTED.pop(int(session_key), None)
    keys = {_legacy_pack_disk_key(session_key), replay_pack_disk_key(session_key)}
    if isinstance(pack, dict):
        keys.add(
            replay_pack_disk_key(
                session_key,
                pack.get("year"),
                pack.get("round_number"),
                pack.get("session_type"),
            )
        )
    try:
        from backend.cache import get_disk

        store = get_disk()
        for key in keys:
            store.pop(key, default=None)
    except Exception:
        pass
    _log.info("replay pack invalidated session_key=%s keys=%s", session_key, sorted(keys))
    if isinstance(pack, dict):
        from backend.sessions import drop_pos_chunk_keys

        drop_pos_chunk_keys(
            pack.get("year"),
            pack.get("round_number"),
            pack.get("session_type"),
            pack.get("pos_chunks") or (pack.get("ff1") or {}).get("pos_chunks"),
        )


def load_replay_pack_disk(
    session_key: int,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
) -> dict[str, Any] | None:
    try:
        from backend.cache import get_disk

        store = get_disk()
    except Exception:
        return None
    primary = replay_pack_disk_key(session_key, year, round_number, session_type)
    keys = [primary]
    legacy = _legacy_pack_disk_key(session_key)
    if legacy not in keys:
        keys.append(legacy)
    for key in keys:
        try:
            stored = store.get(key)
        except Exception:
            stored = None
        if isinstance(stored, dict) and isinstance(stored.get("laps"), list):
            if key != primary:
                try:
                    store.set(primary, stored, expire=TTL_REPLAY)
                    _log.info("replay pack disk migrated %s -> %s", key, primary)
                except Exception:
                    pass
            return stored
    return None


def _pack_disk_writable(pack: dict[str, Any]) -> bool:
    """Completed-session packs with laps are stable enough to persist."""
    stage = replay_pack_stage(pack)
    if stage not in {"minimal", "full"}:
        return False
    if not pack.get("laps"):
        return False
    if str(pack.get("session_status") or "").upper() == "COMPLETED":
        return True
    return replay_pack_is_complete(pack)


def save_replay_pack_disk(session_key: int, pack: dict[str, Any]) -> bool:
    if not _pack_disk_writable(pack):
        return False
    key = replay_pack_disk_key(
        session_key, pack.get("year"), pack.get("round_number"), pack.get("session_type")
    )
    try:
        from backend.cache import get_disk

        # Completed full packs never change — keep them across the 30-day TTL
        # so prebuilt 2024–2026 races stay instant after a restart.
        expire = None if replay_pack_stage(pack) == "full" else TTL_REPLAY
        get_disk().set(key, pack, expire=expire)
        _log.info("replay pack disk SAVE key=%s stage=%s expire=%s", key, replay_pack_stage(pack), expire)
        return True
    except Exception:
        _log.exception("replay pack disk SAVE failed key=%s", key)
        return False


def hydrate_replay_pack_cache(
    session_key: int,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
    *,
    log_hits: bool = True,
) -> tuple[dict[str, Any] | None, bool, bool]:
    """Reuse memory, else disk. Never calls FastF1 or OpenF1.

    Returns ``(pack, memory_hit, disk_hit)``. A metadata stub in memory is not a
    hit — we still read disk so a second visit does not rebuild from FastF1.
    """
    key = replay_pack_disk_key(session_key, year, round_number, session_type)
    cached = _REPLAY_PACKS.get(session_key)
    if cached is not None and not pack_matches_request(cached, year, round_number):
        _log.warning(
            "replay pack MISMATCH session_key=%s cached=%s/%s requested=%s/%s — rebuilding",
            session_key,
            cached.get("year"),
            cached.get("round_number"),
            year,
            round_number,
        )
        _REPLAY_PACKS.pop(session_key, None)
        cached = None
    memory_hit = cached is not None and _stage_rank(cached) >= _PACK_STAGE_RANK["minimal"]
    if memory_hit:
        if log_hits:
            _log.info("key=%s memory_hit=True disk_hit=False", key)
        else:
            _log.debug("key=%s memory_hit=True disk_hit=False", key)
        return cached, True, False
    disk = load_replay_pack_disk(session_key, year, round_number, session_type)
    if disk is not None and not pack_matches_request(disk, year, round_number):
        _log.warning("replay pack DISK MISMATCH session_key=%s key=%s — ignoring disk cache", session_key, key)
        disk = None
    disk_hit = disk is not None and _stage_rank(disk) >= _PACK_STAGE_RANK["minimal"]
    if disk_hit and disk is not None:
        if "stage" not in disk:
            disk["stage"] = "full" if _ff1_pack_ready(disk) else "minimal"
        _REPLAY_PACKS[session_key] = disk
        ensure_replay_pos_chunk(disk, 1)
        _log.info(
            "key=%s memory_hit=False disk_hit=True stage=%s",
            key,
            replay_pack_stage(disk),
        )
        print(f"[ARIS] key={key} memory_hit=False disk_hit=True", flush=True)
        return disk, False, True
    if log_hits:
        _log.info("key=%s memory_hit=%s disk_hit=False", key, cached is not None)
        print(f"[ARIS] key={key} memory_hit={cached is not None} disk_hit=False", flush=True)
    else:
        _log.debug("key=%s memory_hit=%s disk_hit=False", key, cached is not None)
    return cached, False, False


_PACK_STAGE_RANK = {"empty": 0, "metadata": 1, "minimal": 2, "full": 3}


def replay_pack_stage(pack: dict[str, Any] | None) -> str:
    if not pack:
        return "empty"
    explicit = pack.get("stage")
    if explicit in {"metadata", "minimal", "full"}:
        if explicit == "full" and not _ff1_pack_ready(pack):
            return "minimal" if pack.get("laps") else "metadata"
        return str(explicit)
    if _ff1_pack_ready(pack):
        return "full"
    if pack.get("laps"):
        return "minimal"
    return "metadata"


def _stage_rank(pack: dict[str, Any] | None) -> int:
    return _PACK_STAGE_RANK.get(replay_pack_stage(pack), 0)


def _pack_flags(pack: dict[str, Any] | None) -> dict[str, bool]:
    pack = pack or {}
    ff1 = pack.get("ff1") if isinstance(pack.get("ff1"), dict) else {}
    return {
        "laps_ready": bool(pack.get("laps")),
        "map_ready": bool(pack.get("path_x")),
        "gps_ready": _ff1_pack_ready(pack),
        "weather_ready": bool(pack.get("weather")),
        "race_control_ready": bool(pack.get("race_control")),
        "synthetic_gps": bool(ff1.get("synthetic_gps")),
    }


def _pack_progress(pack: dict[str, Any] | None) -> float:
    flags = _pack_flags(pack)
    stage = replay_pack_stage(pack)
    if stage == "full" or flags["gps_ready"]:
        return 1.0
    if stage == "minimal":
        return 0.55
    if stage == "metadata":
        return 0.15
    return 0.0


def _set_pack_stage(pack: dict[str, Any], stage: str) -> None:
    pack["stage"] = stage
    _log.info("Replay pack stage = %s", stage)
    print(f"[ARIS] Replay pack stage = {stage}", flush=True)


def _apply_ff1_to_pack(pack: dict[str, Any], ff1: dict[str, Any], *, synthetic_gps: bool = False) -> None:
    if ff1.get("laps"):
        pack["laps"] = ff1["laps"]
    if ff1.get("weather"):
        pack["weather"] = ff1["weather"]
    if ff1.get("stints"):
        pack["stints"] = ff1["stints"]
    if ff1.get("positions"):
        pack["positions"] = ff1["positions"]
    if ff1.get("race_control"):
        pack["race_control"] = ff1["race_control"]
    if ff1.get("date_start"):
        pack["date_start"] = ff1["date_start"]
    if ff1.get("date_end"):
        pack["date_end"] = ff1["date_end"]
    if ff1.get("code_by_num"):
        pack["codes"] = ff1["code_by_num"]
    if ff1.get("colours"):
        pack["colours"] = ff1["colours"]
    windows = ff1.get("quali_windows") or pack.get("ff1", {}).get("quali_windows") or []
    ff1["quali_windows"] = windows
    if synthetic_gps:
        ff1["synthetic_gps"] = True
    elif ff1.get("pos_samples"):
        ff1["synthetic_gps"] = False
    if ff1.get("pos_chunks"):
        pack["pos_chunks"] = list(ff1["pos_chunks"])
    if ff1.get("pos_chunk_loaded"):
        pack["pos_chunk_loaded"] = ff1["pos_chunk_loaded"]
    pack["ff1"] = ff1
    pack["source"] = "fastf1"
    pack["green_flag_s"] = _green_flag_s(pack.get("race_control") or [], pack.get("date_start"))
    if ff1.get("car_samples"):
        pack["car_samples"] = ff1["car_samples"]
    if ff1.get("pos_samples"):
        from backend.sessions import pit_lane_from_samples

        gps = pit_lane_from_samples(
            ff1.get("pos_samples") or {},
            pack.get("path_x") or [],
            pack.get("path_y") or [],
        )
        if gps:
            pack["pit_lane_x"], pack["pit_lane_y"], pack["pit_stalls"] = gps
        pack.pop("path_traces", None)
        pack.pop("path_traces_v", None)
        if pack.get("path_x"):
            ensure_path_traces(pack)


def _current_race_lap(
    laps: list[Any],
    clock: datetime,
    session_start: datetime | None,
    race_start_s: int | None,
) -> int:
    """Leader lap at `clock`. Never returns a mid-race lap at lights-out."""
    origin = session_start
    elapsed = 0.0
    if origin is not None:
        elapsed = (clock - origin).total_seconds() - float(race_start_s or 0)
    if elapsed < 40:
        return 1
    dated: list[tuple[float, int]] = []
    for row in laps:
        if not isinstance(row, dict):
            continue
        ds = _parse_dt(row.get("date_start")) or _parse_dt(row.get("date"))
        n = int(row.get("lap_number") or 0)
        if ds is None or n <= 0 or ds > clock:
            continue
        dated.append((ds.timestamp(), n))
    if not dated:
        return max(1, int(elapsed / 90.0) + 1)
    unique_starts = {t for t, _ in dated}
    # Identical timestamps on every lap would leak the whole race into t=0.
    if len(unique_starts) <= 2 and len(dated) > 8:
        return max(1, int(elapsed / 90.0) + 1)
    return max(n for _, n in dated)


def _laps_upto(laps: list[Any], as_of: datetime | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in laps:
        if not isinstance(row, dict):
            continue
        if as_of is None:
            out.append(row)
            continue
        start = _parse_dt(row.get("date_start")) or _parse_dt(row.get("date"))
        # Missing timestamps must not leak the whole race into t=0 (lap 23/24 etc).
        if start is None:
            continue
        if start <= as_of:
            out.append(row)
    return out


def _lap_completed(row: dict[str, Any], as_of: datetime | None) -> bool:
    dur = row.get("lap_duration")
    if not dur:
        return False
    if as_of is None:
        return True
    start = _parse_dt(row.get("date_start"))
    if start is None:
        return True
    try:
        end = start + timedelta(seconds=float(dur))
    except (TypeError, ValueError):
        return start <= as_of
    return end <= as_of


def _expected_lap_s(rows: list[dict[str, Any]]) -> float:
    times: list[float] = []
    for row in rows:
        try:
            t = float(row.get("lap_duration") or 0)
        except (TypeError, ValueError):
            continue
        if 30.0 < t < 180.0:
            times.append(t)
    if not times:
        return 90.0
    times.sort()
    return times[len(times) // 2]


def _openf1_driver_laps(
    laps: list[Any],
    driver_number: int,
    clock: datetime,
) -> list[tuple[datetime, dict[str, Any]]]:
    mine: list[tuple[datetime, dict[str, Any]]] = []
    for row in laps:
        if not isinstance(row, dict):
            continue
        try:
            num = int(row.get("driver_number") or -1)
        except (TypeError, ValueError):
            continue
        if num != int(driver_number):
            continue
        start = _parse_dt(row.get("date_start")) or _parse_dt(row.get("date"))
        if start is None or start > clock:
            continue
        mine.append((start, row))
    mine.sort(key=lambda item: item[0])
    return mine


def _openf1_timing_frac(
    laps: list[Any],
    driver_number: int | None,
    clock: datetime,
) -> float | None:
    """Timing-derived path_frac for a live/quali car, or None if not computable."""
    if driver_number is None:
        return None
    from backend.sessions import compute_timing_path_frac

    mine = _openf1_driver_laps(laps, int(driver_number), clock)
    if not mine:
        return None
    start, row = mine[-1]
    lap_n = int(row.get("lap_number") or 1) or 1
    time_since = (clock - start).total_seconds()
    completed = [r for _, r in mine[:-1]]
    if _lap_completed(row, clock):
        completed.append(row)
        try:
            dur = float(row.get("lap_duration") or 0)
        except (TypeError, ValueError):
            dur = 0.0
        if dur > 0:
            time_since = max(0.0, time_since - dur)
            lap_n += 1
    expected = _expected_lap_s(completed if completed else [r for _, r in mine])
    return compute_timing_path_frac(
        lap_number=lap_n,
        time_since_lap_start_s=time_since,
        expected_lap_time_s=expected,
    )


def _race_lap_frac_live(laps: list[Any], clock: datetime) -> float:
    latest_by_num: dict[int, tuple[int, datetime]] = {}
    for row in laps:
        if not isinstance(row, dict):
            continue
        num = row.get("driver_number")
        if num is None:
            continue
        try:
            lap_n = int(row.get("lap_number") or 0)
        except (TypeError, ValueError):
            continue
        start = _parse_dt(row.get("date_start")) or _parse_dt(row.get("date"))
        if start is None or start > clock or lap_n < 1:
            continue
        n = int(num)
        prev = latest_by_num.get(n)
        if prev is None or lap_n > prev[0] or (lap_n == prev[0] and start > prev[1]):
            latest_by_num[n] = (lap_n, start)
    if not latest_by_num:
        return 0.0
    leader_lap = max(v[0] for v in latest_by_num.values())
    time_since = 0.0
    for lap_n, start in latest_by_num.values():
        if lap_n != leader_lap:
            continue
        dt = (clock - start).total_seconds()
        if dt > time_since:
            time_since = dt
    return (leader_lap - 1) + min(1.0, max(0.0, time_since) / 90.0)


def _best_ms_from_laps(laps: list[dict[str, Any]], as_of: datetime | None) -> dict[int, int]:
    best: dict[int, int] = {}
    for row in laps:
        num = row.get("driver_number")
        dur = row.get("lap_duration")
        if num is None or not dur or not _lap_completed(row, as_of):
            continue
        n = int(num)
        ms = int(float(dur) * 1000)
        if n not in best or ms < best[n]:
            best[n] = ms
    return best


def _weather_at(rows: list[Any], as_of: datetime | None) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get("date"))
        if as_of is not None and dt is not None and dt > as_of:
            continue
        last = row
    return last


def _latest_by_date(
    rows: list[Any], as_of: datetime | None, *, key: str = "date"
) -> dict[int, dict[str, Any]]:
    latest: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get(key))
        if as_of is not None and dt is not None and dt > as_of:
            continue
        num = row.get("driver_number")
        if num is None:
            continue
        latest[int(num)] = row
    return latest


def _position_map(rows: list[Any], as_of: datetime | None) -> dict[int, int]:
    latest: dict[int, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get("date"))
        if as_of is not None and dt is not None and dt > as_of:
            continue
        num = row.get("driver_number")
        pos = row.get("position")
        if num is None or pos is None:
            continue
        latest[int(num)] = int(pos)
    return latest


def _stint_tyre_life(stint: dict[str, Any], current_lap: int | None) -> int | None:
    """Current tyre age: start age plus laps into this stint."""
    age0 = stint.get("tyre_age_at_start")
    if age0 is None:
        return None
    try:
        start = int(stint.get("lap_start") or 1)
        age = int(age0)
    except (TypeError, ValueError):
        return None
    lap = int(current_lap or 0)
    if lap <= 0:
        return age
    return age + max(0, lap - start)


def _lap_tyre_life(lap: dict[str, Any], done: dict[str, Any]) -> int | None:
    raw = lap.get("tyre_life")
    if raw is None:
        raw = done.get("tyre_life")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _tower_tyre_life(
    *,
    lap: dict[str, Any],
    done: dict[str, Any],
    stint: dict[str, Any],
    lap_no: int | None,
) -> int | None:
    """Prefer the lap row's TyreLife; else stint start age + laps on this stint."""
    life = _lap_tyre_life(lap, done)
    if life is not None:
        return life
    return _stint_tyre_life(stint, lap_no)


def _stints_at(stints: list[Any], last_lap: dict[int, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    chosen: dict[int, dict[str, Any]] = {}
    for row in stints:
        if not isinstance(row, dict):
            continue
        num = row.get("driver_number")
        if num is None:
            continue
        n = int(num)
        current = int((last_lap.get(n) or {}).get("lap_number") or 0)
        start = int(row.get("lap_start") or 1)
        if current == 0:
            if start <= 1:
                packed = dict(row)
                packed["tyre_life"] = _stint_tyre_life(packed, current)
                chosen[n] = packed
            continue
        if start <= current:
            packed = dict(row)
            packed["tyre_life"] = _stint_tyre_life(packed, current)
            chosen[n] = packed
    return chosen


def rainfall_flag(value: Any) -> bool:
    """OpenF1 rainfall is 0/1, bool, or a string. Never treat SC as rain."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) > 0
    return str(value).strip().lower() in {"1", "true", "yes"}


def rainfall_from_samples(samples: Any, *, recent_n: int = 5) -> bool:
    if not isinstance(samples, list) or not samples:
        return False
    recent = [s for s in samples if isinstance(s, dict)][-recent_n:]
    return any(rainfall_flag(s.get("rainfall")) for s in recent)


async def get_live_rainfall(session_key: int) -> bool:
    """Most recent OpenF1 weather samples. True if any of the last 5 show rain.

    Cached for 30s — rainfall changes slowly and recommend/timing poll often.
    Reuses the poller's ``openf1:weather:{key}`` samples when present.
    Replay (FastF1) keys never hit OpenF1.
    """
    if is_synthetic_session_key(session_key):
        return False
    rkey = f"openf1:rainfall:{int(session_key)}"
    hit = cache.get(rkey, TTL_RAINFALL)
    if hit is not None:
        return bool(hit)
    wkey = f"openf1:weather:{int(session_key)}"
    raw = cache.get(wkey, TTL_WEATHER_LIVE)
    if raw is None:
        try:
            raw = await _openf1("weather", {"session_key": session_key}) or []
            cache.set(wkey, raw)
        except Exception:
            raw = []
    raining = rainfall_from_samples(raw)
    cache.set(rkey, raining)
    return raining


def _weather_from_row(row: dict[str, Any], *, is_live: bool) -> LiveWeatherResponse:
    rain = row.get("rainfall")
    return LiveWeatherResponse(
        is_live=is_live,
        air_temp=_float(row.get("air_temperature")),
        track_temp=_float(row.get("track_temperature")),
        humidity=_float(row.get("humidity")),
        rainfall=rainfall_flag(rain) if rain is not None else None,
        wind_speed=_float(row.get("wind_speed")),
        wind_direction=_float(row.get("wind_direction")),
        pressure=_float(row.get("pressure")),
        last_success_utc=_STATE.get("last_success"),
    )


def _timing_rows_from_payload(
    *,
    codes: dict[int, str],
    colours: dict[int, str],
    positions: dict[int, int],
    laps: list[dict[str, Any]],
    stints: list[Any],
    intervals: dict[int, dict[str, Any]],
    eliminated: set[str],
    locations: dict[int, dict[str, Any]],
    as_of: datetime | None = None,
    cars: dict[int, dict[str, Any]] | None = None,
) -> list[LiveTimingRow]:
    last_lap: dict[int, dict[str, Any]] = {}
    last_done: dict[int, dict[str, Any]] = {}
    pb_s1: dict[int, int] = {}
    pb_s2: dict[int, int] = {}
    pb_s3: dict[int, int] = {}
    sess_s1: int | None = None
    sess_s2: int | None = None
    sess_s3: int | None = None
    for row in laps:
        num = row.get("driver_number")
        if num is None:
            continue
        n = int(num)
        last_lap[n] = row
        if _lap_completed(row, as_of):
            last_done[n] = row
            s1 = _ms(row.get("duration_sector_1"))
            s2 = _ms(row.get("duration_sector_2"))
            s3 = _ms(row.get("duration_sector_3"))
            if s1 is not None and (n not in pb_s1 or s1 < pb_s1[n]):
                pb_s1[n] = s1
            if s2 is not None and (n not in pb_s2 or s2 < pb_s2[n]):
                pb_s2[n] = s2
            if s3 is not None and (n not in pb_s3 or s3 < pb_s3[n]):
                pb_s3[n] = s3
            if s1 is not None and (sess_s1 is None or s1 < sess_s1):
                sess_s1 = s1
            if s2 is not None and (sess_s2 is None or s2 < sess_s2):
                sess_s2 = s2
            if s3 is not None and (sess_s3 is None or s3 < sess_s3):
                sess_s3 = s3
    best_ms = _best_ms_from_laps(laps, as_of)
    stint_of = _stints_at(stints if isinstance(stints, list) else [], last_lap)
    pit_count: dict[int, int] = {}
    if isinstance(stints, list):
        for row in stints:
            if not isinstance(row, dict):
                continue
            num = row.get("driver_number")
            if num is None:
                continue
            n = int(num)
            start = int(row.get("lap_start") or 1)
            current = int((last_lap.get(n) or {}).get("lap_number") or 0)
            if current and start <= current and int(row.get("stint_number") or 1) > 1:
                pit_count[n] = pit_count.get(n, 0) + 1
            elif as_of is None and int(row.get("stint_number") or 1) > 1:
                pit_count[n] = pit_count.get(n, 0) + 1
    latest_pos = _unique_positions({int(k): int(v) for k, v in dict(positions).items() if v is not None})
    leader_best = min(best_ms.values()) if best_ms else None
    fastest_num = min(best_ms, key=best_ms.get) if best_ms else None  # type: ignore[arg-type]
    if not latest_pos and best_ms:
        ranked = sorted(best_ms, key=lambda n: best_ms[n])
        latest_pos = {n: i + 1 for i, n in enumerate(ranked)}
    numbers = sorted(set(latest_pos) | set(last_lap) | set(codes), key=lambda n: latest_pos.get(n, 99))
    if cars is None:
        cars = _STATE.get("car_data") if as_of is None else {}
    if not isinstance(cars, dict):
        cars = {}
    rows: list[LiveTimingRow] = []
    for num in numbers:
        lap = last_lap.get(num) or {}
        done = last_done.get(num) or {}
        iv = intervals.get(num) or {}
        st = stint_of.get(num) or {}
        last_ms = _ms(done.get("lap_duration"))
        code = codes.get(num, f"D{num}")
        gap_leader = _float(iv.get("gap_to_leader"))
        if gap_leader is None and leader_best is not None and num in best_ms:
            gap_leader = (best_ms[num] - leader_best) / 1000.0
        loc = locations.get(num) or {}
        loc_status = str(loc.get("status") or "").lower().replace(" ", "").replace("_", "")
        in_pit = loc_status in {"pit", "inpit"}
        s1 = _ms(lap.get("duration_sector_1")) or _ms(done.get("duration_sector_1"))
        s2 = _ms(lap.get("duration_sector_2")) or _ms(done.get("duration_sector_2"))
        s3 = _ms(lap.get("duration_sector_3")) or _ms(done.get("duration_sector_3"))
        car = cars.get(num) or {}
        lap_no = lap.get("lap_number") or done.get("lap_number")
        rows.append(
            LiveTimingRow(
                position=int(latest_pos.get(num, len(rows) + 1)),
                driver_code=code,
                gap_to_leader_s=gap_leader,
                gap_to_ahead_s=_float(iv.get("interval")),
                last_lap_ms=last_ms,
                best_lap_ms=best_ms.get(num),
                sector1_ms=s1,
                sector2_ms=s2,
                sector3_ms=s3,
                s1_colour=_sector_tone(s1, pb_s1.get(num), sess_s1, lap.get("segments_sector_1") or done.get("segments_sector_1")),
                s2_colour=_sector_tone(s2, pb_s2.get(num), sess_s2, lap.get("segments_sector_2") or done.get("segments_sector_2")),
                s3_colour=_sector_tone(s3, pb_s3.get(num), sess_s3, lap.get("segments_sector_3") or done.get("segments_sector_3")),
                compound=_compound_letter(st.get("compound")),
                tyre_life=_tower_tyre_life(
                    lap=lap,
                    done=done,
                    stint=st,
                    lap_no=int(lap_no) if lap_no is not None else None,
                ),
                stint_number=st.get("stint_number"),
                pit_count=pit_count.get(num, 0),
                speed_trap_kph=_float(lap.get("st_speed") or done.get("st_speed")),
                team_colour=colours.get(num),
                eliminated=code in eliminated,
                in_pit=in_pit,
                fastest_lap=num == fastest_num,
                lap_number=int(lap_no) if lap_no is not None else None,
                throttle_pct=_float(car.get("throttle")),
                brake_pct=_float(car.get("brake")),
                speed_kph=_float(car.get("speed")),
                drs_open=_drs_open(car.get("drs")),
            )
        )
    rows.sort(key=lambda r: (r.position, r.best_lap_ms or 10**9, r.driver_code))
    for i, row in enumerate(rows, start=1):
        row.position = i
    field_lap = max((r.lap_number or 0) for r in rows) if rows else 0
    return _annotate_timing_status(rows, field_lap)


def _eliminated_codes(messages: list[Any], codes: dict[int, str]) -> set[str]:
    out: set[str] = set()
    by_code = {v.upper(): k for k, v in codes.items()}
    by_num = {str(n): c for n, c in codes.items()}
    stop_words = (
        "ELIMINATED",
        "KNOCKED OUT",
        "RETIRED",
        " DNF",
        "WITHDRAWN",
        "DID NOT START",
        "OUT OF THE RACE",
        "BLACK FLAG",
    )
    for row in messages:
        if not isinstance(row, dict):
            continue
        blob = f"{row.get('message') or ''} {row.get('flag') or ''} {row.get('category') or ''}".upper()
        if not any(tok in blob for tok in stop_words):
            continue
        for code in by_code:
            if code and code in blob:
                out.add(code)
        for num in re.findall(r"\bCAR\s+(\d+)\b", blob):
            code = by_num.get(num)
            if code:
                out.add(code)
    return out


def _inactive_from_laps(laps: list[Any], codes: dict[int, str], total_laps: int | None = None) -> set[str]:
    """Drivers who never resumed after the field has done several laps (DNF/DNS)."""
    current: dict[int, int] = {}
    for row in laps:
        if not isinstance(row, dict):
            continue
        num = row.get("driver_number")
        try:
            lap_no = int(row.get("lap_number") or 0)
        except (TypeError, ValueError):
            continue
        if num is None or lap_no <= 0:
            continue
        n = int(num)
        current[n] = max(current.get(n, 0), lap_no)
    field = max(current.values()) if current else 0
    if field < 5:
        return set()
    threshold = max(5, int(0.1 * (total_laps or 50)))
    out: set[str] = set()
    for num, code in codes.items():
        n = int(num)
        last = current.get(n)
        if last is None or last <= 0:
            if field >= threshold:
                out.add(code)
            continue
        if last <= 1 and field >= threshold:
            out.add(code)
        elif field >= 10 and last < field - 3:
            out.add(code)
    return out


def _annotate_timing_status(rows: list[LiveTimingRow], field_lap: int) -> list[LiveTimingRow]:
    """Mark DNF/DNS and laps-down on timing rows."""
    for row in rows:
        row.laps_completed = row.lap_number
        if row.lap_number is not None and field_lap:
            row.laps_down = max(0, field_lap - int(row.lap_number))
        blob = (row.reason or "").upper()
        eliminated = bool(row.eliminated)
        last = int(row.lap_number or 0)
        if "DID NOT START" in blob or "WITHDRAWN" in blob or re.search(r"\bDNS\b", blob):
            row.status = "DNS"
            row.reason = row.reason or "DNS"
            row.eliminated = True
        elif eliminated or "RETIRED" in blob or re.search(r"\bDNF\b", blob):
            if last <= 1:
                row.status = "DNS"
                row.reason = row.reason or "DNS"
            else:
                row.status = "DNF"
                row.reason = row.reason or "DNF"
            row.eliminated = True
        elif field_lap >= 5 and last <= 1:
            row.status = "DNS"
            row.reason = row.reason or "DNS"
            row.eliminated = True
        elif field_lap >= 10 and last and last < field_lap - 3:
            row.status = "DNF"
            row.reason = row.reason or "DNF"
            row.eliminated = True
        else:
            row.status = "RUNNING"
    return rows


async def _timing_from_openf1(
    session_key: int, as_of: datetime | None = None, *, persist: bool = True
) -> list[LiveTimingRow]:
    codes = await _driver_code_map(session_key)
    colours: dict[int, str] = _STATE.get("driver_colours") or {}
    use_feed = persist and as_of is None and _feed_session_key() == session_key
    positions = _STATE.get("latest_pos") or {} if use_feed else {}
    laps = _STATE.get("laps") if use_feed else None
    stints = _STATE.get("stints") if use_feed else None
    intervals = _STATE.get("intervals") if use_feed else None
    if not isinstance(laps, list) or not laps:
        positions_raw, intervals_raw, laps, stints_raw = await asyncio.gather(
            _openf1("position", {"session_key": session_key}),
            _openf1("intervals", {"session_key": session_key}),
            _openf1("laps", {"session_key": session_key}),
            _openf1("stints", {"session_key": session_key}),
        )
        if isinstance(positions_raw, list):
            positions = _position_map(positions_raw, as_of)
            if persist and as_of is None:
                _STATE["latest_pos"] = positions
        intervals = {}
        if isinstance(intervals_raw, list):
            intervals = _latest_by_date(intervals_raw, as_of)
            if persist and as_of is None:
                _STATE["intervals"] = intervals
        if isinstance(stints_raw, list):
            stints = stints_raw
            if persist and as_of is None:
                _STATE["stints"] = stints
        if isinstance(laps, list) and persist and as_of is None:
            _STATE["laps"] = laps
        if isinstance(positions_raw, list) and as_of is not None:
            positions = _position_map(positions_raw, as_of)
        if isinstance(intervals_raw, list) and as_of is not None:
            intervals = _latest_by_date(intervals_raw, as_of)
    latest_pos = positions if isinstance(positions, dict) else {}
    latest_int = intervals if isinstance(intervals, dict) else {}
    filtered = _laps_upto(laps if isinstance(laps, list) else [], as_of)
    rc = _STATE.get("race_control") or []
    locations = _STATE.get("locations") or {} if as_of is None else {}
    if not isinstance(locations, dict):
        locations = {}
    eliminated = _eliminated_codes(rc if isinstance(rc, list) else [], codes)
    eliminated |= _inactive_from_laps(filtered if isinstance(filtered, list) else [], codes)
    if as_of is None:
        _STATE["eliminated"] = set(eliminated)
    return _timing_rows_from_payload(
        codes=codes,
        colours=colours if isinstance(colours, dict) else {},
        positions=latest_pos,
        laps=filtered,
        stints=stints if isinstance(stints, list) else [],
        intervals=latest_int,
        eliminated=eliminated,
        locations=locations if isinstance(locations, dict) else {},
        as_of=as_of,
    )


def _normalize_session_type(session_type: str | None) -> str:
    mapped = str(session_type or "R").upper()
    if mapped not in {"R", "S", "Q", "SQ", "FP1", "FP2", "FP3"}:
        return "R"
    return mapped


def _iso_dt(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _new_replay_pack(
    session_key: int,
    pack_year: int | None,
    pack_round: int | None,
    mapped: str,
    start: datetime | None,
    end: datetime | None,
) -> dict[str, Any]:
    from backend.sessions import quali_windows_for_session_type

    windows = quali_windows_for_session_type(mapped)
    return {
        "session": {
            "session_key": session_key,
            "session_name": _SESSION_DISPLAY.get(mapped, mapped),
            "session_type": mapped,
            "year": pack_year,
        },
        "laps": [],
        "weather": [],
        "stints": [],
        "positions": [],
        "intervals": [],
        "race_control": [],
        "codes": {},
        "colours": {},
        "date_start": start,
        "date_end": end,
        "year": pack_year,
        "round_number": pack_round,
        "session_type": mapped,
        "circuit_path": None,
        "bounds": None,
        "path_x": [],
        "path_y": [],
        "pit_lane_x": [],
        "pit_lane_y": [],
        "pit_stalls": [],
        "source": "fastf1",
        "ff1": {"ok": False, "quali_windows": windows, "synthetic_gps": False},
        "car_samples": {},
        "green_flag_s": None,
        "map_markers": [],
        "drs_segments": [],
        "stage": "metadata",
    }


def _as_openf1_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _codes_from_openf1_drivers(rows: list[Any]) -> tuple[dict[int, str], dict[int, str]]:
    codes: dict[int, str] = {}
    colours: dict[int, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        num = row.get("driver_number")
        code = row.get("name_acronym") or row.get("broadcast_name")
        if num is None or not code:
            continue
        n = int(num)
        codes[n] = str(code)[:3].upper()
        colour = row.get("team_colour")
        if colour:
            colours[n] = f"#{str(colour).lstrip('#')}"
    return codes, colours


def _stamp_openf1_driver_codes(rows: list[Any], codes: dict[int, str]) -> list[dict[str, Any]]:
    """Copy driver_number → driver_code so synthetic GPS / charts can group laps."""
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        num = item.get("driver_number")
        if num is not None and not item.get("driver_code"):
            try:
                item["driver_code"] = codes.get(int(num), "")
            except (TypeError, ValueError):
                pass
        out.append(item)
    return out


def _apply_openf1_to_pack(
    pack: dict[str, Any],
    *,
    session: dict[str, Any] | None = None,
    drivers: list[Any] | None = None,
    laps: list[Any] | None = None,
    stints: list[Any] | None = None,
    positions: list[Any] | None = None,
    weather: list[Any] | None = None,
    race_control: list[Any] | None = None,
) -> dict[str, Any]:
    """Fill a replay pack from OpenF1 payloads (recent sessions FastF1 cannot load yet)."""
    codes, colours = _codes_from_openf1_drivers(drivers or [])
    if codes:
        pack["codes"] = codes
    if colours:
        pack["colours"] = colours
    stamped = _stamp_openf1_driver_codes(laps or [], pack.get("codes") or codes)
    if stamped:
        pack["laps"] = stamped
    if stints:
        pack["stints"] = _as_openf1_rows(stints)
    if positions:
        pack["positions"] = _as_openf1_rows(positions)
    if weather:
        pack["weather"] = _as_openf1_rows(weather)
    if race_control:
        pack["race_control"] = _as_openf1_rows(race_control)
    if isinstance(session, dict):
        start = _parse_dt(session.get("date_start"))
        end = _parse_dt(session.get("date_end"))
        if start is not None:
            pack["date_start"] = start
        if end is not None:
            pack["date_end"] = end
        if session.get("session_key") is not None:
            pack["openf1_session_key"] = int(session["session_key"])
    pack["source"] = "openf1"
    ff1 = dict(pack.get("ff1") or {})
    ff1["ok"] = bool(pack.get("laps"))
    ff1["num_by_code"] = {v: k for k, v in (pack.get("codes") or {}).items()}
    pack["ff1"] = ff1
    pack["green_flag_s"] = _green_flag_s(pack.get("race_control") or [], pack.get("date_start"))
    return pack


async def _fill_pack_openf1(
    pack: dict[str, Any],
    session_key: int,
    year: int,
    round_number: int,
    mapped: str,
) -> bool:
    """Load laps/stints/timing from OpenF1 when FastF1 has nothing for this session."""
    try:
        sess = await resolve_openf1_session(int(year), int(round_number), mapped)
    except Exception:
        _log.exception(
            "OpenF1 session resolve failed year=%s round=%s type=%s", year, round_number, mapped
        )
        return False
    if not isinstance(sess, dict) or sess.get("session_key") is None:
        _log.info("OpenF1 session missing year=%s round=%s type=%s", year, round_number, mapped)
        return False
    of1_key = int(sess["session_key"])
    try:
        drivers, laps, stints, positions, weather, race_control = await asyncio.gather(
            _openf1("drivers", {"session_key": of1_key}),
            _openf1("laps", {"session_key": of1_key}, timeout=20.0),
            _openf1("stints", {"session_key": of1_key}),
            _openf1("position", {"session_key": of1_key}, timeout=20.0),
            _openf1("weather", {"session_key": of1_key}),
            _openf1("race_control", {"session_key": of1_key}),
        )
    except Exception:
        _log.exception("OpenF1 replay fetch failed session_key=%s of1=%s", session_key, of1_key)
        return False
    laps_rows = _as_openf1_rows(laps)
    if not laps_rows:
        _log.info(
            "OpenF1 laps empty of1=%s year=%s round=%s type=%s", of1_key, year, round_number, mapped
        )
        return False
    _apply_openf1_to_pack(
        pack,
        session=sess,
        drivers=_as_openf1_rows(drivers),
        laps=laps_rows,
        stints=_as_openf1_rows(stints),
        positions=_as_openf1_rows(positions),
        weather=_as_openf1_rows(weather),
        race_control=_as_openf1_rows(race_control),
    )
    _PACK_LOAD_ERROR.pop(session_key, None)
    _log.info(
        "OpenF1 replay fill OK session_key=%s of1=%s laps=%s drivers=%s",
        session_key,
        of1_key,
        len(pack.get("laps") or []),
        len(pack.get("codes") or {}),
    )
    return True


def _attach_synthetic_gps(pack: dict[str, Any]) -> None:
    """Enough map motion for the minimal stage when FastF1 GPS is not loaded yet."""
    ff1 = pack.get("ff1") if isinstance(pack.get("ff1"), dict) else {}
    if ff1.get("pos_samples") and not ff1.get("synthetic_gps"):
        return
    path_x = pack.get("path_x") or []
    path_y = pack.get("path_y") or []
    laps = pack.get("laps") or []
    if not path_x or not path_y or not laps:
        return
    from backend.sessions import synthetic_pos_from_laps

    samples = synthetic_pos_from_laps(laps, path_x, path_y)
    if not samples:
        return
    ff1 = dict(ff1)
    ff1["pos_samples"] = samples
    ff1["synthetic_gps"] = True
    pack["ff1"] = ff1
    pack.pop("path_traces", None)
    pack.pop("path_traces_v", None)
    ensure_path_traces(pack)


def _calendar_session_status(year: int | None, round_number: int | None, mapped: str) -> str:
    if not year or not round_number:
        return "COMPLETED"
    try:
        from backend.calendar import get_round_sessions

        weekend = get_round_sessions(int(year), int(round_number))
        match = next((s for s in weekend.sessions if s.session_type == mapped), None)
        return str(match.status) if match is not None else "COMPLETED"
    except Exception:
        return "COMPLETED"


async def _staged_fastf1_fill(
    pack: dict[str, Any], session_key: int, *, executor: Any = None, include_gps: bool = True
) -> dict[str, Any]:
    """Publish metadata → minimal (laps + map + synthetic GPS) → full (chunked GPS).

    Caller holds the per-session pack lock for the minimal stage. GPS loads
    after the lock is released so HTTP can keep serving. Waiters must not
    await that lock; they poll `_REPLAY_PACKS` via `_wait_for_pack_stage`.
    """
    year = pack.get("year")
    rnd = pack.get("round_number")
    mapped = str(pack.get("session_type") or "R")
    if not (year and rnd):
        return pack
    if replay_pack_stage(pack) == "full" and _ff1_pack_ready(pack):
        if not pack.get("path_x"):
            await _fill_pack_map(session_key, int(year), int(rnd), executor=executor)
            pack = _REPLAY_PACKS.get(session_key) or pack
        if _ff1_pack_ready(pack):
            ensure_path_traces(pack)
        return pack

    if not pack.get("path_x"):
        await _fill_pack_map(session_key, int(year), int(rnd), executor=executor)
        pack = _REPLAY_PACKS.get(session_key) or pack

    if not pack.get("laps") or replay_pack_stage(pack) in {"empty", "metadata"}:
        await _upgrade_pack_fastf1(
            session_key,
            int(year),
            int(rnd),
            mapped,
            pack.get("bounds"),
            pack.get("date_start"),
            pack.get("date_end"),
            executor=executor,
            telemetry=False,
            weather=False,
            messages=False,
        )
        pack = _REPLAY_PACKS.get(session_key) or pack
        if not pack.get("laps"):
            await _fill_pack_openf1(pack, session_key, int(year), int(rnd), mapped)
            pack = _REPLAY_PACKS.get(session_key) or pack
        if not pack.get("path_x"):
            await _fill_pack_map(session_key, int(year), int(rnd), executor=executor)
            pack = _REPLAY_PACKS.get(session_key) or pack
        _attach_synthetic_gps(pack)
        if pack.get("laps"):
            _PACK_LOAD_ERROR.pop(session_key, None)
            _set_pack_stage(pack, "minimal")
            if not pack.get("session_status"):
                pack["session_status"] = _calendar_session_status(int(year), int(rnd), mapped)
            save_replay_pack_disk(session_key, pack)

    if _ff1_pack_ready(pack):
        if pack.get("path_x"):
            ensure_path_traces(pack)
        _set_pack_stage(pack, "full")
        if not pack.get("session_status"):
            pack["session_status"] = _calendar_session_status(int(year), int(rnd), mapped)
        save_replay_pack_disk(session_key, pack)
        return pack

    if not include_gps:
        return pack

    return await _fill_gps_chunks(pack, session_key, executor=executor)


async def _fill_gps_chunks(
    pack: dict[str, Any], session_key: int, *, executor: Any = None
) -> dict[str, Any]:
    """Background GPS: position_data only, persisted as 10-lap chunks. No car_data."""
    year = pack.get("year")
    rnd = pack.get("round_number")
    mapped = str(pack.get("session_type") or "R")
    if not (year and rnd) or _ff1_pack_ready(pack):
        return pack
    from backend.sessions import log_process_mem

    log_process_mem("before gps chunks")
    await _upgrade_pack_fastf1(
        session_key,
        int(year),
        int(rnd),
        mapped,
        pack.get("bounds"),
        pack.get("date_start"),
        pack.get("date_end"),
        executor=executor,
        telemetry=True,
        weather=True,
        messages=True,
    )
    pack = _REPLAY_PACKS.get(session_key) or pack
    if not pack.get("path_x"):
        await _fill_pack_map(session_key, int(year), int(rnd), executor=executor)
        pack = _REPLAY_PACKS.get(session_key) or pack
    if _ff1_pack_ready(pack):
        ensure_path_traces(pack)
        _set_pack_stage(pack, "full")
        save_replay_pack_disk(session_key, pack)
    log_process_mem("after gps chunks")
    return pack


async def _wait_for_pack_stage(
    session_key: int, wait_for: str, *, timeout_s: float | None = None
) -> dict[str, Any]:
    wanted = _PACK_STAGE_RANK.get(wait_for, 3)
    if timeout_s is None:
        timeout_s = 240.0 if wanted <= 2 else 900.0
    t0 = time.monotonic()
    while True:
        pack = _REPLAY_PACKS.get(session_key)
        if _stage_rank(pack) >= wanted:
            return pack or {}
        job = _PACK_JOBS.get(session_key)
        err = _PACK_LOAD_ERROR.get(session_key)
        if err and (job is None or job.done()) and not _pack_in_flight(session_key):
            return pack or {}
        if job is not None and job.done() and _stage_rank(pack) < wanted:
            return pack or {}
        if time.monotonic() - t0 > timeout_s:
            _log.warning(
                "wait for pack stage=%s timed out session_key=%s have=%s",
                wait_for,
                session_key,
                replay_pack_stage(pack),
            )
            return pack or {}
        await asyncio.sleep(0.12)


def _kick_pack_job(
    session_key: int,
    year: int | None,
    round_number: int | None,
    session_type: str | None,
    *,
    refresh: bool = False,
    executor: Any = None,
) -> None:
    from backend.calendar import replay_session_type_allowed, replay_year_allowed

    if year is not None and not replay_year_allowed(int(year)):
        _log.info("Replay request for year %s — blocked (not in 2024–2026)", year)
        return
    if not replay_session_type_allowed(session_type):
        _log.info("Replay/ARIS pack skipped for non-Race session %s", session_type)
        return
    existing = _PACK_JOBS.get(session_key)
    if existing is not None and not existing.done() and not refresh:
        return
    _FF1_UPGRADE_INFLIGHT.add(session_key)
    task = asyncio.create_task(
        _run_pack_load(
            session_key,
            year,
            round_number,
            session_type=session_type,
            refresh=refresh,
            executor=executor,
        ),
        name=f"replay-pack-{session_key}",
    )
    _PACK_JOBS[session_key] = task


async def _run_pack_load(
    session_key: int,
    year: int | None,
    round_number: int | None,
    *,
    refresh: bool = False,
    session_type: str | None = None,
    executor: Any = None,
) -> dict[str, Any]:
    """Background job: always continues to stage=full. Waiters poll memory."""
    from backend.calendar import replay_year_allowed

    decoded = decode_synthetic_session_key(session_key)
    if decoded is not None:
        year = year or decoded[0]
        round_number = round_number or decoded[1]
        if not session_type:
            session_type = decoded[2]
    if year is not None and not replay_year_allowed(int(year)):
        _log.info("Replay request for year %s — blocked (not in 2024–2026)", year)
        return _REPLAY_PACKS.get(session_key) or {}
    mapped = _normalize_session_type(session_type)
    pack: dict[str, Any] = {}
    need_gps = False
    from backend.sessions import log_process_mem

    log_process_mem("pack job start")
    try:
        async with _pack_lock(session_key):
            if refresh:
                _REPLAY_PACKS.pop(session_key, None)
            cached, memory_hit, disk_hit = hydrate_replay_pack_cache(
                session_key, year, round_number, mapped, log_hits=True
            )
            if (
                cached is not None
                and _ff1_pack_ready(cached)
                and cached.get("path_traces")
                and cached.get("path_traces_v") == _PATH_TRACES_V
            ):
                _log.info(
                    "key=%s memory_hit=%s disk_hit=%s stage=full — skip FastF1",
                    replay_pack_disk_key(session_key, year, round_number, mapped),
                    memory_hit,
                    disk_hit,
                )
                _set_pack_stage(cached, "full")
                return cached
            if cached is not None and _stage_rank(cached) >= _PACK_STAGE_RANK["minimal"]:
                src = "fastf1" if _ff1_pack_ready(cached) else (cached.get("source") or "fastf1")
                _log.info(
                    "replay pack cache session_key=%s source=%s stage=%s memory_hit=%s disk_hit=%s — FastF1 upgrade if needed",
                    session_key,
                    src,
                    replay_pack_stage(cached),
                    memory_hit,
                    disk_hit,
                )
                pack = await _staged_fastf1_fill(
                    cached, session_key, executor=executor, include_gps=False
                )
                need_gps = not _ff1_pack_ready(pack)
            else:
                pack, need_gps = await _cold_load_minimal(
                    session_key, year, round_number, mapped, executor=executor
                )
        if need_gps and pack.get("source") != "openf1":
            pack = await _fill_gps_chunks(
                _REPLAY_PACKS.get(session_key) or pack, session_key, executor=executor
            )
        pack = _REPLAY_PACKS.get(session_key) or pack
        if not pack.get("laps"):
            _PACK_LOAD_ERROR[session_key] = (
                f"No FastF1 or OpenF1 laps for session_key={session_key}"
            )
        return pack
    except Exception:
        _log.exception("replay pack job failed session_key=%s", session_key)
        pack = _REPLAY_PACKS.get(session_key) or {}
        if pack.get("year") and pack.get("round_number") and not pack.get("laps"):
            try:
                await _fill_pack_openf1(
                    pack,
                    session_key,
                    int(pack["year"]),
                    int(pack["round_number"]),
                    str(pack.get("session_type") or mapped),
                )
                pack = _REPLAY_PACKS.get(session_key) or pack
                _attach_synthetic_gps(pack)
                if pack.get("laps"):
                    _PACK_LOAD_ERROR.pop(session_key, None)
                    _set_pack_stage(pack, "minimal")
                    save_replay_pack_disk(session_key, pack)
            except Exception:
                _log.exception("OpenF1 replay fallback failed session_key=%s", session_key)
        if not pack.get("laps"):
            _PACK_LOAD_ERROR[session_key] = f"Replay load failed for session_key={session_key}"
        return pack
    finally:
        _FF1_UPGRADE_INFLIGHT.discard(session_key)


async def _cold_load_minimal(
    session_key: int,
    year: int | None,
    round_number: int | None,
    mapped: str,
    *,
    executor: Any = None,
) -> tuple[dict[str, Any], bool]:
    """Metadata → minimal under the pack lock. GPS is filled after the lock drops."""
    pack_year = year
    pack_round = round_number
    start = end = None
    if pack_year and pack_round:
        start, end = calendar_session_window(int(pack_year), int(pack_round), mapped)
    if end is None and start is not None:
        end = start + timedelta(hours=_SESSION_HOURS.get(mapped, 1.5))
    cold_load_started = time.monotonic()
    _PACK_LOAD_STARTED[session_key] = cold_load_started
    _PACK_LOAD_ERROR.pop(session_key, None)
    cold_load_started_utc = datetime.now(timezone.utc).isoformat()
    _log.info(
        "Loading replay session %s via FastF1",
        f"{pack_year} R{pack_round} {mapped}",
    )
    _log.info(
        "replay pack MISS session_key=%s year=%s round=%s type=%s start_utc=%s — FastF1 then OpenF1",
        session_key,
        pack_year,
        pack_round,
        mapped,
        cold_load_started_utc,
    )
    pack = _new_replay_pack(session_key, pack_year, pack_round, mapped, start, end)
    _REPLAY_PACKS[session_key] = pack
    _set_pack_stage(pack, "metadata")

    status = _calendar_session_status(pack_year, pack_round, mapped)
    pack["session_status"] = status
    if status != "COMPLETED":
        _log.info(
            "replay session %s status=%s — skipping FastF1, trying OpenF1",
            f"{pack_year} R{pack_round} {mapped}",
            status,
        )
        if pack_year and pack_round:
            if not pack.get("path_x"):
                await _fill_pack_map(session_key, int(pack_year), int(pack_round), executor=executor)
                pack = _REPLAY_PACKS.get(session_key) or pack
            await _fill_pack_openf1(pack, session_key, int(pack_year), int(pack_round), mapped)
            pack = _REPLAY_PACKS.get(session_key) or pack
            _attach_synthetic_gps(pack)
            if pack.get("laps"):
                _PACK_LOAD_ERROR.pop(session_key, None)
                _set_pack_stage(pack, "minimal")
                save_replay_pack_disk(session_key, pack)
        return pack, False

    if pack_year and pack_round:
        pack = await _staged_fastf1_fill(
            pack, session_key, executor=executor, include_gps=False
        )
    else:
        _log.error("replay pack MISS needs year/round session_key=%s", session_key)
    cold_load_elapsed = time.monotonic() - cold_load_started
    _log.info(
        "cold-load COMPLETE session_key=%s year=%s round=%s type=%s "
        "start_utc=%s duration_s=%.2f stage=%s ready=%s",
        session_key,
        pack_year,
        pack_round,
        mapped,
        cold_load_started_utc,
        cold_load_elapsed,
        replay_pack_stage(pack if isinstance(pack, dict) else {}),
        _ff1_pack_ready(pack if isinstance(pack, dict) else {}),
    )
    print(
        f"[ARIS] cold-load {pack_year} R{pack_round} {mapped} "
        f"duration_s={cold_load_elapsed:.2f} session_key={session_key} "
        f"stage={replay_pack_stage(pack if isinstance(pack, dict) else {})}",
        flush=True,
    )
    return pack, not _ff1_pack_ready(pack)


async def _ensure_replay_pack(
    session_key: int,
    year: int | None = None,
    round_number: int | None = None,
    *,
    refresh: bool = False,
    session_type: str | None = None,
    executor: Any = None,
    wait_for: str = "full",
) -> dict[str, Any]:
    """Build/reuse the in-memory replay pack for `session_key`.

    Waiters never hold the pack lock. `wait_for=minimal` returns as soon as
    laps + map are published; the background job always continues to full GPS.
    `executor` lets prewarm pass the dedicated prewarm pool.
    """
    decoded = decode_synthetic_session_key(session_key)
    if decoded is not None:
        year = year or decoded[0]
        round_number = round_number or decoded[1]
        if not session_type:
            session_type = decoded[2]
    if year is not None:
        from backend.calendar import ReplayYearBlocked, replay_year_allowed

        if not replay_year_allowed(int(year)):
            _log.info("Replay request for year %s — blocked (not in 2024–2026)", year)
            raise ReplayYearBlocked("Replay not allowed for this year")
    from backend.calendar import assert_replay_session_type

    assert_replay_session_type(session_type or "R")
    wanted = wait_for if wait_for in _PACK_STAGE_RANK else "full"
    if refresh:
        invalidate_replay_pack(session_key)
        _log.info(
            "replay pack REFRESH session_key=%s year=%s round=%s — bypass cache, load FastF1",
            session_key,
            year,
            round_number,
        )
    cached, memory_hit, disk_hit = hydrate_replay_pack_cache(
        session_key, year, round_number, session_type, log_hits=True
    )
    have_full_gps = (
        cached is not None
        and replay_pack_stage(cached) == "full"
        and _ff1_pack_ready(cached)
    )
    if have_full_gps and wanted == "full":
        _log.info(
            "key=%s memory_hit=%s disk_hit=%s stage=full — skip FastF1",
            replay_pack_disk_key(session_key, year, round_number, session_type),
            memory_hit,
            disk_hit,
        )
        return cached
    if cached is not None and _stage_rank(cached) >= _PACK_STAGE_RANK[wanted] and wanted != "full":
        if replay_pack_stage(cached) != "full":
            _kick_pack_job(
                session_key, year, round_number, session_type, refresh=False, executor=executor
            )
        return cached
    _kick_pack_job(
        session_key, year, round_number, session_type, refresh=refresh, executor=executor
    )
    return await _wait_for_pack_stage(session_key, wanted)


def _jsonish(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return obj
    return obj


def _outline_from_pack(pack: dict[str, Any] | None) -> dict[str, Any]:
    """Static map geometry for init / pack-status. Empty when the pack has no map yet."""
    pack = pack or {}
    path = _jsonish(pack.get("circuit_path"))
    if not isinstance(path, dict) or not path.get("x"):
        xs = pack.get("path_x") or []
        ys = pack.get("path_y") or []
        path = {"x": list(xs), "y": list(ys)} if xs and ys and len(xs) == len(ys) else None
    markers: list[Any] = []
    for marker in pack.get("map_markers") or []:
        dumped = _jsonish(marker)
        if isinstance(dumped, dict) and dumped.get("kind") is not None:
            markers.append(dumped)
    return {
        "circuit_path": path,
        "pit_lane_x": list(pack.get("pit_lane_x") or []),
        "pit_lane_y": list(pack.get("pit_lane_y") or []),
        "markers": markers,
        "drs_segments": [list(s) for s in (pack.get("drs_segments") or [])],
    }


async def init_replay(year: int, round_number: int, session_type: str) -> dict[str, Any]:
    """Return calendar metadata immediately and start FastF1 in the background."""
    from backend.calendar import assert_replay_session_type, assert_replay_year

    assert_replay_year(int(year))
    mapped = assert_replay_session_type(session_type)
    session_key = synthetic_session_key(int(year), int(round_number), mapped)
    circuit_name = ""
    total_laps = 0
    try:
        from backend.calendar import get_round
        from backend.sessions import _scheduled_laps

        rnd = get_round(int(year), int(round_number))
        circuit_name = str(rnd.circuit_name or rnd.name or "")
        total_laps = int(_scheduled_laps(int(year), int(round_number)) or rnd.total_laps or 0)
    except Exception:
        pass
    start, end = calendar_session_window(int(year), int(round_number), mapped)
    if end is None and start is not None:
        end = start + timedelta(hours=_SESSION_HOURS.get(mapped, 1.5))
    status = _calendar_session_status(year, round_number, mapped)
    existing, _memory_hit, _disk_hit = hydrate_replay_pack_cache(
        session_key, int(year), int(round_number), mapped, log_hits=True
    )
    if existing is None or not pack_matches_request(existing, year, round_number):
        pack = _new_replay_pack(session_key, int(year), int(round_number), mapped, start, end)
        pack["session_status"] = status
        _REPLAY_PACKS[session_key] = pack
        _PACK_LOAD_STARTED.setdefault(session_key, time.monotonic())
        _set_pack_stage(pack, "metadata")
    else:
        pack = existing
        pack["session_status"] = pack.get("session_status") or status
    source = "fastf1" if status == "COMPLETED" else "none"
    _log.info(
        "replay init session_key=%s %s R%s %s status=%s source=%s",
        session_key,
        year,
        round_number,
        mapped,
        status,
        source,
    )
    if status == "COMPLETED":
        _kick_pack_job(session_key, int(year), int(round_number), mapped)
    codes = pack.get("codes") or {}
    drivers = [str(v) for v in codes.values() if v]
    payload = {
        "session_key": session_key,
        "year": int(year),
        "round_number": int(round_number),
        "session_type": mapped,
        "stage": replay_pack_stage(pack),
        "session_status": status,
        "source": source,
        "circuit": circuit_name,
        "total_laps": total_laps,
        "drivers": drivers,
        "date_start": _iso_dt(pack.get("date_start") or start),
        "date_end": _iso_dt(pack.get("date_end") or end),
        "flags": _pack_flags(pack),
        "progress": _pack_progress(pack),
    }
    payload.update(_outline_from_pack(pack))
    return payload


async def _fill_pack_map(
    session_key: int, year: int, round_number: int, *, executor: Any = None
) -> None:
    try:
        from backend.models import CircuitPathXY
        from backend.sessions import circuit_map_quick, pit_lane_from_path

        cmap = await _run_pack_blocking(executor, circuit_map_quick, year, round_number)
        pack = _REPLAY_PACKS.get(session_key)
        if pack is None or not cmap or not cmap.available or not cmap.x:
            return
        pack["circuit_path"] = CircuitPathXY(x=cmap.x, y=cmap.y)
        pack["bounds"] = cmap.bounds
        pack["path_x"] = list(cmap.x)
        pack["path_y"] = list(cmap.y)
        pack["pit_stalls"] = [list(p) for p in (cmap.pit_stalls or [])]
        pack["pit_lane_x"] = list(cmap.pit_lane_x or [])
        pack["pit_lane_y"] = list(cmap.pit_lane_y or [])
        pack["map_markers"] = list(cmap.markers or [])
        pack["drs_segments"] = [list(s) for s in (cmap.drs_segments or [])]
        if pack["path_x"] and (not pack["pit_lane_x"] or not pack["pit_stalls"]):
            px, py, stalls = pit_lane_from_path(pack["path_x"], pack["path_y"])
            pack["pit_lane_x"] = pack["pit_lane_x"] or px
            pack["pit_lane_y"] = pack["pit_lane_y"] or py
            pack["pit_stalls"] = pack["pit_stalls"] or [list(p) for p in stalls]
        pack["map_markers"] = list(cmap.markers or [])
        pack["drs_segments"] = [list(s) for s in (cmap.drs_segments or [])]
        pack.pop("path_traces", None)
        pack.pop("path_traces_v", None)
        _align_pack_gps(pack)
        if _ff1_pack_ready(pack):
            ensure_path_traces(pack)
    except Exception:
        return


async def _upgrade_pack_fastf1(
    session_key: int,
    year: int,
    round_number: int,
    mapped: str,
    bounds: Any,
    start: datetime | None,
    end: datetime | None,
    *,
    executor: Any = None,
    telemetry: bool = True,
    weather: bool = True,
    messages: bool = True,
) -> None:
    try:
        from backend.sessions import _coerce_bounds, build_ff1_replay_assets

        load_started = time.monotonic()
        ff1 = await _run_pack_blocking(
            executor,
            build_ff1_replay_assets,
            year,
            round_number,
            mapped,
            _coerce_bounds(bounds),
            date_start=start,
            date_end=end,
            telemetry=telemetry,
            weather=weather,
            messages=messages,
        )
        load_elapsed = time.monotonic() - load_started
        _log.info(
            "cold-load build_ff1_replay_assets session_key=%s year=%s round=%s type=%s "
            "telemetry=%s duration_s=%.2f ok=%s",
            session_key,
            year,
            round_number,
            mapped,
            telemetry,
            load_elapsed,
            isinstance(ff1, dict) and bool(ff1.get("ok")),
        )
        if load_elapsed > 5.0:
            print(
                f"[ARIS] SLOW cold-load: {year} R{round_number} {mapped} "
                f"telemetry={telemetry} took {load_elapsed:.1f}s (session_key={session_key})",
                flush=True,
            )
        if not (isinstance(ff1, dict) and ff1.get("ok")):
            _log.info(
                "FastF1 replay assets unavailable session_key=%s year=%s round=%s type=%s — OpenF1 fallback may fill",
                session_key,
                year,
                round_number,
                mapped,
            )
            return
        _PACK_LOAD_ERROR.pop(session_key, None)
        pack = _REPLAY_PACKS.get(session_key)
        if pack is None:
            return
        _apply_ff1_to_pack(pack, ff1, synthetic_gps=bool(ff1.get("synthetic_gps")))
        if _ff1_pack_ready(pack):
            save_replay_pack_disk(session_key, pack)
        _log.info(
            "FastF1 replay upgrade OK session_key=%s year=%s round=%s telemetry=%s samples=%s stage=%s",
            session_key,
            year,
            round_number,
            telemetry,
            len((pack.get("ff1") or {}).get("pos_samples") or {}),
            replay_pack_stage(pack),
        )
    except Exception:
        _log.exception("FastF1 replay upgrade failed for session_key=%s", session_key)
        return


def _ff1_pack_ready(pack: dict[str, Any]) -> bool:
    """True when real FastF1 GPS is on the pack (not synthetic outline motion)."""
    ff1 = pack.get("ff1") or {}
    if ff1.get("synthetic_gps"):
        return False
    if pack.get("source") == "fastf1" and bool(ff1.get("pos_samples")):
        return True
    chunks = pack.get("pos_chunks") or ff1.get("pos_chunks") or []
    return pack.get("source") == "fastf1" and bool(chunks)


def _pos_chunk_tuple(item: Any) -> tuple[int, int] | None:
    if isinstance(item, dict):
        return int(item.get("lo") or 0), int(item.get("hi") or 0)
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return int(item[0]), int(item[1])
    return None


def _apply_pos_chunk_to_pack(pack: dict[str, Any], lo: int, hi: int, samples: dict[str, Any]) -> None:
    ff1 = dict(pack.get("ff1") or {})
    ff1["pos_samples"] = samples
    ff1["synthetic_gps"] = False
    ff1["pos_chunk_loaded"] = {"lo": int(lo), "hi": int(hi)}
    pack["ff1"] = ff1
    pack["pos_chunk_loaded"] = {"lo": int(lo), "hi": int(hi)}
    pack["source"] = "fastf1"
    pack.pop("path_traces", None)
    pack.pop("path_traces_v", None)
    if pack.get("path_x"):
        ensure_path_traces(pack)


def ensure_replay_pos_chunk(pack: dict[str, Any], lap: int) -> dict[str, Any]:
    """Swap the in-memory GPS window for `lap`. Disk only — never FastF1."""
    from backend.sessions import load_pos_chunk_disk, pos_chunk_range_for_lap

    year = pack.get("year")
    rnd = pack.get("round_number")
    mapped = str(pack.get("session_type") or "R")
    if not (year and rnd):
        return pack
    lo, hi = pos_chunk_range_for_lap(lap)
    loaded = pack.get("pos_chunk_loaded") or (pack.get("ff1") or {}).get("pos_chunk_loaded")
    if isinstance(loaded, dict) and int(loaded.get("lo") or -1) == lo and int(loaded.get("hi") or -1) == hi:
        return pack
    samples = load_pos_chunk_disk(int(year), int(rnd), mapped, lo, hi)
    if not samples:
        return pack
    _apply_pos_chunk_to_pack(pack, lo, hi, samples)
    return pack


async def peek_replay_pos_chunk(
    session_key: int,
    lap: int,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
) -> dict[str, Any]:
    """Prefetch endpoint: load the 10-lap GPS window for `lap` from disk."""
    decoded = decode_synthetic_session_key(session_key)
    if decoded is not None:
        year = year or decoded[0]
        round_number = round_number or decoded[1]
        if not session_type:
            session_type = decoded[2]
    hydrate_replay_pack_cache(session_key, year, round_number, session_type, log_hits=False)
    pack = _REPLAY_PACKS.get(session_key) or {}
    ensure_replay_pos_chunk(pack, int(lap))
    loaded = pack.get("pos_chunk_loaded")
    return {
        "session_key": session_key,
        "lap": int(lap),
        "pos_chunk_loaded": loaded,
        "ok": bool(loaded),
    }


def _schedule_ff1_upgrade(pack: dict[str, Any], session_key: int) -> None:
    if _ff1_pack_ready(pack):
        return
    year = pack.get("year")
    rnd = pack.get("round_number")
    if not (year and rnd):
        return
    _kick_pack_job(session_key, int(year), int(rnd), str(pack.get("session_type") or "R"))


def _trim_buckets(store: dict[tuple[int, int], list[Any]]) -> None:
    if len(store) <= _LOC_BUCKET_KEEP:
        return
    keys = sorted(store, key=lambda k: k[1])
    for key in keys[: len(keys) - (_LOC_BUCKET_KEEP - 16)]:
        store.pop(key, None)


def _trim_loc_buckets() -> None:
    _trim_buckets(_LOC_BUCKETS)


def _drop_excluded(rows: list[Any], year: int | None, round_number: int | None) -> list[Any]:
    from backend.calendar import next_race, weekend_excluded_codes

    excluded = set(weekend_excluded_codes(year, round_number))
    if not excluded:
        try:
            nxt = next_race()
            if year is None or (
                int(year) == int(nxt.year)
                and (round_number is None or int(round_number) == int(nxt.round_number))
            ):
                excluded |= weekend_excluded_codes(nxt.year, nxt.round_number)
        except Exception:
            pass
    if not excluded:
        return rows
    return [row for row in rows if getattr(row, "driver_code", None) not in excluded]


def _mask_aris_focus_strategy(
    rows: list[Any], year: int | None, round_number: int | None, current_lap: int | None
) -> list[Any]:
    """ARIS car: keep live GPS/pace, hide this driver's real Ferrari stints."""
    dutch = int(year or 0) == 2026 and int(round_number or 0) == 12
    if not dutch:
        try:
            from backend.calendar import next_race

            nxt = next_race()
            dutch = int(nxt.year) == 2026 and int(nxt.round_number) == 12
        except Exception:
            dutch = False
    if not dutch:
        return rows
    life = int(current_lap or 1)
    for row in rows:
        if getattr(row, "driver_code", None) != "HAM":
            continue
        try:
            row.compound = "M"
            row.tyre_life = life
            row.stint_number = 1
            row.pit_count = 0
        except Exception:
            pass
    return rows


def _pack_lock(session_key: int) -> asyncio.Lock:
    lock = _REPLAY_LOCKS.get(session_key)
    if lock is None:
        lock = asyncio.Lock()
        _REPLAY_LOCKS[session_key] = lock
    return lock


def _status_is_pit(status: str | None) -> bool:
    from backend.sessions import status_is_pit

    return status_is_pit(status)


def _as_markers(raw: Any) -> list[CircuitMarker]:
    out: list[CircuitMarker] = []
    for marker in raw or []:
        if isinstance(marker, CircuitMarker):
            out.append(marker)
        elif isinstance(marker, dict):
            try:
                out.append(CircuitMarker(**marker))
            except Exception:
                continue
    return out


def _green_flag_s(rc: list[Any], start: datetime | None) -> int | None:
    if start is None:
        return None
    for row in rc or []:
        if not isinstance(row, dict):
            continue
        blob = f"{row.get('flag') or ''} {row.get('message') or ''} {row.get('category') or ''}".upper()
        if "GREEN" not in blob and "LIGHTS OUT" not in blob:
            continue
        dt = _parse_dt(row.get("date"))
        if dt is None:
            continue
        elapsed = int((dt - start).total_seconds())
        if elapsed >= 0:
            return elapsed
    return None


def _race_start_s(pack: dict[str, Any]) -> int:
    """Seconds from session start to lights-out / lap 1. Skips formation."""
    gf = pack.get("green_flag_s")
    if isinstance(gf, int) and gf > 0:
        return gf
    start = pack.get("date_start")
    if not isinstance(start, datetime):
        return 0
    first: int | None = None
    for row in pack.get("laps") or []:
        if not isinstance(row, dict):
            continue
        if int(row.get("lap_number") or 0) != 1:
            continue
        ds = _parse_dt(row.get("date_start"))
        if ds is None:
            continue
        elapsed = int((ds - start).total_seconds())
        if elapsed >= 0 and (first is None or elapsed < first):
            first = elapsed
    return int(first or 0)


def _flag_from_rc(rc: list[Any]) -> str:
    """Current flag from the OpenF1 race-control stream (sector yellows, not last yellow forever)."""
    red = False
    sc = False
    vsc = False
    yellow_sectors: set[str] = set()
    for row in rc or []:
        if not isinstance(row, dict):
            continue
        raw_flag = str(row.get("flag") or "").upper()
        blob = f"{raw_flag} {row.get('category') or ''} {row.get('message') or ''}".upper()
        if raw_flag == "CHEQUERED" or "CHEQUERED" in blob:
            continue
        if "INFRINGEMENT" in blob or "NO FURTHER INVESTIGATION" in blob:
            continue
        if "NOTED" in blob and "YELLOW" in blob:
            continue
        sector = None
        hit = re.search(r"SECTOR\s+(\d+)", blob)
        if hit:
            sector = hit.group(1)
        if raw_flag == "RED" or ("RED" in blob and "FLAG" in blob and "LIGHT" not in blob):
            red = True
            sc = False
            vsc = False
            yellow_sectors.clear()
            continue
        if raw_flag == "GREEN" or "TRACK CLEAR" in blob or "GREEN FLAG" in blob or "LIGHTS OUT" in blob:
            red = False
            sc = False
            vsc = False
            yellow_sectors.clear()
            continue
        if raw_flag == "CLEAR" or "CLEAR IN TRACK" in blob:
            if sector:
                yellow_sectors.discard(sector)
                yellow_sectors.discard("all")
            else:
                yellow_sectors.clear()
            continue
        if "VSC" in blob or "VIRTUAL SAFETY" in blob:
            if "ENDING" in blob or "IN THIS LAP" in blob:
                vsc = False
            else:
                vsc = True
                red = False
            continue
        if raw_flag == "SC" or "SAFETY CAR" in blob:
            if any(tok in blob for tok in ("IN THIS LAP", "LIGHTS OFF", "ENDING", "STANDING START")):
                sc = False
            elif "LIGHTS ON" in blob or "DEPLOY" in blob or raw_flag == "SC":
                sc = True
                red = False
            continue
        if "STANDING START" in blob or "OVERTAKE ENABLED" in blob:
            sc = False
            vsc = False
            red = False
            continue
        if raw_flag in {"YELLOW", "DOUBLE YELLOW", "DOUBLE_YELLOW"} or "YELLOW" in blob:
            yellow_sectors.add(sector or "all")
    if red:
        return "RED"
    if sc:
        return "SC"
    if vsc:
        return "VSC"
    if yellow_sectors:
        return "YELLOW"
    return "GREEN"


def _sc_position(
    positions: list[LivePosition],
    path_x: list[float],
    path_y: list[float],
    leader_code: str | None,
) -> LivePosition | None:
    if not path_x or not path_y:
        return None
    from backend.sessions import point_on_path

    lead = next((p for p in positions if p.driver_code == leader_code), None)
    if lead is None:
        on_track = [p for p in positions if not p.is_pitted and not p.is_dnf]
        if not on_track:
            return None
        lead = on_track[0]
    frac = (float(lead.path_frac) - 0.03) % 1.0
    px, py = point_on_path(path_x, path_y, frac)
    return LivePosition(
        driver_code="SC",
        x=px,
        y=py,
        path_frac=frac,
        team_colour="#F4D03F",
        is_pitted=False,
        is_dnf=False,
        reason="SAFETY CAR",
    )


def _location_in_pit(
    px: float,
    py: float,
    status: str | None,
    path_x: list[float],
    path_y: list[float],
    pit_x: list[float],
    pit_y: list[float],
) -> bool:
    status_pit = _status_is_pit(status)
    if not pit_x or not path_x:
        return status_pit
    from backend.sessions import min_dist_to_path

    d_pit = min_dist_to_path(px, py, pit_x, pit_y)
    d_trk = min_dist_to_path(px, py, path_x, path_y)
    if d_pit + 5.0 < d_trk:
        return True
    if status_pit and d_pit <= d_trk + 8.0:
        return True
    return False


def _gps_usable(row: dict[str, Any], *, now: datetime | None = None, max_age_s: float = 20.0) -> bool:
    """Drop OpenF1 (0,0) placeholders and stale location rows."""
    try:
        x = float(row.get("x"))
        y = float(row.get("y"))
    except (TypeError, ValueError):
        return False
    if abs(x) < 1.0 and abs(y) < 1.0:
        return False
    if now is not None:
        stamp = _parse_dt(row.get("date"))
        if stamp is not None and (now - stamp).total_seconds() > max_age_s:
            return False
    return True


def _circ_mean_frac(fracs: list[float]) -> float | None:
    if len(fracs) < 4:
        return None
    sx = sum(math.cos(2.0 * math.pi * f) for f in fracs)
    sy = sum(math.sin(2.0 * math.pi * f) for f in fracs)
    if abs(sx) < 1e-9 and abs(sy) < 1e-9:
        return None
    ang = math.atan2(sy, sx)
    if ang < 0.0:
        ang += 2.0 * math.pi
    return ang / (2.0 * math.pi)


def _circ_delta(a: float, b: float) -> float:
    return (float(a) - float(b) + 0.5) % 1.0 - 0.5


def _grid_xy(path_x: list[float], path_y: list[float], grid_pos: int) -> tuple[float, float, float]:
    from backend.sessions import grid_slot_xy

    if not path_x or not path_y:
        return 0.0, 0.0, 0.0
    return grid_slot_xy(path_x, path_y, grid_pos)


async def _feed_bucket(
    store: dict[tuple[int, int], list[Any]],
    endpoint: str,
    session_key: int,
    as_of: datetime,
) -> list[Any]:
    ts = int(as_of.timestamp())
    bucket = ts - (ts % _LOC_BUCKET_S)
    key = (session_key, bucket)
    cached = store.get(key)
    if cached is not None:
        return cached
    start = datetime.fromtimestamp(bucket, tz=timezone.utc)
    end = start + timedelta(seconds=_LOC_BUCKET_S + 2)
    try:
        data = await _openf1(
            endpoint,
            {
                "session_key": session_key,
                "date>=": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "date<=": end.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            timeout=8.0,
        )
    except Exception:
        data = []
    rows = data if isinstance(data, list) else []
    store[key] = rows
    _trim_buckets(store)
    return rows


async def _location_bucket(session_key: int, as_of: datetime) -> list[Any]:
    return await _feed_bucket(_LOC_BUCKETS, "location", session_key, as_of)


async def _car_bucket(session_key: int, as_of: datetime) -> list[Any]:
    return await _feed_bucket(_CAR_BUCKETS, "car_data", session_key, as_of)


async def _empty_rows() -> list[Any]:
    return []


async def _prefetch_replay_feed(session_key: int, start: datetime) -> None:
    """Replay GPS is FastF1; OpenF1 location/car buckets are live-only."""
    return


def _cars_from_samples(pack: dict[str, Any], clock: datetime) -> dict[int, dict[str, Any]]:
    from backend.sessions import sample_ff1_car

    ff1 = pack.get("ff1") or {}
    series = ff1.get("car_samples") or pack.get("car_samples") or {}
    if not isinstance(series, dict) or not series:
        return {}
    codes: dict[int, str] = pack.get("codes") or {}
    num_by_code: dict[str, int] = ff1.get("num_by_code") or {v: k for k, v in codes.items()}
    t_epoch = clock.timestamp()
    out: dict[int, dict[str, Any]] = {}
    for key, samples in series.items():
        if not samples:
            continue
        hit = sample_ff1_car(samples, t_epoch)
        if hit is None:
            continue
        if isinstance(key, int) or (isinstance(key, str) and str(key).isdigit()):
            num = int(key)
        else:
            num = num_by_code.get(str(key))
        if num is None:
            continue
        throttle, brake, speed, drs = hit
        out[num] = {"throttle": throttle, "brake": brake, "speed": speed, "drs": drs}
    return out


def _locations_at(rows: list[Any], as_of: datetime) -> dict[int, dict[str, Any]]:
    latest: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get("date"))
        if dt is not None and dt > as_of:
            continue
        num = row.get("driver_number")
        if num is None:
            continue
        prev = latest.get(int(num))
        prev_dt = _parse_dt(prev.get("date")) if prev else None
        if prev is None or prev_dt is None or (dt is not None and dt >= prev_dt):
            latest[int(num)] = row
    return latest


def _positions_from_locations(
    latest: dict[int, dict[str, Any]],
    *,
    codes: dict[int, str],
    colours: dict[int, str],
    bounds: Any,
    path_x: list[float],
    path_y: list[float],
    eliminated: set[str],
) -> list[LivePosition]:
    from backend.sessions import compute_path_distance

    positions: list[LivePosition] = []
    for num, row in latest.items():
        raw_x = float(row.get("x") or 0)
        raw_y = float(row.get("y") or 0)
        if bounds is not None:
            from backend.sessions import _apply_bounds

            px, py = _apply_bounds(raw_x, raw_y, bounds)
        else:
            px, py = raw_x, raw_y
        frac = 0.0
        if path_x and path_y:
            try:
                frac = float(compute_path_distance(px, py, path_x, path_y))
            except Exception:
                frac = 0.0
        code = codes.get(num, f"D{num}")
        in_pit = str(row.get("status") or "").lower() in {"pit", "inpit"}
        is_dnf = code in eliminated
        reason = None
        if is_dnf:
            reason = "OUT"
        elif in_pit:
            reason = "In pit"
        positions.append(
            LivePosition(
                driver_code=code,
                x=px,
                y=py,
                path_frac=frac,
                team_colour=colours.get(num),
                is_pitted=in_pit,
                is_dnf=is_dnf,
                reason=reason,
            )
        )
    return positions


def _quali_phase(windows: list[dict[str, Any]], elapsed_s: int) -> str | None:
    current = None
    for win in windows:
        if win["start_s"] <= elapsed_s <= win["end_s"]:
            return str(win["id"])
        if elapsed_s >= win["start_s"]:
            current = str(win["id"])
    return current


def _driver_reason(
    *,
    code: str,
    has_sample: bool,
    in_pit: bool,
    eliminated: bool,
    status: str,
    phase: str | None,
    q_times: dict[str, int | None] | None,
    started: bool,
) -> str | None:
    st = (status or "").lower()
    if "not start" in st or st == "dns":
        return "DNS"
    if any(tok in st for tok in ("retired", "dnf", "accident", "collision", "withdrew")):
        return "DNF"
    if eliminated:
        if phase and q_times:
            if phase in {"Q2", "SQ2"} and not q_times.get("q2_ms"):
                return "OUT Q1"
            if phase in {"Q3", "SQ3"} and not q_times.get("q3_ms"):
                return "OUT Q2" if q_times.get("q2_ms") else "OUT Q1"
        return "OUT"
    if not started or not has_sample:
        return "Not started"
    if in_pit:
        return "In pit"
    return None


def precompute_ghost_for_session(
    session_data: dict,
    driver_code: str,
    aris_recommendations: list,
) -> dict[int, dict | None]:
    """Pre-compute ghost state for every lap of a historical session.

    Returns a dict keyed by lap number; values are ghost_to_dict() output.
    The ghost is a parallel ARIS run from lap 1 (not gated on divergence).

    Only runs on Race and Sprint Race sessions (session_type R or S).
    """
    session_type = str(session_data.get("session_type") or "")
    if session_type not in ("R", "S"):
        return {}

    try:
        from aris.ghost import (
            GhostPlan,
            plan_from_pits,
            schedule_from_recommendation,
            score_parallel_ghost,
        )
        from aris.physics.tires import normalize_compound
        from aris.state import RaceState
    except Exception:
        return {}

    laps_data: list[dict] = session_data.get("laps") or []
    total_laps = int(session_data.get("total_laps") or len(laps_data) or 60)
    if not laps_data:
        return {}

    ordered = sorted(laps_data, key=lambda r: int(r.get("lap_number") or 0))
    first = next((r for r in ordered if int(r.get("lap_number") or 0) > 0), None)
    if first is None:
        return {}
    start_compound = normalize_compound(str(first.get("compound") or "MEDIUM"))

    recs = list(aris_recommendations or [])
    plan_rec = None
    for want in (1, 2):
        plan_rec = next((r for r in recs if int(r.get("lap") or 0) == want), None)
        if plan_rec is not None:
            break
    if plan_rec is None and recs:
        plan_rec = min(recs, key=lambda r: int(r.get("lap") or 10**9))

    decision_lap = int((plan_rec or {}).get("lap") or 1)
    explicit = session_data.get("plan")
    if isinstance(explicit, dict) and explicit.get("pit_laps") is not None:
        plan = plan_from_pits(
            list(explicit.get("pit_laps") or []),
            list(explicit.get("compounds") or explicit.get("pit_compounds") or []),
            start_compound,
            label=str(explicit.get("label") or explicit.get("name") or ""),
            total_laps=total_laps,
        )
    elif plan_rec:
        plan = schedule_from_recommendation(
            plan_rec,
            start_compound=start_compound,
            lap_number=decision_lap,
            total_laps=total_laps,
        )
    else:
        plan = GhostPlan(
            pit_laps=[],
            pit_compounds=[],
            start_compound=start_compound,
            aris_action="STAY_OUT",
            decision_lap=1,
        )

    template = RaceState(
        session_id=int(session_data.get("session_key") or 0),
        driver_id=int(session_data.get("driver_id") or 0),
        driver_code=driver_code,
        driver_name=driver_code,
        year=int(session_data.get("year") or 2024),
        round_no=int(session_data.get("round_no") or 1),
        country=str(session_data.get("country") or "Bahrain"),
        lap_number=1,
        compound=start_compound,
        tyre_life=1,
        fuel_kg=float(first.get("fuel_kg") or 110.0),
        laps_remaining=max(0, total_laps - 1),
        total_laps=total_laps,
        position=int(first.get("position") or 10),
        track_status=str(first.get("track_status") or "1"),
    )
    typical = 90.0
    times = [float(r["lap_time_s"]) for r in ordered if r.get("lap_time_s")]
    if times:
        typical = float(sorted(times)[len(times) // 2])
        if typical < 30:
            typical = 90.0

    return score_parallel_ghost(
        template_state=template,
        lap_rows=ordered,
        plan=plan,
        typical_lap_s=typical,
        field_cum_by_lap=session_data.get("field_cum_by_lap") or None,
    )


def recompute_ghost_from_plan(
    *,
    year: int,
    round_number: int,
    driver: str,
    current_lap: int,
    pit_laps: list[int],
    compounds: list[str],
    session_key: int | None = None,
    label: str = "",
) -> dict[str, Any]:
    """Recompute ghost ticks from ``current_lap`` under a new pit schedule.

    Ticks before ``current_lap`` are kept from the cached original plan.
    Fast when a replay pack is already warm (no FastF1 fetch).
    """
    from aris.ghost import r2_ghost_tick

    code = str(driver).upper()
    pack: dict | None = None
    if session_key:
        pack = _REPLAY_PACKS.get(int(session_key))
    if pack is None:
        for _key, candidate in list(_REPLAY_PACKS.items()):
            if not isinstance(candidate, dict):
                continue
            if int(candidate.get("year") or 0) == int(year) and int(
                candidate.get("round_number") or 0
            ) == int(round_number):
                pack = candidate
                session_key = int(_key) if session_key is None else int(session_key)
                break
    if pack is None:
        raise RuntimeError("replay pack not warm — load the race before ghost-recompute")

    sk = int(session_key or pack.get("session_key") or 0)
    plan = {
        "pit_laps": [int(x) for x in pit_laps],
        "compounds": [str(c) for c in compounds],
        "label": label,
    }
    cache_key = _ghost_driver_key(year, round_number, code)
    prior = dict(_GHOST_CACHE.get(cache_key) or {})
    session_data = _session_data_from_pack(pack, code, sk, plan)
    if not session_data.get("laps"):
        raise RuntimeError("pack has no laps for ghost recompute")
    fresh = precompute_ghost_for_session(session_data, code, [])
    if not fresh:
        raise RuntimeError("ghost recompute produced no ticks")
    lap_cut = max(1, int(current_lap))
    merged: dict[int, dict | None] = {}
    for lap, tick in prior.items():
        if int(lap) < lap_cut:
            merged[int(lap)] = tick
    for lap, tick in fresh.items():
        if int(lap) >= lap_cut:
            merged[int(lap)] = tick
    _GHOST_PLAN[cache_key] = plan
    _store_ghost_map(year, round_number, sk, code, merged)
    ticks_out = []
    for lap in sorted(k for k in merged if int(k) >= lap_cut):
        tick = merged.get(int(lap))
        if not isinstance(tick, dict):
            continue
        ticks_out.append(r2_ghost_tick(int(lap), tick, plan["pit_laps"]))
    return {
        "driver": code,
        "year": int(year),
        "round": int(round_number),
        "current_lap": lap_cut,
        "strategy": {
            "pit_laps": plan["pit_laps"],
            "compounds": plan["compounds"],
            "label": label,
        },
        "ticks": ticks_out,
    }


def _session_data_from_pack(
    pack: dict, driver: str, session_key: int, plan: dict | None = None
) -> dict[str, Any]:
    """Build precompute_ghost_for_session input from a warm replay pack (no DB)."""
    code = str(driver).upper()
    laps_data: list[dict] = []
    for row in pack.get("laps") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("driver_code") or "").upper() != code:
            continue
        lap_n = int(row.get("lap_number") or 0)
        if lap_n < 1:
            continue
        pit_in = bool(row.get("is_pit_in_lap") or row.get("pit_in"))
        compound = str(row.get("compound") or "HARD")
        dur = row.get("lap_duration")
        if dur is None:
            dur = row.get("lap_time_s")
        try:
            lap_s = float(dur) if dur is not None else None
        except (TypeError, ValueError):
            lap_s = None
        laps_data.append(
            {
                "lap_number": lap_n,
                "real_action": f"PIT_NOW_{compound.upper()}" if pit_in else "STAY_OUT",
                "compound": compound,
                "tyre_life": int(row.get("tyre_life") or 1),
                "fuel_kg": 30.0,
                "position": int(row.get("position") or 10),
                "lap_time_s": lap_s,
                "track_status": str(row.get("track_status") or "1"),
            }
        )
    return {
        "session_key": session_key,
        "session_type": str(pack.get("session_type") or "R"),
        "year": int(pack.get("year") or 0),
        "round_no": int(pack.get("round_number") or 0),
        "country": str(pack.get("country") or pack.get("circuit") or ""),
        "laps": laps_data,
        "total_laps": int(
            pack.get("total_laps") or max((r["lap_number"] for r in laps_data), default=0)
        ),
        "driver_id": 0,
        "field_cum_by_lap": _field_cum_from_pack(pack),
        "plan": plan,
    }


async def replay_frame(
    session_key: int,
    as_of: datetime,
    *,
    year: int | None = None,
    round_number: int | None = None,
    driver: str | None = None,
    refresh: bool = False,
) -> ReplayFrameResponse:
    pack = await _ensure_replay_pack(
        session_key, year, round_number, refresh=refresh, wait_for="minimal"
    )
    start: datetime | None = pack.get("date_start")
    end: datetime | None = pack.get("date_end")
    clock = now_utc(as_of)
    if start is not None and clock < start:
        clock = start
    if end is not None and clock > end:
        clock = end
    duration = int((end - start).total_seconds()) if start and end else 0
    elapsed = int((clock - start).total_seconds()) if start else 0
    ff1 = pack.get("ff1") or {}
    source = str(pack.get("source") or "fastf1")
    from backend.sessions import quali_windows_for_session_type

    windows_raw = ff1.get("quali_windows") or quali_windows_for_session_type(str(pack.get("session_type") or ""))
    phase = _quali_phase(windows_raw, elapsed) if windows_raw else None
    laps = _laps_upto(pack.get("laps") or [], clock)
    race_lap = _current_race_lap(
        pack.get("laps") or [],
        clock,
        start,
        _race_start_s(pack) if str(pack.get("session_type") or "") in {"R", "S"} else pack.get("green_flag_s"),
    )
    ensure_replay_pos_chunk(pack, race_lap)
    ff1 = pack.get("ff1") or {}
    weather_row = _weather_at(pack.get("weather") or [], clock)
    rc_upto = []
    for row in pack.get("race_control") or []:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get("date"))
        if dt is None or dt <= clock:
            rc_upto.append(row)
    codes: dict[int, str] = pack.get("codes") or {}
    eliminated = _eliminated_codes(rc_upto, codes)
    q_times: dict[str, dict[str, int | None]] = ff1.get("q_times") or {}
    status_by = ff1.get("status_by_code") or {}
    if phase:
        for code, qt in q_times.items():
            if phase in {"Q2", "SQ2"} and not qt.get("q2_ms") and not qt.get("q3_ms"):
                eliminated.add(code)
            if phase in {"Q3", "SQ3"} and not qt.get("q3_ms"):
                eliminated.add(code)
    locations: dict[int, dict[str, Any]] = {}
    cars = _cars_from_samples(pack, clock)
    has_ff1_pos = bool((ff1.get("pos_samples") or {}))
    if has_ff1_pos:
        source = "fastf1"
        pack["source"] = "fastf1"
    if not has_ff1_pos:
        traces = {}
    elif pack.get("path_traces") and pack.get("path_traces_v") == _PATH_TRACES_V:
        # Already computed (cached on the pack) — cheap dict read, stay on the loop.
        traces = pack["path_traces"]
    else:
        # First-frame-only cost: GPS sample counts are capped but still non-trivial
        # (fix-pass item 4) — move off the event loop so it can't stall other requests.
        traces = await run_sync(ensure_path_traces, pack)
    timing_rows = _timing_rows_from_payload(
        codes=codes,
        colours=pack.get("colours") or {},
        positions=_position_map(pack.get("positions") or [], clock),
        laps=laps,
        stints=pack.get("stints") or [],
        intervals=_latest_by_date(pack.get("intervals") or [], clock),
        eliminated=eliminated,
        locations=locations,
        as_of=clock,
        cars=cars,
    )
    stalls: list[list[float]] = pack.get("pit_stalls") or []
    pit_lane_x: list[float] = pack.get("pit_lane_x") or []
    pit_lane_y: list[float] = pack.get("pit_lane_y") or []
    from backend.sessions import (
        GPS_CORR_EPSILON_LIVE,
        compute_path_distance,
        correct_path_frac,
        point_on_path,
        sample_ff1_position,
        sample_path_trace,
    )

    path_x = pack.get("path_x") or []
    path_y = pack.get("path_y") or []
    colours: dict[int, str] = pack.get("colours") or {}
    num_by_code: dict[str, int] = ff1.get("num_by_code") or {v: k for k, v in codes.items()}
    pos_samples: dict[str, list[Any]] = ff1.get("pos_samples") or {}
    positions: list[LivePosition] = []
    t_epoch = clock.timestamp()
    all_codes = sorted(set(num_by_code) | set(status_by) | {r.driver_code for r in timing_rows} | set(pos_samples))
    pos_by_code = {r.driver_code: r.position for r in timing_rows}
    for i, code in enumerate(all_codes):
        num = num_by_code.get(code)
        sample = sample_ff1_position(pos_samples.get(code) or [], t_epoch) if has_ff1_pos else None
        has_gps = sample is not None or (num is not None and num in locations)
        started = has_gps or any(int(r.get("driver_number") or -1) == num for r in laps if num is not None)
        in_pit = False
        is_dnf = code in eliminated
        px = py = None
        frac = 0.0
        st_txt = ""
        traced = sample_path_trace(traces.get(code) or {}, t_epoch) if traces.get(code) else None
        timing = _openf1_timing_frac(laps, num, clock) if num is not None else None
        if traced is not None and path_x and path_y:
            gps = float(traced)
            frac = float(correct_path_frac(timing, gps, GPS_CORR_EPSILON_LIVE) if timing is not None else gps)
            px, py = point_on_path(path_x, path_y, frac)
            if sample is not None:
                st_txt = sample[2]
                in_pit = _location_in_pit(sample[0], sample[1], st_txt, path_x, path_y, pit_lane_x, pit_lane_y)
        elif sample is not None:
            px, py, st_txt = sample
            in_pit = _location_in_pit(px, py, st_txt, path_x, path_y, pit_lane_x, pit_lane_y)
            if path_x and path_y and not in_pit:
                try:
                    gps = float(compute_path_distance(px, py, path_x, path_y))
                    frac = float(correct_path_frac(timing, gps, GPS_CORR_EPSILON_LIVE) if timing is not None else gps)
                except Exception:
                    frac = 0.0
        elif num is not None and num in locations:
            row = locations[num]
            raw_x = float(row.get("x") or 0)
            raw_y = float(row.get("y") or 0)
            bounds = pack.get("bounds")
            if bounds is not None:
                from backend.sessions import _apply_bounds

                px, py = _apply_bounds(raw_x, raw_y, bounds)
            else:
                px, py = raw_x, raw_y
            in_pit = _location_in_pit(px, py, str(row.get("status") or ""), path_x, path_y, pit_lane_x, pit_lane_y)
            if path_x and path_y and not in_pit:
                try:
                    gps = float(compute_path_distance(px, py, path_x, path_y))
                    frac = float(correct_path_frac(timing, gps, GPS_CORR_EPSILON_LIVE) if timing is not None else gps)
                except Exception:
                    frac = 0.0
        reason = _driver_reason(
            code=code,
            has_sample=has_gps,
            in_pit=in_pit,
            eliminated=is_dnf,
            status=str(status_by.get(code) or ""),
            phase=phase,
            q_times=q_times.get(code),
            started=started,
        )
        parked = reason in {"DNS", "DNF", "OUT", "OUT Q1", "OUT Q2"}
        if parked:
            in_pit = True
            if stalls:
                stall = stalls[i % len(stalls)]
                px, py = float(stall[0]), float(stall[1])
            elif pit_lane_x and pit_lane_y:
                px, py = point_on_path(pit_lane_x, pit_lane_y, min(0.85, 0.15 + 0.03 * i))
            elif path_x:
                px, py = float(path_x[0]), float(path_y[0])
            if pit_lane_x and pit_lane_y and px is not None and py is not None:
                try:
                    frac = float(compute_path_distance(px, py, pit_lane_x, pit_lane_y))
                except Exception:
                    frac = 0.0
            else:
                frac = 0.0
        elif in_pit and pit_lane_x and pit_lane_y and px is not None and py is not None:
            try:
                frac = float(compute_path_distance(px, py, pit_lane_x, pit_lane_y))
            except Exception:
                frac = min(0.85, 0.2 + 0.03 * i)
            px, py = point_on_path(pit_lane_x, pit_lane_y, frac)
        elif reason == "Not started" or px is None or py is None:
            grid_pos = pos_by_code.get(code) or (i + 1)
            if path_x and path_y:
                px, py, frac = _grid_xy(path_x, path_y, int(grid_pos))
            else:
                continue
            in_pit = False
        if px is None or py is None:
            continue
        qt = q_times.get(code) or {}
        positions.append(
            LivePosition(
                driver_code=code,
                x=px,
                y=py,
                path_frac=frac,
                team_colour=colours.get(num) if num is not None else None,
                is_pitted=in_pit,
                is_dnf=is_dnf or reason in {"DNF", "DNS"},
                reason=None if reason == "Not started" else reason,
            )
        )
        for row in timing_rows:
            if row.driver_code != code:
                continue
            row.reason = None if reason == "Not started" else reason
            row.in_pit = in_pit or row.in_pit
            row.eliminated = is_dnf or row.eliminated
            row.q1_ms = qt.get("q1_ms")
            row.q2_ms = qt.get("q2_ms")
            row.q3_ms = qt.get("q3_ms")
    weather = _weather_from_row(weather_row, is_live=True)
    quali_windows = [QualiWindow(**w) for w in windows_raw if isinstance(w, dict) and "id" in w]
    from backend.calendar import weekend_excluded_codes

    excluded = weekend_excluded_codes(pack.get("year"), pack.get("round_number"))
    if excluded:
        timing_rows = [r for r in timing_rows if r.driver_code not in excluded]
        positions = [p for p in positions if p.driver_code not in excluded]
    session_flag = _flag_from_rc(rc_upto)
    if session_flag in {"SC", "VSC"}:
        leader_code = timing_rows[0].driver_code if timing_rows else None
        sc = _sc_position(positions, path_x, path_y, leader_code)
        if sc is not None:
            positions.append(sc)
    markers = _as_markers(pack.get("map_markers"))
    drs_segs = [list(s) for s in (pack.get("drs_segments") or [])]
    has_drs = any(m.kind == "drs_detect" for m in markers)
    if (not has_drs or not drs_segs) and path_x and path_y:
        from backend.sessions import drs_on_path
        from backend.calendar import get_round as _get_round

        circuit_key = None
        try:
            if pack.get("year") and pack.get("round_number"):
                circuit_key = _get_round(int(pack["year"]), int(pack["round_number"])).circuit_key
        except Exception:
            circuit_key = None
        # First-frame-only cost (fix-pass item 4): cached on the pack afterwards,
        # so run the one-time computation off the event loop.
        segs, marks = await run_sync(drs_on_path, path_x, path_y, circuit_key)
        if not drs_segs:
            drs_segs = segs
        if not has_drs:
            markers = markers + list(marks)
        pack["map_markers"] = markers
        pack["drs_segments"] = drs_segs
    race_start = (
        _race_start_s(pack) if str(pack.get("session_type") or "") in {"R", "S"} else pack.get("green_flag_s")
    )
    current_lap = _current_race_lap(laps, clock, start, int(race_start) if race_start is not None else 0)
    if driver:
        _schedule_ghost_precompute(pack, session_key, driver)
    ghost_value, ghost_reason = _ghost_at_lap(
        pack.get("year") or year,
        pack.get("round_number") or round_number,
        session_key,
        current_lap,
        driver,
    )
    ghost_value = _ghost_on_track(ghost_value, positions, driver)

    return ReplayFrameResponse(
        session_key=session_key,
        as_of=clock,
        elapsed_s=max(0, elapsed),
        duration_s=max(0, duration),
        date_start=start,
        date_end=end,
        timing=LiveTimingResponse(
            is_live=True,
            session_key=session_key,
            rows=timing_rows,
            last_success_utc=clock,
            current_lap=current_lap,
            rainfall=bool(weather.rainfall) if weather.rainfall is not None else False,
        ),
        weather=weather,
        positions=LivePositionsResponse(
            is_live=True,
            positions=positions,
            last_success_utc=clock,
            circuit_path=pack.get("circuit_path"),
            pit_lane_x=pit_lane_x,
            pit_lane_y=pit_lane_y,
            markers=markers,
            drs_segments=drs_segs,
        ),
        source=source,
        quali_phase=phase,
        quali_windows=quali_windows,
        green_flag_s=int(race_start) if race_start is not None else None,
        session_flag=session_flag,
        ready=True,
        ghost=ghost_value,
        ghost_reason=ghost_reason,
    )


# fix-pass item 10: `live_timing`/`live_positions`/etc all called `replay_frame`
# (a full recompute) independently, wrapped only in a 1s TTL HTTP cache keyed on
# `as_of` — which changes on every replay tick, so the cache never actually hit
# and every panel poll triggered its own full frame computation. This wrapper
# decouples "what frame are we at" from "recompute that frame": the first caller
# for a given (session_key, as_of, driver) computes it, a short in-process TTL
# cache serves near-simultaneous repeats, and an in-flight map makes concurrent
# callers (timing + positions polled together) await the *same* computation
# instead of racing to recompute it twice.
_FRAME_CACHE: dict[tuple[int, str, str], tuple[float, ReplayFrameResponse]] = {}
_FRAME_LOCKS: dict[tuple[int, str, str], asyncio.Lock] = {}
_FRAME_CACHE_TTL_S = 1.0
_FRAME_CACHE_MAX = 64


def _frame_cache_key(session_key: int, as_of: datetime, driver: str | None) -> tuple[int, str, str]:
    return (int(session_key), as_of.isoformat(), str(driver or ""))


def _evict_stale_frames(now: float) -> None:
    if len(_FRAME_CACHE) <= _FRAME_CACHE_MAX:
        return
    cutoff = now - (_FRAME_CACHE_TTL_S * 10)
    stale = [k for k, (t, _resp) in _FRAME_CACHE.items() if t < cutoff]
    for k in stale:
        _FRAME_CACHE.pop(k, None)


async def cached_replay_frame(
    session_key: int,
    as_of: datetime,
    *,
    year: int | None = None,
    round_number: int | None = None,
    driver: str | None = None,
    refresh: bool = False,
) -> ReplayFrameResponse:
    """Shared, deduped `replay_frame` — see module note above (fix-pass item 10)."""
    if refresh:
        return await replay_frame(
            session_key, as_of, year=year, round_number=round_number, driver=driver, refresh=refresh
        )
    key = _frame_cache_key(session_key, as_of, driver)
    cached = _FRAME_CACHE.get(key)
    now = time.monotonic()
    if cached is not None and (now - cached[0]) < _FRAME_CACHE_TTL_S:
        return cached[1]
    lock = _FRAME_LOCKS.setdefault(key, asyncio.Lock())
    try:
        async with lock:
            cached = _FRAME_CACHE.get(key)
            now = time.monotonic()
            if cached is not None and (now - cached[0]) < _FRAME_CACHE_TTL_S:
                return cached[1]
            result = await replay_frame(
                session_key, as_of, year=year, round_number=round_number, driver=driver, refresh=refresh
            )
            now = time.monotonic()
            _FRAME_CACHE[key] = (now, result)
            _evict_stale_frames(now)
            return result
    finally:
        # Drop the lock from the map once nobody else holds it so `_FRAME_LOCKS`
        # doesn't grow unbounded across a long replay session. A waiter that
        # grabbed this same Lock object just before the check below keeps
        # working fine either way — this only affects whether *future* callers
        # reuse or recreate the Lock for this key.
        if not lock.locked():
            _FRAME_LOCKS.pop(key, None)


def _frame_as_of_key(value: datetime | str) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if raw.endswith("+00:00"):
            return raw[:-6] + "Z"
        return raw
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    iso = dt.astimezone(timezone.utc).isoformat()
    if iso.endswith("+00:00"):
        return iso[:-6] + "Z"
    return iso


def _index_by_code(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("driver_code")): row for row in rows if row.get("driver_code")}


def _strip_frame_outline(frame: ReplayFrameResponse) -> ReplayFrameResponse:
    return frame.model_copy(
        update={
            "positions": frame.positions.model_copy(
                update={
                    "circuit_path": None,
                    "pit_lane_x": [],
                    "pit_lane_y": [],
                    "markers": [],
                    "drs_segments": [],
                }
            ),
            "is_delta": False,
        }
    )


def _replay_frame_delta(
    prev: dict[str, Any], curr: dict[str, Any], template: ReplayFrameResponse
) -> ReplayFrameResponse | None:
    prev_rows = list((prev.get("timing") or {}).get("rows") or [])
    curr_rows = list((curr.get("timing") or {}).get("rows") or [])
    prev_pos = list((prev.get("positions") or {}).get("positions") or [])
    curr_pos = list((curr.get("positions") or {}).get("positions") or [])
    if _index_by_code(prev_rows).keys() != _index_by_code(curr_rows).keys():
        return None
    if _index_by_code(prev_pos).keys() != _index_by_code(curr_pos).keys():
        return None
    prev_row_by = _index_by_code(prev_rows)
    prev_pos_by = _index_by_code(prev_pos)
    changed_rows = [row for row in curr_rows if row != prev_row_by.get(str(row.get("driver_code")))]
    changed_pos = [row for row in curr_pos if row != prev_pos_by.get(str(row.get("driver_code")))]
    return template.model_copy(
        update={
            "is_delta": True,
            "date_start": None,
            "date_end": None,
            "quali_windows": [],
            "timing": template.timing.model_copy(
                update={"rows": [LiveTimingRow.model_validate(row) for row in changed_rows]}
            ),
            "positions": template.positions.model_copy(
                update={
                    "positions": [LivePosition.model_validate(row) for row in changed_pos],
                    "circuit_path": None,
                    "pit_lane_x": [],
                    "pit_lane_y": [],
                    "markers": [],
                    "drs_segments": [],
                }
            ),
        }
    )


_LAST_FRAMES: dict[tuple[int, str], dict[str, Any]] = {}
_LAST_FRAME_ORDER: list[tuple[int, str]] = []
_LAST_FRAMES_MAX = 48


def clear_replay_frame_delta_cache() -> None:
    _LAST_FRAMES.clear()
    _LAST_FRAME_ORDER.clear()


def _store_last_frame(key: tuple[int, str], dump: dict[str, Any]) -> None:
    _LAST_FRAMES[key] = dump
    _LAST_FRAME_ORDER.append(key)
    while len(_LAST_FRAME_ORDER) > _LAST_FRAMES_MAX:
        old = _LAST_FRAME_ORDER.pop(0)
        if old not in _LAST_FRAMES:
            continue
        # Keep the newest dump for a repeated key.
        if old == key:
            continue
        later = old in _LAST_FRAME_ORDER
        if not later:
            _LAST_FRAMES.pop(old, None)


def encode_replay_wire_frame(
    frame: ReplayFrameResponse,
    *,
    prev_as_of: datetime | None = None,
    force_full: bool = False,
) -> ReplayFrameResponse:
    """Strip static outline and optionally emit a per-car delta vs prev_as_of."""
    stripped = _strip_frame_outline(frame)
    curr = stripped.model_dump(mode="json")
    cache_key = (int(stripped.session_key), _frame_as_of_key(stripped.as_of))
    out = stripped
    if not force_full and prev_as_of is not None:
        prev = _LAST_FRAMES.get((int(stripped.session_key), _frame_as_of_key(prev_as_of)))
        if prev is not None:
            delta = _replay_frame_delta(prev, curr, stripped)
            if delta is not None:
                out = delta
    _store_last_frame(cache_key, curr)
    return out


async def serve_replay_frame(
    session_key: int,
    as_of: datetime,
    *,
    year: int | None = None,
    round_number: int | None = None,
    driver: str | None = None,
    refresh: bool = False,
    prev_as_of: datetime | None = None,
    force_full: bool = False,
) -> ReplayFrameResponse:
    frame = await cached_replay_frame(
        session_key, as_of, year=year, round_number=round_number, driver=driver, refresh=refresh
    )
    return encode_replay_wire_frame(frame, prev_as_of=prev_as_of, force_full=force_full)


async def replay_ready(
    session_key: int,
    year: int | None = None,
    round_number: int | None = None,
    *,
    refresh: bool = False,
    driver: str | None = None,
) -> dict[str, Any]:
    from backend.sessions import quali_windows_for_session_type

    pack = await _ensure_replay_pack(
        session_key, year, round_number, refresh=refresh, wait_for="minimal"
    )
    start = pack.get("date_start")
    end = pack.get("date_end")
    windows = (pack.get("ff1") or {}).get("quali_windows") or quali_windows_for_session_type(
        str(pack.get("session_type") or "")
    )
    samples = (pack.get("ff1") or {}).get("pos_samples") or {}
    traces = ensure_path_traces(pack) if samples else {}

    _schedule_ghost_precompute(pack, session_key, driver)

    return {
        "session_key": session_key,
        "ready": _stage_rank(pack) >= _PACK_STAGE_RANK["minimal"],
        "stage": replay_pack_stage(pack),
        "source": "fastf1" if _ff1_pack_ready(pack) else pack.get("source"),
        "date_start": start.isoformat() if hasattr(start, "isoformat") else start,
        "date_end": end.isoformat() if hasattr(end, "isoformat") else end,
        "session_type": pack.get("session_type"),
        "quali_windows": windows,
        "green_flag_s": (
            _race_start_s(pack) if str(pack.get("session_type") or "") in {"R", "S"} else pack.get("green_flag_s")
        ),
        "cars": len(pack.get("codes") or {}),
        "has_map": bool(pack.get("path_x")),
    }


def _pack_in_flight(session_key: int) -> bool:
    lock = _REPLAY_LOCKS.get(session_key)
    job = _PACK_JOBS.get(session_key)
    return (
        (lock is not None and lock.locked())
        or session_key in _FF1_UPGRADE_INFLIGHT
        or (job is not None and not job.done())
    )


def _pack_status_label(session_key: int) -> str:
    """Cheap peek: `loading` / `ready` / `error`. Ready means stage >= minimal."""
    pack = _REPLAY_PACKS.get(session_key)
    if pack is not None and _stage_rank(pack) >= _PACK_STAGE_RANK["minimal"]:
        return "ready"
    if _PACK_LOAD_ERROR.get(session_key) and not _pack_in_flight(session_key):
        return "error"
    return "loading"


def _pack_status_payload(
    session_key: int,
    *,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
) -> dict[str, Any]:
    pack = _REPLAY_PACKS.get(session_key) or {}
    status = _pack_status_label(session_key)
    started = _PACK_LOAD_STARTED.get(session_key)
    elapsed_s = round(time.monotonic() - started, 1) if started else None
    start = pack.get("date_start")
    end = pack.get("date_end")
    stage = replay_pack_stage(pack) if pack else "empty"
    flags = _pack_flags(pack)
    return {
        "session_key": session_key,
        "session_id": session_key,
        "status": status,
        "ready": status == "ready",
        "stage": stage,
        "progress": _pack_progress(pack),
        "flags": flags,
        "laps_ready": flags["laps_ready"],
        "map_ready": flags["map_ready"],
        "gps_ready": flags["gps_ready"],
        "weather_ready": flags["weather_ready"],
        "error": _PACK_LOAD_ERROR.get(session_key) if status == "error" else None,
        "elapsed_s": elapsed_s,
        "source": pack.get("source") or "fastf1",
        "date_start": start.isoformat() if hasattr(start, "isoformat") else start,
        "date_end": end.isoformat() if hasattr(end, "isoformat") else end,
        "session_type": pack.get("session_type") or session_type,
        "year": pack.get("year") or year,
        "round_number": pack.get("round_number") or round_number,
        "green_flag_s": (
            _race_start_s(pack)
            if str(pack.get("session_type") or session_type or "") in {"R", "S"}
            else pack.get("green_flag_s")
        ),
        "pos_chunks": pack.get("pos_chunks") or (pack.get("ff1") or {}).get("pos_chunks") or [],
        "pos_chunk_loaded": pack.get("pos_chunk_loaded")
        or (pack.get("ff1") or {}).get("pos_chunk_loaded"),
    }


async def peek_replay_pack_status(
    session_key: int,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
    *,
    refresh: bool = False,
    outline: bool = False,
) -> dict[str, Any]:
    """Non-blocking pack status for the frontend cold-load poller (fix-pass item 3).

    Kicks the FastF1 job in the background when the pack is not yet at full,
    then returns immediately with stage/flags so the client can start at minimal.
    """
    decoded = decode_synthetic_session_key(session_key)
    if decoded is not None:
        year = year or decoded[0]
        round_number = round_number or decoded[1]
        if not session_type:
            session_type = decoded[2]
    from backend.calendar import assert_replay_session_type

    assert_replay_session_type(session_type or "R")
    hydrate_replay_pack_cache(
        session_key, year, round_number, session_type, log_hits=False
    )
    pack = _REPLAY_PACKS.get(session_key)
    need_job = refresh or replay_pack_stage(pack) != "full" or not _ff1_pack_ready(pack or {})
    if need_job and (refresh or not _pack_in_flight(session_key)):
        _kick_pack_job(
            session_key,
            year,
            round_number,
            session_type,
            refresh=refresh,
        )
    payload = _pack_status_payload(
        session_key, year=year, round_number=round_number, session_type=session_type
    )
    if outline:
        payload.update(_outline_from_pack(_REPLAY_PACKS.get(session_key)))
    return payload


async def ghost_for_driver(
    *,
    year: int,
    round_number: int,
    driver: str,
    lap: int,
    session_key: int | None = None,
) -> dict[str, Any]:
    """HTTP helper: ghost tick for a driver/lap. Computes on first miss."""
    code = str(driver).upper()
    ghost, reason = _ghost_at_lap(year, round_number, int(session_key or 0), lap, code)
    if ghost is None and session_key:
        pack = _REPLAY_PACKS.get(int(session_key))
        if pack is None:
            pack = await _ensure_replay_pack(int(session_key), year, round_number, wait_for="minimal")
        key = _ghost_driver_key(year, round_number, code)
        if key not in _GHOST_CACHE:
            await asyncio.to_thread(_precompute_ghost_sync, pack, int(session_key), code)
        ghost, reason = _ghost_at_lap(year, round_number, int(session_key), lap, code)
    return {"driver": code, "lap": int(lap), "ghost": ghost, "ghost_reason": reason}


_PATH_TRACES_V = 3


def _align_pack_gps(pack: dict[str, Any]) -> None:
    ff1 = pack.get("ff1")
    if not isinstance(ff1, dict):
        return
    from backend.sessions import align_pos_samples_to_path

    samples, changed = align_pos_samples_to_path(ff1.get("pos_samples") or {}, pack.get("bounds"))
    if changed:
        ff1["pos_samples"] = samples
        pack["ff1"] = ff1
        pack.pop("path_traces", None)
        pack.pop("path_traces_v", None)


def ensure_path_traces(pack: dict[str, Any]) -> dict[str, dict[str, list[float]]]:
    _align_pack_gps(pack)
    existing = pack.get("path_traces")
    if (
        isinstance(existing, dict)
        and existing
        and pack.get("path_traces_v") == _PATH_TRACES_V
    ):
        return existing
    from backend.sessions import build_path_traces

    ff1 = pack.get("ff1") or {}
    traces = build_path_traces(
        ff1.get("pos_samples") or {},
        pack.get("path_x") or [],
        pack.get("path_y") or [],
    )
    if traces:
        pack["path_traces"] = traces
        pack["path_traces_v"] = _PATH_TRACES_V
    return traces


async def replay_path(
    session_key: int, year: int | None = None, round_number: int | None = None
) -> dict[str, Any]:
    pack = await _ensure_replay_pack(session_key, year, round_number, wait_for="minimal")
    samples = (pack.get("ff1") or {}).get("pos_samples") or {}
    traces = ensure_path_traces(pack) if samples else {}
    if traces and replay_pack_is_complete(pack):
        save_replay_pack_disk(session_key, pack)
    start = pack.get("date_start")
    return {
        "session_key": session_key,
        "source": pack.get("source"),
        "date_start": start.isoformat() if hasattr(start, "isoformat") else start,
        "traces": traces,
        "drivers": list(traces),
    }


async def live_timing(
    as_of: datetime | None = None,
    replay_session_key: int | None = None,
    *,
    status: LiveStatus | None = None,
) -> LiveTimingResponse:
    if replay_session_key is not None:
        clock = as_of
        if clock is None:
            pack = _REPLAY_PACKS.get(replay_session_key)
            start = pack.get("date_start") if isinstance(pack, dict) else None
            clock = start if isinstance(start, datetime) else now_utc()
        frame = await cached_replay_frame(replay_session_key, clock)
        return frame.timing
    if status is None:
        status = await live_status(as_of, replay_session_key=replay_session_key)
    if not status.is_live or status.session_key is None:
        return LiveTimingResponse(is_live=False, rows=[], last_success_utc=status.last_success_utc, rainfall=False)
    try:
        rows = await _timing_from_openf1(status.session_key or 0, as_of, persist=as_of is None)
        _STATE["last_success"] = now_utc(as_of)
        current = max((r.lap_number or 0) for r in rows) if rows else None
        rainfall = False
        try:
            rainfall = await get_live_rainfall(int(status.session_key))
        except Exception:
            rainfall = False
        rows = _mask_aris_focus_strategy(
            _drop_excluded(rows, status.year, status.round_number),
            status.year,
            status.round_number,
            current,
        )
        fl_row = next((r for r in rows if r.fastest_lap), None)
        return LiveTimingResponse(
            is_live=True,
            session_key=status.session_key,
            rows=rows,
            last_success_utc=_STATE["last_success"],
            current_lap=current or None,
            rainfall=rainfall,
            session_flag=status.session_flag,
            fastest_lap_ms=fl_row.best_lap_ms if fl_row else None,
            fastest_lap_driver=fl_row.driver_code if fl_row else None,
        )
    except Exception:
        return LiveTimingResponse(
            is_live=True,
            session_key=status.session_key,
            rows=[],
            last_success_utc=_STATE.get("last_success"),
            rainfall=False,
        )


async def _live_map_pack(
    status_year: int | None, status_round: int | None
) -> tuple[Any, Any, list[float], list[float]]:
    """Return the weekend outline + bounds. Never block the live GPS path after the first hit."""
    pack = _STATE.get("cmap_pack")
    if isinstance(pack, dict) and pack.get("path_x"):
        return pack.get("circuit_path"), pack.get("bounds"), pack["path_x"], pack["path_y"]
    year = status_year
    rnd = status_round
    try:
        from backend.calendar import next_race

        nxt = next_race()
        year = nxt.year or year
        rnd = nxt.round_number or rnd
    except Exception:
        pass
    if not (year and rnd):
        return None, None, [], []
    try:
        from backend.models import CircuitPathXY
        from backend.sessions import circuit_map_quick

        cmap = await asyncio.wait_for(run_sync(circuit_map_quick, int(year), int(rnd)), timeout=6.0)
        if cmap is None or not cmap.available or not cmap.x:
            return None, None, [], []
        out = {
            "circuit_path": CircuitPathXY(x=cmap.x, y=cmap.y),
            "bounds": cmap.bounds,
            "path_x": list(cmap.x),
            "path_y": list(cmap.y),
        }
        _STATE["cmap_pack"] = out
        return out["circuit_path"], out["bounds"], out["path_x"], out["path_y"]
    except Exception:
        return None, None, [], []


async def live_positions(
    as_of: datetime | None = None,
    replay_session_key: int | None = None,
    simulated: bool = False,
    *,
    status: LiveStatus | None = None,
) -> LivePositionsResponse:
    if replay_session_key is not None:
        clock = as_of
        if clock is None:
            pack = _REPLAY_PACKS.get(replay_session_key)
            start = pack.get("date_start") if isinstance(pack, dict) else None
            clock = start if isinstance(start, datetime) else now_utc()
        frame = await cached_replay_frame(replay_session_key, clock)
        return frame.positions
    from backend.sessions import GPS_CORR_EPSILON_LIVE, grid_path_frac, nudge_path_frac

    if status is None:
        status = await live_status(
            as_of, replay_session_key=replay_session_key, simulated=simulated
        )
    circuit_path, bounds, path_x, path_y = await _live_map_pack(status.year, status.round_number)

    if not status.is_live or status.session_key is None:
        return LivePositionsResponse(
            is_live=bool(status.is_live),
            positions=[],
            last_success_utc=status.last_success_utc,
            circuit_path=circuit_path,
        )
    codes = await _driver_code_map(status.session_key)
    colours: dict[int, str] = _STATE.get("driver_colours") or {}
    latest: dict[int, dict[str, Any]] = dict(_STATE.get("locations") or {}) if _feed_session_key() == status.session_key else {}
    if not latest and not _STATE.get("locations"):
        now = now_utc(as_of)
        loc: list[Any] = []
        windows = (8, 120, 600)
        sess_row = _STATE.get("session") if _feed_session_key() == status.session_key else None
        end = _parse_dt((sess_row or {}).get("date_end")) if isinstance(sess_row, dict) else None
        if end is None:
            meta = await _openf1("sessions", {"session_key": status.session_key})
            if isinstance(meta, list) and meta and isinstance(meta[0], dict):
                end = _parse_dt(meta[0].get("date_end"))
        if end is not None and end < now:
            since = (end - timedelta(seconds=12)).strftime("%Y-%m-%dT%H:%M:%S")
            try:
                data = await _openf1(
                    "location",
                    {"session_key": status.session_key, "date>": since},
                )
            except Exception:
                data = []
            if isinstance(data, list) and data:
                loc = data
        if not loc:
            for window in windows:
                since = (now - timedelta(seconds=window)).strftime("%Y-%m-%dT%H:%M:%S")
                try:
                    data = await _openf1(
                        "location",
                        {"session_key": status.session_key, "date>": since},
                    )
                except Exception:
                    data = []
                if isinstance(data, list) and data:
                    loc = data
                    break
        if isinstance(loc, list):
            for row in loc:
                if not isinstance(row, dict) or not _gps_usable(row):
                    continue
                num = row.get("driver_number")
                if num is None:
                    continue
                latest[int(num)] = row
            if _feed_session_key() == status.session_key:
                _STATE["locations"] = latest
    eliminated = set(_STATE.get("eliminated") or set())
    if isinstance(_STATE.get("race_control"), list):
        eliminated |= _eliminated_codes(_STATE.get("race_control") or [], codes)
    if isinstance(_STATE.get("laps"), list):
        eliminated |= _inactive_from_laps(_STATE.get("laps") or [], codes)
    _STATE["eliminated"] = eliminated
    prev_fracs: dict[str, float] = dict(_STATE.get("live_frac") or {})
    cars = _STATE.get("car_data") if isinstance(_STATE.get("car_data"), dict) else {}
    raw_laps: list[Any] = _STATE.get("laps") if isinstance(_STATE.get("laps"), list) else []
    clock = as_of or now_utc()
    race_lap_frac = _race_lap_frac_live(raw_laps, clock)
    grid_by_num: dict[int, int] = {}
    for rec in _STATE.get("positions") or []:
        if not isinstance(rec, dict) or rec.get("driver_number") is None:
            continue
        try:
            grid_by_num[int(rec["driver_number"])] = int(rec.get("position") or 0)
        except (TypeError, ValueError):
            continue
    positions: list[LivePosition] = []
    for num, row in latest.items():
        if not isinstance(row, dict) or not _gps_usable(row):
            continue
        raw_x = float(row.get("x") or 0)
        raw_y = float(row.get("y") or 0)
        if bounds is not None:
            from backend.sessions import _apply_bounds

            px, py = _apply_bounds(raw_x, raw_y, bounds)
        else:
            px, py = raw_x, raw_y
        code = codes.get(num, f"D{num}")
        is_dnf = code in eliminated
        if is_dnf:
            prev_fracs.pop(code, None)
            continue
        frac = 0.0
        if path_x and path_y:
            try:
                timing = _openf1_timing_frac(raw_laps, int(num), clock)
                frac = float(
                    nudge_path_frac(
                        prev_fracs.get(code),
                        px,
                        py,
                        path_x,
                        path_y,
                        timing_frac=timing,
                        epsilon=GPS_CORR_EPSILON_LIVE,
                    )
                )
                if race_lap_frac < 0.02:
                    frac = grid_path_frac(grid_by_num.get(int(num)))
            except Exception:
                frac = float(prev_fracs.get(code) or 0.0)
        car = cars.get(num) or {}
        spd_kph = _float(car.get("speed"))
        positions.append(
            LivePosition(
                driver_code=code,
                x=px,
                y=py,
                path_frac=frac,
                team_colour=colours.get(num),
                is_pitted=_status_is_pit(str(row.get("status") or "")),
                is_dnf=False,
                speed_ms=(spd_kph / 3.6) if spd_kph is not None else None,
            )
        )
    flag = str(status.session_flag or "").upper()
    cluster = _circ_mean_frac([p.path_frac for p in positions if not p.is_pitted])
    if cluster is not None and flag in {"SC", "VSC", "RED"} and path_x and path_y:
        from backend.sessions import point_on_path

        code_num = {v: k for k, v in codes.items()}
        for pos in positions:
            if pos.is_pitted or pos.is_dnf:
                continue
            if abs(_circ_delta(pos.path_frac, cluster)) <= 0.06:
                continue
            num = code_num.get(pos.driver_code)
            car = cars.get(num) if num is not None else {}
            try:
                speed = float((car or {}).get("speed") or 0.0)
            except (TypeError, ValueError):
                speed = 0.0
            if speed > 8.0:
                continue
            pos.path_frac = cluster
            try:
                pos.x, pos.y = point_on_path(path_x, path_y, cluster)
            except Exception:
                pass
    for pos in positions:
        if not pos.is_dnf:
            prev_fracs[pos.driver_code] = float(pos.path_frac)
    _STATE["live_frac"] = prev_fracs
    return LivePositionsResponse(
        is_live=True,
        positions=_drop_excluded(positions, status.year, status.round_number),
        last_success_utc=_STATE.get("last_success"),
        circuit_path=circuit_path,
    )


def _laps_response_from_raw(
    raw: list[Any],
    codes: dict[int, str],
    stints: list[Any],
    as_of: datetime | None,
    session_key: int | None,
) -> LiveLapsResponse:
    filtered = _laps_upto(raw if isinstance(raw, list) else [], as_of)
    best = _best_ms_from_laps(filtered, as_of)
    out: list[LapRow] = []
    current = 0
    for row in filtered:
        if not isinstance(row, dict):
            continue
        num = row.get("driver_number")
        if num is None:
            continue
        n = int(num)
        if not _lap_completed(row, as_of):
            continue
        ms = _ms(row.get("lap_duration"))
        lap_no = int(row.get("lap_number") or 0)
        current = max(current, lap_no)
        pit_out = bool(row.get("is_pit_out_lap"))
        pit_in = bool(row.get("is_pit_in_lap") or row.get("pit_in_lap"))
        stint_comp = next(
            (
                s.get("compound")
                for s in stints
                if isinstance(s, dict)
                and int(s.get("driver_number") or 0) == n
                and int(s.get("lap_start") or 1) <= lap_no
            ),
            None,
        )
        end_ms = row.get("end_time_ms")
        try:
            end_time_ms = int(end_ms) if end_ms is not None and end_ms != "" else None
        except (TypeError, ValueError):
            end_time_ms = None
        tyre = row.get("tyre_life")
        try:
            tyre_life = int(tyre) if tyre is not None and tyre != "" else None
        except (TypeError, ValueError):
            tyre_life = None
        pos = row.get("position")
        try:
            position = int(pos) if pos is not None and pos != "" else None
        except (TypeError, ValueError):
            position = None
        out.append(
            LapRow(
                driver_code=str(row.get("driver_code") or codes.get(n, f"D{n}")),
                lap_number=lap_no,
                lap_time_ms=ms,
                sector1_ms=_ms(row.get("duration_sector_1")),
                sector2_ms=_ms(row.get("duration_sector_2")),
                sector3_ms=_ms(row.get("duration_sector_3")),
                is_personal_best=ms is not None and best.get(n) == ms,
                pit_out_lap=pit_out,
                pit_in_lap=pit_in,
                compound=_compound_letter(row.get("compound") or stint_comp),
                tyre_life=tyre_life,
                position=position,
                end_time_ms=end_time_ms,
                track_status=str(row["track_status"]) if row.get("track_status") else None,
            )
        )
    return LiveLapsResponse(
        is_live=True,
        session_key=session_key,
        current_lap=current or None,
        laps=out,
    )


def _stints_from_lap_rows(rows: list[LapRow]) -> list[StintRow]:
    grouped: dict[str, list[LapRow]] = {}
    for lap in rows:
        grouped.setdefault(lap.driver_code, []).append(lap)
    stints: list[StintRow] = []
    for code, laps in grouped.items():
        ordered = sorted(laps, key=lambda r: r.lap_number)
        current: list[LapRow] = []
        stint_no = 1
        prev_comp: str | None = None
        for lap in ordered:
            new_stint = bool(lap.pit_out_lap) or (
                prev_comp is not None and lap.compound is not None and lap.compound != prev_comp
            )
            if current and new_stint:
                times = [r.lap_time_ms for r in current if r.lap_time_ms]
                avg = sum(times) / len(times) if times else None
                stints.append(
                    StintRow(
                        driver_code=code,
                        stint_number=stint_no,
                        compound=current[0].compound,
                        lap_start=current[0].lap_number,
                        lap_end=current[-1].lap_number,
                        total_laps=current[-1].lap_number - current[0].lap_number + 1,
                        average_lap_ms=avg,
                    )
                )
                stint_no += 1
                current = [lap]
            else:
                current.append(lap)
            prev_comp = lap.compound or prev_comp
        if current:
            times = [r.lap_time_ms for r in current if r.lap_time_ms]
            avg = sum(times) / len(times) if times else None
            stints.append(
                StintRow(
                    driver_code=code,
                    stint_number=stint_no,
                    compound=current[0].compound,
                    lap_start=current[0].lap_number,
                    lap_end=current[-1].lap_number,
                    total_laps=current[-1].lap_number - current[0].lap_number + 1,
                    average_lap_ms=avg,
                )
            )
    return stints


async def live_laps(
    as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveLapsResponse:
    if replay_session_key is not None:
        pack = await _ensure_replay_pack(replay_session_key, wait_for="minimal")
        clock = now_utc(as_of) if as_of is not None else pack.get("date_end")
        if not isinstance(clock, datetime):
            clock = now_utc()
        return _laps_response_from_raw(
            pack.get("laps") or [],
            pack.get("codes") or {},
            pack.get("stints") or [],
            clock,
            replay_session_key,
        )
    status = await live_status(as_of)
    if not status.is_live or status.session_key is None:
        return LiveLapsResponse(is_live=False, laps=[])
    codes = await _driver_code_map(status.session_key)
    raw = _STATE.get("laps") if _feed_session_key() == status.session_key else None
    if not isinstance(raw, list) or not raw:
        raw = await _openf1("laps", {"session_key": status.session_key})
        if isinstance(raw, list):
            _STATE["laps"] = raw
    stints = _STATE.get("stints") if isinstance(_STATE.get("stints"), list) else []
    return _laps_response_from_raw(
        raw if isinstance(raw, list) else [],
        codes,
        stints,
        as_of,
        status.session_key,
    )


def _telemetry_from_samples(
    samples: list[Any],
    driver_code: str,
    clock: datetime,
    window_s: float = 75.0,
) -> LiveTelemetryResponse:
    want = driver_code.upper()
    t_end = clock.timestamp()
    t0 = t_end - window_s
    t_s: list[float] = []
    throttle: list[float] = []
    speed: list[float] = []
    brake: list[float] = []
    rpm: list[float] = []
    for rec in samples:
        if not rec:
            continue
        ts = float(rec[0])
        if ts < t0 or ts > t_end + 0.25:
            continue
        t_s.append(round(ts - t0, 3))
        throttle.append(float(rec[1]))
        brake.append(float(rec[2]))
        speed.append(float(rec[3]))
        rpm.append(0.0)
    return LiveTelemetryResponse(
        is_live=True,
        driver_code=want,
        t_s=t_s,
        throttle=throttle,
        speed=speed,
        brake=brake,
        rpm=rpm,
    )


def _car_samples_for_driver(pack: dict[str, Any], driver_code: str) -> list[Any]:
    want = driver_code.upper()
    ff1 = pack.get("ff1") or {}
    series = ff1.get("car_samples") or pack.get("car_samples") or {}
    if not isinstance(series, dict):
        return []
    if want in series:
        return series[want] or []
    codes: dict[int, str] = pack.get("codes") or {}
    num = next((n for n, c in codes.items() if c == want), None)
    if num is None:
        return []
    return series.get(num) or series.get(str(num)) or []


async def _telemetry_from_car_buckets(
    session_key: int, driver_num: int, clock: datetime, window_s: float = 75.0
) -> LiveTelemetryResponse:
    start = clock - timedelta(seconds=window_s)
    rows: list[Any] = []
    cursor = start
    while cursor <= clock + timedelta(seconds=1):
        chunk = await _car_bucket(session_key, cursor)
        if isinstance(chunk, list):
            rows.extend(chunk)
        cursor += timedelta(seconds=_LOC_BUCKET_S)
    t0 = None
    t_s: list[float] = []
    throttle: list[float] = []
    speed: list[float] = []
    brake: list[float] = []
    rpm: list[float] = []
    window_start = clock - timedelta(seconds=window_s)
    for row in rows:
        if not isinstance(row, dict):
            continue
        if int(row.get("driver_number") or -1) != driver_num:
            continue
        dt = _parse_dt(row.get("date"))
        if dt is None or dt < window_start or dt > clock:
            continue
        if t0 is None:
            t0 = dt
        t_s.append(round((dt - t0).total_seconds(), 3))
        throttle.append(float(row.get("throttle") or 0))
        speed.append(float(row.get("speed") or 0))
        brake.append(float(row.get("brake") or 0))
        rpm.append(float(row.get("rpm") or 0))
    return LiveTelemetryResponse(
        is_live=True,
        driver_code="",
        t_s=t_s,
        throttle=throttle,
        speed=speed,
        brake=brake,
        rpm=rpm,
    )


async def live_telemetry(
    driver_code: str, as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveTelemetryResponse:
    want = driver_code.upper()
    if replay_session_key is not None:
        pack = await _ensure_replay_pack(replay_session_key, wait_for="minimal")
        clock = now_utc(as_of) if as_of is not None else pack.get("date_end")
        if not isinstance(clock, datetime):
            clock = now_utc()
        samples = _car_samples_for_driver(pack, want)
        if samples:
            return _telemetry_from_samples(samples, want, clock)
        return LiveTelemetryResponse(is_live=True, driver_code=want)
    status = await live_status(as_of)
    empty = LiveTelemetryResponse(is_live=bool(status.is_live), driver_code=want)
    if not status.is_live or status.session_key is None:
        return empty
    codes = await _driver_code_map(status.session_key)
    num = next((n for n, c in codes.items() if c == want), None)
    if num is None:
        return empty
    traces = _STATE.get("car_trace") if isinstance(_STATE.get("car_trace"), dict) else {}
    rows = traces.get(num) or []
    t0 = None
    t_s: list[float] = []
    throttle: list[float] = []
    speed: list[float] = []
    brake: list[float] = []
    rpm: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get("date"))
        if dt is None:
            continue
        if t0 is None:
            t0 = dt
        t_s.append(round((dt - t0).total_seconds(), 3))
        throttle.append(float(row.get("throttle") or 0))
        speed.append(float(row.get("speed") or 0))
        brake.append(float(row.get("brake") or 0))
        rpm.append(float(row.get("rpm") or 0))
    return LiveTelemetryResponse(
        is_live=True,
        driver_code=want,
        t_s=t_s,
        throttle=throttle,
        speed=speed,
        brake=brake,
        rpm=rpm,
    )


async def live_intervals(
    as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveIntervalsResponse:
    timing = await live_timing(as_of, replay_session_key=replay_session_key)
    return LiveIntervalsResponse(
        is_live=timing.is_live,
        intervals=[
            LiveInterval(
                driver_code=r.driver_code,
                gap_to_leader_s=r.gap_to_leader_s,
                gap_to_ahead_s=r.gap_to_ahead_s,
            )
            for r in timing.rows
        ],
    )


async def live_race_control(
    as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveRaceControlResponse:
    if replay_session_key is not None:
        pack = await _ensure_replay_pack(replay_session_key, wait_for="minimal")
        clock = now_utc(as_of) if as_of is not None else pack.get("date_end")
        messages: list[RaceControlMessage] = []
        for row in pack.get("race_control") or []:
            if not isinstance(row, dict):
                continue
            dt = _parse_dt(row.get("date"))
            if isinstance(clock, datetime) and dt is not None and dt > clock:
                continue
            messages.append(
                RaceControlMessage(
                    utc_time=str(row.get("date") or ""),
                    lap=row.get("lap_number"),
                    flag=row.get("flag") or row.get("category"),
                    category=row.get("category"),
                    message=str(row.get("message") or ""),
                )
            )
        return LiveRaceControlResponse(is_live=True, messages=messages)
    status = await live_status(as_of, replay_session_key=replay_session_key)
    if not status.is_live or status.session_key is None:
        return LiveRaceControlResponse(is_live=False, messages=[])
    raw = _STATE.get("race_control") if isinstance(_STATE.get("race_control"), list) else []
    if not raw:
        try:
            raw = await _openf1("race_control", {"session_key": status.session_key})
            if isinstance(raw, list):
                _STATE["race_control"] = raw
        except Exception:
            raw = []
    messages: list[RaceControlMessage] = []
    if isinstance(raw, list):
        for row in raw:
            messages.append(
                RaceControlMessage(
                    utc_time=str(row.get("date") or ""),
                    lap=row.get("lap_number"),
                    flag=row.get("flag") or row.get("category"),
                    category=row.get("category"),
                    message=str(row.get("message") or ""),
                )
            )
    return LiveRaceControlResponse(is_live=True, messages=messages)


async def live_stints(
    as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveStintsResponse:
    if replay_session_key is not None:
        pack = await _ensure_replay_pack(replay_session_key, wait_for="minimal")
        clock = now_utc(as_of) if as_of is not None else pack.get("date_end")
        if not isinstance(clock, datetime):
            clock = now_utc()
        laps = _laps_response_from_raw(
            pack.get("laps") or [],
            pack.get("codes") or {},
            pack.get("stints") or [],
            clock,
            replay_session_key,
        )
        derived = _stints_from_lap_rows(laps.laps)
        return LiveStintsResponse(is_live=True, stints=derived)
    status = await live_status(as_of, replay_session_key=replay_session_key)
    if not status.is_live or status.session_key is None:
        return LiveStintsResponse(is_live=False, stints=[])
    codes = await _driver_code_map(status.session_key)
    try:
        raw = await _openf1("stints", {"session_key": status.session_key})
    except Exception:
        raw = []
    stints: list[StintRow] = []
    if isinstance(raw, list):
        for row in raw:
            num = row.get("driver_number")
            code = codes.get(int(num), f"D{num}") if num is not None else "?"
            start = int(row.get("lap_start") or 1)
            end = int(row.get("lap_end") or start)
            stints.append(
                StintRow(
                    driver_code=code,
                    stint_number=int(row.get("stint_number") or 1),
                    compound=row.get("compound"),
                    fresh_tyre=None,
                    lap_start=start,
                    lap_end=end,
                    total_laps=max(0, end - start + 1),
                    average_lap_ms=None,
                    deg_rate_ms_per_lap=None,
                )
            )
    return LiveStintsResponse(is_live=True, stints=stints)


async def live_weather(
    as_of: datetime | None = None,
    replay_session_key: int | None = None,
    *,
    status: LiveStatus | None = None,
) -> LiveWeatherResponse:
    if replay_session_key is not None:
        pack = await _ensure_replay_pack(replay_session_key, wait_for="minimal")
        clock = now_utc(as_of) if as_of is not None else pack.get("date_end")
        row = _weather_at(pack.get("weather") or [], clock if isinstance(clock, datetime) else None)
        return _weather_from_row(row, is_live=True)
    if status is None:
        status = await live_status(as_of, replay_session_key=replay_session_key)
    if not status.is_live or status.session_key is None:
        return LiveWeatherResponse(is_live=False)
    wkey = f"openf1:weather:{status.session_key}"
    raw = cache.get(wkey, TTL_WEATHER_LIVE)
    if raw is None:
        try:
            raw = await _openf1("weather", {"session_key": status.session_key}) or []
            cache.set(wkey, raw)
        except Exception:
            raw = []
    last = _weather_at(raw if isinstance(raw, list) else [], as_of)
    return _weather_from_row(last, is_live=True)


def _sse_iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sse_data(payload: dict[str, Any]) -> str:
    return "data: " + json.dumps(payload, separators=(",", ":")) + "\n\n"


def _dump_or_none(obj: Any) -> Any:
    if obj is None or isinstance(obj, Exception):
        return None
    return obj.model_dump(mode="json")


def _session_meta(status: LiveStatus | dict[str, Any] | None) -> tuple[Any, Any, Any]:
    if status is None:
        return (None, None, None)
    if isinstance(status, dict):
        return (status.get("session_key"), status.get("year"), status.get("round_number"))
    return (status.session_key, status.year, status.round_number)


def _slim_sse_payload(
    payload: dict[str, Any], *, full: bool
) -> dict[str, Any]:
    """Drop static outline/metadata on delta ticks so the client can keep last-known.

    `frontend-next/lib/liveFeed.ts` only applies `positions.circuit_path` when present
    (`applyCircuitPath` no-ops on omit) and always reads timing rows + lap/flag from
    `status` / `timing`. Those changing fields stay on every tick.
    """
    if full:
        return payload
    status = payload.get("status")
    if isinstance(status, dict):
        slim_status = dict(status)
        slim_status.pop("session", None)
        payload["status"] = slim_status
    positions = payload.get("positions")
    if isinstance(positions, dict):
        slim_pos = dict(positions)
        slim_pos.pop("circuit_path", None)
        slim_pos.pop("markers", None)
        slim_pos.pop("pit_lane_x", None)
        slim_pos.pop("pit_lane_y", None)
        slim_pos.pop("drs_segments", None)
        payload["positions"] = slim_pos
    return payload


async def sse_build_payload(
    replay_session_key: int | None = None,
    seq: int = 1,
    prev_meta: tuple[Any, Any, Any] | None = None,
) -> tuple[dict[str, Any], float, tuple[Any, Any, Any]]:
    """Build one SSE snapshot. Timing/weather/positions run in parallel off one status.

    Returns (payload, elapsed_ms, session_meta). Payload keys:
      seq, last_updated, full, status, timing, weather, positions
    """
    t0 = time.perf_counter()
    status = await live_status(replay_session_key=replay_session_key)
    timing, weather, positions = await asyncio.gather(
        live_timing(replay_session_key=replay_session_key, status=status),
        live_weather(replay_session_key=replay_session_key, status=status),
        live_positions(replay_session_key=replay_session_key, status=status),
        return_exceptions=True,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    meta = _session_meta(status)
    full = prev_meta != meta
    payload: dict[str, Any] = {
        "seq": seq,
        "last_updated": _sse_iso_now(),
        "full": full,
        "status": status.model_dump(mode="json"),
        "timing": _dump_or_none(timing),
        "weather": _dump_or_none(weather),
        "positions": _dump_or_none(positions),
    }
    payload = _slim_sse_payload(payload, full=full)
    return payload, elapsed_ms, meta


async def sse_generator(replay_session_key: int | None = None):
    """SSE ~1 Hz snapshots for the pit-wall (`GET /api/live/stream`).

    Served by the same uvicorn process as HTTP. Bind address/port come from
    the process command (Heroku ``$PORT``, locally 8765) — this generator
    does not open a socket and does not assume localhost in the handshake.

    Each `data:` JSON object:
      seq (int)            — monotonic per connection; 0 is the handshake stub
      last_updated (str)   — UTC timestamp for this tick
      full (bool)          — True when static metadata / circuit_path are included
      status, timing, weather, positions — same models as the REST live endpoints

    Delta-friendly: after the first full tick (and until session_key/year/round
    change), `status.session` and `positions.circuit_path` / markers / pit-lane
    are omitted. `frontend-next/lib/liveFeed.ts` keeps the last outline.
    """
    # First bytes must flush immediately so EventSource leaves CONNECTING.
    # Handshake is a comment frame — no host/port, so it is origin-agnostic.
    seq = 0
    prev_meta: tuple[Any, Any, Any] | None = None
    yield ": connected\n\n"
    yield _sse_data(
        {
            "seq": 0,
            "last_updated": _sse_iso_now(),
            "full": False,
            "status": {"is_live": False},
            "timing": {"rows": [], "is_live": False},
            "weather": None,
            "positions": {"positions": [], "is_live": False},
        }
    )
    while True:
        seq += 1
        try:
            payload, elapsed_ms, prev_meta = await asyncio.wait_for(
                sse_build_payload(replay_session_key, seq, prev_meta),
                timeout=4.0,
            )
        except TimeoutError:
            await asyncio.sleep(2)
            continue
        except Exception as extra:
            print(f"[ARIS] SSE tick failed: {extra}", flush=True)
            await asyncio.sleep(2)
            continue
        if seq == 1 or seq % 10 == 0:
            print(f"[ARIS] SSE tick seq={seq} {elapsed_ms:.0f}ms", flush=True)
        yield _sse_data(payload)
        is_live = bool((payload.get("status") or {}).get("is_live"))
        await asyncio.sleep(1 if is_live else 2)


async def _poll_location(session_key: int) -> None:
    now = datetime.now(timezone.utc)
    have = bool(_STATE.get("locations"))
    windows = (8, 20) if have else (12, 60, 300)
    loc: list[Any] = []
    for window in windows:
        since = (now - timedelta(seconds=window)).strftime("%Y-%m-%dT%H:%M:%S")
        data = await _openf1("location", {"session_key": session_key, "date>": since})
        if isinstance(data, list) and data:
            loc = data
            break
    latest: dict[int, dict[str, Any]] = dict(_STATE.get("locations") or {})
    seen: dict[int, datetime | None] = {}
    for row in loc:
        if not isinstance(row, dict):
            continue
        num = row.get("driver_number")
        if num is None:
            continue
        n = int(num)
        if not _gps_usable(row):
            continue
        stamp = _parse_dt(row.get("date"))
        prev = seen.get(n)
        if prev is not None and stamp is not None and stamp < prev:
            continue
        latest[n] = row
        seen[n] = stamp or prev
    if latest:
        _STATE["locations"] = latest
        _STATE["last_success"] = now_utc()


async def _poll_laps(session_key: int) -> None:
    laps = await _openf1("laps", {"session_key": session_key})
    if isinstance(laps, list):
        _STATE["laps"] = laps


async def _poll_position(session_key: int) -> None:
    have = bool(_STATE.get("latest_pos"))
    if have:
        since = (datetime.now(timezone.utc) - timedelta(seconds=45)).strftime("%Y-%m-%dT%H:%M:%S")
        raw = await _openf1("position", {"session_key": session_key, "date>": since})
    else:
        raw = await _openf1("position", {"session_key": session_key})
    latest: dict[int, int] = dict(_STATE.get("latest_pos") or {})
    if isinstance(raw, list):
        for row in raw:
            num = row.get("driver_number")
            pos = row.get("position")
            if num is None or pos is None:
                continue
            latest[int(num)] = int(pos)
        _STATE["latest_pos"] = _unique_positions(latest)


async def _poll_car_data(session_key: int) -> None:
    now = datetime.now(timezone.utc)
    since = (now - timedelta(seconds=4)).strftime("%Y-%m-%dT%H:%M:%S")
    raw = await _openf1("car_data", {"session_key": session_key, "date>": since})
    latest: dict[int, dict[str, Any]] = dict(_STATE.get("car_data") or {})
    traces: dict[int, list[dict[str, Any]]] = dict(_STATE.get("car_trace") or {})
    if not isinstance(raw, list):
        return
    for row in raw:
        if not isinstance(row, dict):
            continue
        num = row.get("driver_number")
        if num is None:
            continue
        n = int(num)
        latest[n] = row
        buf = list(traces.get(n) or [])
        buf.append(row)
        traces[n] = buf[-360:]
    if latest:
        _STATE["car_data"] = latest
        _STATE["car_trace"] = traces
        _STATE["last_success"] = now_utc()


async def poll_openf1_forever() -> None:
    """Background refresh that stays under OpenF1's 60 req/min paid cap."""
    slot = 0
    from backend.http_client import openf1_headers

    auth = openf1_headers()
    print(
        "[ARIS] OpenF1 live poller started · paid auth",
        "on" if auth.get("Authorization") else "MISSING",
        flush=True,
    )
    while True:
        try:
            sess = await peek_live_session()
            key = sess.get("session_key") if isinstance(sess, dict) else None
            if key is None:
                if _STATE.get("poll_session_key") is not None:
                    print("[ARIS] OpenF1 live window closed", flush=True)
                    _STATE["poll_session_key"] = None
                await asyncio.sleep(5)
                slot += 1
                continue
            if key is not None:
                key = int(key)
                if _STATE.get("poll_session_key") != key:
                    _STATE["poll_session_key"] = key
                    _STATE["locations"] = {}
                    _STATE["laps"] = []
                    _STATE["latest_pos"] = {}
                    _STATE["stints"] = []
                    _STATE["race_control"] = []
                    _STATE["car_data"] = {}
                    _STATE["car_trace"] = {}
                    _STATE["eliminated"] = set()
                    print(f"[ARIS] OpenF1 attached session {key}", flush=True)
                # Location on most slots so the map stays dense; other feeds share leftover quota.
                extra = slot % 5
                if extra != 4:
                    await _poll_location(key)
                elif extra == 4:
                    kind = (slot // 5) % 6
                    if kind == 0:
                        await _poll_car_data(key)
                    elif kind == 1:
                        await _poll_position(key)
                    elif kind == 2:
                        await _poll_laps(key)
                    elif kind == 3:
                        rc = await _openf1("race_control", {"session_key": key})
                        if isinstance(rc, list):
                            _STATE["race_control"] = rc
                            cache.set(f"openf1:rc-flag:{key}", rc)
                    elif kind == 4:
                        iv = await _openf1("intervals", {"session_key": key})
                        if isinstance(iv, list):
                            _STATE["intervals"] = _latest_by_date(iv, None)
                    else:
                        st = await _openf1("stints", {"session_key": key})
                        if isinstance(st, list):
                            _STATE["stints"] = st
                    if slot % 30 == 4:
                        await _driver_code_map(key)
                if slot == 0:
                    await _driver_code_map(key)
                    await _poll_position(key)
                    await _poll_laps(key)
        except asyncio.CancelledError:
            raise
        except Exception as extra:
            _STATE["error"] = str(extra)
            print(f"[ARIS] OpenF1 poll: {extra}", flush=True)
        slot += 1
        await asyncio.sleep(1.15)
