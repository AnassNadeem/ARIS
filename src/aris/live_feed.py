"""Live F1 dashboard feed for Streamlit — SignalR first, OpenF1 live fill, FastF1 replay.

Streamlit Cloud does not run the FastAPI broker. This module pulls the same
real feeds the React app uses and exposes a single snapshot the Live page
can render without a Play click.

Live path: F1 livetiming SignalR (no auth) + OpenF1 REST when credentials
or the public post-session API are available.

After the live window ends: replay from FastF1. OpenF1 is live-only.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from aris.models.features import estimate_fuel_kg
from aris.physics.tires import normalize_compound
from aris.state import RaceState, SC_PACE_CAVEAT, track_status_is_sc_vsc

Mode = Literal["waiting", "live", "replay"]

# FIA / calendar overlay for the Dutch GP sprint weekend (UTC).
# Used only for countdown / auto-replay when SessionInfo has not arrived yet.
ZANDVOORT_2026_WINDOWS: tuple[tuple[str, str, str, float], ...] = (
    ("FP1", "Practice 1", "2026-08-21T10:30:00+00:00", 1.5),
    ("SQ", "Sprint Qualifying", "2026-08-21T14:30:00+00:00", 0.8),
    ("S", "Sprint", "2026-08-22T10:00:00+00:00", 1.0),
    ("Q", "Qualifying", "2026-08-22T14:00:00+00:00", 1.0),
    ("R", "Race", "2026-08-23T13:00:00+00:00", 2.0),
)

_COMPOUND_FULL = {
    "S": "SOFT",
    "M": "MEDIUM",
    "H": "HARD",
    "I": "INTERMEDIATE",
    "W": "WET",
    "SOFT": "SOFT",
    "MEDIUM": "MEDIUM",
    "HARD": "HARD",
    "INTERMEDIATE": "INTERMEDIATE",
    "INTER": "INTERMEDIATE",
    "WET": "WET",
    "UNKNOWN": "MEDIUM",
}

_TRACK_FLAG = {
    "1": "GREEN",
    "2": "YELLOW",
    "3": "YELLOW",
    "4": "SC",
    "5": "RED",
    "6": "VSC",
    "7": "VSC",
}

_STATE_LOCK = threading.RLock()
_LAST_LIVE: "LiveSnapshot | None" = None
_REPLAY_PACK: dict[str, Any] | None = None
_REPLAY_KEY: str | None = None
_FF1_THREAD: threading.Thread | None = None
_FF1_ERROR: str | None = None
_OPENF1_HITS: list[float] = []


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def session_type_map(name: str, stype: str = "") -> str:
    blob = f"{name} {stype}".lower()
    if "sprint quali" in blob or "sprint shootout" in blob:
        return "SQ"
    if "sprint" in blob:
        return "S"
    if "race" in blob:
        return "R"
    if "quali" in blob:
        return "Q"
    if "practice 1" in blob or blob.strip() == "fp1":
        return "FP1"
    if "practice 2" in blob or blob.strip() == "fp2":
        return "FP2"
    if "practice 3" in blob or blob.strip() == "fp3":
        return "FP3"
    return (stype or name or "UNKNOWN")[:4].upper()


def compound_letter(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    u = str(raw).strip().upper()
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
    full = _COMPOUND_FULL.get(u)
    if full == "SOFT":
        return "S"
    if full == "MEDIUM":
        return "M"
    if full == "HARD":
        return "H"
    if full == "INTERMEDIATE":
        return "I"
    if full == "WET":
        return "W"
    return u[:1]


def compound_full(raw: Any) -> str:
    letter = compound_letter(raw)
    if letter and letter in _COMPOUND_FULL:
        return _COMPOUND_FULL[letter]
    try:
        return normalize_compound(str(raw or "MEDIUM"))
    except Exception:
        return "MEDIUM"


def fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "—"
    if ms < 0:
        return "—"
    total = ms / 1000.0
    minutes = int(total // 60)
    seconds = total - minutes * 60
    if minutes:
        return f"{minutes}:{seconds:06.3f}"
    return f"{seconds:.3f}"


def fmt_gap(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds == 0:
        return "LEADER"
    if seconds >= 90:
        laps = int(round(seconds / 90.0))
        return f"+{laps} LAP" if laps == 1 else f"+{laps} LAPS"
    return f"+{seconds:.3f}"


@dataclass
class DriverLive:
    number: int
    code: str
    name: str = ""
    team: str = ""
    team_colour: str | None = None
    position: int = 99
    grid_position: int | None = None
    position_change: int | None = None
    gap_to_leader_s: float | None = None
    gap_to_ahead_s: float | None = None
    last_lap_ms: int | None = None
    best_lap_ms: int | None = None
    sector1_ms: int | None = None
    sector2_ms: int | None = None
    sector3_ms: int | None = None
    s1_colour: str = "grey"
    s2_colour: str = "grey"
    s3_colour: str = "grey"
    compound: str | None = None
    tyre_life: int | None = None
    stint_number: int | None = None
    pit_count: int = 0
    in_pit: bool = False
    retired: bool = False
    fastest_lap: bool = False
    n_laps: int | None = None
    gps_x: float | None = None
    gps_y: float | None = None
    speed_kph: float | None = None
    throttle: float | None = None
    brake: float | None = None
    rpm: float | None = None
    gear: int | None = None
    drs: int | None = None


@dataclass
class LiveSnapshot:
    mode: Mode
    is_live: bool
    source: str
    session_name: str
    session_type: str
    year: int | None
    round_number: int | None
    circuit: str
    country: str
    current_lap: int | None
    total_laps: int | None
    flag: str
    remaining_s: int | None
    elapsed_s: int | None
    feed_age_s: float | None
    delay_note: str
    air_temp: float | None = None
    track_temp: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    wind_speed: float | None = None
    wind_direction: float | None = None
    rainfall: bool | None = None
    drivers: list[DriverLive] = field(default_factory=list)
    race_control: list[str] = field(default_factory=list)
    path_x: list[float] = field(default_factory=list)
    path_y: list[float] = field(default_factory=list)
    error: str | None = None
    as_of: datetime = field(default_factory=now_utc)
    next_session_name: str | None = None
    next_session_utc: datetime | None = None
    replay_duration_s: int = 0
    session_key: int | None = None


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _channel_float(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in row and row[key] is not None:
            return _float(row[key])
    return None


def last_stint(stints: Any) -> tuple[dict[str, Any], int]:
    """Return (latest stint dict, stint count). Accepts list or keyed dict."""
    if isinstance(stints, dict):
        items = []
        for key, val in stints.items():
            if not isinstance(val, dict):
                continue
            try:
                idx = int(key)
            except (TypeError, ValueError):
                idx = 0
            items.append((idx, val))
        items.sort(key=lambda kv: kv[0])
        if not items:
            return {}, 0
        return items[-1][1], len(items)
    if isinstance(stints, list):
        rows = [s for s in stints if isinstance(s, dict)]
        if not rows:
            return {}, 0
        return rows[-1], len(rows)
    return {}, 0


def parse_timing_lines(
    timing: dict[str, Any],
    *,
    drivers: dict[str, Any] | None = None,
    app: dict[str, Any] | None = None,
    stats: dict[str, Any] | None = None,
    positions: dict[str, dict[str, Any]] | None = None,
    cardata: dict[str, dict[str, Any]] | None = None,
) -> list[DriverLive]:
    """Build driver rows from F1 livetiming TimingData (+ optional topics)."""
    from backend.f1_live import parse_gap_s, parse_laptime_ms, sector_colour

    lines = timing.get("Lines") if isinstance(timing, dict) else None
    if not isinstance(lines, dict):
        return []
    drivers = drivers or {}
    app_lines = (app or {}).get("Lines") if isinstance(app, dict) else {}
    if not isinstance(app_lines, dict):
        app_lines = {}
    stat_lines = (stats or {}).get("Lines") if isinstance(stats, dict) else {}
    if not isinstance(stat_lines, dict):
        stat_lines = {}
    positions = positions or {}
    cardata = cardata or {}

    rows: list[DriverLive] = []
    best_ms: dict[str, int] = {}
    for num, line in lines.items():
        if not isinstance(line, dict):
            continue
        drv = drivers.get(str(num)) if isinstance(drivers.get(str(num)), dict) else {}
        code = str(drv.get("Tla") or line.get("Tla") or f"D{num}")[:3].upper()
        last_ms = parse_laptime_ms(line.get("LastLapTime"))
        best_ms_val = parse_laptime_ms(line.get("BestLapTime"))
        stat = stat_lines.get(str(num)) if isinstance(stat_lines.get(str(num)), dict) else {}
        if best_ms_val is None:
            best_ms_val = parse_laptime_ms((stat.get("PersonalBestLapTime") or {}).get("Value") if isinstance(stat.get("PersonalBestLapTime"), dict) else stat.get("PersonalBestLapTime"))
        if last_ms is not None:
            best_ms[str(num)] = min(last_ms, best_ms.get(str(num), last_ms))
        if best_ms_val is not None:
            best_ms[str(num)] = min(best_ms_val, best_ms.get(str(num), best_ms_val))

        sectors = line.get("Sectors") or {}
        if isinstance(sectors, list):
            s1 = sectors[0] if len(sectors) > 0 else {}
            s2 = sectors[1] if len(sectors) > 1 else {}
            s3 = sectors[2] if len(sectors) > 2 else {}
        elif isinstance(sectors, dict):
            s1 = sectors.get("0") or sectors.get(0) or {}
            s2 = sectors.get("1") or sectors.get(1) or {}
            s3 = sectors.get("2") or sectors.get(2) or {}
        else:
            s1 = s2 = s3 = {}
        if not isinstance(s1, dict):
            s1 = {}
        if not isinstance(s2, dict):
            s2 = {}
        if not isinstance(s3, dict):
            s3 = {}

        app_line = app_lines.get(str(num)) if isinstance(app_lines.get(str(num)), dict) else {}
        stint, stint_n = last_stint(app_line.get("Stints"))
        tyre_life = _int(stint.get("TotalLaps") or stint.get("TyresNotLaps"))
        compound = compound_letter(stint.get("Compound"))
        pit_count = max(0, stint_n - 1) if stint_n else _int(line.get("NumberOfPitStops")) or 0

        pos = _int(line.get("Position")) or 99
        grid = _int(line.get("GridPos") or line.get("StartingPosition"))
        change = None
        if grid is not None and pos < 90:
            change = grid - pos

        gps = positions.get(str(num)) or {}
        car = cardata.get(str(num)) or {}
        colour = drv.get("TeamColour")
        if colour and not str(colour).startswith("#"):
            colour = f"#{colour}"

        rows.append(
            DriverLive(
                number=_int(num) or 0,
                code=code,
                name=str(drv.get("FullName") or drv.get("BroadcastName") or code),
                team=str(drv.get("TeamName") or ""),
                team_colour=str(colour) if colour else None,
                position=pos,
                grid_position=grid,
                position_change=change,
                gap_to_leader_s=parse_gap_s(line.get("GapToLeader")),
                gap_to_ahead_s=parse_gap_s(line.get("IntervalToPositionAhead")),
                last_lap_ms=last_ms,
                best_lap_ms=best_ms_val,
                sector1_ms=parse_laptime_ms(s1),
                sector2_ms=parse_laptime_ms(s2),
                sector3_ms=parse_laptime_ms(s3),
                s1_colour=sector_colour(s1),
                s2_colour=sector_colour(s2),
                s3_colour=sector_colour(s3),
                compound=compound,
                tyre_life=tyre_life,
                stint_number=stint_n or None,
                pit_count=int(pit_count or 0),
                in_pit=bool(line.get("InPit") or line.get("Pit") or str(gps.get("Status") or "").lower() in {"pit", "inpit"}),
                retired=bool(line.get("Retired") or line.get("Stopped")),
                n_laps=_int(line.get("NumberOfLaps")),
                gps_x=_float(gps.get("X")),
                gps_y=_float(gps.get("Y")),
                speed_kph=_channel_float(car, "speed"),
                throttle=_channel_float(car, "throttle"),
                brake=_channel_float(car, "brake"),
                rpm=_channel_float(car, "rpm"),
                gear=_int(car.get("gear")) if car else None,
                drs=_int(car.get("drs")) if car else None,
            )
        )

    if best_ms:
        fastest = min(best_ms.values())
        for row in rows:
            personal = best_ms.get(str(row.number))
            if personal is not None:
                row.best_lap_ms = personal
            if personal is not None and personal == fastest:
                row.fastest_lap = True
    rows.sort(key=lambda r: (r.position, r.best_lap_ms or 10**9))
    if rows and rows[0].gap_to_leader_s is None:
        rows[0].gap_to_leader_s = 0.0
    return rows


def weather_from_topic(wx: Any) -> dict[str, Any]:
    if not isinstance(wx, dict):
        return {}
    rain = wx.get("Rainfall")
    rainfall = None
    if rain is not None and str(rain) != "":
        rainfall = str(rain).strip() not in {"0", "false", "False", "no", "No"}
    return {
        "air_temp": _float(wx.get("AirTemp") or wx.get("air_temperature")),
        "track_temp": _float(wx.get("TrackTemp") or wx.get("track_temperature")),
        "humidity": _float(wx.get("Humidity") or wx.get("humidity")),
        "pressure": _float(wx.get("Pressure") or wx.get("pressure")),
        "wind_speed": _float(wx.get("WindSpeed") or wx.get("wind_speed")),
        "wind_direction": _float(wx.get("WindDirection") or wx.get("wind_direction")),
        "rainfall": rainfall,
    }


def rc_messages(rc: Any, *, limit: int = 8) -> list[str]:
    messages = []
    blob = rc.get("Messages") if isinstance(rc, dict) else rc
    rows: list[dict[str, Any]] = []
    if isinstance(blob, dict):
        items = []
        for key, val in blob.items():
            if isinstance(val, dict):
                try:
                    idx = int(key)
                except (TypeError, ValueError):
                    idx = 0
                items.append((idx, val))
        items.sort(key=lambda kv: kv[0])
        rows = [v for _, v in items]
    elif isinstance(blob, list):
        rows = [r for r in blob if isinstance(r, dict)]
    for row in rows[-limit:]:
        text = str(row.get("Message") or row.get("message") or "").strip()
        flag = str(row.get("Flag") or row.get("flag") or "").strip()
        if flag and text and flag.upper() not in text.upper():
            text = f"{flag} · {text}"
        elif flag and not text:
            text = flag
        if text:
            messages.append(text)
    return messages


def _calendar_windows(as_of: datetime) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for stype, name, start_iso, hours in ZANDVOORT_2026_WINDOWS:
        start = parse_dt(start_iso)
        if start is None:
            continue
        end = start + timedelta(hours=hours)
        windows.append(
            {
                "session_type": stype,
                "session_name": name,
                "start": start,
                "end": end,
                "year": 2026,
                "round_number": 15,
                "circuit": "Zandvoort",
                "country": "Netherlands",
            }
        )
    try:
        from backend.calendar import get_calendar

        cal = get_calendar(as_of.year)
        for rnd in cal.rounds:
            for sess in getattr(rnd, "sessions", []) or []:
                start = getattr(sess, "date_start", None)
                end = getattr(sess, "date_end", None)
                if start is None:
                    continue
                if getattr(start, "tzinfo", None) is None:
                    start = start.replace(tzinfo=timezone.utc)
                if end is None:
                    end = start + timedelta(hours=1.5)
                elif getattr(end, "tzinfo", None) is None:
                    end = end.replace(tzinfo=timezone.utc)
                windows.append(
                    {
                        "session_type": getattr(sess, "type", None) or "R",
                        "session_name": getattr(sess, "type", None) or "Session",
                        "start": start,
                        "end": end,
                        "year": as_of.year,
                        "round_number": rnd.round_number,
                        "circuit": rnd.circuit_name,
                        "country": rnd.country,
                    }
                )
    except Exception:
        pass
    windows.sort(key=lambda w: w["start"])
    return windows


def matching_window(as_of: datetime, *, grace_min: int = 12) -> dict[str, Any] | None:
    hits = []
    for win in _calendar_windows(as_of):
        start = win["start"] - timedelta(minutes=5)
        end = win["end"] + timedelta(minutes=grace_min)
        if start <= as_of <= end:
            hits.append(win)
    if not hits:
        return None
    hits.sort(key=lambda w: (w["end"] - w["start"]).total_seconds())
    return hits[0]


def next_window(as_of: datetime) -> dict[str, Any] | None:
    upcoming = [w for w in _calendar_windows(as_of) if w["start"] > as_of]
    return upcoming[0] if upcoming else None


def just_ended_window(as_of: datetime, *, within_h: float = 6.0) -> dict[str, Any] | None:
    ended = [
        w
        for w in _calendar_windows(as_of)
        if w["end"] < as_of <= w["end"] + timedelta(hours=within_h)
    ]
    if not ended:
        return None
    ended.sort(key=lambda w: w["end"], reverse=True)
    return ended[0]


def delay_note(age_s: float | None, *, connected: bool, source: str) -> str:
    if age_s is None:
        if connected:
            return f"{source} connected · waiting for first timing frame"
        return f"{source} · no frame yet"
    if age_s <= 3:
        return f"{source} · {age_s:.1f}s stale"
    if age_s <= 12:
        return f"{source} · {age_s:.0f}s delay (cars may jump)"
    return f"{source} STALE {age_s:.0f}s — feed lagged, values are last known"


def start_live_ingest() -> None:
    from backend.f1_live import start_background

    start_background()


def _signalr_snapshot() -> LiveSnapshot | None:
    from backend.f1_live import (
        connected,
        fetch_session_info,
        parse_remaining_s,
        session_info_is_live,
        snapshot,
    )

    start_live_ingest()
    raw = snapshot()
    info = fetch_session_info()
    topics = raw.get("topics") or {}
    timing = topics.get("TimingData") or {}
    has_lines = isinstance(timing, dict) and isinstance(timing.get("Lines"), dict) and timing["Lines"]
    live_info = session_info_is_live(info)
    age = raw.get("age_s")
    feed_ok = connected() or (has_lines and age is not None and age < 90)
    if not live_info and not feed_ok:
        return None
    if not has_lines and not live_info:
        return None

    meeting = (info or {}).get("Meeting") if isinstance(info, dict) else {}
    if not isinstance(meeting, dict):
        meeting = {}
    name = str((info or {}).get("Name") or "Live session")
    stype = session_type_map(name, str((info or {}).get("Type") or ""))
    circuit = str(meeting.get("Location") or meeting.get("Name") or "Unknown")
    country = ""
    country_blob = meeting.get("Country")
    if isinstance(country_blob, dict):
        country = str(country_blob.get("Name") or "")
    year = None
    path = str((info or {}).get("Path") or "")
    if path[:4].isdigit():
        year = int(path[:4])

    lap_count = topics.get("LapCount") or {}
    clock = topics.get("ExtrapolatedClock") or {}
    track = topics.get("TrackStatus") or {}
    wx = weather_from_topic(topics.get("WeatherData"))
    drivers = parse_timing_lines(
        timing if isinstance(timing, dict) else {},
        drivers=topics.get("DriverList") if isinstance(topics.get("DriverList"), dict) else {},
        app=topics.get("TimingAppData") if isinstance(topics.get("TimingAppData"), dict) else {},
        stats=topics.get("TimingStats") if isinstance(topics.get("TimingStats"), dict) else {},
        positions=raw.get("positions") if isinstance(raw.get("positions"), dict) else {},
        cardata=raw.get("cardata") if isinstance(raw.get("cardata"), dict) else {},
    )
    current_lap = _int((lap_count or {}).get("CurrentLap"))
    total_laps = _int((lap_count or {}).get("TotalLaps"))
    if current_lap is None and drivers:
        current_lap = max((d.n_laps or 0) for d in drivers) or None
    flag = _TRACK_FLAG.get(str((track or {}).get("Status") or ""), "UNKNOWN")
    if flag == "UNKNOWN" and (track or {}).get("Message"):
        msg = str(track["Message"]).upper()
        if "RED" in msg:
            flag = "RED"
        elif "VSC" in msg:
            flag = "VSC"
        elif "SAFETY" in msg or msg == "SC":
            flag = "SC"
        elif "YELLOW" in msg:
            flag = "YELLOW"
        elif "CLEAR" in msg or "GREEN" in msg:
            flag = "GREEN"
    remaining = parse_remaining_s((clock or {}).get("Remaining"))
    start = parse_dt((info or {}).get("StartDate")) if info else None
    # SessionInfo StartDate is local; f1_live already converts when using _local_dt via session_info_is_live.
    elapsed = None
    if start is not None:
        elapsed = max(0, int((now_utc() - start).total_seconds()))
    win = matching_window(now_utc())
    return LiveSnapshot(
        mode="live",
        is_live=True,
        source="signalr",
        session_name=name,
        session_type=stype,
        year=year or (win["year"] if win else 2026),
        round_number=win["round_number"] if win else 15,
        circuit=circuit,
        country=country or (win["country"] if win else "Netherlands"),
        current_lap=current_lap,
        total_laps=total_laps,
        flag=flag,
        remaining_s=remaining,
        elapsed_s=elapsed,
        feed_age_s=float(age) if age is not None else None,
        delay_note=delay_note(float(age) if age is not None else None, connected=bool(raw.get("connected")), source="SignalR"),
        air_temp=wx.get("air_temp"),
        track_temp=wx.get("track_temp"),
        humidity=wx.get("humidity"),
        pressure=wx.get("pressure"),
        wind_speed=wx.get("wind_speed"),
        wind_direction=wx.get("wind_direction"),
        rainfall=wx.get("rainfall"),
        drivers=drivers,
        race_control=rc_messages(topics.get("RaceControlMessages")),
        error=raw.get("error"),
        as_of=now_utc(),
    )


def _openf1_get(path: str, params: dict[str, Any] | None = None) -> Any:
    global _OPENF1_HITS
    now = time.monotonic()
    _OPENF1_HITS = [t for t in _OPENF1_HITS if now - t < 60.0]
    if len(_OPENF1_HITS) >= 45:
        return []
    _OPENF1_HITS.append(now)
    try:
        from backend.http_client import openf1

        return openf1(path, params)
    except Exception:
        return []


def _openf1_latest_session() -> dict[str, Any] | None:
    try:
        data = _openf1_get("sessions", {"session_key": "latest"})
    except Exception:
        return None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return None


def _session_window_live(sess: dict[str, Any], as_of: datetime) -> bool:
    start = parse_dt(sess.get("date_start"))
    end = parse_dt(sess.get("date_end"))
    if start is None:
        return False
    if end is None:
        end = start + timedelta(hours=2)
    return start - timedelta(minutes=5) <= as_of <= end + timedelta(minutes=8)


def _openf1_snapshot() -> LiveSnapshot | None:
    sess = _openf1_latest_session()
    as_of = now_utc()
    if not sess or not _session_window_live(sess, as_of):
        return None
    key = sess.get("session_key")
    if key is None:
        return None
    try:
        key = int(key)
    except (TypeError, ValueError):
        return None
    drivers_raw = _openf1_get("drivers", {"session_key": key})
    laps = _openf1_get("laps", {"session_key": key})
    stints = _openf1_get("stints", {"session_key": key})
    positions = _openf1_get("position", {"session_key": key})
    intervals = _openf1_get("intervals", {"session_key": key})
    weather = _openf1_get("weather", {"session_key": key})
    loc = []
    since = (as_of - timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        loc = _openf1_get("location", {"session_key": key, "date>": since})
    except Exception:
        loc = []

    codes: dict[int, dict[str, Any]] = {}
    if isinstance(drivers_raw, list):
        for row in drivers_raw:
            if not isinstance(row, dict) or row.get("driver_number") is None:
                continue
            codes[int(row["driver_number"])] = row

    last_lap: dict[int, dict[str, Any]] = {}
    best: dict[int, int] = {}
    if isinstance(laps, list):
        for row in laps:
            if not isinstance(row, dict) or row.get("driver_number") is None:
                continue
            n = int(row["driver_number"])
            last_lap[n] = row
            dur = row.get("lap_duration")
            if dur:
                ms = int(float(dur) * 1000)
                if n not in best or ms < best[n]:
                    best[n] = ms
    last_pos: dict[int, int] = {}
    if isinstance(positions, list):
        for row in positions:
            if not isinstance(row, dict):
                continue
            n = row.get("driver_number")
            p = row.get("position")
            if n is None or p is None:
                continue
            last_pos[int(n)] = int(p)
    last_int: dict[int, dict[str, Any]] = {}
    if isinstance(intervals, list):
        for row in intervals:
            if isinstance(row, dict) and row.get("driver_number") is not None:
                last_int[int(row["driver_number"])] = row
    last_st: dict[int, dict[str, Any]] = {}
    if isinstance(stints, list):
        for row in stints:
            if isinstance(row, dict) and row.get("driver_number") is not None:
                last_st[int(row["driver_number"])] = row
    last_loc: dict[int, dict[str, Any]] = {}
    if isinstance(loc, list):
        for row in loc:
            if isinstance(row, dict) and row.get("driver_number") is not None:
                last_loc[int(row["driver_number"])] = row
    wx_row: dict[str, Any] = {}
    if isinstance(weather, list) and weather:
        wx_row = weather[-1] if isinstance(weather[-1], dict) else {}

    fastest = min(best.values()) if best else None
    numbers = sorted(set(codes) | set(last_lap) | set(last_pos), key=lambda n: last_pos.get(n, 99))
    rows: list[DriverLive] = []
    for n in numbers:
        meta = codes.get(n) or {}
        lap = last_lap.get(n) or {}
        st = last_st.get(n) or {}
        iv = last_int.get(n) or {}
        gps = last_loc.get(n) or {}
        colour = meta.get("team_colour")
        if colour and not str(colour).startswith("#"):
            colour = f"#{colour}"
        last_ms = int(float(lap["lap_duration"]) * 1000) if lap.get("lap_duration") else None
        rows.append(
            DriverLive(
                number=n,
                code=str(meta.get("name_acronym") or f"D{n}")[:3].upper(),
                name=str(meta.get("full_name") or meta.get("broadcast_name") or ""),
                team=str(meta.get("team_name") or ""),
                team_colour=str(colour) if colour else None,
                position=int(last_pos.get(n, len(rows) + 1)),
                gap_to_leader_s=_float(iv.get("gap_to_leader")),
                gap_to_ahead_s=_float(iv.get("interval")),
                last_lap_ms=last_ms,
                best_lap_ms=best.get(n),
                sector1_ms=int(float(lap["duration_sector_1"]) * 1000) if lap.get("duration_sector_1") else None,
                sector2_ms=int(float(lap["duration_sector_2"]) * 1000) if lap.get("duration_sector_2") else None,
                sector3_ms=int(float(lap["duration_sector_3"]) * 1000) if lap.get("duration_sector_3") else None,
                compound=compound_letter(st.get("compound")),
                tyre_life=_int(st.get("tyre_age_at_start")),
                stint_number=_int(st.get("stint_number")),
                fastest_lap=fastest is not None and best.get(n) == fastest,
                n_laps=_int(lap.get("lap_number")),
                gps_x=_float(gps.get("x")),
                gps_y=_float(gps.get("y")),
            )
        )
    rows.sort(key=lambda r: r.position)
    start = parse_dt(sess.get("date_start"))
    end = parse_dt(sess.get("date_end"))
    elapsed = int((as_of - start).total_seconds()) if start else None
    remaining = int((end - as_of).total_seconds()) if end else None
    name = str(sess.get("session_name") or "Live")
    current = max((d.n_laps or 0) for d in rows) if rows else None
    return LiveSnapshot(
        mode="live",
        is_live=True,
        source="openf1",
        session_name=name,
        session_type=session_type_map(name, str(sess.get("session_type") or "")),
        year=_int(sess.get("year")),
        round_number=15,
        circuit=str(sess.get("circuit_short_name") or sess.get("location") or ""),
        country=str(sess.get("country_name") or ""),
        current_lap=current,
        total_laps=None,
        flag="GREEN",
        remaining_s=remaining if remaining is not None and remaining > 0 else None,
        elapsed_s=elapsed,
        feed_age_s=None,
        delay_note="OpenF1 REST · polling (may trail official timing)",
        air_temp=_float(wx_row.get("air_temperature")),
        track_temp=_float(wx_row.get("track_temperature")),
        humidity=_float(wx_row.get("humidity")),
        pressure=_float(wx_row.get("pressure")),
        wind_speed=_float(wx_row.get("wind_speed")),
        wind_direction=_float(wx_row.get("wind_direction")),
        rainfall=bool(wx_row.get("rainfall")) if wx_row.get("rainfall") is not None else None,
        drivers=rows,
        as_of=as_of,
        session_key=key,
    )


def _merge_live(primary: LiveSnapshot, extra: LiveSnapshot | None) -> LiveSnapshot:
    if extra is None or not extra.drivers:
        return primary
    by_code = {d.code: d for d in extra.drivers}
    merged: list[DriverLive] = []
    for row in primary.drivers:
        other = by_code.get(row.code)
        if other is None:
            merged.append(row)
            continue
        if row.gps_x is None and other.gps_x is not None:
            row.gps_x, row.gps_y = other.gps_x, other.gps_y
        if row.compound is None:
            row.compound = other.compound
        if row.tyre_life is None:
            row.tyre_life = other.tyre_life
        if row.best_lap_ms is None:
            row.best_lap_ms = other.best_lap_ms
        if row.throttle is None:
            row.throttle = other.throttle
            row.brake = other.brake
            row.speed_kph = other.speed_kph
            row.rpm = other.rpm
            row.gear = other.gear
        merged.append(row)
    primary.drivers = merged
    if primary.source == "signalr" and extra.source == "openf1":
        primary.source = "signalr+openf1"
        primary.session_key = extra.session_key or primary.session_key
        if primary.air_temp is None:
            primary.air_temp = extra.air_temp
            primary.track_temp = extra.track_temp
            primary.humidity = extra.humidity
            primary.rainfall = extra.rainfall
    return primary


def _waiting_snapshot(as_of: datetime) -> LiveSnapshot:
    nxt = next_window(as_of)
    ended = just_ended_window(as_of)
    return LiveSnapshot(
        mode="waiting",
        is_live=False,
        source="calendar",
        session_name=nxt["session_name"] if nxt else (ended["session_name"] if ended else "No session"),
        session_type=nxt["session_type"] if nxt else (ended["session_type"] if ended else ""),
        year=2026,
        round_number=15,
        circuit="Zandvoort",
        country="Netherlands",
        current_lap=None,
        total_laps=None,
        flag="UNKNOWN",
        remaining_s=int((nxt["start"] - as_of).total_seconds()) if nxt else None,
        elapsed_s=None,
        feed_age_s=None,
        delay_note="Waiting for the official live feed — this page starts itself",
        next_session_name=nxt["session_name"] if nxt else None,
        next_session_utc=nxt["start"] if nxt else None,
        as_of=as_of,
    )


def collect_live_snapshot() -> LiveSnapshot:
    """Prefer SignalR (works during a live session). Fill gaps from OpenF1."""
    global _LAST_LIVE
    start_live_ingest()
    sig = None
    try:
        sig = _signalr_snapshot()
    except Exception as extra:
        sig = None
        err = str(extra)
    else:
        err = None
    of1 = None
    try:
        of1 = _openf1_snapshot()
    except Exception:
        of1 = None
    snap = None
    if sig and sig.drivers:
        snap = _merge_live(sig, of1)
    elif of1 and of1.drivers:
        snap = of1
    elif sig:
        snap = sig
    if snap is None:
        waiting = _waiting_snapshot(now_utc())
        if err:
            waiting.error = err
        return waiting
    if err and not snap.error:
        snap.error = err
    with _STATE_LOCK:
        _LAST_LIVE = snap
    return snap


def last_live_snapshot() -> LiveSnapshot | None:
    with _STATE_LOCK:
        return _LAST_LIVE


def build_live_race_state(snap: LiveSnapshot, focus_code: str) -> RaceState | None:
    """RaceState from the live feed — no Postgres required."""
    row = next((d for d in snap.drivers if d.code == focus_code), None)
    if row is None:
        return None
    total = snap.total_laps or (24 if snap.session_type == "S" else 72)
    lap = int(row.n_laps or snap.current_lap or 1)
    lap = max(1, min(lap, total))
    remaining = max(0, total - lap)
    compound = compound_full(row.compound or "MEDIUM")
    ahead = None
    behind = None
    ordered = [d for d in snap.drivers if not d.retired]
    ordered.sort(key=lambda d: d.position)
    idx = next((i for i, d in enumerate(ordered) if d.code == focus_code), None)
    if idx is not None:
        if idx > 0:
            ahead = ordered[idx].gap_to_ahead_s
        if idx + 1 < len(ordered):
            behind = ordered[idx + 1].gap_to_ahead_s
    times = []
    if row.last_lap_ms:
        times.append(row.last_lap_ms / 1000.0)
    if row.best_lap_ms:
        times.append(row.best_lap_ms / 1000.0)
    lag1 = times[0] if times else None
    lag2 = times[1] if len(times) > 1 else lag1
    flag = snap.flag
    track_status = {"SC": "4", "VSC": "6", "RED": "5", "YELLOW": "2"}.get(flag, "1")
    recent = track_status_is_sc_vsc(track_status)
    return RaceState(
        session_id=0,
        driver_id=row.number,
        driver_code=row.code,
        driver_name=row.name or row.code,
        team=row.team or None,
        year=int(snap.year or 2026),
        round_no=int(snap.round_number or 15),
        country=snap.country or "Netherlands",
        lap_number=lap,
        compound=compound,
        tyre_life=int(row.tyre_life or 1),
        fuel_kg=estimate_fuel_kg(lap, total),
        laps_remaining=remaining,
        total_laps=total,
        track_name=snap.circuit or "Netherlands",
        gap_to_leader_s=row.gap_to_leader_s,
        gap_ahead_s=ahead,
        gap_behind_s=behind,
        position=row.position if row.position < 90 else None,
        pit_compound="HARD" if compound == "SOFT" else "SOFT",
        lag1_pace=lag1,
        lag2_pace=lag2,
        stint_roll3=lag1,
        air_temp_c=snap.air_temp,
        track_temp_c=snap.track_temp,
        track_status=track_status,
        recent_sc_pace=recent,
        confidence_caveat=SC_PACE_CAVEAT if recent else None,
        weather_rainfall=snap.rainfall,
        rainfall=bool(snap.rainfall),
    )


def _laps_upto(laps: list[dict[str, Any]], clock: datetime) -> list[dict[str, Any]]:
    out = []
    for row in laps:
        start = parse_dt(row.get("date_start"))
        if start is None or start <= clock:
            out.append(row)
    return out


def _replay_drivers_from_pack(pack: dict[str, Any], clock: datetime) -> list[DriverLive]:
    laps = _laps_upto(pack.get("laps") or [], clock)
    last_lap: dict[int, dict[str, Any]] = {}
    best: dict[int, int] = {}
    for row in laps:
        n = row.get("driver_number")
        if n is None:
            continue
        n = int(n)
        last_lap[n] = row
        dur = row.get("lap_duration")
        if dur:
            ms = int(float(dur) * 1000)
            if n not in best or ms < best[n]:
                best[n] = ms
    codes: dict[int, dict[str, Any]] = pack.get("drivers") or {}
    stints: list[Any] = pack.get("stints") or []
    last_st: dict[int, dict[str, Any]] = {}
    for row in stints:
        if isinstance(row, dict) and row.get("driver_number") is not None:
            start_lap = int(row.get("lap_start") or 1)
            current = int((last_lap.get(int(row["driver_number"])) or {}).get("lap_number") or 0)
            if current == 0 or start_lap <= current:
                last_st[int(row["driver_number"])] = row
    pos_map: dict[int, int] = {}
    for row in pack.get("positions") or []:
        dt = parse_dt(row.get("date"))
        if dt is not None and dt > clock:
            continue
        n = row.get("driver_number")
        p = row.get("position")
        if n is None or p is None:
            continue
        pos_map[int(n)] = int(p)
    samples: dict[str, list[Any]] = pack.get("pos_samples") or {}
    t_epoch = clock.timestamp()
    fastest = min(best.values()) if best else None
    rows: list[DriverLive] = []
    numbers = sorted(set(codes) | set(last_lap) | set(pos_map))
    for n in numbers:
        meta = codes.get(n) or {}
        code = str(meta.get("code") or meta.get("name_acronym") or f"D{n}")[:3].upper()
        lap = last_lap.get(n) or {}
        st = last_st.get(n) or {}
        colour = meta.get("team_colour") or meta.get("colour")
        if colour and not str(colour).startswith("#"):
            colour = f"#{colour}"
        gps_x = gps_y = None
        trail = samples.get(code) or samples.get(str(n)) or []
        hit = None
        for sample in trail:
            if sample[0] <= t_epoch:
                hit = sample
            else:
                break
        if hit is not None:
            gps_x, gps_y = float(hit[1]), float(hit[2])
        last_ms = int(float(lap["lap_duration"]) * 1000) if lap.get("lap_duration") else None
        rows.append(
            DriverLive(
                number=n,
                code=code,
                name=str(meta.get("name") or meta.get("full_name") or code),
                team=str(meta.get("team") or meta.get("team_name") or ""),
                team_colour=str(colour) if colour else None,
                position=int(pos_map.get(n, 99)),
                last_lap_ms=last_ms,
                best_lap_ms=best.get(n),
                sector1_ms=int(float(lap["duration_sector_1"]) * 1000) if lap.get("duration_sector_1") else None,
                sector2_ms=int(float(lap["duration_sector_2"]) * 1000) if lap.get("duration_sector_2") else None,
                sector3_ms=int(float(lap["duration_sector_3"]) * 1000) if lap.get("duration_sector_3") else None,
                compound=compound_letter(st.get("compound")),
                tyre_life=_int(st.get("tyre_age_at_start") or st.get("tyre_life")),
                stint_number=_int(st.get("stint_number")),
                fastest_lap=fastest is not None and best.get(n) == fastest,
                n_laps=_int(lap.get("lap_number")),
                gps_x=gps_x,
                gps_y=gps_y,
            )
        )
    if any(r.position < 90 for r in rows):
        rows.sort(key=lambda r: r.position)
    else:
        rows.sort(key=lambda r: r.best_lap_ms or 10**9)
        for i, row in enumerate(rows, start=1):
            row.position = i
    return rows


def _load_openf1_pack(year: int, session_type: str, circuit_hint: str) -> dict[str, Any] | None:
    sessions = _openf1_get("sessions", {"year": year})
    if not isinstance(sessions, list):
        return None
    names = {
        "FP1": ("Practice 1",),
        "SQ": ("Sprint Qualifying", "Sprint Shootout"),
        "S": ("Sprint",),
        "Q": ("Qualifying",),
        "R": ("Race",),
    }.get(session_type, (session_type,))
    hint = circuit_hint.lower()
    chosen = None
    for sess in sessions:
        if not isinstance(sess, dict):
            continue
        if str(sess.get("session_name") or "") not in names:
            continue
        blob = f"{sess.get('circuit_short_name') or ''} {sess.get('location') or ''} {sess.get('country_name') or ''}".lower()
        if hint and hint not in blob and "zandvoort" not in blob and "nether" not in blob:
            continue
        chosen = sess
    if chosen is None or chosen.get("session_key") is None:
        return None
    key = int(chosen["session_key"])
    drivers_raw = _openf1_get("drivers", {"session_key": key})
    laps = _openf1_get("laps", {"session_key": key})
    stints = _openf1_get("stints", {"session_key": key})
    positions = _openf1_get("position", {"session_key": key})
    weather = _openf1_get("weather", {"session_key": key})
    drivers: dict[int, dict[str, Any]] = {}
    if isinstance(drivers_raw, list):
        for row in drivers_raw:
            if isinstance(row, dict) and row.get("driver_number") is not None:
                n = int(row["driver_number"])
                drivers[n] = {
                    "code": str(row.get("name_acronym") or f"D{n}")[:3].upper(),
                    "name": row.get("full_name"),
                    "team": row.get("team_name"),
                    "team_colour": row.get("team_colour"),
                    "name_acronym": row.get("name_acronym"),
                }
    start = parse_dt(chosen.get("date_start"))
    end = parse_dt(chosen.get("date_end"))
    if end is None and start is not None:
        end = start + timedelta(hours=1.5)
    duration = int((end - start).total_seconds()) if start and end else 0
    return {
        "source": "openf1",
        "session_key": key,
        "session_name": chosen.get("session_name"),
        "session_type": session_type,
        "date_start": start,
        "date_end": end,
        "duration_s": duration,
        "year": year,
        "laps": laps if isinstance(laps, list) else [],
        "stints": stints if isinstance(stints, list) else [],
        "positions": positions if isinstance(positions, list) else [],
        "weather": weather if isinstance(weather, list) else [],
        "drivers": drivers,
        "pos_samples": {},
        "path_x": [],
        "path_y": [],
    }


def _ff1_cache_dir() -> str:
    root = os.environ.get("FASTF1_CACHE")
    if root:
        return root
    here = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fastf1_cache"))
    os.makedirs(here, exist_ok=True)
    return here


def _load_fastf1_pack(year: int, event: str, session_type: str) -> dict[str, Any] | None:
    import fastf1

    fastf1.Cache.enable_cache(_ff1_cache_dir())
    sess = fastf1.get_session(year, event, session_type)
    sess.load(telemetry=False, weather=True, messages=False)
    laps = sess.laps
    drivers: dict[int, dict[str, Any]] = {}
    pos_samples: dict[str, list[Any]] = {}
    try:
        results = sess.results
    except Exception:
        results = None
    if results is not None:
        for _, row in results.iterrows():
            num = row.get("DriverNumber")
            code = str(row.get("Abbreviation") or "")[:3].upper()
            if num is None or not code:
                continue
            n = int(num)
            drivers[n] = {
                "code": code,
                "name": str(row.get("FullName") or code),
                "team": str(row.get("TeamName") or ""),
                "colour": None,
            }
    openf1_laps: list[dict[str, Any]] = []
    if laps is not None and not laps.empty:
        for _, lap in laps.iterrows():
            num = lap.get("DriverNumber")
            if num is None:
                continue
            start = lap.get("LapStartDate")
            date_start = None
            if hasattr(start, "to_pydatetime"):
                dt = start.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                date_start = dt.astimezone(timezone.utc).isoformat()
            dur = lap.get("LapTime")
            lap_s = dur.total_seconds() if hasattr(dur, "total_seconds") else None
            s1 = lap.get("Sector1Time")
            s2 = lap.get("Sector2Time")
            s3 = lap.get("Sector3Time")
            openf1_laps.append(
                {
                    "driver_number": int(num),
                    "lap_number": int(lap.get("LapNumber") or 0),
                    "lap_duration": lap_s,
                    "duration_sector_1": s1.total_seconds() if hasattr(s1, "total_seconds") else None,
                    "duration_sector_2": s2.total_seconds() if hasattr(s2, "total_seconds") else None,
                    "duration_sector_3": s3.total_seconds() if hasattr(s3, "total_seconds") else None,
                    "date_start": date_start,
                    "compound": lap.get("Compound"),
                }
            )
            code = str(lap.get("Driver") or "")[:3].upper()
            if code and int(num) not in drivers:
                drivers[int(num)] = {"code": code, "name": code, "team": str(lap.get("Team") or "")}

    try:
        pos = sess.pos_data
    except Exception:
        pos = {}
    if isinstance(pos, dict):
        for drv, df in pos.items():
            if df is None or getattr(df, "empty", True):
                continue
            code = str(drv)[:3].upper()
            samples = []
            step = max(1, len(df) // 4000)
            for _, prow in df.iloc[::step].iterrows():
                t = prow.get("Date")
                if hasattr(t, "to_pydatetime"):
                    dt = t.to_pydatetime()
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    ts = dt.timestamp()
                else:
                    continue
                samples.append((ts, float(prow.get("X") or 0), float(prow.get("Y") or 0), str(prow.get("Status") or "")))
            pos_samples[code] = samples

    path_x: list[float] = []
    path_y: list[float] = []
    try:
        info = sess.get_circuit_info()
        if info is not None and getattr(info, "corners", None) is not None:
            pass
    except Exception:
        info = None
    try:
        tel = None
        if laps is not None and not laps.empty:
            fastest = laps.pick_fastest()
            tel = fastest.get_telemetry()
            if tel is not None and "X" in tel and "Y" in tel:
                step = max(1, len(tel) // 400)
                path_x = [float(x) for x in tel["X"].tolist()[::step]]
                path_y = [float(y) for y in tel["Y"].tolist()[::step]]
    except Exception:
        path_x, path_y = [], []

    start = sess.session_info.get("StartDate") if isinstance(getattr(sess, "session_info", None), dict) else None
    t0 = parse_dt(str(start)) if start else None
    if t0 is None:
        t0 = parse_dt(str(getattr(sess, "date", None)))
    duration = 90 * 60
    if laps is not None and not laps.empty and "Time" in laps:
        try:
            last = laps["Time"].max()
            if hasattr(last, "total_seconds"):
                duration = int(last.total_seconds()) + 30
        except Exception:
            pass
    end = t0 + timedelta(seconds=duration) if t0 else None
    weather_rows = []
    try:
        wdf = sess.weather_data
        if wdf is not None and not wdf.empty:
            for _, wrow in wdf.iterrows():
                t = wrow.get("Time")
                weather_rows.append(
                    {
                        "date": (t0 + t).isoformat() if t0 is not None and hasattr(t, "total_seconds") else None,
                        "air_temperature": _float(wrow.get("AirTemp")),
                        "track_temperature": _float(wrow.get("TrackTemp")),
                        "humidity": _float(wrow.get("Humidity")),
                        "rainfall": bool(wrow.get("Rainfall")),
                        "wind_speed": _float(wrow.get("WindSpeed")),
                        "pressure": _float(wrow.get("Pressure")),
                    }
                )
    except Exception:
        weather_rows = []
    return {
        "source": "fastf1",
        "session_key": None,
        "session_name": str(session_type),
        "session_type": session_type,
        "date_start": t0,
        "date_end": end,
        "duration_s": duration,
        "year": year,
        "laps": openf1_laps,
        "stints": [],
        "positions": [],
        "weather": weather_rows,
        "drivers": drivers,
        "pos_samples": pos_samples,
        "path_x": path_x,
        "path_y": path_y,
    }


def _ensure_replay_pack(year: int, session_type: str, circuit: str, event: str) -> dict[str, Any] | None:
    global _REPLAY_PACK, _REPLAY_KEY, _FF1_ERROR
    key = f"{year}:{session_type}:{event}"
    with _STATE_LOCK:
        if _REPLAY_PACK is not None and _REPLAY_KEY == key:
            return _REPLAY_PACK
    pack = None
    try:
        pack = _load_fastf1_pack(year, event, session_type)
    except Exception as extra:
        _FF1_ERROR = str(extra)
        pack = None
    if pack is None:
        return None
    with _STATE_LOCK:
        _REPLAY_PACK = pack
        _REPLAY_KEY = key
    return pack


def replay_snapshot(
    *,
    year: int,
    session_type: str,
    circuit: str,
    event: str,
    elapsed_s: float,
) -> LiveSnapshot | None:
    pack = _ensure_replay_pack(year, session_type, circuit, event)
    if pack is None:
        return None
    start: datetime | None = pack.get("date_start")
    end: datetime | None = pack.get("date_end")
    duration = int(pack.get("duration_s") or 0)
    if start is None:
        start = now_utc() - timedelta(seconds=duration)
    clock = start + timedelta(seconds=max(0.0, elapsed_s))
    if end is not None and clock > end:
        clock = end
    drivers = _replay_drivers_from_pack(pack, clock)
    wx_row: dict[str, Any] = {}
    for row in pack.get("weather") or []:
        dt = parse_dt(row.get("date"))
        if dt is None or dt <= clock:
            wx_row = row
    current = max((d.n_laps or 0) for d in drivers) if drivers else None
    return LiveSnapshot(
        mode="replay",
        is_live=False,
        source=str(pack.get("source") or "replay"),
        session_name=str(pack.get("session_name") or session_type),
        session_type=session_type,
        year=year,
        round_number=15,
        circuit=circuit,
        country="Netherlands",
        current_lap=current,
        total_laps=None,
        flag="GREEN",
        remaining_s=max(0, duration - int(elapsed_s)),
        elapsed_s=int(elapsed_s),
        feed_age_s=None,
        delay_note=f"Replay · {pack.get('source')} · cars jump at high speed",
        air_temp=_float(wx_row.get("air_temperature")),
        track_temp=_float(wx_row.get("track_temperature")),
        humidity=_float(wx_row.get("humidity")),
        pressure=_float(wx_row.get("pressure")),
        wind_speed=_float(wx_row.get("wind_speed")),
        rainfall=bool(wx_row.get("rainfall")) if wx_row.get("rainfall") is not None else None,
        drivers=drivers,
        path_x=list(pack.get("path_x") or []),
        path_y=list(pack.get("path_y") or []),
        error=_FF1_ERROR,
        as_of=clock,
        replay_duration_s=duration,
        session_key=pack.get("session_key"),
    )


def resolve_mode(as_of: datetime | None = None) -> tuple[Mode, dict[str, Any] | None]:
    """live if a feed is up; replay if a session just ended; else waiting."""
    as_of = as_of or now_utc()
    live = matching_window(as_of)
    try:
        from backend.f1_live import connected, fetch_session_info, session_info_is_live, snapshot

        start_live_ingest()
        info = fetch_session_info()
        raw = snapshot()
        if session_info_is_live(info) or connected() or (raw.get("age_s") is not None and raw["age_s"] < 45 and raw.get("topics", {}).get("TimingData")):
            return "live", live
    except Exception:
        pass
    if live is not None:
        return "live", live
    ended = just_ended_window(as_of)
    if ended is not None:
        return "replay", ended
    return "waiting", next_window(as_of)
