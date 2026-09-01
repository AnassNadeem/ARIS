"""FastF1 session loading: laps, summary, stints, telemetry, weather, results, messages."""

from __future__ import annotations

import gc
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.fastf1_guard import FASTF1_LOCK

import pandas as pd

from backend.cache import enable_fastf1_cache
from backend.models import (
    CircuitCorner,
    CircuitMapBounds,
    CircuitMapResponse,
    CircuitMarker,
    CircuitPathXY,
    CircuitPathPoint,
    CircuitPathResponse,
    CircuitSectorPath,
    CommentaryEvent,
    DriverFastest,
    LapRow,
    LapsResponse,
    LiveTimingResponse,
    MessagesResponse,
    RaceControlMessage,
    SectorRecord,
    SessionCarPosition,
    SessionEventsResponse,
    SessionPositionsAllResponse,
    SessionPositionsResponse,
    SessionResultRow,
    SessionResultsResponse,
    SessionSummary,
    StintRow,
    StintsResponse,
    TelemetryResponse,
    WeatherSeries,
    WeatherSummary,
)

_log = logging.getLogger(__name__)

_SESSION_CACHE: dict[str, Any] = {}
_SESSION_FLAGS: dict[str, tuple[bool, bool, bool]] = {}
_SCHEDULED_LAPS_MEM: dict[tuple[int, int], int | None] = {}


def _pack_cache_key(year: int, round_number: int, session_type: str) -> str:
    """Stable replay-pack / FastF1 session key — same string for read and write."""
    stype = str(session_type or "R").upper()
    return f"replay_pack_v1:{int(year)}:{int(round_number)}:{stype}"


POS_CHUNK_LAPS = 10


