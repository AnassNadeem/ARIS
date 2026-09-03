"""F1 calendar from 2018 onward: FastF1 schedule + overlay notes + computed status."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import yaml

from backend.cache import TTL_CALENDAR, cache as mem_cache, enable_fastf1_cache
from backend.models import (
    CalendarResponse,
    CalendarRound,
    CalendarSessionWindow,
    NextRaceResponse,
    RoundSessionsResponse,
    SessionInfo,
    WeekendSession,
)
from backend.paths import BACKEND

_log = logging.getLogger(__name__)

NOTES_PATH = BACKEND / "calendar_notes.yaml"
_SCHED_MEM: dict[int, pd.DataFrame] = {}

# Replay FastF1 window — older seasons are calendar/standings only (no session packs).
ALLOWED_REPLAY_YEARS = frozenset({2024, 2025, 2026})
REPLAY_YEAR_LIMIT_MSG = (
    "Replay is only available for 2024, 2025, and 2026 to improve loading speed."
)


class ReplayYearBlocked(ValueError):
    """Replay was requested for a year outside ALLOWED_REPLAY_YEARS."""


REPLAY_SESSION_ONLY_MSG = "Only Race sessions are supported for Replay/ARIS"


class ReplaySessionBlocked(ValueError):
    """Replay/ARIS was requested for a non-Race session."""


def replay_year_allowed(year: int) -> bool:
    return int(year) in ALLOWED_REPLAY_YEARS


def replay_session_type_allowed(session_type: str | None) -> bool:
    return str(session_type or "R").upper() == "R"


def assert_replay_session_type(session_type: str | None) -> str:
    """Replay/ARIS packs are Race-only. Returns 'R' or raises ReplaySessionBlocked."""
    mapped = str(session_type or "R").upper()
    if mapped == "R":
        return "R"
    raise ReplaySessionBlocked(REPLAY_SESSION_ONLY_MSG)


def assert_replay_year(year: int, *, session_load: bool = False) -> int:
    """Log and raise if `year` is outside the replay FastF1 window."""
    y = int(year)
    if y in ALLOWED_REPLAY_YEARS:
        msg = f"Replay request for year {y} — allowed"
        _log.info(msg)
        print(f"[ARIS] {msg}", flush=True)
        return y
    msg = f"Replay request for year {y} — blocked (not in 2024–2026)"
    _log.info(msg)
    print(f"[ARIS] {msg}", flush=True)
    raise ReplayYearBlocked("Replay not allowed for this year" if session_load else REPLAY_YEAR_LIMIT_MSG)

# Official 2026 championship calendar (Jolpica / Ergast, verified 2026-09-03).
# Sakhir Bahrain, Jeddah, and Imola were dropped; Bahrain's round later
# returned at Sepang. Overlay round numbers are championship rounds 1–23.
NOTES_OVERLAY: dict[int, list[dict[str, Any]]] = {
    2026: [
        {"round_number": 1, "name": "Australia", "circuit_name": "Albert Park", "country": "Australia", "city": "Melbourne", "date_race": "2026-03-08T04:00:00Z", "is_sprint_weekend": False},
        {"round_number": 2, "name": "China", "circuit_name": "Shanghai International Circuit", "country": "China", "city": "Shanghai", "date_race": "2026-03-15T07:00:00Z", "is_sprint_weekend": True},
        {"round_number": 3, "name": "Japan", "circuit_name": "Suzuka", "country": "Japan", "city": "Suzuka", "date_race": "2026-03-29T05:00:00Z", "is_sprint_weekend": False},
        {"round_number": 4, "name": "Miami", "circuit_name": "Miami International Autodrome", "country": "United States", "city": "Miami", "date_race": "2026-05-03T20:00:00Z", "is_sprint_weekend": True},
        {"round_number": 5, "name": "Canada", "circuit_name": "Circuit Gilles-Villeneuve", "country": "Canada", "city": "Montreal", "date_race": "2026-05-24T20:00:00Z", "is_sprint_weekend": True},
        {"round_number": 6, "name": "Monaco", "circuit_name": "Circuit de Monaco", "country": "Monaco", "city": "Monaco", "date_race": "2026-06-07T13:00:00Z", "is_sprint_weekend": False},
        {"round_number": 7, "name": "Barcelona", "circuit_name": "Circuit de Barcelona-Catalunya", "country": "Spain", "city": "Barcelona", "date_race": "2026-06-14T13:00:00Z", "is_sprint_weekend": False},
        {"round_number": 8, "name": "Austria", "circuit_name": "Red Bull Ring", "country": "Austria", "city": "Spielberg", "date_race": "2026-06-28T13:00:00Z", "is_sprint_weekend": False},
        {"round_number": 9, "name": "Britain", "circuit_name": "Silverstone", "country": "United Kingdom", "city": "Silverstone", "date_race": "2026-07-05T14:00:00Z", "is_sprint_weekend": True},
        {"round_number": 10, "name": "Belgium", "circuit_name": "Circuit de Spa-Francorchamps", "country": "Belgium", "city": "Spa", "date_race": "2026-07-19T13:00:00Z", "is_sprint_weekend": False},
        {"round_number": 11, "name": "Hungary", "circuit_name": "Hungaroring", "country": "Hungary", "city": "Budapest", "date_race": "2026-07-26T13:00:00Z", "is_sprint_weekend": False},
        {
            "round_number": 12,
            "name": "Netherlands",
            "circuit_name": "Circuit Zandvoort",
            "circuit_key": "netherlands",
            "country": "Netherlands",
            "city": "Zandvoort",
            "date_race": "2026-08-23T13:00:00Z",
            "is_sprint_weekend": True,
            "date_fp1": "2026-08-21T10:30:00Z",
            "date_sprint_quali": "2026-08-21T14:30:00Z",
            "date_sprint": "2026-08-22T10:00:00Z",
            "date_quali": "2026-08-22T14:00:00Z",
        },
        {"round_number": 13, "name": "Italy", "circuit_name": "Autodromo Nazionale Monza", "country": "Italy", "city": "Monza", "date_race": "2026-09-06T13:00:00Z", "is_sprint_weekend": False},
        {"round_number": 14, "name": "Madrid", "circuit_name": "Madring", "circuit_key": "madrid", "country": "Spain", "city": "Madrid", "date_race": "2026-09-13T13:00:00Z", "is_sprint_weekend": False},
        {"round_number": 15, "name": "Azerbaijan", "circuit_name": "Baku City Circuit", "country": "Azerbaijan", "city": "Baku", "date_race": "2026-09-26T11:00:00Z", "is_sprint_weekend": False},
        {"round_number": 16, "name": "Malaysia", "circuit_name": "Sepang International Circuit", "circuit_key": "sepang", "country": "Malaysia", "city": "Sepang", "date_race": "2026-10-04T07:00:00Z", "is_sprint_weekend": False},
        {"round_number": 17, "name": "Singapore", "circuit_name": "Marina Bay Street Circuit", "country": "Singapore", "city": "Singapore", "date_race": "2026-10-11T12:00:00Z", "is_sprint_weekend": True},
        {"round_number": 18, "name": "United States", "circuit_name": "Circuit of the Americas", "country": "United States", "city": "Austin", "date_race": "2026-10-25T20:00:00Z", "is_sprint_weekend": False},
        {"round_number": 19, "name": "Mexico City", "circuit_name": "Autodromo Hermanos Rodriguez", "country": "Mexico", "city": "Mexico City", "date_race": "2026-11-01T20:00:00Z", "is_sprint_weekend": False},
        {"round_number": 20, "name": "Sao Paulo", "circuit_name": "Autodromo Jose Carlos Pace", "country": "Brazil", "city": "Sao Paulo", "date_race": "2026-11-08T17:00:00Z", "is_sprint_weekend": False},
        {"round_number": 21, "name": "Las Vegas", "circuit_name": "Las Vegas Strip Circuit", "country": "United States", "city": "Las Vegas", "date_race": "2026-11-22T04:00:00Z", "is_sprint_weekend": False},
        {"round_number": 22, "name": "Qatar", "circuit_name": "Lusail International Circuit", "country": "Qatar", "city": "Lusail", "date_race": "2026-11-29T16:00:00Z", "is_sprint_weekend": False},
        {"round_number": 23, "name": "Abu Dhabi", "circuit_name": "Yas Marina Circuit", "country": "UAE", "city": "Abu Dhabi", "date_race": "2026-12-06T13:00:00Z", "is_sprint_weekend": False},
    ]
}

FIA_2026_SPRINT_ROUNDS = {2, 4, 5, 9, 12, 17}

_SESSION_DURATION_H = {
    "FP1": 1.5,
    "FP2": 1.5,
    "FP3": 1.5,
    "Sprint Qualifying": 0.8,
    "Sprint": 1.0,
    "Qualifying": 1.5,
    "Race": 2.5,
}

SESSION_NAME_MAP = {
    "practice 1": "FP1",
    "fp1": "FP1",
    "practice 2": "FP2",
    "fp2": "FP2",
    "practice 3": "FP3",
    "fp3": "FP3",
    "qualifying": "Q",
    "sprint qualifying": "SQ",
    "sprint shootout": "SQ",
    "sprint": "S",
    "race": "R",
}


COUNTRY_FLAGS: dict[str, str] = {
    "australia": "🇦🇺",
    "bahrain": "🇧🇭",
    "malaysia": "🇲🇾",
    "sepang": "🇲🇾",
    "saudi arabia": "🇸🇦",
    "saudiarabia": "🇸🇦",
    "japan": "🇯🇵",
    "china": "🇨🇳",
    "united states": "🇺🇸",
    "usa": "🇺🇸",
    "miami": "🇺🇸",
    "italy": "🇮🇹",
    "emilia romagna": "🇮🇹",
    "monaco": "🇲🇨",
    "spain": "🇪🇸",
    "madrid": "🇪🇸",
    "madring": "🇪🇸",
    "canada": "🇨🇦",
    "austria": "🇦🇹",
    "united kingdom": "🇬🇧",
    "great britain": "🇬🇧",
    "britain": "🇬🇧",
    "belgium": "🇧🇪",
    "hungary": "🇭🇺",
    "netherlands": "🇳🇱",
    "azerbaijan": "🇦🇿",
    "singapore": "🇸🇬",
    "mexico": "🇲🇽",
    "mexico city": "🇲🇽",
    "brazil": "🇧🇷",
    "sao paulo": "🇧🇷",
    "qatar": "🇶🇦",
    "uae": "🇦🇪",
    "abu dhabi": "🇦🇪",
    "las vegas": "🇺🇸",
}


def country_flag(country: str | None, circuit_key: str | None = None) -> str:
    for raw in (country, circuit_key):
        if not raw:
            continue
        key = str(raw).strip().lower().replace("_", " ").replace("-", " ")
        if key in COUNTRY_FLAGS:
            return COUNTRY_FLAGS[key]
        for needle, flag in COUNTRY_FLAGS.items():
            if needle in key or key in needle:
                return flag
    return "🏁"


def replay_years(as_of: datetime | None = None) -> list[int]:
    end = max(now_utc(as_of).year, 2026)
    return list(range(end, 2017, -1))


def replayable_rounds(year: int, as_of: datetime | None = None) -> list[CalendarRound]:
    """Completed or in-progress weekends; cancelled and future rounds omitted."""
    cal = get_calendar(year, as_of=as_of)
    return [r for r in cal.rounds if r.status not in {"CANCELLED", "UPCOMING"}]


def now_utc(as_of: datetime | None = None) -> datetime:
    if as_of is not None:
        if as_of.tzinfo is None:
            return as_of.replace(tzinfo=timezone.utc)
        return as_of.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def load_notes() -> dict[str, Any]:
    raw = yaml.safe_load(NOTES_PATH.read_text(encoding="utf-8")) or {}
    return raw


def weekend_excluded_codes(year: int | None, round_number: int | None) -> set[str]:
    """Drivers withdrawn for a specific weekend — do not draw them on the map."""
    if year is None or round_number is None:
        return set()
    notes = load_notes()
    block = (notes.get("weekend_lineups") or {}).get(f"{int(year)}-{int(round_number)}") or {}
    return {str(c).upper() for c in (block.get("exclude") or []) if c}


def session_is_open(
    year: int, round_number: int, session_type: str = "R", as_of: datetime | None = None
) -> bool:
    """True when FastF1 must not load this session in-process (upcoming or live)."""
    try:
        weekend = get_round_sessions(int(year), int(round_number), as_of=as_of)
    except Exception:
        return False
    want = str(session_type or "R").upper()
    hit = next((s for s in weekend.sessions if s.session_type == want), None)
    return hit is not None and hit.status in {"UPCOMING", "LIVE"}


def _to_dt(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        ts = value.to_pydatetime()
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(str(value)[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _slug(value: str) -> str:
    return (
        value.lower()
        .replace("&", "and")
        .replace(" ", "_")
        .replace("-", "_")
        .replace("'", "")
    )


def circuit_key_for(country: str, location: str, event_name: str) -> str:
    try:
        from aris.tracks import _match_track_file
    except Exception:
        _match_track_file = None  # type: ignore[assignment]
    for needle in (location, event_name, country):
        if not needle or _match_track_file is None:
            continue
        path = _match_track_file(str(needle))
        if path is not None:
            return path.stem
    return _slug(location or country or event_name or "unknown")


_FIA_OVERLAY_NOTE = "[ADDED FROM FIA CALENDAR — FastF1 data incomplete]"


def _annotate_overlay() -> None:
    for rows in NOTES_OVERLAY.values():
        for row in rows:
            row.setdefault("status", "UPCOMING")
            notes = row.get("notes")
            if not notes:
                row["notes"] = [_FIA_OVERLAY_NOTE]
            if not row.get("circuit_key"):
                row["circuit_key"] = circuit_key_for(
                    str(row.get("country") or ""),
                    str(row.get("city") or row.get("name") or ""),
                    str(row.get("name") or ""),
                )


_annotate_overlay()


def _short_name(event_name: str, country: str) -> str:
    name = (event_name or country or "").replace("Grand Prix", "").strip()
    aliases = {
        "Emilia Romagna": "Emilia Romagna",
        "United States": "United States",
        "Mexico City": "Mexico City",
        "São Paulo": "Sao Paulo",
        "Sao Paulo": "Sao Paulo",
        "Las Vegas": "Las Vegas",
        "Abu Dhabi": "Abu Dhabi",
        "Great Britain": "Britain",
        "British": "Britain",
        "Spanish": "Spain",
        "Monégasque": "Monaco",
        "Monegasque": "Monaco",
        "Dutch": "Netherlands",
        "Italian": "Italy",
        "Japanese": "Japan",
        "Australian": "Australia",
        "Canadian": "Canada",
        "Austrian": "Austria",
        "Belgian": "Belgium",
        "Hungarian": "Hungary",
        "Chinese": "China",
        "Saudi Arabian": "Saudi Arabia",
        "Qatari": "Qatar",
        "Singapore": "Singapore",
        "Azerbaijan": "Azerbaijan",
        "Miami": "Miami",
        "Bahrain": "Bahrain",
    }
    for key, short in aliases.items():
        if key.lower() in name.lower() or key.lower() in country.lower():
            return short
    return name or country


def _session_type_from_name(name: str) -> str | None:
    key = str(name or "").strip().lower()
    return SESSION_NAME_MAP.get(key)


def _is_sprint_format(fmt: str, year: int, round_no: int, notes: dict[str, Any]) -> bool:
    if "sprint" in (fmt or "").lower():
        return True
    estimated = notes.get("estimated_sprint") or {}
    rounds = estimated.get(str(year)) or estimated.get(year) or []
    return int(round_no) in {int(r) for r in rounds}


def _overlay_notes(notes: dict[str, Any], year: int, round_no: int) -> list[str]:
    block = notes.get("notes") or {}
    items = block.get(f"{year}-{round_no}") or []
    return [str(x) for x in items]


def _cancelled(notes: dict[str, Any], year: int, round_no: int) -> str | None:
    block = notes.get("cancelled") or {}
    val = block.get(f"{year}-{round_no}")
    return str(val) if val else None


def _pick_session_dt(row: pd.Series, *names: str) -> datetime | None:
    for i in range(1, 6):
        label = row.get(f"Session{i}")
        mapped = _session_type_from_name(str(label) if pd.notna(label) else "")
        if mapped in names:
            for col in (f"Session{i}DateUtc", f"Session{i}Date"):
                dt = _to_dt(row.get(col))
                if dt is not None:
                    return dt
    return None


def _live_session_keys(_as_of: datetime) -> set[tuple[int, int]]:
    """OpenF1 live detection lives in backend.live — calendar uses session windows only.

    Calling OpenF1 (and FastF1 again) from every calendar request was blocking the
    event loop. Round LIVE/UPCOMING is derived from FastF1 session timestamps.
    """
    return set()


def _round_status(
    *,
    year: int,
    round_no: int,
    race_dt: datetime | None,
    first_dt: datetime | None,
    as_of: datetime,
    cancelled: str | None,
    live_keys: set[tuple[int, int]],
) -> str:
    if cancelled:
        return "CANCELLED"
    if (year, round_no) in live_keys:
        return "LIVE"
    if race_dt is None:
        return "UPCOMING"
    # Typical GP is ~90–110 minutes. After this window, advance next_race.
    race_done = race_dt + timedelta(hours=2, minutes=15)
    if as_of >= race_done:
        return "COMPLETED"
    if first_dt is not None and first_dt <= as_of < race_done:
        return "LIVE"
    if as_of >= race_dt:
        return "LIVE"
    return "UPCOMING"


def _schedule_from_fastf1(year: int) -> pd.DataFrame:
    hit = _SCHED_MEM.get(year)
    if hit is not None:
        return hit
    from backend.fastf1_guard import FASTF1_LOCK

    enable_fastf1_cache()
    import fastf1

    with FASTF1_LOCK:
        hit = _SCHED_MEM.get(year)
        if hit is not None:
            return hit
        sched = fastf1.get_event_schedule(year, include_testing=False)
        _SCHED_MEM[year] = sched
        return sched


def _fallback_rounds(year: int, notes: dict[str, Any], as_of: datetime) -> list[CalendarRound]:
    rows = (notes.get("fallback_schedule") or {}).get(year) or (
        notes.get("fallback_schedule") or {}
    ).get(str(year)) or []
    live_keys = _live_session_keys(as_of)
    out: list[CalendarRound] = []
    for raw in rows:
        round_no = int(raw["round"])
        race_dt = _to_dt(raw.get("date"))
        fp1 = _to_dt(raw.get("fp1"))
        if race_dt is not None and race_dt.hour == 0 and race_dt.minute == 0:
            race_dt = race_dt.replace(hour=13, minute=0)
        cancelled = _cancelled(notes, year, round_no)
        first = fp1 or (race_dt - timedelta(days=2) if race_dt else None)
        status = _round_status(
            year=year,
            round_no=round_no,
            race_dt=race_dt,
            first_dt=first,
            as_of=as_of,
            cancelled=cancelled,
            live_keys=live_keys,
        )
        name = str(raw["name"])
        loc = str(raw.get("city") or "")
        country = str(raw.get("country") or "")
        circuit = str(raw.get("circuit") or loc)
        sprint = bool(raw.get("sprint"))
        out.append(
            CalendarRound(
                round_number=round_no,
                name=name,
                circuit_name=circuit,
                circuit_key=circuit_key_for(country, loc or name, name),
                country=country,
                city=loc,
                date_fp1=fp1,
                date_race=race_dt,
                status=status,  # type: ignore[arg-type]
                is_sprint_weekend=sprint,
                cancelled_reason=cancelled,
                notes=_overlay_notes(notes, year, round_no),
                estimated=True,
            )
        )
    return out


def _rounds_from_schedule(year: int, sched: pd.DataFrame, as_of: datetime) -> list[CalendarRound]:
    notes = load_notes()
    live_keys = _live_session_keys(as_of)
    rounds: list[CalendarRound] = []
    for _, row in sched.iterrows():
        try:
            round_no = int(row["RoundNumber"])
        except (TypeError, ValueError):
            continue
        if round_no <= 0:
            continue
        country = str(row.get("Country") or "")
        location = str(row.get("Location") or "")
        event_name = str(row.get("EventName") or row.get("OfficialEventName") or country)
        fmt = str(row.get("EventFormat") or "")
        race_dt = _pick_session_dt(row, "R") or _to_dt(row.get("EventDate"))
        fp1 = _pick_session_dt(row, "FP1")
        fp2 = _pick_session_dt(row, "FP2")
        fp3 = _pick_session_dt(row, "FP3")
        sq = _pick_session_dt(row, "SQ")
        sprint = _pick_session_dt(row, "S")
        quali = _pick_session_dt(row, "Q")
        cancelled = _cancelled(notes, year, round_no)
        first_candidates = [d for d in (fp1, fp2, fp3, sq, sprint, quali, race_dt) if d]
        first_dt = min(first_candidates) if first_candidates else None
        status = _round_status(
            year=year,
            round_no=round_no,
            race_dt=race_dt,
            first_dt=first_dt,
            as_of=as_of,
            cancelled=cancelled,
            live_keys=live_keys,
        )
        is_sprint = _is_sprint_format(fmt, year, round_no, notes)
        name = _short_name(event_name, country)
        rounds.append(
            CalendarRound(
                round_number=round_no,
                name=name,
                circuit_name=location or name,
                circuit_key=circuit_key_for(country, location, event_name),
                country=country,
                city=location,
                date_fp1=fp1,
                date_fp2=fp2,
                date_fp3=fp3,
                date_sprint_quali=sq,
                date_sprint=sprint,
                date_quali=quali,
                date_race=race_dt,
                status=status,  # type: ignore[arg-type]
                is_sprint_weekend=is_sprint,
                cancelled_reason=cancelled,
                notes=_overlay_notes(notes, year, round_no),
                estimated=False,
                official_event_name=event_name,
            )
        )
    rounds.sort(key=lambda r: r.round_number)
    return rounds


def _norm_round_name(name: str) -> str:
    return (
        (name or "")
        .lower()
        .replace("grand prix", "")
        .replace("são", "sao")
        .replace(" ", "")
        .replace("-", "")
        .replace("'", "")
    )


def _race_anchor(race_dt: datetime | None) -> datetime | None:
    """Sunday (or Saturday for Vegas) race start used to estimate session windows."""
    if race_dt is None:
        return None
    dt = race_dt
    if dt.hour == 0 and dt.minute == 0:
        if dt.weekday() == 4:  # Friday listing → Sunday race
            dt = dt + timedelta(days=2)
        dt = dt.replace(hour=13, minute=0, second=0, microsecond=0)
    return dt


def _estimated_session_starts(race_dt: datetime | None, is_sprint: bool) -> dict[str, datetime]:
    race = _race_anchor(race_dt)
    if race is None:
        return {}
    friday = race - timedelta(days=2)
    saturday = race - timedelta(days=1)
    if is_sprint:
        return {
            "FP1": friday.replace(hour=10, minute=30),
            "Sprint Qualifying": friday.replace(hour=14, minute=30),
            "Sprint": saturday.replace(hour=10, minute=0),
            "Qualifying": saturday.replace(hour=14, minute=0),
            "Race": race,
        }
    return {
        "FP1": friday.replace(hour=11, minute=30),
        "FP2": friday.replace(hour=15, minute=0),
        "FP3": saturday.replace(hour=10, minute=30),
        "Qualifying": saturday.replace(hour=14, minute=0),
        "Race": race,
    }


def _with_sessions(rnd: CalendarRound) -> CalendarRound:
    estimated = _estimated_session_starts(rnd.date_race, rnd.is_sprint_weekend)
    if rnd.is_sprint_weekend:
        pairs: list[tuple[str, datetime | None]] = [
            ("FP1", rnd.date_fp1),
            ("Sprint Qualifying", rnd.date_sprint_quali),
            ("Sprint", rnd.date_sprint),
            ("Qualifying", rnd.date_quali),
            ("Race", rnd.date_race),
        ]
    else:
        pairs = [
            ("FP1", rnd.date_fp1),
            ("FP2", rnd.date_fp2),
            ("FP3", rnd.date_fp3),
            ("Qualifying", rnd.date_quali),
            ("Race", rnd.date_race),
        ]
    windows: list[CalendarSessionWindow] = []
    for typ, dt in pairs:
        start = dt or estimated.get(typ)
        if start is None:
            continue
        hours = _SESSION_DURATION_H.get(typ, 1.5)
        windows.append(
            CalendarSessionWindow(
                type=typ,
                date_start=start,
                date_end=start + timedelta(hours=hours),
                key=f"{rnd.round_number}-{typ}",
            )
        )
    updates: dict[str, Any] = {"sessions": windows}
    if rnd.date_fp1 is None and "FP1" in estimated:
        updates["date_fp1"] = estimated["FP1"]
    if rnd.date_fp2 is None and "FP2" in estimated:
        updates["date_fp2"] = estimated["FP2"]
    if rnd.date_fp3 is None and "FP3" in estimated:
        updates["date_fp3"] = estimated["FP3"]
    if rnd.date_sprint_quali is None and "Sprint Qualifying" in estimated:
        updates["date_sprint_quali"] = estimated["Sprint Qualifying"]
    if rnd.date_sprint is None and "Sprint" in estimated:
        updates["date_sprint"] = estimated["Sprint"]
    if rnd.date_quali is None and "Qualifying" in estimated:
        updates["date_quali"] = estimated["Qualifying"]
    if rnd.date_race is None and "Race" in estimated:
        updates["date_race"] = estimated["Race"]
    return rnd.model_copy(update=updates)


def _round_from_overlay(raw: dict[str, Any], as_of: datetime, *, from_fia_gap: bool = True) -> CalendarRound:
    race_dt = _to_dt(raw.get("date_race"))
    fp1 = _to_dt(raw.get("date_fp1"))
    country = str(raw.get("country") or "")
    city = str(raw.get("city") or "")
    name = str(raw["name"])
    circuit = str(raw.get("circuit_name") or city or name)
    sprint = bool(raw.get("is_sprint_weekend"))
    first = fp1 or (race_dt - timedelta(days=2) if race_dt else None)
    cancelled = _cancelled(load_notes(), 2026, int(raw["round_number"]))
    status = _round_status(
        year=2026,
        round_no=int(raw["round_number"]),
        race_dt=race_dt,
        first_dt=first,
        as_of=as_of,
        cancelled=cancelled,
        live_keys=set(),
    )
    notes = [str(n) for n in (raw.get("notes") or [])]
    if from_fia_gap and _FIA_OVERLAY_NOTE not in notes:
        notes.append(_FIA_OVERLAY_NOTE)
    elif not from_fia_gap:
        notes = [n for n in notes if n != _FIA_OVERLAY_NOTE]
    return CalendarRound(
        round_number=int(raw["round_number"]),
        name=name,
        circuit_name=circuit,
        circuit_key=raw.get("circuit_key") or circuit_key_for(country, city or name, name),
        country=country,
        city=city,
        date_fp1=fp1,
        date_fp2=_to_dt(raw.get("date_fp2")),
        date_fp3=_to_dt(raw.get("date_fp3")),
        date_sprint_quali=_to_dt(raw.get("date_sprint_quali")),
        date_sprint=_to_dt(raw.get("date_sprint")),
        date_quali=_to_dt(raw.get("date_quali")),
        date_race=race_dt,
        status=status,  # type: ignore[arg-type]
        is_sprint_weekend=sprint,
        cancelled_reason=cancelled,
        notes=notes,
        estimated=True,
        official_event_name=name,
    )


def _find_round_by_event(name: str, circuit: str, rounds: list[CalendarRound]) -> CalendarRound | None:
    needles = {_norm_round_name(name), _norm_round_name(circuit)}
    needles.discard("")
    aliases = {
        "netherlands": {"dutch", "zandvoort"},
        "britain": {"british", "greatbritain", "silverstone"},
        "saopaulo": {"brazil", "interlagos"},
        "saudiarabia": {"jeddah", "saudiarabian"},
        "emiliaromagna": {"imola"},
        "unitedstates": {"austin", "cota", "usa"},
        "abudhabi": {"yasmarina"},
        "lasvegas": {"vegas"},
        "mexicocity": {"mexico"},
        "barcelona": {"catalunya", "barcelonacatalunya"},
        "madrid": {"madring"},
        "malaysia": {"sepang", "kualalumpur"},
    }
    expanded: set[str] = set(needles)
    for n in list(needles):
        expanded.update(aliases.get(n, set()))
        for key, vals in aliases.items():
            if n in vals or n == key:
                expanded.add(key)
                expanded.update(vals)
    for rnd in rounds:
        hay = {_norm_round_name(rnd.name), _norm_round_name(rnd.circuit_name), _norm_round_name(rnd.city)}
        if hay & expanded:
            return rnd
        if any(n and any(n in h or h in n for h in hay if h) for n in expanded):
            return rnd
    return None


def _ensure_complete_calendar(year: int, rounds: list[CalendarRound], as_of: datetime) -> list[CalendarRound]:
    overlay = NOTES_OVERLAY.get(year) or []
    if year == 2026 and overlay:
        missing: list[str] = []
        out: list[CalendarRound] = []
        for raw in overlay:
            n = int(raw["round_number"])
            ff1 = _find_round_by_event(str(raw.get("name") or ""), str(raw.get("circuit_name") or ""), rounds)
            rnd = _round_from_overlay(raw, as_of, from_fia_gap=ff1 is None)
            if ff1 is None:
                missing.append(f"{n}:{raw.get('name')}")
            else:
                rnd = rnd.model_copy(
                    update={
                        "estimated": False,
                        "official_event_name": ff1.official_event_name or rnd.official_event_name,
                        "circuit_key": rnd.circuit_key or ff1.circuit_key,
                        "date_fp1": rnd.date_fp1 or ff1.date_fp1,
                        "date_fp2": rnd.date_fp2 or ff1.date_fp2,
                        "date_fp3": rnd.date_fp3 or ff1.date_fp3,
                        "date_sprint_quali": rnd.date_sprint_quali or ff1.date_sprint_quali,
                        "date_sprint": rnd.date_sprint or ff1.date_sprint,
                        "date_quali": rnd.date_quali or ff1.date_quali,
                    }
                )
            extra_notes = _overlay_notes(load_notes(), year, n)
            merged = list(rnd.notes or [])
            for note in extra_notes:
                if note not in merged:
                    merged.append(note)
            rnd = rnd.model_copy(
                update={"is_sprint_weekend": n in FIA_2026_SPRINT_ROUNDS, "notes": merged}
            )
            out.append(rnd)
        if missing:
            print(f"[ARIS] FastF1 calendar 2026 missing {missing} — filled from FIA overlay", flush=True)
        return out

    by_num: dict[int, CalendarRound] = {}
    for rnd in rounds:
        if rnd.round_number > 0:
            by_num[rnd.round_number] = rnd

    missing_n: list[int] = []
    for raw in overlay:
        n = int(raw["round_number"])
        if n not in by_num:
            missing_n.append(n)
            by_num[n] = _round_from_overlay(raw, as_of)

    if missing_n:
        print(f"[ARIS] FastF1 calendar {year} missing round(s) {missing_n} — filled from FIA overlay", flush=True)

    return [by_num[n] for n in sorted(by_num)]


_LAPS_MEM: dict[tuple[int, int], int | None] = {}


def scheduled_laps(
    year: int, round_number: int, country: str = "", circuit_key: str = ""
) -> int | None:
    """Race lap count from track YAML. Does not call get_calendar (avoids recursion)."""
    key = (int(year), int(round_number))
    if key in _LAPS_MEM:
        return _LAPS_MEM[key]
    n: int | None = None
    try:
        from aris.tracks import load_track_config

        cfg = load_track_config(country or circuit_key, year=year, round_no=round_number)
        val = int(getattr(cfg, "total_laps", 0) or 0)
        n = val if val > 0 else None
    except Exception:
        n = None
    _LAPS_MEM[key] = n
    return n


def get_calendar(year: int, as_of: datetime | None = None, *, for_replay: bool = False) -> CalendarResponse:
    if for_replay:
        assert_replay_year(year)
    wall = datetime.now(timezone.utc)
    as_of = now_utc(as_of)
    near_now = abs((as_of - wall).total_seconds()) < 180
    cache_key = f"calbuild_jolpica23_{year}" if near_now else f"calbuild_jolpica23_{year}_{as_of.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    hit = mem_cache.get(cache_key, TTL_CALENDAR)
    if hit is not None:
        return hit
    notes = load_notes()
    sched = _SCHED_MEM.get(year)
    source: str = "estimated"
    # 2026 round list and race dates always come from NOTES_OVERLAY (23-round FIA
    # calendar). FastF1 may still supply circuit keys / session stamps via
    # _ensure_complete_calendar, but it must not keep the old 24-round draft
    # (Australia 15 Mar, Japan as round 4) in the API.
    if year == 2026:
        ff1_rounds: list[CalendarRound] = []
        if sched is not None:
            try:
                ff1_rounds = _rounds_from_schedule(year, sched, as_of)
                source = "fastf1"
            except Exception:
                source = "estimated"
        rounds = ff1_rounds
    elif sched is not None:
        try:
            rounds = _rounds_from_schedule(year, sched, as_of)
            source = "fastf1"
        except Exception:
            rounds = _fallback_rounds(year, notes, as_of)
    elif year in NOTES_OVERLAY:
        rounds = [_round_from_overlay(raw, as_of) for raw in NOTES_OVERLAY[year]]
        source = "estimated"
    else:
        try:
            sched = _schedule_from_fastf1(year)
            rounds = _rounds_from_schedule(year, sched, as_of)
            source = "fastf1"
        except Exception:
            rounds = _fallback_rounds(year, notes, as_of)
            source = "estimated"
    rounds = _ensure_complete_calendar(year, rounds, as_of)
    rounds = [_with_sessions(r) for r in rounds]
    stamped: list[CalendarRound] = []
    for rnd in rounds:
        reason = _cancelled(notes, year, rnd.round_number)
        if reason and rnd.status != "CANCELLED":
            stamped.append(rnd.model_copy(update={"status": "CANCELLED", "cancelled_reason": reason}))
        else:
            stamped.append(rnd)
    rounds = stamped
    filled: list[CalendarRound] = []
    for rnd in rounds:
        laps = scheduled_laps(year, rnd.round_number, rnd.country, rnd.circuit_key)
        if laps and rnd.total_laps != laps:
            filled.append(rnd.model_copy(update={"total_laps": laps}))
        else:
            filled.append(rnd)
    rounds = filled
    result = CalendarResponse(year=year, rounds=rounds, source=source, as_of=as_of)  # type: ignore[arg-type]
    mem_cache.set(cache_key, result)
    return result


def get_round(year: int, round_number: int, as_of: datetime | None = None) -> CalendarRound:
    cal = get_calendar(year, as_of=as_of)
    for rnd in cal.rounds:
        if rnd.round_number == round_number:
            return rnd
    raise KeyError(f"No round {round_number} in {year}")


def peek_round_meta(year: int, round_number: int) -> tuple[str, str]:
    """Country + circuit_key from memory/overlay only — never loads FastF1."""
    wall = datetime.now(timezone.utc)
    hit = mem_cache.get(f"calbuild_jolpica23_{year}", TTL_CALENDAR)
    if hit is None:
        hit = mem_cache.get(f"calbuild_jolpica23_{year}_{wall.strftime('%Y-%m-%dT%H:%M:%SZ')}", TTL_CALENDAR)
    if hit is not None:
        for rnd in getattr(hit, "rounds", []):
            if int(getattr(rnd, "round_number", 0) or 0) == int(round_number):
                return str(rnd.country or ""), str(rnd.circuit_key or "")
    for row in NOTES_OVERLAY.get(int(year), []):
        if int(row.get("round_number") or 0) == int(round_number):
            return str(row.get("country") or ""), str(row.get("circuit_key") or row.get("name") or "")
    return "", ""


def _session_status(dt: datetime | None, as_of: datetime, duration_h: float = 1.5) -> str:
    if dt is None:
        return "UPCOMING"
    if as_of < dt:
        return "UPCOMING"
    if as_of <= dt + timedelta(hours=duration_h):
        return "LIVE"
    return "COMPLETED"


def get_round_sessions(
    year: int,
    round_number: int,
    as_of: datetime | None = None,
    *,
    replay: bool = False,
) -> RoundSessionsResponse:
    as_of = now_utc(as_of)
    rnd = get_round(year, round_number, as_of=as_of)
    specs: list[tuple[str, str, datetime | None, float]] = [
        ("FP1", "Free Practice 1", rnd.date_fp1, 1.5),
        ("FP2", "Free Practice 2", rnd.date_fp2, 1.5),
        ("FP3", "Free Practice 3", rnd.date_fp3, 1.5),
        ("SQ", "Sprint Qualifying", rnd.date_sprint_quali, 0.8),
        ("S", "Sprint", rnd.date_sprint, 1.0),
        ("Q", "Qualifying", rnd.date_quali, 1.5),
        ("R", "Race", rnd.date_race, 2.25),
    ]
    sessions: list[SessionInfo] = []
    for stype, name, dt, hours in specs:
        if dt is None and stype in {"FP2", "FP3"} and rnd.is_sprint_weekend:
            continue
        if dt is None and stype in {"SQ", "S"} and not rnd.is_sprint_weekend:
            continue
        status = _session_status(dt, as_of, hours)
        if rnd.status == "CANCELLED":
            status = "UPCOMING"
        if replay and stype != "R":
            continue
        sessions.append(
            SessionInfo(
                session_type=stype,
                session_name=name,
                status=status,  # type: ignore[arg-type]
                datetime_utc=dt,
                fastf1_key=f"{year}/{round_number}/{stype}" if status == "COMPLETED" else None,
            )
        )
    return RoundSessionsResponse(
        year=year,
        round_number=round_number,
        name=rnd.name,
        is_sprint_weekend=rnd.is_sprint_weekend,
        sessions=sessions,
    )


def next_race(as_of: datetime | None = None, year: int | None = None) -> NextRaceResponse:
    as_of = now_utc(as_of)
    years = [year] if year is not None else [as_of.year, as_of.year + 1]
    candidates: list[CalendarRound] = []
    cal_year = years[0]
    for y in years:
        if y < 2024 or y > 2026:
            continue
        cal = get_calendar(y, as_of=as_of)
        cal_year = y
        for rnd in cal.rounds:
            if rnd.status == "UPCOMING":
                candidates.append(rnd)
            elif rnd.status == "LIVE":
                try:
                    weekend = get_round_sessions(y, rnd.round_number, as_of=as_of)
                except Exception:
                    candidates.append(rnd)
                    continue
                if any(s.status in {"UPCOMING", "LIVE"} for s in weekend.sessions):
                    candidates.append(rnd)
        if candidates:
            break
    if not candidates:
        # Off season: first race of next listed year, or last completed
        for y in (2026, 2025, 2024):
            cal = get_calendar(y, as_of=as_of)
            if cal.rounds:
                rnd = cal.rounds[0]
                return _next_from_round(cal.year, rnd, as_of, off_season=True)
        raise RuntimeError("No calendar rounds available")
    rnd = candidates[0]
    return _next_from_round(rnd_year(rnd, cal_year, as_of), rnd, as_of, off_season=False)


def rnd_year(rnd: CalendarRound, fallback: int, as_of: datetime) -> int:
    dt = rnd.date_race or rnd.date_fp1
    if dt is not None:
        return dt.year
    return fallback


def _next_from_round(
    year: int, rnd: CalendarRound, as_of: datetime, *, off_season: bool
) -> NextRaceResponse:
    weekend = get_round_sessions(year, rnd.round_number, as_of=as_of)
    upcoming = [
        s
        for s in weekend.sessions
        if s.datetime_utc is not None and s.status in {"UPCOMING", "LIVE"}
    ]
    next_s = upcoming[0] if upcoming else None
    target = (
        next_s.datetime_utc
        if next_s and next_s.datetime_utc
        else rnd.date_fp1 or rnd.date_race or as_of
    )
    delta = target - as_of
    secs = max(0, int(delta.total_seconds()))
    first = None
    dts = [s.datetime_utc for s in weekend.sessions if s.datetime_utc]
    if dts:
        first = min(dts)
    is_weekend = False
    if first is not None:
        is_weekend = first - timedelta(days=1) <= as_of <= (rnd.date_race or first) + timedelta(
            hours=6
        )
        if 0 <= (first - as_of).total_seconds() <= 3 * 86400:
            is_weekend = True
    sessions = [
        WeekendSession(
            session_type=s.session_type,
            session_name=s.session_name,
            datetime_utc=s.datetime_utc,
            status=s.status,
        )
        for s in weekend.sessions
    ]
    return NextRaceResponse(
        year=year,
        round_number=rnd.round_number,
        name=rnd.name,
        circuit_name=rnd.circuit_name,
        circuit_key=rnd.circuit_key,
        country=rnd.country,
        city=rnd.city,
        date_race=rnd.date_race,
        status=rnd.status,
        is_sprint_weekend=rnd.is_sprint_weekend,
        is_this_weekend=is_weekend and not off_season,
        countdown_seconds=secs,
        days_until=secs // 86400,
        hours_until=(secs % 86400) // 3600,
        next_session_name=next_s.session_name if next_s else None,
        next_session_datetime=next_s.datetime_utc if next_s else target,
        sessions_this_weekend=sessions,
        notes=rnd.notes,
        as_of=as_of,
        off_season=off_season,
        is_live=rnd.status == "LIVE",
    )
