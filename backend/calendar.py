"""F1 calendar for 2024–2026: FastF1 schedule + overlay notes + computed status."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import yaml

from backend.cache import enable_fastf1_cache
from backend.models import (
    CalendarResponse,
    CalendarRound,
    NextRaceResponse,
    RoundSessionsResponse,
    SessionInfo,
    WeekendSession,
)
from backend.paths import BACKEND

NOTES_PATH = BACKEND / "calendar_notes.yaml"

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


def now_utc(as_of: datetime | None = None) -> datetime:
    if as_of is not None:
        if as_of.tzinfo is None:
            return as_of.replace(tzinfo=timezone.utc)
        return as_of.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def load_notes() -> dict[str, Any]:
    raw = yaml.safe_load(NOTES_PATH.read_text(encoding="utf-8")) or {}
    return raw


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


def _live_session_keys(as_of: datetime) -> set[tuple[int, int]]:
    """(year, round) pairs that currently have a live OpenF1 session."""
    try:
        from backend.live import peek_live_round

        hit = peek_live_round(as_of)
        if hit is None:
            return set()
        return {hit}
    except Exception:
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
    # Session windows: treat as complete once race start + 4h has passed.
    if as_of >= race_dt + timedelta(hours=4):
        return "COMPLETED"
    if first_dt is not None and first_dt <= as_of <= race_dt + timedelta(hours=4):
        return "LIVE"
    if as_of >= race_dt:
        return "LIVE"
    return "UPCOMING"


def _schedule_from_fastf1(year: int) -> pd.DataFrame:
    enable_fastf1_cache()
    import fastf1

    sched = fastf1.get_event_schedule(year, include_testing=False)
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


def get_calendar(year: int, as_of: datetime | None = None) -> CalendarResponse:
    as_of = now_utc(as_of)
    notes = load_notes()
    try:
        sched = _schedule_from_fastf1(year)
        rounds = _rounds_from_schedule(year, sched, as_of)
        source: str = "fastf1"
    except Exception:
        rounds = _fallback_rounds(year, notes, as_of)
        source = "estimated"
    return CalendarResponse(year=year, rounds=rounds, source=source, as_of=as_of)  # type: ignore[arg-type]


def get_round(year: int, round_number: int, as_of: datetime | None = None) -> CalendarRound:
    cal = get_calendar(year, as_of=as_of)
    for rnd in cal.rounds:
        if rnd.round_number == round_number:
            return rnd
    raise KeyError(f"No round {round_number} in {year}")


def _session_status(dt: datetime | None, as_of: datetime, duration_h: float = 1.5) -> str:
    if dt is None:
        return "UPCOMING"
    if as_of < dt:
        return "UPCOMING"
    if as_of <= dt + timedelta(hours=duration_h):
        return "LIVE"
    return "COMPLETED"


def get_round_sessions(
    year: int, round_number: int, as_of: datetime | None = None
) -> RoundSessionsResponse:
    as_of = now_utc(as_of)
    rnd = get_round(year, round_number, as_of=as_of)
    specs: list[tuple[str, str, datetime | None, float]] = [
        ("FP1", "Free Practice 1", rnd.date_fp1, 1.5),
        ("FP2", "Free Practice 2", rnd.date_fp2, 1.5),
        ("FP3", "Free Practice 3", rnd.date_fp3, 1.5),
        ("SQ", "Sprint Qualifying", rnd.date_sprint_quali, 1.0),
        ("S", "Sprint", rnd.date_sprint, 1.0),
        ("Q", "Qualifying", rnd.date_quali, 1.5),
        ("R", "Race", rnd.date_race, 3.0),
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
            if rnd.status in {"LIVE", "UPCOMING"}:
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
    )