def process_rss_mb() -> int:
    """Current process RSS in megabytes. 0 if the platform cannot report it."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import POINTER, byref, sizeof, wintypes

            class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            fn = ctypes.windll.kernel32.K32GetProcessMemoryInfo
            fn.restype = wintypes.BOOL
            fn.argtypes = [wintypes.HANDLE, POINTER(_PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
            counters = _PROCESS_MEMORY_COUNTERS()
            counters.cb = sizeof(_PROCESS_MEMORY_COUNTERS)
            if fn(ctypes.windll.kernel32.GetCurrentProcess(), byref(counters), counters.cb):
                return int(counters.WorkingSetSize / (1024 * 1024))
            return 0
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 0


def log_process_mem(tag: str = "") -> int:
    """Emit `Process running mem=XXX` for Heroku logs. Returns RSS MB."""
    mb = process_rss_mb()
    suffix = f" {tag}" if tag else ""
    msg = f"Process running mem={mb}MB{suffix}"
    _log.info(msg)
    print(msg, flush=True)
    return mb


def pos_chunk_cache_key(year: int, round_number: int, session_type: str, lo: int, hi: int) -> str:
    """Disk key for a 10-lap position window, e.g. replay_pack_v1:2025:15:R:pos:0-10."""
    return f"{_pack_cache_key(year, round_number, session_type)}:pos:{int(lo)}-{int(hi)}"


def pos_chunk_range_for_lap(lap: int) -> tuple[int, int]:
    """Half-open lap window covering `lap` (1-indexed). Lap 1–10 → (0, 10)."""
    n = max(1, int(lap))
    lo = ((n - 1) // POS_CHUNK_LAPS) * POS_CHUNK_LAPS
    return lo, lo + POS_CHUNK_LAPS


def iter_pos_chunk_ranges(max_lap: int) -> list[tuple[int, int]]:
    max_lap = max(1, int(max_lap or 1))
    return [(lo, lo + POS_CHUNK_LAPS) for lo in range(0, max_lap, POS_CHUNK_LAPS)]


def save_pos_chunk_disk(
    year: int,
    round_number: int,
    session_type: str,
    lo: int,
    hi: int,
    pos_samples: dict[str, list[Any]],
) -> bool:
    key = pos_chunk_cache_key(year, round_number, session_type, lo, hi)
    try:
        from backend.cache import get_disk

        get_disk().set(
            key,
            {"pos_samples": pos_samples, "lo": int(lo), "hi": int(hi)},
            expire=None,
        )
        _log.info("pos chunk SAVE key=%s drivers=%s", key, len(pos_samples))
        return True
    except Exception:
        _log.exception("pos chunk SAVE failed key=%s", key)
        return False


def load_pos_chunk_disk(
    year: int, round_number: int, session_type: str, lo: int, hi: int
) -> dict[str, list[Any]] | None:
    key = pos_chunk_cache_key(year, round_number, session_type, lo, hi)
    try:
        from backend.cache import get_disk

        stored = get_disk().get(key)
    except Exception:
        return None
    if isinstance(stored, dict) and isinstance(stored.get("pos_samples"), dict):
        return stored["pos_samples"]
    return None


def drop_pos_chunk_keys(
    year: int | None,
    round_number: int | None,
    session_type: str | None,
    ranges: list[Any] | None,
) -> None:
    if not (year and round_number and ranges):
        return
    try:
        from backend.cache import get_disk

        store = get_disk()
    except Exception:
        return
    mapped = str(session_type or "R")
    for item in ranges:
        if isinstance(item, dict):
            lo, hi = int(item.get("lo") or 0), int(item.get("hi") or 0)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            lo, hi = int(item[0]), int(item[1])
        else:
            continue
        try:
            store.pop(pos_chunk_cache_key(int(year), int(round_number), mapped, lo, hi), default=None)
        except Exception:
            pass


def _scheduled_laps(year: int, round_number: int) -> int | None:
    """Race distance from track YAML — never loads FastF1."""
    key = (int(year), int(round_number))
    if key in _SCHEDULED_LAPS_MEM:
        return _SCHEDULED_LAPS_MEM[key]
    n: int | None = None
    try:
        from backend.calendar import get_round
        from aris.tracks import load_track_config

        rnd = get_round(year, round_number)
        cfg = load_track_config(rnd.country or rnd.circuit_key, year=year, round_no=round_number)
        val = int(getattr(cfg, "total_laps", 0) or 0)
        n = val if val > 0 else None
    except Exception:
        n = None
    _SCHEDULED_LAPS_MEM[key] = n
    return n


def _td_ms(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "total_seconds"):
        return int(value.total_seconds() * 1000)
    try:
        return int(float(value) * 1000)
    except (TypeError, ValueError):
        return None


def _num(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None


def _bool(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    try:
        if pd.isna(value):
            return False
    except TypeError:
        pass
    return bool(value)


def _get_fastf1_session(year: int, round_number: int, session_type: str):
    """Load by FastF1 round number; fall back to event name if numbering drifts."""
    enable_fastf1_cache()
    import fastf1

    stype = session_type.upper()
    if year == 2026:
        try:
            from backend.calendar import get_round

            rnd = get_round(year, round_number)
            ident = rnd.name or rnd.official_event_name
            if ident:
                return fastf1.get_session(year, ident, stype)
        except Exception:
            pass
    try:
        return fastf1.get_session(year, round_number, stype)
    except Exception as first:
        try:
            from backend.calendar import get_round

            rnd = get_round(year, round_number)
            ident = rnd.official_event_name or rnd.name
            return fastf1.get_session(year, ident, stype)
        except Exception:
            raise first from None


def _blocked_open_session(year: int, round_number: int, session_type: str) -> bool:
    stype = str(session_type or "R").upper()
    if stype not in {"R", "S"}:
        return False
    try:
        from backend.calendar import session_is_open

        return bool(session_is_open(int(year), int(round_number), stype))
    except Exception:
        return False


def clear_session_cache(
    year: int | None = None, round_number: int | None = None, session_type: str | None = None
) -> None:
    """Drop FastF1 in-process session objects so the next load hits FastF1."""
    if year is None:
        n = len(_SESSION_CACHE)
        _SESSION_CACHE.clear()
        _SESSION_FLAGS.clear()
        _log.info("FastF1 session cache cleared (%s entries)", n)
        return
    key = _pack_cache_key(year, round_number or 0, session_type or "R")
    _SESSION_CACHE.pop(key, None)
    _SESSION_FLAGS.pop(key, None)
    _log.info("FastF1 session cache invalidate key=%s", key)


def load_session(
    year: int,
    round_number: int,
    session_type: str,
    *,
    telemetry: bool = False,
    weather: bool = True,
    messages: bool = False,
    refresh: bool = False,
):
    from backend.calendar import ALLOWED_REPLAY_YEARS, ReplayYearBlocked

    y = int(year)
    if y not in ALLOWED_REPLAY_YEARS:
        msg = f"Replay request for year {y} — blocked (not in 2024–2026)"
        _log.info(msg)
        print(f"[ARIS] {msg}", flush=True)
        raise ReplayYearBlocked("Replay not allowed for this year")
    stype = str(session_type or "R").upper()
    if _blocked_open_session(year, round_number, stype):
        raise RuntimeError(f"refusing FastF1 load of open {year} R{round_number} {stype}")
    key = _pack_cache_key(year, round_number, stype)
    with FASTF1_LOCK:
        if refresh:
            _SESSION_CACHE.pop(key, None)
            _SESSION_FLAGS.pop(key, None)
        hit = _SESSION_CACHE.get(key)
        prev = _SESSION_FLAGS.get(key, (False, False, False))
        tel = bool(telemetry or prev[0])
        wx = bool(weather or prev[1])
        msg = bool(messages or prev[2])
        memory_hit = hit is not None and (tel, wx, msg) == prev
        _log.info("key=%s memory_hit=%s disk_hit=False", key, memory_hit)
        if memory_hit:
            return hit
        _log.info("Replay request for year %s — allowed", y)
        print(f"[ARIS] Replay request for year {y} — allowed", flush=True)
        _log.info(
            "Loading replay session %s via FastF1",
            f"{year} R{round_number} {stype}",
        )
        print(
            f"[ARIS] Loading replay session {year} R{round_number} {stype} via FastF1",
            flush=True,
        )
        _log.info(
            "FastF1 session LOAD year=%s round=%s type=%s telemetry=%s weather=%s messages=%s refresh=%s",
            year,
            round_number,
            stype,
            tel,
            wx,
            msg,
            refresh,
        )
        t0 = time.monotonic()
        sess = hit if hit is not None else _get_fastf1_session(year, round_number, stype)
        try:
            sess.load(laps=True, telemetry=tel, weather=wx, messages=msg)
        except Exception as extra:
            # Cache miss / corrupt FastF1 pickle on an ephemeral dyno must rebuild,
            # not take down uvicorn.
            _log.exception(
                "FastF1 sess.load failed year=%s round=%s type=%s; retrying once",
                year,
                round_number,
                stype,
            )
            try:
                sess = _get_fastf1_session(year, round_number, stype)
                sess.load(laps=True, telemetry=tel, weather=wx, messages=msg)
            except Exception:
                _log.exception(
                    "FastF1 rebuild failed year=%s round=%s type=%s",
                    year,
                    round_number,
                    stype,
                )
                raise RuntimeError(
                    f"FastF1 session load failed for {year} R{round_number} {stype}: {extra}"
                ) from extra
        elapsed = time.monotonic() - t0
        if not tel and not wx and not msg:
            _log.info("Metadata loaded in %.2fs", elapsed)
            _log.info("Basic laps loaded in %.2fs", elapsed)
            print(f"[ARIS] Metadata loaded in {elapsed:.2f}s", flush=True)
            print(f"[ARIS] Basic laps loaded in {elapsed:.2f}s", flush=True)
        elif tel:
            _log.info("GPS loaded in %.2fs", elapsed)
            print(f"[ARIS] GPS loaded in {elapsed:.2f}s", flush=True)
        else:
            _log.info("FastF1 sess.load finished in %.2fs telemetry=%s weather=%s", elapsed, tel, wx)
        _SESSION_CACHE[key] = sess
        _SESSION_FLAGS[key] = (tel, wx, msg)
        return sess


def _sector_colours(laps: pd.DataFrame) -> dict[tuple[str, int], tuple[str, str, str]]:
    """(driver, lap) -> (s1, s2, s3) colour."""
    colours: dict[tuple[str, int], tuple[str, str, str]] = {}
    if laps.empty:
        return colours
    best_s: dict[str, float] = {}
    for col in ("Sector1Time", "Sector2Time", "Sector3Time"):
        series = laps[col].dropna()
        if series.empty:
            continue
        secs = series.map(lambda x: x.total_seconds() if hasattr(x, "total_seconds") else float(x))
        best_s[col] = float(secs.min())
    personal: dict[str, dict[str, float]] = {}
    prev: dict[str, dict[str, float]] = {}
    ordered = laps.sort_values(["Driver", "LapNumber"])
    for rec in ordered.itertuples(index=False):
        code = str(rec.Driver)
        lap_no = int(rec.LapNumber) if pd.notna(rec.LapNumber) else 0
        tones: list[str] = []
        for col, attr in (
            ("Sector1Time", "Sector1Time"),
            ("Sector2Time", "Sector2Time"),
            ("Sector3Time", "Sector3Time"),
        ):
            val = getattr(rec, attr, None)
            ms = _td_ms(val)
            if ms is None:
                tones.append("grey")
                continue
            sec = ms / 1000.0
            pb = personal.setdefault(code, {})
            last = prev.setdefault(code, {})
            session_best = best_s.get(col)
            if session_best is not None and abs(sec - session_best) < 0.0005:
                tone = "purple"
            elif col not in pb or sec < pb[col]:
                tone = "green"
            elif col in last and sec < last[col]:
                tone = "yellow"
            else:
                tone = "grey"
            pb[col] = min(sec, pb.get(col, sec))
            last[col] = sec
            tones.append(tone)
        colours[(code, lap_no)] = (tones[0], tones[1], tones[2])
    return colours


def session_laps(year: int, round_number: int, session_type: str) -> LapsResponse:
    if _blocked_open_session(year, round_number, session_type):
        return LapsResponse(
            year=year, round_number=round_number, session_type=str(session_type).upper(), laps=[]
        )
    sess = load_session(year, round_number, session_type)
    laps = sess.laps
    colours = _sector_colours(laps)
    rows: list[LapRow] = []
    for rec in laps.itertuples(index=False):
        if pd.isna(rec.LapNumber) or pd.isna(rec.Driver):
            continue
        code = str(rec.Driver)
        lap_no = int(rec.LapNumber)
        s1, s2, s3 = colours.get((code, lap_no), ("grey", "grey", "grey"))
        rows.append(
            LapRow(
                driver_code=code,
                lap_number=lap_no,
                lap_time_ms=_td_ms(rec.LapTime),
                sector1_ms=_td_ms(rec.Sector1Time),
                sector2_ms=_td_ms(rec.Sector2Time),
                sector3_ms=_td_ms(rec.Sector3Time),
                compound=None if pd.isna(rec.Compound) else str(rec.Compound),
                tyre_life=_int(rec.TyreLife),
                is_personal_best=_bool(getattr(rec, "IsPersonalBest", False)),
                pit_in_lap=pd.notna(rec.PitInTime),
                pit_out_lap=pd.notna(rec.PitOutTime),
                position=_int(getattr(rec, "Position", None)),
                end_time_ms=_td_ms(getattr(rec, "Time", None)),
                track_status=None if pd.isna(rec.TrackStatus) else str(rec.TrackStatus),
                speed_i1=_num(rec.SpeedI1),
                speed_i2=_num(rec.SpeedI2),
                speed_fl=_num(rec.SpeedFL),
                speed_st=_num(rec.SpeedST),
                s1_colour=s1,  # type: ignore[arg-type]
                s2_colour=s2,  # type: ignore[arg-type]
                s3_colour=s3,  # type: ignore[arg-type]
                team=None if pd.isna(getattr(rec, "Team", None)) else str(rec.Team),
            )
        )
    return LapsResponse(year=year, round_number=round_number, session_type=session_type.upper(), laps=rows)


def session_summary(year: int, round_number: int, session_type: str) -> SessionSummary:
    if _blocked_open_session(year, round_number, session_type):
        return SessionSummary(
            year=year,
            round_number=round_number,
            session_type=str(session_type).upper(),
            fastest_laps=[],
            laps_completed=0,
            weather=WeatherSummary(),
            total_laps=_scheduled_laps(year, round_number),
        )
    laps_resp = session_laps(year, round_number, session_type)
    sess = load_session(year, round_number, session_type, weather=True)
    fastest: dict[str, DriverFastest] = {}
    s1 = s2 = s3 = None
    top_speed = None
    top_driver = None
    for lap in laps_resp.laps:
        if lap.lap_time_ms is not None:
            prev = fastest.get(lap.driver_code)
            if prev is None or lap.lap_time_ms < prev.lap_time_ms:
                fastest[lap.driver_code] = DriverFastest(
                    driver_code=lap.driver_code,
                    lap_time_ms=lap.lap_time_ms,
                    lap_number=lap.lap_number,
                    compound=lap.compound,
                )
        if lap.sector1_ms is not None and (s1 is None or lap.sector1_ms < s1.time_ms):
            s1 = SectorRecord(driver_code=lap.driver_code, time_ms=lap.sector1_ms)
        if lap.sector2_ms is not None and (s2 is None or lap.sector2_ms < s2.time_ms):
            s2 = SectorRecord(driver_code=lap.driver_code, time_ms=lap.sector2_ms)
        if lap.sector3_ms is not None and (s3 is None or lap.sector3_ms < s3.time_ms):
            s3 = SectorRecord(driver_code=lap.driver_code, time_ms=lap.sector3_ms)
        for spd in (lap.speed_i1, lap.speed_i2, lap.speed_fl, lap.speed_st):
            if spd is not None and (top_speed is None or spd > top_speed):
                top_speed = spd
                top_driver = lap.driver_code
    weather = WeatherSummary()
    wet = False
    try:
        wd = sess.weather_data
        if wd is not None and not wd.empty:
            air = wd["AirTemp"].dropna() if "AirTemp" in wd else pd.Series(dtype=float)
            track = wd["TrackTemp"].dropna() if "TrackTemp" in wd else pd.Series(dtype=float)
            rain = wd["Rainfall"] if "Rainfall" in wd else pd.Series(dtype=bool)
            weather = WeatherSummary(
                avg_air_temp=float(air.mean()) if not air.empty else None,
                min_air_temp=float(air.min()) if not air.empty else None,
                max_air_temp=float(air.max()) if not air.empty else None,
                avg_track_temp=float(track.mean()) if not track.empty else None,
                min_track_temp=float(track.min()) if not track.empty else None,
                max_track_temp=float(track.max()) if not track.empty else None,
                rainfall=bool(rain.any()) if not rain.empty else None,
            )
            wet = bool(weather.rainfall)
    except Exception:
        pass
    return SessionSummary(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        fastest_laps=sorted(fastest.values(), key=lambda x: x.lap_time_ms),
        sector1_record=s1,
        sector2_record=s2,
        sector3_record=s3,
        top_speed_kph=top_speed,
        top_speed_driver=top_driver,
        laps_completed=len(laps_resp.laps),
        weather=weather,
        wet_reduced_confidence=wet,
        total_laps=_scheduled_laps(year, round_number),
    )


def session_stints(year: int, round_number: int, session_type: str) -> StintsResponse:
    laps = session_laps(year, round_number, session_type).laps
    grouped: dict[str, list[LapRow]] = {}
    for lap in laps:
        grouped.setdefault(lap.driver_code, []).append(lap)
    stints: list[StintRow] = []
    for code, rows in grouped.items():
        rows = sorted(rows, key=lambda r: r.lap_number)
        current: list[LapRow] = []
        stint_no = 1
        prev_comp = None
        for lap in rows:
            new_stint = bool(lap.pit_out_lap) or (prev_comp is not None and lap.compound != prev_comp and lap.compound)
            if current and new_stint:
                stints.append(_stint_from_laps(code, stint_no, current))
                stint_no += 1
                current = [lap]
            else:
                current.append(lap)
            prev_comp = lap.compound or prev_comp
        if current:
            stints.append(_stint_from_laps(code, stint_no, current))
    return StintsResponse(year=year, round_number=round_number, session_type=session_type.upper(), stints=stints)


def _stint_from_laps(code: str, stint_no: int, rows: list[LapRow]) -> StintRow:
    times = [r.lap_time_ms for r in rows if r.lap_time_ms and not r.pit_in_lap and not r.pit_out_lap]
    avg = sum(times) / len(times) if times else None
    deg = None
    if len(times) >= 4:
        n = len(times)
        xs = list(range(n))
        xbar = sum(xs) / n
        ybar = sum(times) / n
        num = sum((x - xbar) * (y - ybar) for x, y in zip(xs, times))
        den = sum((x - xbar) ** 2 for x in xs) or 1
        deg = num / den
    fresh = rows[0].tyre_life == 1 if rows[0].tyre_life is not None else None
    return StintRow(
        driver_code=code,
        stint_number=stint_no,
        compound=rows[0].compound,
        fresh_tyre=fresh,
        lap_start=rows[0].lap_number,
        lap_end=rows[-1].lap_number,
        total_laps=rows[-1].lap_number - rows[0].lap_number + 1,
        average_lap_ms=avg,
        deg_rate_ms_per_lap=deg,
    )


def session_telemetry(
    year: int, round_number: int, session_type: str, driver_code: str, *, full: bool = False
) -> TelemetryResponse:
    if _blocked_open_session(year, round_number, session_type):
        return TelemetryResponse(
            year=year,
            round_number=round_number,
            session_type=str(session_type).upper(),
            driver_code=driver_code.upper(),
            sampled=False,
            distance=[],
            speed=[],
            throttle=[],
            brake=[],
            drs=[],
            rpm=[],
            gear=[],
            x=[],
            y=[],
        )
    sess = load_session(year, round_number, session_type, telemetry=True)
    laps = sess.laps.pick_drivers(driver_code.upper())
    if laps.empty:
        raise KeyError(f"No laps for {driver_code}")
    fast = laps.pick_fastest()
    car = fast.get_car_data().add_distance()
    try:
        pos = fast.get_pos_data()
    except Exception:
        pos = None
    step = 1 if full else 10
    dist = car["Distance"].tolist()[::step] if "Distance" in car else []
    speed = car["Speed"].tolist()[::step] if "Speed" in car else []
    throttle = car["Throttle"].tolist()[::step] if "Throttle" in car else []
    brake = [float(b) * 100 if float(b) <= 1 else float(b) for b in (car["Brake"].tolist()[::step] if "Brake" in car else [])]
    drs = [int(x) for x in (car["DRS"].tolist()[::step] if "DRS" in car else [])]
    rpm = [float(x) for x in (car["RPM"].tolist()[::step] if "RPM" in car else [])]
    gear = [int(x) if pd.notna(x) else 0 for x in (car["nGear"].tolist()[::step] if "nGear" in car else [])]
    xs: list[float] = []
    ys: list[float] = []
    if pos is not None and not pos.empty and "X" in pos.columns:
        xs = [float(x) for x in pos["X"].tolist()[::step]]
        ys = [float(y) for y in pos["Y"].tolist()[::step]]
    n = len(dist)
    return TelemetryResponse(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        driver_code=driver_code.upper(),
        sampled=not full,
        distance=[float(x) for x in dist[:n]],
        speed=[float(x) for x in speed[:n]],
        throttle=[float(x) for x in throttle[:n]],
        brake=brake[:n],
        drs=drs[:n],
        rpm=rpm[:n],
        gear=gear[:n],
        x=xs[:n] if xs else [],
        y=ys[:n] if ys else [],
    )


def session_weather(year: int, round_number: int, session_type: str) -> WeatherSeries:
    if _blocked_open_session(year, round_number, session_type):
        return WeatherSeries(
            year=year,
            round_number=round_number,
            session_type=str(session_type).upper(),
            timestamp=[],
            air_temp=[],
            track_temp=[],
            humidity=[],
            rainfall=[],
            wind_speed=[],
            wind_direction=[],
        )
    sess = load_session(year, round_number, session_type, weather=True)
    wd = sess.weather_data
    empty = WeatherSeries(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        timestamp=[],
        air_temp=[],
        track_temp=[],
        humidity=[],
        rainfall=[],
        wind_speed=[],
        wind_direction=[],
    )
    if wd is None or wd.empty:
        return empty
    ts = []
    for t in wd.index:
        if hasattr(t, "isoformat"):
            ts.append(t.isoformat())
        else:
            ts.append(str(t))
    rain_col = wd["Rainfall"] if "Rainfall" in wd else None
    rainfall = []
    if rain_col is not None:
        for v in rain_col.tolist():
            rainfall.append(None if pd.isna(v) else bool(v))
    return WeatherSeries(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        timestamp=ts,
        air_temp=[_num(v) for v in wd["AirTemp"].tolist()] if "AirTemp" in wd else [],
        track_temp=[_num(v) for v in wd["TrackTemp"].tolist()] if "TrackTemp" in wd else [],
        humidity=[_num(v) for v in wd["Humidity"].tolist()] if "Humidity" in wd else [],
        rainfall=rainfall,
        wind_speed=[_num(v) for v in wd["WindSpeed"].tolist()] if "WindSpeed" in wd else [],
        wind_direction=[_num(v) for v in wd["WindDirection"].tolist()] if "WindDirection" in wd else [],
    )


def session_results(year: int, round_number: int, session_type: str) -> SessionResultsResponse:
    if _blocked_open_session(year, round_number, session_type):
        return SessionResultsResponse(
            year=year, round_number=round_number, session_type=str(session_type).upper(), results=[]
        )
    sess = load_session(year, round_number, session_type)
    results = sess.results
    rows: list[SessionResultRow] = []
    winner_ms = None
    if results is not None and not results.empty:
        ordered = results.sort_values("Position")
        for rec in ordered.itertuples(index=False):
            pos = _int(rec.Position)
            time_ms = _td_ms(getattr(rec, "Time", None))
            if pos == 1 and time_ms:
                winner_ms = time_ms
            status = str(getattr(rec, "Status", "") or "Finished")
            gap = None
            if winner_ms is not None and time_ms is not None and pos != 1:
                gap = time_ms - winner_ms
            fl = False
            try:
                fl = bool(getattr(rec, "FastestLapRank", None) == 1)
            except Exception:
                fl = False
            rows.append(
                SessionResultRow(
                    position=pos,
                    driver_code=str(rec.Abbreviation),
                    team=None if pd.isna(rec.TeamName) else str(rec.TeamName),
                    time_ms=time_ms,
                    gap_to_winner_ms=gap,
                    points=_num(getattr(rec, "Points", None)),
                    fastest_lap=fl,
                    laps_completed=_int(getattr(rec, "Laps", None)),
                    status=status,
                    grid=_int(getattr(rec, "GridPosition", None)),
                )
            )
    return SessionResultsResponse(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        results=rows,
    )


def session_messages(year: int, round_number: int, session_type: str) -> MessagesResponse:
    if _blocked_open_session(year, round_number, session_type):
        return MessagesResponse(
            year=year, round_number=round_number, session_type=str(session_type).upper(), messages=[]
        )
    sess = load_session(year, round_number, session_type, messages=True)
    msgs: list[RaceControlMessage] = []
    raw = getattr(sess, "messages", None)
    if raw is None or (hasattr(raw, "empty") and raw.empty):
        return MessagesResponse(
            year=year, round_number=round_number, session_type=session_type.upper(), messages=[]
        )
    for rec in raw.itertuples(index=False):
        t = getattr(rec, "Time", None) or getattr(rec, "Utc", None)
        utc = None
        if hasattr(t, "isoformat"):
            utc = t.isoformat()
        elif t is not None:
            utc = str(t)
        msgs.append(
            RaceControlMessage(
                utc_time=utc,
                lap=_int(getattr(rec, "Lap", None)),
                flag=None if pd.isna(getattr(rec, "Flag", None)) else str(rec.Flag),
                category=None if pd.isna(getattr(rec, "Category", None)) else str(rec.Category),
                message=str(getattr(rec, "Message", "") or ""),
            )
        )
    return MessagesResponse(
        year=year, round_number=round_number, session_type=session_type.upper(), messages=msgs
    )


def _normalize_xy(xs: list[float], ys: list[float], w: float = 440, h: float = 280, pad: float = 20) -> list[CircuitPathPoint]:
    if not xs or not ys:
        return []
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    dx = max(maxx - minx, 1e-6)
    dy = max(maxy - miny, 1e-6)
    scale = min((w - 2 * pad) / dx, (h - 2 * pad) / dy)
    points: list[CircuitPathPoint] = []
    for x, y in zip(xs, ys):
        px = pad + (x - minx) * scale
        py = h - pad - (y - miny) * scale
        points.append(CircuitPathPoint(x=round(px, 2), y=round(py, 2)))
    return points


def circuit_path(year: int, round_number: int, session_type: str = "R") -> CircuitPathResponse:
    if _blocked_open_session(year, round_number, session_type):
        cmap = circuit_map_quick(year, round_number)
        return CircuitPathResponse(
            year=year,
            round_number=round_number,
            session_type=str(session_type).upper(),
            points=[CircuitPathPoint(x=x, y=y) for x, y in zip(cmap.x or [], cmap.y or [])],
        )
    try:
        sess = load_session(year, round_number, session_type, telemetry=True)
        laps = sess.laps
        fast = laps.pick_fastest()
        pos = fast.get_pos_data()
        xs = [float(x) for x in pos["X"].tolist()] if pos is not None and "X" in pos else []
        ys = [float(y) for y in pos["Y"].tolist()] if pos is not None and "Y" in pos else []
        # downsample path
        step = max(1, len(xs) // 400)
        xs, ys = xs[::step], ys[::step]
        points = _normalize_xy(xs, ys)
        corners: list[CircuitPathPoint] = []
        try:
            info = sess.get_circuit_info()
            if info is not None and getattr(info, "corners", None) is not None:
                c = info.corners
                if "X" in c.columns:
                    corners = _normalize_xy(
                        [float(x) for x in c["X"].tolist()],
                        [float(y) for y in c["Y"].tolist()],
                    )
        except Exception:
            corners = []
        return CircuitPathResponse(
            year=year,
            round_number=round_number,
            session_type=session_type.upper(),
            points=points,
            estimated=not bool(points),
            corners=corners,
        )
    except Exception:
        return CircuitPathResponse(
            year=year,
            round_number=round_number,
            session_type=session_type.upper(),
            points=[],
            estimated=True,
        )


_RAINFALL_LAP_CACHE: dict[tuple[int, int, str, int], bool] = {}


def rainfall_at_session_lap(year: int, round_number: int, session_type: str, lap: int) -> bool:
    """Per-lap observed rainfall from FastF1 weather_data (boolean). Cached."""
    key = (int(year), int(round_number), str(session_type).upper(), int(lap))
    hit = _RAINFALL_LAP_CACHE.get(key)
    if hit is not None:
        return hit
    raining = False
    try:
        from aris.physics.wet import nearest_rainfall

        sess = load_session(year, round_number, session_type, telemetry=False, weather=True, messages=False)
        weather = getattr(sess, "weather_data", None)
        laps = getattr(sess, "laps", None)
        start = None
        if laps is not None and not laps.empty and "LapNumber" in laps.columns:
            row = laps[laps["LapNumber"] == int(lap)]
            if row.empty:
                prior = laps[laps["LapNumber"] < int(lap)].sort_values("LapNumber")
                row = prior.tail(1)
            if not row.empty and "LapStartTime" in row.columns:
                start = row.iloc[0].get("LapStartTime")
        raining = bool(nearest_rainfall(weather, start))
    except Exception:
        raining = False
    _RAINFALL_LAP_CACHE[key] = raining
    return raining


def replay_timing(year: int, round_number: int, session_type: str, current_lap: int) -> LiveTimingResponse:
    from backend.models import LiveTimingResponse, LiveTimingRow
    from backend.standings import team_colour

    if _blocked_open_session(year, round_number, session_type):
        return LiveTimingResponse(is_live=True, rows=[], current_lap=current_lap, rainfall=False)
    raw = timing_at_lap(year, round_number, session_type, current_lap)
    rows = [
        LiveTimingRow(
            position=int(r["position"]),
            driver_code=str(r["driver_code"]),
            gap_to_leader_s=r.get("gap_to_leader_s"),
            last_lap_ms=r.get("last_lap_ms"),
            best_lap_ms=r.get("best_lap_ms"),
            sector1_ms=r.get("sector1_ms"),
            sector2_ms=r.get("sector2_ms"),
            sector3_ms=r.get("sector3_ms"),
            s1_colour=r.get("s1_colour") or "grey",
            s2_colour=r.get("s2_colour") or "grey",
            s3_colour=r.get("s3_colour") or "grey",
            compound=_compound_letter(r.get("compound")),
            tyre_life=r.get("tyre_life"),
            team_colour=team_colour(str(r.get("team") or "")),
        )
        for r in raw
    ]
    raining = False
    try:
        raining = rainfall_at_session_lap(year, round_number, session_type, current_lap)
    except Exception:
        raining = False
    return LiveTimingResponse(
        is_live=False, rows=rows, current_lap=current_lap, replay=True, rainfall=raining
    )


def _compound_letter(raw: str | None) -> str | None:
    if not raw:
        return None
    u = str(raw).upper()
    if u.startswith("SOFT") or u == "S":
        return "S"
    if u.startswith("MED") or u == "M":
        return "M"
    if u.startswith("HARD") or u == "H":
        return "H"
    if u.startswith("INTER") or u == "I":
        return "I"
    if u.startswith("WET") or u == "W":
        return "W"
    return u[:1]


def timing_at_lap(year: int, round_number: int, session_type: str, current_lap: int) -> list[dict[str, Any]]:
    """Replay timing tower derived from completed laps up to current_lap."""
    from backend.analytics import gap_history, position_history

    laps = session_laps(year, round_number, session_type).laps
    pos = position_history(year, round_number)
    gaps = gap_history(year, round_number)
    pos_map: dict[str, int] = {}
    gap_map: dict[str, float] = {}
    for row in pos.laps:
        if row.lap <= current_lap:
            pos_map = row.positions
    for row in gaps.laps:
        if row.lap <= current_lap:
            gap_map = row.gaps
    latest: dict[str, LapRow] = {}
    best: dict[str, int] = {}
    for lap in laps:
        if lap.lap_number > current_lap:
            continue
        latest[lap.driver_code] = lap
        if lap.lap_time_ms is not None:
            if lap.driver_code not in best or lap.lap_time_ms < best[lap.driver_code]:
                best[lap.driver_code] = lap.lap_time_ms
    rows = []
    for code, lap in latest.items():
        rows.append(
            {
                "position": pos_map.get(code, 99),
                "driver_code": code,
                "gap_to_leader_s": gap_map.get(code),
                "last_lap_ms": lap.lap_time_ms,
                "best_lap_ms": best.get(code),
                "sector1_ms": lap.sector1_ms,
                "sector2_ms": lap.sector2_ms,
                "sector3_ms": lap.sector3_ms,
                "s1_colour": lap.s1_colour,
                "s2_colour": lap.s2_colour,
                "s3_colour": lap.s3_colour,
                "compound": lap.compound,
                "tyre_life": lap.tyre_life,
                "team": lap.team,
            }
        )
    rows.sort(key=lambda r: r["position"])
    return rows


def _bounds_and_norm(
    xs: list[float], ys: list[float], w: float = 400.0, h: float = 240.0, pad: float = 20.0
) -> tuple[CircuitMapBounds | None, list[float], list[float]]:
    if not xs or not ys:
        return None, [], []
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    dx = max(max_x - min_x, 1e-6)
    dy = max(max_y - min_y, 1e-6)
    nx: list[float] = []
    ny: list[float] = []
    for x, y in zip(xs, ys):
        nx.append(round(pad + (x - min_x) / dx * w, 2))
        ny.append(round(pad + (1.0 - (y - min_y) / dy) * h, 2))
    return CircuitMapBounds(min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y), nx, ny


def _coerce_bounds(bounds: CircuitMapBounds | dict[str, Any] | None) -> CircuitMapBounds | None:
    if bounds is None:
        return None
    if isinstance(bounds, CircuitMapBounds):
        return bounds
    if isinstance(bounds, dict) and {"min_x", "max_x", "min_y", "max_y"} <= set(bounds):
        return CircuitMapBounds(
            min_x=float(bounds["min_x"]),
            max_x=float(bounds["max_x"]),
            min_y=float(bounds["min_y"]),
            max_y=float(bounds["max_y"]),
        )
    return None


def _is_null_gps(x: float, y: float) -> bool:
    return abs(x) < 1.0 and abs(y) < 1.0


def _pos_samples_are_raw(pos_samples: dict[str, list[Any]]) -> bool:
    """True when FastF1 GPS is still in metre space, not the 400x240 map."""
    for rows in pos_samples.values():
        for row in rows or []:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            try:
                x, y = float(row[1]), float(row[2])
            except (TypeError, ValueError):
                continue
            if _is_null_gps(x, y):
                continue
            if abs(x) > 800.0 or abs(y) > 500.0:
                return True
    return False


def align_pos_samples_to_path(
    pos_samples: dict[str, list[Any]],
    bounds: CircuitMapBounds | dict[str, Any] | None,
) -> tuple[dict[str, list[Any]], bool]:
    """Map raw FastF1 XY onto the circuit view. No-op if already aligned."""
    bounds = _coerce_bounds(bounds)
    if not pos_samples or bounds is None or not _pos_samples_are_raw(pos_samples):
        return pos_samples, False
    out: dict[str, list[Any]] = {}
    for code, rows in pos_samples.items():
        fitted: list[Any] = []
        for row in rows or []:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            try:
                t, x, y = float(row[0]), float(row[1]), float(row[2])
            except (TypeError, ValueError):
                continue
            if _is_null_gps(x, y):
                continue
            px, py = _apply_bounds(x, y, bounds)
            extra = list(row[3:])
            fitted.append((t, px, py, *extra) if extra else (t, px, py))
        if fitted:
            out[str(code)] = fitted
    return out, True


def _apply_bounds(
    x: float,
    y: float,
    bounds: CircuitMapBounds | dict[str, Any] | None,
    w: float = 400.0,
    h: float = 240.0,
    pad: float = 20.0,
) -> tuple[float, float]:
    bounds = _coerce_bounds(bounds)
    if bounds is None:
        return x, y
    dx = max(bounds.max_x - bounds.min_x, 1e-6)
    dy = max(bounds.max_y - bounds.min_y, 1e-6)
    return (
        round(pad + (x - bounds.min_x) / dx * w, 2),
        round(pad + (1.0 - (y - bounds.min_y) / dy) * h, 2),
    )


def point_at_path_frac(path_x: list[float], path_y: list[float], frac: float) -> tuple[float, float]:
    n = min(len(path_x), len(path_y))
    if n < 2:
        return 220.0, 140.0
    f = (frac % 1.0 + 1.0) % 1.0
    total = 0.0
    segs: list[tuple[float, float, float, float, float]] = []
    for i in range(n - 1):
        dx = path_x[i + 1] - path_x[i]
        dy = path_y[i + 1] - path_y[i]
        ln = (dx * dx + dy * dy) ** 0.5
        if ln <= 0:
            continue
        segs.append((path_x[i], path_y[i], path_x[i + 1], path_y[i + 1], ln))
        total += ln
    if total <= 0 or not segs:
        return path_x[0], path_y[0]
    target = f * total
    acc = 0.0
    for x0, y0, x1, y1, ln in segs:
        if acc + ln >= target:
            t = (target - acc) / ln if ln else 0.0
            t = max(0.0, min(1.0, t))
            return x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        acc += ln
    return path_x[-1], path_y[-1]


GPS_CORR_EPSILON = 0.015
GPS_CORR_EPSILON_LIVE = 0.02
GRID_START_LAP_FRAC = 0.02
GRID_SLOT_FRAC = 0.0035
DEFAULT_EXPECTED_LAP_S = 90.0


def _wrap01(f: float) -> float:
    return (float(f) % 1.0 + 1.0) % 1.0


def grid_path_frac(grid_position: int | None, slot_frac: float = GRID_SLOT_FRAC) -> float:
    slot = grid_position if grid_position and grid_position > 0 else 1
    return _wrap01(0.0 - (slot - 1) * slot_frac)


def compute_timing_path_frac(
    *,
    lap_number: int | float | None,
    time_since_lap_start_s: float | None,
    expected_lap_time_s: float | None,
) -> float:
    """Along-track fraction from classified timing only. No GPS."""
    expected = float(expected_lap_time_s) if expected_lap_time_s and expected_lap_time_s > 1 else DEFAULT_EXPECTED_LAP_S
    t = float(time_since_lap_start_s) if time_since_lap_start_s is not None else 0.0
    if t < 0:
        t = 0.0
    frac_within = min(1.0, t / expected)
    lap_n = float(lap_number) if lap_number is not None else 1.0
    return _wrap01(lap_n - 1.0 + frac_within)


def correct_path_frac(
    timing_frac: float,
    gps_frac: float | None,
    epsilon: float = GPS_CORR_EPSILON,
) -> float:
    """Bounded GPS correction. |gps-timing| > epsilon → discard GPS, use timing."""
    timing = _wrap01(timing_frac)
    if gps_frac is None:
        return timing
    try:
        gps = _wrap01(float(gps_frac))
    except (TypeError, ValueError):
        return timing
    d = gps - timing
    if abs(d) > epsilon:
        return timing
    if d > epsilon:
        d = epsilon
    elif d < -epsilon:
        d = -epsilon
    return _wrap01(timing + d)


def display_path_frac(
    *,
    timing_frac: float,
    gps_frac: float | None = None,
    grid_position: int | None = None,
    race_lap_frac: float | None = None,
    epsilon: float = GPS_CORR_EPSILON,
) -> float:
    corrected = correct_path_frac(timing_frac, gps_frac, epsilon)
    if race_lap_frac is not None and race_lap_frac < GRID_START_LAP_FRAC:
        return grid_path_frac(grid_position)
    return corrected


def nudge_path_frac(
    prev: float | None,
    car_x: float,
    car_y: float,
    path_x: list[float],
    path_y: list[float],
    *,
    max_back: float = 0.03,
    max_fwd: float = 0.15,
    timing_frac: float | None = None,
    epsilon: float = GPS_CORR_EPSILON_LIVE,
) -> float:
    """Live GPS as a bounded correction on timing. Reverse samples are dropped, not held."""
    raw = compute_path_distance(car_x, car_y, path_x, path_y)
    if timing_frac is not None:
        return correct_path_frac(timing_frac, raw, epsilon)
    if prev is None:
        return raw
    try:
        prev_f = float(prev) % 1.0
    except (TypeError, ValueError):
        return raw
    if prev_f < 0:
        prev_f += 1.0
    d = raw - prev_f
    if d < -0.5:
        d += 1.0
    if d < -max_back or d > max_fwd:
        return prev_f
    return (prev_f + d) % 1.0


def compute_path_distance(
    car_x: float,
    car_y: float,
    path_x: list[float],
    path_y: list[float],
) -> float:
    """Nearest-point projection of (car_x, car_y) onto the circuit polyline.

    Returns a fraction 0.0–1.0 of total path length.
    """
    fracs = project_points_to_path([car_x], [car_y], path_x, path_y)
    return float(fracs[0]) if fracs else 0.0


def _path_segments(path_x: list[float], path_y: list[float]) -> tuple[Any, ...] | None:
    import numpy as np

    if len(path_x) < 2 or len(path_y) < 2:
        return None
    n = min(len(path_x), len(path_y))
    path = np.column_stack((np.asarray(path_x[:n], dtype=float), np.asarray(path_y[:n], dtype=float)))
    a = path[:-1]
    b = path[1:]
    ab = b - a
    ln2 = np.sum(ab * ab, axis=1)
    valid = ln2 > 1e-12
    if not np.any(valid):
        return None
    a = a[valid]
    ab = ab[valid]
    ln2 = ln2[valid]
    seglen = np.sqrt(ln2)
    cum = np.concatenate(([0.0], np.cumsum(seglen)))
    total = float(cum[-1])
    if total <= 0:
        return None
    return a, ab, ln2, seglen, cum, total


def project_points_to_path(
    xs: list[float],
    ys: list[float],
    path_x: list[float],
    path_y: list[float],
) -> list[float]:
    """Vectorized nearest-point path fractions for many cars."""
    import numpy as np

    segs = _path_segments(path_x, path_y)
    if not xs or not ys or segs is None:
        return [0.0] * len(xs)
    a, ab, ln2, seglen, cum, total = segs
    pts = np.column_stack((np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)))
    delta = pts[:, None, :] - a[None, :, :]
    t = np.clip(np.sum(delta * ab[None, :, :], axis=2) / ln2[None, :], 0.0, 1.0)
    proj = a[None, :, :] + t[:, :, None] * ab[None, :, :]
    d2 = np.sum((pts[:, None, :] - proj) ** 2, axis=2)
    j = np.argmin(d2, axis=1)
    idx = np.arange(len(pts))
    fracs = (cum[j] + t[idx, j] * seglen[j]) / total
    return [float(v) for v in fracs]


def project_points_along_path(
    xs: list[float],
    ys: list[float],
    path_x: list[float],
    path_y: list[float],
    *,
    back_frac: float = 0.025,
    fwd_frac: float = 0.12,
) -> list[float]:
    """Project GPS onto the circuit, preferring the next stretch of track.

    Global nearest-segment snaps to the opposite side of a hairpin and reverses
    cars. After the first point, only a short backward / forward window is
    searched so motion stays along the racing direction.
    """
    import numpy as np

    global_fracs = project_points_to_path(xs, ys, path_x, path_y)
    if len(global_fracs) <= 1:
        return global_fracs
    segs = _path_segments(path_x, path_y)
    if segs is None:
        return global_fracs
    a, ab, ln2, seglen, cum, total = segs
    pts = np.column_stack((np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)))
    mid = cum[:-1] + 0.5 * seglen
    back_s = back_frac * total
    fwd_s = fwd_frac * total
    out = [global_fracs[0]]
    last_s = out[0] * total
    for i in range(1, len(pts)):
        d_along = mid - last_s
        d_along = np.where(d_along < -0.5 * total, d_along + total, d_along)
        d_along = np.where(d_along > 0.5 * total, d_along - total, d_along)
        keep = (d_along >= -back_s) & (d_along <= fwd_s)
        if not np.any(keep):
            out.append(global_fracs[i])
            last_s = out[-1] * total
            continue
        idx = np.flatnonzero(keep)
        delta = pts[i] - a[idx]
        t = np.clip(np.sum(delta * ab[idx], axis=1) / ln2[idx], 0.0, 1.0)
        proj = a[idx] + t[:, None] * ab[idx]
        d2 = np.sum((pts[i] - proj) ** 2, axis=1)
        j = int(idx[int(np.argmin(d2))])
        frac = float((cum[j] + t[int(np.argmin(d2))] * seglen[j]) / total)
        out.append(frac)
        last_s = frac * total
    return out


def stabilize_path_fracs(fracs: list[float], *, max_back: float = 0.04, max_fwd: float = 0.45) -> list[float]:
    """Keep path distance moving forward. Reverse / huge jumps are dropped, not frozen-crawled."""
    out: list[float] = []
    prev: float | None = None
    for raw in fracs:
        try:
            f = float(raw) % 1.0
        except (TypeError, ValueError):
            f = prev if prev is not None else 0.0
        if f < 0:
            f += 1.0
        if prev is None:
            out.append(f)
            prev = f
            continue
        d = f - prev
        if d < -0.5:
            d += 1.0
        if d < -max_back or d > max_fwd:
            out.append(prev)
            continue
        nxt = (prev + d) % 1.0
        out.append(nxt)
        prev = nxt
    return out


def _nearest_index(distances: list[float], target: float) -> int:
    if not distances:
        return 0
    best_i = 0
    best = abs(distances[0] - target)
    for i, d in enumerate(distances):
        err = abs(d - target)
        if err < best:
            best = err
            best_i = i
    return best_i


def _path_length(xs: list[float], ys: list[float]) -> float:
    n = min(len(xs), len(ys))
    total = 0.0
    for i in range(n - 1):
        dx = xs[i + 1] - xs[i]
        dy = ys[i + 1] - ys[i]
        total += (dx * dx + dy * dy) ** 0.5
    return total


def close_circuit_loop(xs: list[float], ys: list[float]) -> tuple[list[float], list[float]]:
    """Close the start/finish gap. FastF1 flying-lap XY is an open polyline."""
    n = min(len(xs), len(ys))
    if n < 3:
        return xs[:n], ys[:n]
    xs = list(xs[:n])
    ys = list(ys[:n])
    for _ in range(8):
        if len(xs) < 3:
            break
        gap = ((xs[0] - xs[-1]) ** 2 + (ys[0] - ys[-1]) ** 2) ** 0.5
        total = _path_length(xs, ys)
        last_step = ((xs[-1] - xs[-2]) ** 2 + (ys[-1] - ys[-2]) ** 2) ** 0.5
        if total > 0 and last_step > max(28.0, 0.045 * total) and gap > 12:
            xs.pop()
            ys.pop()
            continue
        break
    if not xs:
        return xs, ys
    gap = ((xs[0] - xs[-1]) ** 2 + (ys[0] - ys[-1]) ** 2) ** 0.5
    if gap < 1.2:
        xs[-1] = xs[0]
        ys[-1] = ys[0]
        return xs, ys
    xs.append(xs[0])
    ys.append(ys[0])
    return xs, ys


def min_dist_to_path(x: float, y: float, xs: list[float], ys: list[float]) -> float:
    """Shortest distance from a point to a polyline."""
    n = min(len(xs), len(ys))
    if n < 2:
        return float("inf")
    best = float("inf")
    for i in range(n - 1):
        ax, ay = xs[i], ys[i]
        bx, by = xs[i + 1], ys[i + 1]
        abx, aby = bx - ax, by - ay
        denom = abx * abx + aby * aby
        if denom <= 0:
            dist = ((x - ax) ** 2 + (y - ay) ** 2) ** 0.5
        else:
            t = max(0.0, min(1.0, ((x - ax) * abx + (y - ay) * aby) / denom))
            px, py = ax + t * abx, ay + t * aby
            dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        if dist < best:
            best = dist
    return best


def point_on_path(xs: list[float], ys: list[float], frac: float) -> tuple[float, float]:
    n = min(len(xs), len(ys))
    if n < 1:
        return 0.0, 0.0
    if n == 1:
        return float(xs[0]), float(ys[0])
    f = max(0.0, min(1.0, float(frac)))
    total = 0.0
    lengths: list[float] = []
    for i in range(n - 1):
        dx = xs[i + 1] - xs[i]
        dy = ys[i + 1] - ys[i]
        seg = (dx * dx + dy * dy) ** 0.5
        lengths.append(seg)
        total += seg
    if total <= 0:
        return float(xs[0]), float(ys[0])
    target = f * total
    walked = 0.0
    for i, seg in enumerate(lengths):
        if walked + seg >= target or i == len(lengths) - 1:
            local = 0.0 if seg <= 0 else (target - walked) / seg
            local = max(0.0, min(1.0, local))
            return (
                float(xs[i] + local * (xs[i + 1] - xs[i])),
                float(ys[i] + local * (ys[i + 1] - ys[i])),
            )
        walked += seg
    return float(xs[-1]), float(ys[-1])


def path_frame(xs: list[float], ys: list[float], frac: float) -> tuple[float, float, float, float]:
    """Point and unit tangent (tx, ty) at a wrapped path fraction."""
    n = min(len(xs), len(ys))
    if n < 2:
        return 220.0, 140.0, 1.0, 0.0
    f = (frac % 1.0 + 1.0) % 1.0
    total = _path_length(xs[:n], ys[:n])
    if total <= 0:
        return float(xs[0]), float(ys[0]), 1.0, 0.0
    target = f * total
    walked = 0.0
    for i in range(n - 1):
        dx = xs[i + 1] - xs[i]
        dy = ys[i + 1] - ys[i]
        seg = (dx * dx + dy * dy) ** 0.5
        if walked + seg >= target or i == n - 2:
            t = 0.0 if seg <= 0 else (target - walked) / seg
            t = max(0.0, min(1.0, t))
            px = xs[i] + t * dx
            py = ys[i] + t * dy
            norm = seg or 1.0
            return px, py, dx / norm, dy / norm
        walked += seg
    return float(xs[-1]), float(ys[-1]), 1.0, 0.0


def offset_at_frac(
    xs: list[float], ys: list[float], frac: float, offset: float, *, inward: bool = True
) -> tuple[float, float]:
    x, y, tx, ty = path_frame(xs, ys, frac)
    nx, ny = -ty, tx
    n = min(len(xs), len(ys))
    if inward and n:
        cx = sum(xs[:n]) / n
        cy = sum(ys[:n]) / n
        if nx * (cx - x) + ny * (cy - y) < 0:
            nx, ny = -nx, -ny
    return x + nx * offset, y + ny * offset


def status_is_pit(status: str | None) -> bool:
    """True for FastF1/OpenF1 pit labels (Pit, InPit, PitLane, …)."""
    return "pit" in str(status or "").lower().replace(" ", "").replace("_", "")


def pit_lane_from_points(
    points: list[tuple[float, float]],
    path_x: list[float],
    path_y: list[float],
    *,
    stalls: int = 22,
) -> tuple[list[float], list[float], list[list[float]]] | None:
    """Fit a pit-lane polyline from GPS points that already sit in the lane."""
    if len(points) < 12 or len(path_x) < 2:
        return None
    tagged: list[tuple[float, float, float, float]] = []
    for x, y in points:
        try:
            frac = float(compute_path_distance(x, y, path_x, path_y))
        except Exception:
            continue
        px, py = point_on_path(path_x, path_y, frac)
        dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        tagged.append((frac, x, y, dist))
    if len(tagged) < 12:
        return None
    dists = sorted(t[3] for t in tagged)
    med = dists[len(dists) // 2]
    if med < 5.0:
        return None
    keep = [t for t in tagged if abs(t[3] - med) <= max(10.0, med * 0.7)]
    if len(keep) < 10:
        return None
    keep.sort(key=lambda t: t[0] if t[0] >= 0.45 else t[0] + 1.0)
    bins = min(24, max(10, len(keep) // 4))
    pit_x: list[float] = []
    pit_y: list[float] = []
    for i in range(bins):
        lo = int(i * len(keep) / bins)
        hi = max(lo + 1, int((i + 1) * len(keep) / bins))
        chunk = keep[lo:hi]
        pit_x.append(round(sum(p[1] for p in chunk) / len(chunk), 2))
        pit_y.append(round(sum(p[2] for p in chunk) / len(chunk), 2))
    mid = keep[len(keep) // 5 : max(len(keep) // 5 + 1, (4 * len(keep)) // 5)]
    stall_pts: list[list[float]] = []
    if mid:
        last = max(len(mid) - 1, 1)
        for k in range(stalls):
            rec = mid[int(k * last / max(stalls - 1, 1))]
            stall_pts.append([round(rec[1], 2), round(rec[2], 2)])
    return pit_x, pit_y, stall_pts


def pit_lane_from_samples(
    pos_samples: dict[str, list[Any]],
    path_x: list[float],
    path_y: list[float],
) -> tuple[list[float], list[float], list[list[float]]] | None:
    pts: list[tuple[float, float]] = []
    for samples in (pos_samples or {}).values():
        for row in samples or []:
            if not isinstance(row, (list, tuple)) or len(row) < 4:
                continue
            if not status_is_pit(str(row[3])):
                continue
            try:
                pts.append((float(row[1]), float(row[2])))
            except (TypeError, ValueError):
                continue
    return pit_lane_from_points(pts, path_x, path_y)


def _pit_points_from_pos_data(pos_data: Any, bounds: Any) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    values = pos_data.values() if hasattr(pos_data, "values") else []
    for df in values:
        if df is None or getattr(df, "empty", True) or "X" not in getattr(df, "columns", []):
            continue
        n = len(df)
        step = max(3, n // 600)
        status_col = "Status" if "Status" in df.columns else None
        for i in range(0, n, step):
            rec = df.iloc[i]
            st = str(rec[status_col]) if status_col and pd.notna(rec.get(status_col)) else ""
            if not status_is_pit(st):
                continue
            if pd.isna(rec["X"]) or pd.isna(rec["Y"]):
                continue
            raw_x, raw_y = float(rec["X"]), float(rec["Y"])
            if bounds is not None:
                pts.append(_apply_bounds(raw_x, raw_y, bounds))
            else:
                pts.append((raw_x, raw_y))
    return pts


def pit_lane_from_path(
    xs: list[float], ys: list[float], *, stalls: int = 22, offset: float = 26.0
) -> tuple[list[float], list[float], list[list[float]]]:
    """Pit lane along the start/finish straight: entry, boxes, exit."""
    n = min(len(xs), len(ys))
    if n < 4:
        return [], [], []
    samples = [
        (-0.16, 0.0),
        (-0.13, offset * 0.28),
        (-0.10, offset * 0.62),
        (-0.075, offset * 0.9),
        (-0.05, offset),
        (-0.02, offset),
        (0.000, offset),
        (0.03, offset),
        (0.055, offset * 0.9),
        (0.08, offset * 0.62),
        (0.11, offset * 0.28),
        (0.15, 0.0),
    ]
    pit_x: list[float] = []
    pit_y: list[float] = []
    for frac, mag in samples:
        px, py = offset_at_frac(xs, ys, frac, mag, inward=True)
        pit_x.append(round(px, 2))
        pit_y.append(round(py, 2))
    stall_pts: list[list[float]] = []
    for k in range(stalls):
        t = -0.028 + (k + 0.5) / stalls * 0.055
        sx, sy = offset_at_frac(xs, ys, t, offset, inward=True)
        stall_pts.append([round(sx, 2), round(sy, 2)])
    return pit_x, pit_y, stall_pts


def grid_slot_xy(
    xs: list[float], ys: list[float], grid_pos: int
) -> tuple[float, float, float]:
    """Staggered 2-wide grid just before S/F. P1 is closest to the line."""
    pos = max(1, int(grid_pos))
    row = (pos - 1) // 2
    left = pos % 2 == 1
    frac = (1.0 - 0.010 - 0.011 * row) % 1.0
    side = -7.0 if left else 7.0
    x, y, tx, ty = path_frame(xs, ys, frac)
    if not xs:
        return 0.0, 0.0, frac
    px, py = x + (-ty) * side, y + tx * side
    return round(px, 2), round(py, 2), frac


def _frac_to_index(xs: list[float], frac: float) -> int:
    n = max(1, len(xs) - 1)
    return min(n, max(0, int(round(((frac % 1.0) + 1.0) % 1.0 * n))))


def _yaml_drs_zones(circuit_key: str | None) -> list[dict[str, Any]]:
    if not circuit_key:
        return []
    try:
        from aris.tracks import _match_track_file

        path = _match_track_file(circuit_key)
        if path is None:
            return []
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw = data.get("drs_zones") or []
        return [z for z in raw if isinstance(z, dict)]
    except Exception:
        return []


def _longest_straight_fracs(xs: list[float], ys: list[float], count: int = 2) -> list[tuple[float, float]]:
    n = min(len(xs), len(ys))
    if n < 8:
        return [(0.92, 0.02)]
    runs: list[tuple[float, int, int]] = []
    start = 0
    acc = 0.0
    for i in range(n - 1):
        dx = xs[i + 1] - xs[i]
        dy = ys[i + 1] - ys[i]
        seg = (dx * dx + dy * dy) ** 0.5
        prev = max(0, i - 1)
        pdx, pdy = xs[i] - xs[prev], ys[i] - ys[prev]
        bend = abs(dx * pdy - dy * pdx)
        straight = bend < 18.0
        if straight:
            acc += seg
        else:
            if acc > 12:
                runs.append((acc, start, i))
            start = i
            acc = 0.0
    if acc > 12:
        runs.append((acc, start, n - 1))
    runs.sort(reverse=True)
    out: list[tuple[float, float]] = []
    for _ln, a, b in runs[:count]:
        out.append((a / max(n - 1, 1), b / max(n - 1, 1)))
    return out or [(0.92, 0.02)]


def drs_on_path(
    xs: list[float], ys: list[float], circuit_key: str | None = None
) -> tuple[list[list[int]], list[CircuitMarker]]:
    """DRS activation segments (path indices) and detection-point markers."""
    zones = _yaml_drs_zones(circuit_key)
    if not zones:
        zones = []
        for i, (a, b) in enumerate(_longest_straight_fracs(xs, ys, 2), start=1):
            span = (b - a) % 1.0
            detect = (a - min(0.04, max(0.015, span * 0.25))) % 1.0
            zones.append(
                {
                    "name": f"DRS {i}",
                    "detect_frac": detect,
                    "activate_frac": a,
                    "end_frac": b,
                }
            )
    segments: list[list[int]] = []
    markers: list[CircuitMarker] = []
    for zone in zones:
        try:
            detect = float(zone.get("detect_frac"))
            act = float(zone.get("activate_frac"))
            end = float(zone.get("end_frac"))
        except (TypeError, ValueError):
            continue
        a = _frac_to_index(xs, act)
        b = _frac_to_index(xs, end)
        if a == b:
            b = min(len(xs) - 1, a + 4)
        segments.append([a, b] if a < b else [a, len(xs) - 1])
        if a > b:
            segments.append([0, b])
        dx, dy = offset_at_frac(xs, ys, detect, 0.0)
        markers.append(
            CircuitMarker(
                kind="drs_detect",
                x=round(dx, 2),
                y=round(dy, 2),
                label=str(zone.get("name") or "DRS DET"),
            )
        )
    return segments, markers


def grid_marks(xs: list[float], ys: list[float], cars: int = 20) -> list[CircuitMarker]:
    marks: list[CircuitMarker] = []
    for pos in range(1, cars + 1):
        x, y, _frac = grid_slot_xy(xs, ys, pos)
        marks.append(CircuitMarker(kind="grid", x=x, y=y, label=f"P{pos}"))
    return marks


def _ff1_session_candidates(session_type: str) -> list[str]:
    u = (session_type or "R").upper()
    if u == "SQ":
        return ["SQ", "SS", "Q"]
    if u in {"Q", "QUALIFYING"}:
        return ["Q"]
    return [u]


QUALI_SEGMENT_BLOCKS: dict[bool, list[tuple[str, int, int]]] = {
    False: [("Q1", 18, 7), ("Q2", 15, 8), ("Q3", 12, 0)],
    True: [("SQ1", 12, 4), ("SQ2", 10, 4), ("SQ3", 8, 0)],
}


def official_quali_windows(sprint: bool) -> list[dict[str, Any]]:
    """FIA segment lengths only — never the whole ~40/90 minute session envelope."""
    t = 0
    out: list[dict[str, Any]] = []
    for lab, mins, gap in QUALI_SEGMENT_BLOCKS[bool(sprint)]:
        out.append({"id": lab, "label": lab, "start_s": t, "end_s": t + mins * 60})
        t += mins * 60 + gap * 60
    return out


def quali_windows_for_session_type(session_type: str) -> list[dict[str, Any]]:
    u = (session_type or "").upper()
    if u in {"Q", "QUALIFYING"}:
        return official_quali_windows(False)
    if u in {"SQ", "SS"}:
        return official_quali_windows(True)
    return []


def _quali_window_sane(windows: list[dict[str, Any]], sprint: bool) -> bool:
    if len(windows) < 2:
        return False
    cap = 14 * 60 if sprint else 22 * 60
    for win in windows:
        span = int(win.get("end_s") or 0) - int(win.get("start_s") or 0)
        if span <= 30 or span > cap:
            return False
    return True


def _quali_windows_from_duration(duration_s: int, sprint: bool) -> list[dict[str, Any]]:
    official = official_quali_windows(sprint)
    if duration_s <= 0:
        return official
    out: list[dict[str, Any]] = []
    for win in official:
        if win["start_s"] >= duration_s:
            break
        out.append({**win, "end_s": min(int(win["end_s"]), duration_s)})
    return out or official[:1]


def _quali_windows_from_messages(messages: list[Any], start: datetime | None, duration_s: int, sprint: bool) -> list[dict[str, Any]]:
    labels = ("SQ1", "SQ2", "SQ3") if sprint else ("Q1", "Q2", "Q3")
    hits: dict[str, list[int]] = {lab: [] for lab in labels}
    for row in messages:
        blob = ""
        dt = None
        if hasattr(row, "message"):
            blob = str(row.message or "").upper()
            dt = _parse_maybe_dt(getattr(row, "utc_time", None))
        elif isinstance(row, dict):
            blob = str(row.get("message") or "").upper()
            dt = _parse_maybe_dt(row.get("date") or row.get("utc_time"))
        if start is None or dt is None:
            continue
        elapsed = int((dt - start).total_seconds())
        if elapsed < 0 or elapsed > duration_s + 120:
            continue
        for lab in labels:
            if lab in blob.replace(" ", ""):
                hits[lab].append(elapsed)
    windows: list[dict[str, Any]] = []
    prev_end = 0
    for i, lab in enumerate(labels):
        times = sorted(hits[lab])
        if not times:
            continue
        start_s = prev_end if i == 0 else max(prev_end, times[0] - 60)
        end_s = times[-1]
        windows.append({"id": lab, "label": lab, "start_s": max(0, start_s), "end_s": min(duration_s, max(end_s, start_s + 60))})
        prev_end = windows[-1]["end_s"]
    if _quali_window_sane(windows, sprint):
        return windows
    return _quali_windows_from_duration(duration_s, sprint)


def _parse_maybe_dt(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


_FF1_POS_CAP = 18000
_FF1_CAR_CAP = 24000
_FF1_POS_MIN_DT = 0.10
_FF1_CAR_MIN_DT = 0.08


def _ff1_keep_step(n: int, cap: int) -> int:
    if n <= 400:
        return 1
    return max(1, n // cap)


def _sample_lo(samples: list[Any], t_epoch: float, lead: float = 0.25) -> int | None:
    if not samples:
        return None
    if t_epoch + lead < samples[0][0]:
        return None
    lo, hi = 0, len(samples) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if samples[mid][0] <= t_epoch:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def _ff1_message_dt(rec: Any, sess: Any) -> datetime | None:
    dt = _parse_maybe_dt(getattr(rec, "Utc", None))
    if dt is not None:
        return dt
    t0 = _parse_maybe_dt(getattr(sess, "t0_date", None))
    t = getattr(rec, "Time", None)
    if t0 is not None and t is not None and hasattr(t, "total_seconds"):
        try:
            return t0 + timedelta(seconds=float(t.total_seconds()))
        except (TypeError, ValueError):
            return t0
    return _parse_maybe_dt(t)


def _ff1_race_control_rows(sess: Any) -> list[dict[str, Any]]:
    raw = getattr(sess, "messages", None)
    if raw is None or (hasattr(raw, "empty") and raw.empty):
        return []
    rows: list[dict[str, Any]] = []
    for rec in raw.itertuples(index=False):
        dt = _ff1_message_dt(rec, sess)
        flag = getattr(rec, "Flag", None)
        category = getattr(rec, "Category", None)
        try:
            flag_s = None if flag is None or pd.isna(flag) else str(flag)
        except (TypeError, ValueError):
            flag_s = str(flag) if flag is not None else None
        try:
            cat_s = None if category is None or pd.isna(category) else str(category)
        except (TypeError, ValueError):
            cat_s = str(category) if category is not None else None
        rows.append(
            {
                "date": dt.isoformat() if dt is not None else None,
                "flag": flag_s,
                "category": cat_s,
                "message": str(getattr(rec, "Message", "") or ""),
                "lap_number": _int(getattr(rec, "Lap", None)),
            }
        )
    return rows


def _ff1_clock_bounds(
    sess: Any,
    laps_rows: list[dict[str, Any]],
    pos_samples: dict[str, list[Any]],
    date_start: datetime | None,
    date_end: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    t0 = date_start
    try:
        t0 = _parse_maybe_dt(getattr(sess, "t0_date", None)) or date_start
    except Exception:
        t0 = date_start
    if t0 is None:
        for row in laps_rows:
            t0 = _parse_maybe_dt(row.get("date_start"))
            if t0 is not None:
                break
    last_end: datetime | None = date_end
    for row in laps_rows:
        start = _parse_maybe_dt(row.get("date_start"))
        if start is None:
            continue
        try:
            dur = float(row.get("lap_duration") or 0)
        except (TypeError, ValueError):
            dur = 0.0
        end = start + timedelta(seconds=dur)
        if last_end is None or end > last_end:
            last_end = end
    for samples in pos_samples.values():
        if not samples:
            continue
        try:
            ts = datetime.fromtimestamp(float(samples[-1][0]), tz=timezone.utc)
        except (TypeError, ValueError, OSError, IndexError):
            continue
        if last_end is None or ts > last_end:
            last_end = ts
    if t0 is not None and last_end is None:
        last_end = t0 + timedelta(hours=2)
    if t0 is not None and last_end is not None and last_end <= t0:
        last_end = t0 + timedelta(hours=2)
    return t0, last_end


def _lap_start_epochs(laps_rows: list[dict[str, Any]]) -> dict[int, float]:
    starts: dict[int, float] = {}
    for row in laps_rows:
        n = int(row.get("lap_number") or 0)
        if n <= 0:
            continue
        start = _parse_maybe_dt(row.get("date_start"))
        if start is None:
            continue
        t = start.timestamp()
        prev = starts.get(n)
        if prev is None or t < prev:
            starts[n] = t
    return starts


def pos_chunk_time_window(
    starts: dict[int, float], lo: int, hi: int
) -> tuple[float | None, float | None]:
    """Inclusive start / exclusive end timestamps for a pos chunk.

    Chunk (0, 10) includes formation-lap samples (t0 is None). Chunk (10, 20)
    starts at the first lap-11 timestamp.
    """
    t0 = starts.get(int(lo) + 1) if int(lo) > 0 else None
    t1 = starts.get(int(hi) + 1)
    return t0, t1


def slice_pos_samples(
    pos_samples: dict[str, list[Any]],
    t0: float | None,
    t1: float | None,
) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for code, samples in (pos_samples or {}).items():
        kept: list[Any] = []
        for row in samples or []:
            try:
                t = float(row[0])
            except (TypeError, ValueError, IndexError):
                continue
            if t0 is not None and t < t0:
                continue
            if t1 is not None and t >= t1:
                continue
            kept.append(row)
        if kept:
            out[str(code)] = kept
    return out


def persist_pos_chunks(
    year: int,
    round_number: int,
    session_type: str,
    pos_samples: dict[str, list[Any]],
    laps_rows: list[dict[str, Any]],
) -> list[dict[str, int]]:
    """Slice full GPS into 10-lap windows and cache each separately.

    Returns the catalog ``[{lo, hi}, ...]``. The caller should keep only the
    first window in the in-memory pack.
    """
    max_lap = 1
    for row in laps_rows or []:
        try:
            max_lap = max(max_lap, int(row.get("lap_number") or 0))
        except (TypeError, ValueError):
            continue
    starts = _lap_start_epochs(laps_rows)
    catalog: list[dict[str, int]] = []
    mapped = str(session_type or "R")
    for lo, hi in iter_pos_chunk_ranges(max_lap):
        t0, t1 = pos_chunk_time_window(starts, lo, hi)
        chunk = slice_pos_samples(pos_samples, t0, t1)
        save_pos_chunk_disk(int(year), int(round_number), mapped, lo, hi, chunk)
        catalog.append({"lo": lo, "hi": hi})
    return catalog


def _parse_one_pos_df(
    df: Any,
    drv_key: Any,
    code_by_num: dict[int, str],
    bounds: CircuitMapBounds | None,
    pos_cap: int,
) -> tuple[str, list[tuple[float, float, float, str]]] | None:
    if df is None or getattr(df, "empty", True) or "X" not in getattr(df, "columns", []):
        return None
    code = code_by_num.get(int(drv_key)) if str(drv_key).isdigit() else str(drv_key)
    if not code:
        code = str(drv_key)
    n = len(df)
    step = _ff1_keep_step(n, pos_cap)
    samples: list[tuple[float, float, float, str]] = []
    last_kept: float | None = None
    for i in range(0, n, step):
        rec = df.iloc[i]
        ts = _parse_maybe_dt(rec["Date"] if "Date" in df.columns else None)
        if ts is None:
            continue
        t = ts.timestamp()
        if last_kept is not None and (t - last_kept) < _FF1_POS_MIN_DT and i + step < n:
            continue
        last_kept = t
        raw_x = float(rec["X"]) if pd.notna(rec["X"]) else 0.0
        raw_y = float(rec["Y"]) if pd.notna(rec["Y"]) else 0.0
        if bounds is not None:
            px, py = _apply_bounds(raw_x, raw_y, bounds)
        else:
            px, py = raw_x, raw_y
        st = str(rec["Status"]) if "Status" in df.columns and pd.notna(rec.get("Status")) else "OnTrack"
        samples.append((t, px, py, st))
    if n > 0 and samples:
        rec = df.iloc[n - 1]
        ts = _parse_maybe_dt(rec["Date"] if "Date" in df.columns else None)
        if ts is not None and samples[-1][0] < ts.timestamp() - 1e-6:
            raw_x = float(rec["X"]) if pd.notna(rec["X"]) else 0.0
            raw_y = float(rec["Y"]) if pd.notna(rec["Y"]) else 0.0
            px, py = _apply_bounds(raw_x, raw_y, bounds) if bounds is not None else (raw_x, raw_y)
            st = str(rec["Status"]) if "Status" in df.columns and pd.notna(rec.get("Status")) else "OnTrack"
            samples.append((ts.timestamp(), px, py, st))
    if not samples:
        return None
    return str(code), samples


def load_position_data_only(sess: Any) -> dict[str, Any]:
    """FastF1 ``position_data`` without ever fetching ``car_data``."""
    from fastf1 import api

    try:
        return api.position_data(sess.api_path) or {}
    except Exception as extra:
        _log.info("FastF1 position_data unavailable: %s", extra)
        return {}


def parse_and_chunk_position_data(
    sess: Any,
    year: int,
    round_number: int,
    session_type: str,
    bounds: CircuitMapBounds | None,
    code_by_num: dict[int, str],
    laps_rows: list[dict[str, Any]],
    *,
    pos_cap: int | None = None,
) -> tuple[dict[str, list[tuple[float, float, float, str]]], list[dict[str, int]]]:
    """Load GPS, persist 10-lap chunks, return the first chunk + catalog.

    Never loads car_data. Drops FastF1 dataframes as each driver is parsed.
    """
    log_process_mem("before position_data")
    raw = load_position_data_only(sess)
    cap = int(pos_cap) if pos_cap else _FF1_POS_CAP
    pos_samples: dict[str, list[tuple[float, float, float, str]]] = {}
    try:
        for drv_key in list(raw.keys()):
            df = raw.pop(drv_key, None)
            try:
                parsed = _parse_one_pos_df(df, drv_key, code_by_num, bounds, cap)
            finally:
                del df
            if parsed is None:
                continue
            code, samples = parsed
            pos_samples[code] = samples
    finally:
        raw.clear()
        gc.collect()
    log_process_mem("after position_data parse")
    catalog = persist_pos_chunks(year, round_number, session_type, pos_samples, laps_rows)
    first: dict[str, list[tuple[float, float, float, str]]] = {}
    if catalog:
        lo, hi = int(catalog[0]["lo"]), int(catalog[0]["hi"])
        starts = _lap_start_epochs(laps_rows)
        t0, t1 = pos_chunk_time_window(starts, lo, hi)
        first = slice_pos_samples(pos_samples, t0, t1)
    pos_samples.clear()
    gc.collect()
    log_process_mem("after pos chunk persist")
    return first, catalog


def build_ff1_replay_assets(
    year: int,
    round_number: int,
    session_type: str,
    bounds: CircuitMapBounds | None,
    *,
    date_start: datetime | None = None,
    date_end: datetime | None = None,
    telemetry: bool = True,
    weather: bool = True,
    messages: bool = True,
    pos_cap: int | None = None,
) -> dict[str, Any]:
    """In-memory FastF1 samples for completed-session replay (no OpenF1 GPS).

    Call with telemetry=False for the fast laps-only (minimal) stage.
    """
    from backend.calendar import ALLOWED_REPLAY_YEARS, ReplayYearBlocked, assert_replay_session_type

    if int(year) not in ALLOWED_REPLAY_YEARS:
        _log.info("Replay request for year %s — blocked (not in 2024–2026)", year)
        raise ReplayYearBlocked("Replay not allowed for this year")
    session_type = assert_replay_session_type(session_type)
    empty: dict[str, Any] = {"ok": False}
    sess = None
    used = session_type
    _log.info(
        "Loading replay session %s via FastF1",
        f"{year} R{round_number} {session_type}",
    )
    t_all = time.monotonic()
    for cand in _ff1_session_candidates(session_type):
        try:
            sess = load_session(
                year,
                round_number,
                cand,
                telemetry=False,
                weather=weather,
                messages=messages,
            )
            used = cand
            break
        except Exception as extra:
            _log.info("FastF1 replay load %s %s %s failed: %s", year, round_number, cand, extra)
            sess = None
    if sess is None:
        return empty
    _log.info("Metadata loaded in %.2fs", time.monotonic() - t_all)
    code_by_num: dict[int, str] = {}
    num_by_code: dict[str, int] = {}
    colours: dict[int, str] = {}
    q_times: dict[str, dict[str, int | None]] = {}
    status_by_code: dict[str, str] = {}
    try:
        from backend.standings import team_colour

        results = getattr(sess, "results", None)
        if results is not None and not getattr(results, "empty", True):
            for rec in results.itertuples(index=False):
                code = str(getattr(rec, "Abbreviation", "") or "")
                if not code:
                    continue
                num = _int(getattr(rec, "DriverNumber", None))
                if num is not None:
                    code_by_num[num] = code
                    num_by_code[code] = num
                    colours[num] = team_colour(str(getattr(rec, "TeamName", "") or "")) or ""
                status_by_code[code] = str(getattr(rec, "Status", "") or "")
                q_times[code] = {
                    "q1_ms": _td_ms(getattr(rec, "Q1", None)),
                    "q2_ms": _td_ms(getattr(rec, "Q2", None)),
                    "q3_ms": _td_ms(getattr(rec, "Q3", None)),
                }
    except Exception as extra:
        _log.info("FastF1 results parse failed: %s", extra)

    laps_rows: list[dict[str, Any]] = []
    stints_acc: dict[tuple[int, int], dict[str, Any]] = {}
    positions_rows: list[dict[str, Any]] = []
    try:
        laps = sess.laps
        if laps is not None and not laps.empty:
            for rec in laps.itertuples(index=False):
                code = str(getattr(rec, "Driver", "") or "")
                if not code:
                    continue
                num = num_by_code.get(code)
                if num is None:
                    num = _int(getattr(rec, "DriverNumber", None))
                    if num is not None:
                        num_by_code[code] = num
                        code_by_num[num] = code
                start = _parse_maybe_dt(getattr(rec, "LapStartDate", None))
                lap_n = _int(getattr(rec, "LapNumber", None)) or 0
                pos = _int(getattr(rec, "Position", None))
                compound = None if pd.isna(getattr(rec, "Compound", None)) else str(rec.Compound)
                laps_rows.append(
                    {
                        "driver_number": num,
                        "driver_code": code,
                        "date_start": start.isoformat() if start else None,
                        "lap_duration": None
                        if _td_ms(getattr(rec, "LapTime", None)) is None
                        else _td_ms(getattr(rec, "LapTime", None)) / 1000.0,
                        "lap_number": lap_n,
                        "duration_sector_1": None
                        if _td_ms(getattr(rec, "Sector1Time", None)) is None
                        else _td_ms(getattr(rec, "Sector1Time", None)) / 1000.0,
                        "duration_sector_2": None
                        if _td_ms(getattr(rec, "Sector2Time", None)) is None
                        else _td_ms(getattr(rec, "Sector2Time", None)) / 1000.0,
                        "duration_sector_3": None
                        if _td_ms(getattr(rec, "Sector3Time", None)) is None
                        else _td_ms(getattr(rec, "Sector3Time", None)) / 1000.0,
                        "is_pit_out_lap": pd.notna(getattr(rec, "PitOutTime", None)),
                        "is_pit_in_lap": pd.notna(getattr(rec, "PitInTime", None)),
                        "compound": compound,
                        "tyre_life": _int(getattr(rec, "TyreLife", None)),
                        "position": pos,
                        "end_time_ms": _td_ms(getattr(rec, "Time", None)),
                        "track_status": None if pd.isna(getattr(rec, "TrackStatus", None)) else str(rec.TrackStatus),
                        "st_speed": _num(getattr(rec, "SpeedST", None)),
                    }
                )
                if start is not None and num is not None and pos is not None:
                    positions_rows.append(
                        {
                            "driver_number": num,
                            "position": pos,
                            "date": start.isoformat(),
                        }
                    )
                if num is not None:
                    stint_n = _int(getattr(rec, "Stint", None)) or 1
                    skey = (int(num), int(stint_n))
                    if skey not in stints_acc:
                        stints_acc[skey] = {
                            "driver_number": int(num),
                            "stint_number": int(stint_n),
                            "compound": compound,
                            "lap_start": lap_n or 1,
                            "lap_end": lap_n or 1,
                            "tyre_age_at_start": _int(getattr(rec, "TyreLife", None)),
                        }
                    else:
                        stints_acc[skey]["lap_end"] = lap_n or stints_acc[skey]["lap_end"]
    except Exception as extra:
        _log.info("FastF1 laps parse failed: %s", extra)
    _log.info("Basic laps loaded in %.2fs", time.monotonic() - t_all)
    print(f"[ARIS] Basic laps loaded in {time.monotonic() - t_all:.2f}s", flush=True)

    weather_rows: list[dict[str, Any]] = []
    if weather:
        try:
            series = session_weather(year, round_number, used)
            for i, ts in enumerate(series.timestamp):
                weather_rows.append(
                    {
                        "date": ts,
                        "air_temperature": series.air_temp[i] if i < len(series.air_temp) else None,
                        "track_temperature": series.track_temp[i] if i < len(series.track_temp) else None,
                        "humidity": series.humidity[i] if i < len(series.humidity) else None,
                        "rainfall": series.rainfall[i] if i < len(series.rainfall) else None,
                        "wind_speed": series.wind_speed[i] if i < len(series.wind_speed) else None,
                        "wind_direction": series.wind_direction[i] if i < len(series.wind_direction) else None,
                        "pressure": None,
                    }
                )
        except Exception as extra:
            _log.info("FastF1 weather parse failed: %s", extra)

    pos_samples: dict[str, list[tuple[float, float, float, str]]] = {}
    car_samples: dict[str, list[tuple[float, float, float, float, float]]] = {}
    pos_chunks: list[dict[str, int]] = []
    pos_chunk_loaded: dict[str, int] | None = None
    if telemetry:
        t_gps = time.monotonic()
        try:
            pos_samples, pos_chunks = parse_and_chunk_position_data(
                sess,
                year,
                round_number,
                used,
                bounds,
                code_by_num,
                laps_rows,
                pos_cap=pos_cap,
            )
            if pos_chunks:
                pos_chunk_loaded = dict(pos_chunks[0])
        except Exception as extra:
            _log.info("FastF1 position_data parse failed: %s", extra)
        _log.info("GPS loaded in %.2fs", time.monotonic() - t_gps)
        print(f"[ARIS] GPS loaded in {time.monotonic() - t_gps:.2f}s", flush=True)

    rc_rows = _ff1_race_control_rows(sess) if messages else []
    clock_start, clock_end = _ff1_clock_bounds(sess, laps_rows, pos_samples, date_start, date_end)
    duration_s = 0
    if clock_start and clock_end:
        duration_s = max(0, int((clock_end - clock_start).total_seconds()))
    sprint = used in {"SQ", "SS"} or session_type.upper() == "SQ"
    is_quali = used in {"Q", "SQ", "SS"} or session_type.upper() in {"Q", "SQ"}
    windows: list[dict[str, Any]] = []
    if is_quali and duration_s:
        if messages:
            try:
                msgs = session_messages(year, round_number, used)
                windows = _quali_windows_from_messages(list(msgs.messages), clock_start, duration_s, sprint)
            except Exception:
                windows = _quali_windows_from_duration(duration_s, sprint)
        else:
            windows = _quali_windows_from_duration(duration_s, sprint)

    stage = "full" if pos_samples else ("minimal" if laps_rows else "metadata")
    _log.info("Replay pack stage = %s", stage)
    print(f"[ARIS] Replay pack stage = {stage}", flush=True)

    return {
        "ok": True,
        "session_type": used,
        "code_by_num": code_by_num,
        "num_by_code": num_by_code,
        "colours": colours,
        "q_times": q_times,
        "status_by_code": status_by_code,
        "laps": laps_rows,
        "weather": weather_rows,
        "pos_samples": pos_samples,
        "car_samples": car_samples,
        "pos_chunks": pos_chunks,
        "pos_chunk_loaded": pos_chunk_loaded,
        "quali_windows": windows,
        "stints": list(stints_acc.values()),
        "positions": positions_rows,
        "race_control": rc_rows,
        "date_start": clock_start,
        "date_end": clock_end,
        "synthetic_gps": False,
    }


def synthetic_pos_from_laps(
    laps: list[dict[str, Any]],
    path_x: list[float],
    path_y: list[float],
    *,
    step_s: float = 2.0,
) -> dict[str, list[tuple[float, float, float, str]]]:
    """Place cars on the circuit outline from lap timing (no FastF1 GPS).

    Enough for map motion during the minimal replay stage.
    """
    if not path_x or not path_y or not laps:
        return {}
    by_code: dict[str, list[dict[str, Any]]] = {}
    for row in laps:
        code = str(row.get("driver_code") or "")
        if not code:
            continue
        by_code.setdefault(code, []).append(row)
    out: dict[str, list[tuple[float, float, float, str]]] = {}
    for code, rows in by_code.items():
        rows = sorted(
            rows,
            key=lambda r: (int(r.get("lap_number") or 0), str(r.get("date_start") or "")),
        )
        samples: list[tuple[float, float, float, str]] = []
        for row in rows:
            start = _parse_maybe_dt(row.get("date_start"))
            if start is None:
                continue
            try:
                dur = float(row.get("lap_duration") or 90.0)
            except (TypeError, ValueError):
                dur = 90.0
            if dur <= 1:
                dur = 90.0
            pit = bool(row.get("is_pit_in_lap") or row.get("is_pit_out_lap"))
            st = "PitLane" if pit else "OnTrack"
            t0 = start.timestamp()
            n = max(2, int(dur / max(0.5, step_s)))
            for i in range(n + 1):
                u = i / n
                px, py = point_on_path(path_x, path_y, u)
                samples.append((t0 + u * dur, px, py, st))
        if samples:
            out[code] = samples
    return out


def sample_ff1_position(
    samples: list[tuple[float, float, float, str]], t_epoch: float
) -> tuple[float, float, str] | None:
    lo = _sample_lo(samples, t_epoch)
    if lo is None:
        return None
    t0, x0, y0, st0 = samples[lo]
    if lo + 1 >= len(samples):
        return x0, y0, st0
    t1, x1, y1, st1 = samples[lo + 1]
    dt = t1 - t0
    u = 0.0 if dt <= 1e-9 else max(0.0, min(1.0, (t_epoch - t0) / dt))
    return _lerp(x0, x1, u), _lerp(y0, y1, u), st1 if u >= 0.5 else st0


def _lerp_frac(f0: float, f1: float, u: float) -> float:
    d = f1 - f0
    if d < -0.5:
        d += 1.0
    if d > 0.5:
        d -= 1.0
    return ((f0 + u * d) % 1.0 + 1.0) % 1.0


def build_path_traces(
    pos_samples: dict[str, list[Any]],
    path_x: list[float],
    path_y: list[float],
    *,
    min_dt: float = 0.45,
) -> dict[str, dict[str, list[float]]]:
    """Compact (t, path_frac) traces so the client can animate replay cars at 60fps."""
    traces: dict[str, dict[str, list[float]]] = {}
    if not path_x or not path_y or not pos_samples:
        return traces
    for code, samples in pos_samples.items():
        thin_t: list[float] = []
        thin_x: list[float] = []
        thin_y: list[float] = []
        last_t: float | None = None
        for row in samples or []:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            try:
                t = float(row[0])
                x = float(row[1])
                y = float(row[2])
            except (TypeError, ValueError):
                continue
            if _is_null_gps(x, y) and path_x and min(path_x) > 5:
                continue
            if last_t is not None and (t - last_t) < min_dt:
                continue
            thin_t.append(t)
            thin_x.append(x)
            thin_y.append(y)
            last_t = t
        if len(thin_t) < 2:
            continue
        fracs = stabilize_path_fracs(project_points_along_path(thin_x, thin_y, path_x, path_y))
        traces[str(code)] = {
            "t": [round(v, 3) for v in thin_t],
            "f": [round(v, 5) for v in fracs],
        }
    return traces


def sample_path_trace(trace: dict[str, list[float]], t_epoch: float) -> float | None:
    times = trace.get("t") or []
    fracs = trace.get("f") or []
    n = min(len(times), len(fracs))
    if n == 0:
        return None
    if t_epoch + 0.25 < times[0]:
        return None
    lo, hi = 0, n - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if times[mid] <= t_epoch:
            lo = mid
        else:
            hi = mid - 1
    if lo >= n - 1:
        return float(fracs[lo])
    t0, t1 = times[lo], times[lo + 1]
    dt = t1 - t0
    u = 0.0 if dt <= 1e-9 else max(0.0, min(1.0, (t_epoch - t0) / dt))
    return _lerp_frac(float(fracs[lo]), float(fracs[lo + 1]), u)


def sample_ff1_car(
    samples: list[tuple[float, float, float, float, float]], t_epoch: float
) -> tuple[float, float, float, float] | None:
    """Return (throttle, brake, speed, drs) interpolated at t_epoch."""
    lo = _sample_lo(samples, t_epoch)
    if lo is None:
        return None
    t0, thr0, brk0, spd0, drs0 = samples[lo]
    if lo + 1 >= len(samples):
        return thr0, brk0, spd0, drs0
    t1, thr1, brk1, spd1, drs1 = samples[lo + 1]
    dt = t1 - t0
    u = 0.0 if dt <= 1e-9 else max(0.0, min(1.0, (t_epoch - t0) / dt))
    return (
        _lerp(thr0, thr1, u),
        _lerp(brk0, brk1, u),
        _lerp(spd0, spd1, u),
        _lerp(drs0, drs1, u),
    )


_CIRCUIT_MAP_MEM: dict[tuple[int, int], CircuitMapResponse] = {}


def sector_paths_from_outline(
    nx: list[float],
    ny: list[float],
    markers: list[CircuitMarker] | None = None,
) -> list[CircuitSectorPath]:
    """Split a closed racing line into S1 / S2 / S3 polylines."""
    n = min(len(nx), len(ny))
    if n < 4:
        return []

    def nearest(mx: float, my: float) -> int:
        best_i, best_d = 0, float("inf")
        for i in range(n):
            d = (nx[i] - mx) ** 2 + (ny[i] - my) ** 2
            if d < best_d:
                best_d, best_i = d, i
        return best_i

    by_kind = {m.kind: m for m in (markers or []) if getattr(m, "kind", None)}
    i1 = nearest(by_kind["s1"].x, by_kind["s1"].y) if "s1" in by_kind else max(1, n // 3)
    i2 = nearest(by_kind["s2"].x, by_kind["s2"].y) if "s2" in by_kind else max(i1 + 1, (2 * n) // 3)
    if not (0 < i1 < i2 < n):
        i1, i2 = max(1, n // 3), max(n // 3 + 1, (2 * n) // 3)

    def slice_path(i0: int, i1_end: int) -> tuple[list[float], list[float]]:
        if i1_end > i0:
            return nx[i0 : i1_end + 1], ny[i0 : i1_end + 1]
        return nx[i0:] + nx[: i1_end + 1], ny[i0:] + ny[: i1_end + 1]

    s1x, s1y = slice_path(0, i1)
    s2x, s2y = slice_path(i1, i2)
    s3x, s3y = slice_path(i2, n - 1)
    if s3x and (s3x[-1] != nx[0] or s3y[-1] != ny[0]):
        s3x = list(s3x) + [nx[0]]
        s3y = list(s3y) + [ny[0]]
    return [
        CircuitSectorPath(kind="s1", label="S1", x=s1x, y=s1y),
        CircuitSectorPath(kind="s2", label="S2", x=s2x, y=s2y),
        CircuitSectorPath(kind="s3", label="S3", x=s3x, y=s3y),
    ]


def ensure_sector_paths(cmap: CircuitMapResponse | dict) -> CircuitMapResponse:
    if isinstance(cmap, dict):
        cmap = CircuitMapResponse.model_validate(cmap)
    if cmap.sector_paths and any(p.x and p.y for p in cmap.sector_paths):
        return cmap
    if not cmap.x or not cmap.y:
        return cmap
    return cmap.model_copy(update={"sector_paths": sector_paths_from_outline(cmap.x, cmap.y, cmap.markers)})


def circuit_map_quick(year: int, round_number: int) -> CircuitMapResponse:
    """Prefer a cached / previous-year outline so replay never waits on this year's race load."""
    key = (int(year), int(round_number))
    hit = _CIRCUIT_MAP_MEM.get(key)
    if hit is not None and hit.available and hit.x:
        return hit
    open_now = _blocked_open_session(year, round_number, "R")
    # Always try a previous-year outline first so 2025 (and earlier) replays
    # do not block on this year's FastF1 telemetry just to draw the map.
    # Stay inside the replay window so 2023 FastF1 is never fetched.
    from backend.calendar import ALLOWED_REPLAY_YEARS

    for prev in (int(year) - 1, int(year) - 2):
        if prev not in ALLOWED_REPLAY_YEARS:
            continue
        fb = _circuit_map_same_track(prev, year, round_number)
        if fb is not None and fb.available and fb.x:
            copied = fb.model_copy(update={"year": year, "round_number": round_number})
            _CIRCUIT_MAP_MEM[key] = copied
            return copied
    if open_now:
        return CircuitMapResponse(
            year=year,
            round_number=round_number,
            available=False,
            fallback=True,
            error="Live race — using previous-year outline when available",
        )
    result = circuit_map(year, round_number)
    _CIRCUIT_MAP_MEM[key] = result
    return result


def circuit_map(year: int, round_number: int, *, _fallback: bool = True) -> CircuitMapResponse:
    """Track outline, corners, DRS and sector markers from FastF1."""
    empty = CircuitMapResponse(
        year=year,
        round_number=round_number,
        available=False,
        fallback=True,
        error="Corner data unavailable for this circuit",
    )
    mem_key = (int(year), int(round_number))

    def _unavailable() -> CircuitMapResponse:
        if _fallback and year >= 2026:
            fb = _circuit_map_same_track(year - 1, year, round_number)
            if fb is not None and fb.available:
                copied = fb.model_copy(update={"year": year, "round_number": round_number})
                _CIRCUIT_MAP_MEM[mem_key] = copied
                return copied
        return empty

    if _fallback:
        cached_map = _CIRCUIT_MAP_MEM.get(mem_key)
        if cached_map is not None and cached_map.available and cached_map.x:
            return cached_map
        if year >= 2026:
            fb = _circuit_map_same_track(year - 1, year, round_number)
            if fb is not None and fb.available and fb.x:
                copied = fb.model_copy(update={"year": year, "round_number": round_number})
                _CIRCUIT_MAP_MEM[mem_key] = copied
                return copied
    if _blocked_open_session(year, round_number, "R"):
        return _unavailable()
    try:
        sess = load_session(year, round_number, "R", telemetry=True)
        laps = sess.laps
        if laps is None or laps.empty:
            return _unavailable()
        pos = None
        try:
            fast = laps.pick_fastest()
            pos = fast.get_pos_data()
        except Exception as extra:
            _log.warning("pick_fastest failed for %s R%s: %s", year, round_number, extra)
            pos = None
        if pos is None or getattr(pos, "empty", True) or "X" not in getattr(pos, "columns", []):
            pos_data = getattr(sess, "pos_data", None) or {}
            drivers = list(pos_data.keys())
            if drivers:
                pos = pos_data[drivers[0]]
            else:
                return _unavailable()
        if pos is None or getattr(pos, "empty", True) or "X" not in pos.columns:
            return _unavailable()
        raw_x = [float(v) for v in pos["X"].dropna().tolist()]
        raw_y = [float(v) for v in pos["Y"].dropna().tolist()]
        if not raw_x or not raw_y:
            return _unavailable()
        if max(raw_x) - min(raw_x) == 0 or max(raw_y) - min(raw_y) == 0:
            return _unavailable()
        step = max(1, len(raw_x) // 400)
        raw_x, raw_y = raw_x[::step], raw_y[::step]
        bounds, nx, ny = _bounds_and_norm(raw_x, raw_y)
        if bounds is None or len(nx) < 2:
            return _unavailable()
        nx, ny = close_circuit_loop(nx, ny)
        pit_x, pit_y, pit_stalls = pit_lane_from_path(nx, ny)
        gps_lane = pit_lane_from_points(
            _pit_points_from_pos_data(getattr(sess, "pos_data", None) or {}, bounds),
            nx,
            ny,
        )
        if gps_lane:
            pit_x, pit_y, pit_stalls = gps_lane

        npts = max(len(nx) - 1, 1)
        corners: list[CircuitCorner] = []
        circuit_key = None
        try:
            from backend.calendar import get_round

            circuit_key = get_round(year, round_number).circuit_key
        except Exception:
            circuit_key = None
        drs_segments, drs_marks = drs_on_path(nx, ny, circuit_key)
        markers: list[CircuitMarker] = [CircuitMarker(kind="sf", x=nx[0], y=ny[0], label="S/F")]
        if pit_x and pit_y:
            markers.append(CircuitMarker(kind="pit_in", x=pit_x[0], y=pit_y[0], label="PIT IN"))
            markers.append(CircuitMarker(kind="pit_out", x=pit_x[-1], y=pit_y[-1], label="PIT OUT"))
        markers.extend(drs_marks)
        markers.extend(grid_marks(nx, ny))
        try:
            info = sess.get_circuit_info()
        except Exception as extra:
            _log.warning("get_circuit_info failed for %s R%s: %s", year, round_number, extra)
            info = None
        if info is not None:
            cdf = getattr(info, "corners", None)
            if cdf is not None and not getattr(cdf, "empty", True):
                n = max(len(cdf), 1)
                dist_col = "Distance" if "Distance" in getattr(pos, "columns", []) else None
                pos_dist = [float(v) for v in pos["Distance"].tolist()] if dist_col else []
                for i, rec in cdf.iterrows():
                    number = (
                        int(rec["Number"])
                        if "Number" in cdf.columns and pd.notna(rec.get("Number"))
                        else int(i) + 1
                    )
                    letter = ""
                    if "Letter" in cdf.columns and pd.notna(rec.get("Letter")):
                        letter = str(rec["Letter"])
                    angle = _num(rec.get("Angle")) if "Angle" in cdf.columns else None
                    dist = _num(rec.get("Distance")) if "Distance" in cdf.columns else None
                    if "X" in cdf.columns and "Y" in cdf.columns and pd.notna(rec.get("X")):
                        cx, cy = _apply_bounds(float(rec["X"]), float(rec["Y"]), bounds)
                    elif dist is not None and pos_dist:
                        idx_src = _nearest_index(pos_dist, dist)
                        idx = min(len(nx) - 1, int(idx_src / max(len(pos_dist) - 1, 1) * npts))
                        cx, cy = nx[idx], ny[idx]
                    else:
                        idx = min(len(nx) - 1, int((number - 0.5) / n * npts))
                        cx, cy = nx[idx], ny[idx]
                    corners.append(
                        CircuitCorner(
                            number=number,
                            letter=letter,
                            angle=angle,
                            distance=dist,
                            x=cx,
                            y=cy,
                            description=f"Turn {number}{letter}".strip(),
                        )
                    )
            sectors = getattr(info, "marshal_sectors", None)
            if sectors is not None and not getattr(sectors, "empty", True) and "X" in sectors.columns:
                labels = [("S1", "s1"), ("S2", "s2"), ("S3", "s3")]
                count = 0
                for _, rec in sectors.iterrows():
                    if count >= 3 or pd.isna(rec.get("X")):
                        continue
                    mx, my = _apply_bounds(float(rec["X"]), float(rec["Y"]), bounds)
                    lab, kind = labels[count]
                    markers.append(CircuitMarker(kind=kind, x=mx, y=my, label=lab))
                    count += 1

        if not any(m.kind in {"s1", "s2", "s3"} for m in markers) and len(nx) > 3:
            for frac, lab, kind in ((1 / 3, "S1", "s1"), (2 / 3, "S2", "s2"), (0.99, "S3", "s3")):
                idx = min(len(nx) - 1, int(frac * npts))
                markers.append(CircuitMarker(kind=kind, x=nx[idx], y=ny[idx], label=lab))

        built = CircuitMapResponse(
            year=year,
            round_number=round_number,
            x=nx,
            y=ny,
            corners=corners,
            markers=markers,
            drs_segments=drs_segments,
            pit_lane_x=pit_x,
            pit_lane_y=pit_y,
            pit_stalls=pit_stalls,
            sector_paths=sector_paths_from_outline(nx, ny, markers),
            bounds=bounds,
            available=True,
            fallback=False,
        )
        _CIRCUIT_MAP_MEM[mem_key] = built
        return built
    except Exception as extra:
        _log.warning("circuit_map failed for %s R%s: %s", year, round_number, extra)
        if _fallback and year >= 2026:
            fb = _circuit_map_same_track(year - 1, year, round_number)
            if fb is not None and fb.available:
                copied = fb.model_copy(update={"year": year, "round_number": round_number})
                _CIRCUIT_MAP_MEM[mem_key] = copied
                return copied
        return empty


def _circuit_map_same_track(prev_year: int, year: int, round_number: int) -> CircuitMapResponse | None:
    try:
        from backend.calendar import ALLOWED_REPLAY_YEARS, get_calendar, get_round

        if int(prev_year) not in ALLOWED_REPLAY_YEARS:
            return None

        rnd = get_round(year, round_number)
        key = (rnd.circuit_key or "").lower()
        name = (rnd.name or rnd.circuit_name or "").lower()
        city = (rnd.city or "").lower()
        prev = get_calendar(prev_year)
        for other in prev.rounds:
            other_key = (other.circuit_key or "").lower()
            other_name = (other.name or other.circuit_name or "").lower()
            other_city = (other.city or "").lower()
            if key and other_key == key:
                return circuit_map(prev_year, other.round_number, _fallback=False)
            if city and other_city == city:
                return circuit_map(prev_year, other.round_number, _fallback=False)
            if name and (name in other_name or other_name in name):
                return circuit_map(prev_year, other.round_number, _fallback=False)
    except Exception as extra:
        _log.info("same-track fallback failed: %s", extra)
    return None


def session_positions(
    year: int, round_number: int, session_type: str, lap: int
) -> SessionPositionsResponse:
    from backend.standings import team_colour

    if _blocked_open_session(year, round_number, session_type):
        return SessionPositionsResponse(
            year=year, round_number=round_number, session_type=str(session_type).upper(), lap=lap, positions=[]
        )

    empty = SessionPositionsResponse(
        year=year, round_number=round_number, session_type=session_type.upper(), lap=lap, positions=[]
    )
    try:
        cmap = circuit_map(year, round_number)
        bounds = cmap.bounds
        sess = load_session(year, round_number, session_type, telemetry=True)
        results = sess.results
        laps_df = sess.laps
        if laps_df is None or laps_df.empty:
            return empty

        code_by_num: dict[str, str] = {}
        team_by_code: dict[str, str | None] = {}
        dnf_codes: set[str] = set()
        if results is not None and not results.empty:
            for _, rec in results.iterrows():
                code = str(rec.get("Abbreviation") or rec.get("Driver") or "")[:3].upper()
                num = rec.get("DriverNumber")
                if not code:
                    continue
                if num is not None and pd.notna(num):
                    code_by_num[str(int(num))] = code
                team_by_code[code] = team_colour(str(rec.get("TeamName") or rec.get("Team") or ""))
                status = str(rec.get("Status") or "")
                laps_done = _int(rec.get("Laps")) or 0
                low = status.lower()
                finished = low in {"finished", "lapped"} or "+" in status or "lap" in low and "+" in status
                if not finished and laps_done < max(lap, 1) and low not in {"", "finished"}:
                    dnf_codes.add(code)

        this_lap = laps_df[laps_df["LapNumber"] == lap] if "LapNumber" in laps_df.columns else laps_df.iloc[0:0]
        ref_time = None
        if not this_lap.empty and "Time" in this_lap.columns:
            times = this_lap["Time"].dropna()
            if not times.empty:
                ref_time = times.median()

        positions: list[SessionCarPosition] = []
        pos_data = getattr(sess, "pos_data", None) or {}
        for num, df in pos_data.items():
            code = code_by_num.get(str(num), "")
            if not code:
                try:
                    drv = sess.get_driver(str(num))
                    code = str(getattr(drv, "Abbreviation", "") or "")[:3].upper()
                except Exception:
                    code = f"D{num}"
            if df is None or getattr(df, "empty", True) or "X" not in df.columns:
                continue
            try:
                if ref_time is not None and "Time" in df.columns:
                    delta = (df["Time"] - ref_time).abs()
                    row = df.iloc[int(delta.argmin())]
                else:
                    row = df.iloc[min(len(df) - 1, max(0, int(lap * len(df) / 80)))]
                rx, ry = float(row["X"]), float(row["Y"])
            except Exception:
                continue
            px, py = _apply_bounds(rx, ry, bounds) if bounds else (rx, ry)
            pitted = False
            if "Status" in df.columns:
                pitted = "pit" in str(row.get("Status") or "").lower()
            drv_laps = this_lap[this_lap["Driver"] == code] if "Driver" in this_lap.columns else this_lap.iloc[0:0]
            if not drv_laps.empty:
                for col in ("PitInTime", "PitOutTime"):
                    if col in drv_laps.columns:
                        pit_val = drv_laps.iloc[0].get(col)
                        pitted = pitted or (pit_val is not None and not pd.isna(pit_val))
            positions.append(
                SessionCarPosition(
                    driver_code=code,
                    x=px,
                    y=py,
                    team_colour=team_by_code.get(code),
                    is_pitted=bool(pitted),
                    is_dnf=code in dnf_codes,
                )
            )

        if not positions and "Driver" in laps_df.columns:
            for code in laps_df["Driver"].unique().tolist():
                try:
                    dlaps = laps_df[(laps_df["Driver"] == code) & (laps_df["LapNumber"] == lap)]
                    if dlaps.empty:
                        dlaps = laps_df[laps_df["Driver"] == code].tail(1)
                    if dlaps.empty:
                        continue
                    pdata = dlaps.iloc[0].get_pos_data()
                    if pdata is None or pdata.empty:
                        continue
                    mid = pdata.iloc[len(pdata) // 2]
                    rx, ry = float(mid["X"]), float(mid["Y"])
                    px, py = _apply_bounds(rx, ry, bounds) if bounds else (rx, ry)
                    positions.append(
                        SessionCarPosition(
                            driver_code=str(code),
                            x=px,
                            y=py,
                            team_colour=team_by_code.get(str(code)),
                            is_dnf=str(code) in dnf_codes,
                        )
                    )
                except Exception:
                    continue

        return SessionPositionsResponse(
            year=year,
            round_number=round_number,
            session_type=session_type.upper(),
            lap=lap,
            positions=positions,
        )
    except Exception:
        return empty


def circuit_preview_safe(year: int, round_number: int) -> CircuitMapResponse:
    """Thumbnail from memory/disk only — never starts a FastF1 session load."""
    from backend.cache import cache, get_disk

    empty = CircuitMapResponse(
        year=year,
        round_number=round_number,
        available=False,
        fallback=True,
        error="Preview not cached yet",
    )
    try:
        preview_key = f"circuit_preview_{year}_{round_number}"
        hit = cache.get(preview_key, 7 * 24 * 3600)
        if hit is not None:
            return hit
        disk = get_disk()
        disk_hit = disk.get(preview_key)
        if disk_hit is not None:
            return disk_hit
        mem = _CIRCUIT_MAP_MEM.get((int(year), int(round_number)))
        if mem is not None and mem.available and mem.x:
            preview = circuit_preview_from_map(mem)
            cache.set(preview_key, preview)
            return preview
        map_key = f"circuit_map_v6_{year}_{round_number}"
        full = cache.get(map_key, 7 * 24 * 3600) or disk.get(map_key)
        if full is not None:
            preview = circuit_preview_from_map(full)
            cache.set(preview_key, preview)
            return preview
        for y in (year - 1, year - 2, 2025, 2024):
            if y < 2018 or y == year:
                continue
            sib = cache.get(f"circuit_preview_{y}_{round_number}", 7 * 24 * 3600) or disk.get(
                f"circuit_preview_{y}_{round_number}"
            )
            if sib is not None and getattr(sib, "available", False) and getattr(sib, "x", None):
                if hasattr(sib, "model_copy"):
                    return sib.model_copy(update={"year": year, "round_number": round_number})
                return sib
            mem_y = _CIRCUIT_MAP_MEM.get((int(y), int(round_number)))
            if mem_y is not None and mem_y.available and mem_y.x:
                return circuit_preview_from_map(
                    mem_y.model_copy(update={"year": year, "round_number": round_number})
                )
        return empty
    except Exception as extra:
        _log.warning("circuit preview safe failed for %s R%s: %s", year, round_number, extra)
        return empty


def circuit_preview_from_map(full: CircuitMapResponse) -> CircuitMapResponse:
    """Downsample a cached full map to ~20 points for index cards."""
    if not full.x or not full.y or not full.available:
        return CircuitMapResponse(
            year=full.year,
            round_number=full.round_number,
            available=False,
            fallback=True,
            error=full.error or "Circuit preview unavailable",
        )
    step = max(1, len(full.x) // 20)
    xs = full.x[::step]
    ys = full.y[::step]
    if xs[-1] != full.x[-1]:
        xs.append(full.x[-1])
        ys.append(full.y[-1])
    xs, ys = close_circuit_loop(xs[:21], ys[:21])
    return CircuitMapResponse(
        year=full.year,
        round_number=full.round_number,
        x=xs[:21],
        y=ys[:21],
        corners=[],
        markers=[],
        drs_segments=[],
        bounds=full.bounds,
        available=True,
        fallback=False,
        view_box=full.view_box,
    )


def build_circuit_preview(year: int, round_number: int) -> CircuitMapResponse:
    """20-point Quali outline for the circuits index. Used by startup pre-warm only."""
    empty = CircuitMapResponse(
        year=year,
        round_number=round_number,
        available=False,
        fallback=True,
        error="Circuit preview unavailable",
    )
    try:
        sess = load_session(year, round_number, "Q", telemetry=True, weather=False, messages=False)
        laps = sess.laps
        if laps is None or laps.empty:
            return empty
        fast = laps.pick_fastest()
        pos = fast.get_pos_data()
        if pos is None or getattr(pos, "empty", True) or "X" not in pos.columns:
            return empty
        x = pos["X"].dropna().values
        y = pos["Y"].dropna().values
        if len(x) < 10:
            return empty
        indices = [int(i * (len(x) - 1) / 19) for i in range(20)]
        raw_x = [float(x[i]) for i in indices]
        raw_y = [float(y[i]) for i in indices]
        bounds, nx, ny = _bounds_and_norm(raw_x, raw_y)
        if bounds is None or len(nx) < 2:
            return empty
        return CircuitMapResponse(
            year=year,
            round_number=round_number,
            x=nx,
            y=ny,
            bounds=bounds,
            available=True,
            fallback=False,
        )
    except Exception as extra:
        _log.warning("circuit preview failed for %s R%s: %s", year, round_number, extra)
        return empty


def session_positions_all(
    year: int, round_number: int, session_type: str = "R"
) -> SessionPositionsAllResponse:
    from backend.standings import team_colour

    if _blocked_open_session(year, round_number, session_type):
        return SessionPositionsAllResponse(
            year=year, round_number=round_number, session_type=str(session_type).upper(), laps={}
        )

    empty = SessionPositionsAllResponse(
        year=year, round_number=round_number, session_type=session_type.upper(), laps={}
    )
    try:
        cmap = circuit_map(year, round_number)
        bounds = cmap.bounds
        sess = load_session(year, round_number, session_type, telemetry=True)
        laps_df = sess.laps
        results = sess.results
        if laps_df is None or laps_df.empty:
            return empty
        max_lap = int(laps_df["LapNumber"].max()) if "LapNumber" in laps_df.columns else 0
        if max_lap < 1:
            return empty

        code_by_num: dict[str, str] = {}
        team_by_code: dict[str, str | None] = {}
        last_lap_by_code: dict[str, int] = {}
        if results is not None and not results.empty:
            for _, rec in results.iterrows():
                code = str(rec.get("Abbreviation") or rec.get("Driver") or "")[:3].upper()
                num = rec.get("DriverNumber")
                if not code:
                    continue
                if num is not None and pd.notna(num):
                    code_by_num[str(int(num))] = code
                team_by_code[code] = team_colour(str(rec.get("TeamName") or rec.get("Team") or ""))
                last_lap_by_code[code] = _int(rec.get("Laps")) or 0

        if "Driver" in laps_df.columns and "LapNumber" in laps_df.columns:
            for code, grp in laps_df.groupby("Driver"):
                last_lap_by_code[str(code)] = int(grp["LapNumber"].max())

        pos_data = getattr(sess, "pos_data", None) or {}
        laps_out: dict[str, list[SessionCarPosition]] = {str(n): [] for n in range(1, max_lap + 1)}

        last_frac_by_code: dict[str, float] = {}
        for num, df in pos_data.items():
            code = code_by_num.get(str(num), "")
            if not code:
                try:
                    drv = sess.get_driver(str(num))
                    code = str(getattr(drv, "Abbreviation", "") or "")[:3].upper()
                except Exception:
                    code = f"D{num}"
            if df is None or getattr(df, "empty", True) or "X" not in df.columns:
                continue
            drv_laps = (
                laps_df[laps_df["Driver"] == code]
                if "Driver" in laps_df.columns
                else laps_df.iloc[0:0]
            )
            last_for_driver = last_lap_by_code.get(code, max_lap)
            for lap_no in range(1, max_lap + 1):
                row = None
                this = drv_laps[drv_laps["LapNumber"] == lap_no] if not drv_laps.empty else drv_laps
                ref_time = None
                pitted = False
                if not this.empty:
                    for col in ("LapStartTime", "Time"):
                        if col in this.columns and pd.notna(this.iloc[0].get(col)):
                            ref_time = this.iloc[0].get(col)
                            break
                    for col in ("PitInTime", "PitOutTime"):
                        if col in this.columns:
                            pit_val = this.iloc[0].get(col)
                            pitted = pitted or (pit_val is not None and not pd.isna(pit_val))
                try:
                    if ref_time is not None and "Time" in df.columns:
                        delta = (df["Time"] - ref_time).abs()
                        row = df.iloc[int(delta.argmin())]
                    else:
                        frac = lap_no / max(max_lap, 1)
                        row = df.iloc[min(len(df) - 1, max(0, int(frac * (len(df) - 1))))]
                    rx, ry = float(row["X"]), float(row["Y"])
                except Exception:
                    continue
                px, py = _apply_bounds(rx, ry, bounds) if bounds else (rx, ry)
                path_frac = 0.0
                gps: float | None = None
                if cmap.x and cmap.y:
                    try:
                        gps = float(compute_path_distance(px, py, cmap.x, cmap.y))
                    except Exception:
                        gps = None
                timing_frac: float | None = None
                if ref_time is not None and row is not None and "Time" in df.columns:
                    try:
                        dt = float((row["Time"] - ref_time).total_seconds())
                        lt = this.iloc[0].get("LapTime") if not this.empty else None
                        lap_s = None
                        if lt is not None and pd.notna(lt) and hasattr(lt, "total_seconds"):
                            lap_s = float(lt.total_seconds())
                        if lap_s and lap_s > 1 and dt >= 0:
                            timing_frac = max(0.0, min(1.0, dt / lap_s))
                    except Exception:
                        timing_frac = None
                if timing_frac is not None:
                    path_frac = correct_path_frac(timing_frac, gps)
                elif gps is not None:
                    prev = last_frac_by_code.get(code)
                    path_frac = correct_path_frac(prev, gps) if prev is not None else gps
                if gps is not None or timing_frac is not None:
                    last_frac_by_code[code] = path_frac
                speed_ms = None
                if not this.empty and "LapTime" in this.columns:
                    lt = this.iloc[0].get("LapTime")
                    if lt is not None and pd.notna(lt) and hasattr(lt, "total_seconds"):
                        speed_ms = float(lt.total_seconds())
                laps_out[str(lap_no)].append(
                    SessionCarPosition(
                        driver_code=code,
                        x=px,
                        y=py,
                        team_colour=team_by_code.get(code),
                        is_pitted=bool(pitted),
                        is_dnf=last_for_driver < max_lap and lap_no > last_for_driver,
                        path_frac=path_frac,
                        speed_ms=speed_ms,
                    )
                )

        if cmap.x and cmap.y and not any(laps_out.values()):
            for lap_no in range(1, max_lap + 1):
                field = (
                    laps_df[laps_df["LapNumber"] == lap_no]
                    if "LapNumber" in laps_df.columns
                    else laps_df.iloc[0:0]
                )
                if field.empty:
                    continue
                ordered = field.sort_values("Position") if "Position" in field.columns else field
                for i, rec in ordered.iterrows():
                    code = str(rec.get("Driver") or "")[:3].upper()
                    if not code:
                        continue
                    pos = rec.get("Position")
                    try:
                        p = float(pos) if pos is not None and pd.notna(pos) else float(i + 1)
                    except (TypeError, ValueError):
                        p = float(i + 1)
                    frac = ((p - 1.0) * 0.012) % 1.0
                    px, py = point_at_path_frac(cmap.x, cmap.y, frac)
                    last_for_driver = last_lap_by_code.get(code, max_lap)
                    laps_out[str(lap_no)].append(
                        SessionCarPosition(
                            driver_code=code,
                            x=px,
                            y=py,
                            team_colour=team_by_code.get(code),
                            is_pitted=False,
                            is_dnf=last_for_driver < max_lap and lap_no > last_for_driver,
                            path_frac=frac,
                        )
                    )

        return SessionPositionsAllResponse(
            year=year,
            round_number=round_number,
            session_type=session_type.upper(),
            laps=laps_out,
            circuit_path=CircuitPathXY(x=list(cmap.x), y=list(cmap.y)) if cmap.x and cmap.y else None,
        )
    except Exception as extra:
        _log.warning("session_positions_all failed for %s R%s: %s", year, round_number, extra)
        return empty


def _snapshot_at_lap(year: int, round_number: int, lap: int, total_laps: int):
    from aris.commentary import DriverSnap, FieldSnapshot

    raw = timing_at_lap(year, round_number, "R", lap)
    stints = session_stints(year, round_number, "R").stints
    stint_no: dict[str, int] = {}
    compound: dict[str, str | None] = {}
    for s in stints:
        if s.lap_start <= lap <= s.lap_end:
            stint_no[s.driver_code] = s.stint_number
            compound[s.driver_code] = s.compound
    drivers: list[DriverSnap] = []
    ordered = sorted(raw, key=lambda r: r.get("position") or 99)
    for i, r in enumerate(ordered):
        code = str(r["driver_code"])
        gap_ahead = None
        if i > 0:
            g0 = ordered[i - 1].get("gap_to_leader_s")
            g1 = r.get("gap_to_leader_s")
            if g0 is not None and g1 is not None:
                gap_ahead = float(g1) - float(g0)
        drivers.append(
            DriverSnap(
                code=code,
                position=r.get("position"),
                gap_to_leader_s=r.get("gap_to_leader_s"),
                gap_ahead_s=gap_ahead,
                compound=compound.get(code) or r.get("compound"),
                tyre_life=r.get("tyre_life"),
                stint_number=stint_no.get(code),
                last_lap_ms=r.get("last_lap_ms"),
                best_lap_ms=r.get("best_lap_ms"),
            )
        )
    msgs = []
    try:
        for m in session_messages(year, round_number, "R").messages:
            if m.lap == lap:
                msgs.append({"lap": m.lap, "flag": m.flag, "category": m.category, "message": m.message})
    except Exception:
        msgs = []
    raining = False
    try:
        raining = rainfall_at_session_lap(year, round_number, "R", lap)
    except Exception:
        raining = False
    return FieldSnapshot(lap=lap, total_laps=total_laps, drivers=drivers, messages=msgs, rainfall=raining)


def session_events(
    year: int, round_number: int, session_type: str, lap: int, focus_driver: str = "NOR"
) -> SessionEventsResponse:
    if _blocked_open_session(year, round_number, session_type):
        return SessionEventsResponse(
            year=year,
            round_number=round_number,
            session_type=str(session_type).upper(),
            lap=lap,
            events=[],
        )
    from aris.commentary import events_for_transition
    from aris.tracks import load_track_config
    from backend.calendar import get_round

    try:
        rnd = get_round(year, round_number)
        cfg = load_track_config(rnd.country, year=year, round_no=round_number)
        total = cfg.total_laps
        pit_loss_s: float | None = cfg.pit_loss_s
    except Exception:
        cfg = None
        total = 72
        pit_loss_s = None

    from aris.physics.tires import DEFAULT_COMPOUND_SLOPE, normalize_compound

    deg_rate_s: float | None = DEFAULT_COMPOUND_SLOPE.get("MEDIUM", 0.05)
    prev = _snapshot_at_lap(year, round_number, max(1, lap - 1), total) if lap > 1 else None
    current = _snapshot_at_lap(year, round_number, lap, total)
    if cfg is not None:
        focus = current.get_driver((focus_driver or "").upper())
        if focus and focus.compound:
            key = normalize_compound(focus.compound)
            slopes = cfg.compound_slopes or DEFAULT_COMPOUND_SLOPE
            deg_rate_s = float(slopes.get(key, DEFAULT_COMPOUND_SLOPE.get(key, 0.05)))
    msgs = events_for_transition(
        prev, current, focus_driver, pit_loss_s=pit_loss_s, deg_rate_s=deg_rate_s
    )
    # Deduplicate identical texts in one lap (SC messages can repeat).
    seen: set[str] = set()
    events: list[CommentaryEvent] = []
    for m in msgs:
        if m.text in seen:
            continue
        seen.add(m.text)
        events.append(CommentaryEvent(type=m.type.lower() if m.type != "INTEL" else "intel", text=m.text))
    return SessionEventsResponse(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        lap=lap,
        events=events,
    )
