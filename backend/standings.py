"""Driver/team metadata (OpenF1) and championship standings (Jolpica)."""

from __future__ import annotations

from typing import Any

from backend.cache import TTL_METADATA, TTL_STANDINGS, cached
from backend.calendar import load_notes
from backend.http_client import openf1
from backend.models import (
    ConstructorStanding,
    ConstructorStandingsResponse,
    Driver,
    DriverStanding,
    DriverStandingsResponse,
    DriversResponse,
    Team,
    TeamsResponse,
)

ALLOWED_YEARS = frozenset({2024, 2025, 2026})
STANDINGS_YEAR_LIMIT_MSG = "Standings only available for 2024, 2025, and 2026."
STANDINGS_2026_UNAVAILABLE = "2026 standings not yet available."


class StandingsYearBlocked(ValueError):
    """Standings were requested for a year outside ALLOWED_YEARS."""


def assert_standings_year(year: int) -> int:
    y = int(year)
    if y not in ALLOWED_YEARS:
        raise StandingsYearBlocked(STANDINGS_YEAR_LIMIT_MSG)
    return y

# OpenF1 team colours are hex without '#'.
_TEAM_COLOUR_FALLBACK: dict[str, str] = {}

_OPENF1_SESSION_NAMES = {
    "FP1": ("Practice 1",),
    "FP2": ("Practice 2",),
    "FP3": ("Practice 3",),
    "SQ": ("Sprint Qualifying", "Sprint Shootout"),
    "SS": ("Sprint Qualifying", "Sprint Shootout"),
    "S": ("Sprint",),
    "Q": ("Qualifying",),
    "R": ("Race",),
}


def _hex(colour: str | None) -> str | None:
    if not colour:
        return None
    c = str(colour).strip()
    if not c:
        return None
    if not c.startswith("#"):
        c = f"#{c}"
    return c.upper()


def _session_start(row: dict[str, Any]):
    raw = str(row.get("date_start") or "")
    if not raw:
        return None
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _openf1_year_sessions(year: int) -> list[dict[str, Any]]:
    def _sessions() -> list[dict[str, Any]]:
        try:
            data = openf1("sessions", {"year": year})
        except Exception:
            return []
        return data if isinstance(data, list) else []

    rows = cached(f"openf1:sessions-year:{year}", TTL_METADATA, _sessions)
    return rows if isinstance(rows, list) else []


def _openf1_session_key(year: int) -> int | None:
    sessions = _openf1_year_sessions(year)
    if not sessions:
        return None
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    started = [
        s
        for s in sessions
        if isinstance(s, dict) and (_session_start(s) is not None and _session_start(s) <= now)
    ]
    pool = started or [s for s in sessions if isinstance(s, dict)]
    # A future race entry often still has last week's lineup (HAD in, TSU out).
    pool = sorted(pool, key=lambda s: str(s.get("date_start") or ""))
    key = pool[-1].get("session_key") if pool else None
    return int(key) if key is not None else None


def _meeting_sessions(year: int, round_number: int) -> list[dict[str, Any]]:
    from backend.calendar import get_round

    try:
        rnd = get_round(year, round_number)
    except Exception:
        return []
    from backend.live import _circuit_match

    return [
        sess
        for sess in _openf1_year_sessions(year)
        if isinstance(sess, dict) and _circuit_match(sess, rnd)
    ]


def _openf1_session_key_for(
    year: int, round_number: int | None, session_type: str | None
) -> int | None:
    if round_number is None:
        return _openf1_session_key(year)
    meeting = _meeting_sessions(year, int(round_number))
    st = str(session_type or "").upper()
    names = _OPENF1_SESSION_NAMES.get(st, (session_type,) if session_type else ())
    named = [
        sess
        for sess in meeting
        if names
        and str(sess.get("session_name") or "") in names
        and sess.get("session_key") is not None
    ]
    if named:
        named.sort(key=lambda row: str(row.get("date_start") or ""))
        return int(named[-1]["session_key"])
    dated = [sess for sess in meeting if sess.get("session_key") is not None]
    dated.sort(key=lambda row: str(row.get("date_start") or ""))
    if not dated:
        return _openf1_session_key(year)
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    started = [sess for sess in dated if (_session_start(sess) or now) <= now]
    pick = (started or dated)[-1]
    return int(pick["session_key"])


def _parse_openf1_drivers(rows: list[dict[str, Any]]) -> list[Driver]:
    seen: set[str] = set()
    out: list[Driver] = []
    for row in rows:
        code = str(row.get("name_acronym") or "").upper()
        if not code or code in seen:
            continue
        seen.add(code)
        full = str(row.get("full_name") or row.get("broadcast_name") or code)
        team = str(row.get("team_name") or "")
        colour = _hex(row.get("team_colour"))
        if team and colour:
            _TEAM_COLOUR_FALLBACK[team.lower()] = colour
        out.append(
            Driver(
                driver_code=code,
                full_name=full,
                team_name=team,
                team_colour=colour,
                driver_number=(
                    int(row["driver_number"]) if row.get("driver_number") is not None else None
                ),
                country_code=row.get("country_code"),
                headshot_url=row.get("headshot_url"),
                estimated=False,
            )
        )
    return out


def _drivers_from_openf1_key(session_key: int) -> list[Driver]:
    def _fetch() -> list[dict[str, Any]]:
        try:
            data = openf1("drivers", {"session_key": session_key})
        except Exception:
            return []
        return data if isinstance(data, list) else []

    rows = cached(f"openf1:drivers:{session_key}", TTL_METADATA, _fetch)
    return _parse_openf1_drivers(rows if isinstance(rows, list) else [])


def _session_entry_drivers(
    year: int, round_number: int | None = None, session_type: str | None = None
) -> list[Driver]:
    """OpenF1 entry list for this session, else this meeting, else year-latest."""
    keys: list[int] = []
    primary = _openf1_session_key_for(year, round_number, session_type)
    if primary is not None:
        keys.append(primary)
    if round_number is not None:
        meeting = _meeting_sessions(year, int(round_number))
        meeting.sort(key=lambda row: str(row.get("date_start") or ""), reverse=True)
        for sess in meeting:
            key = sess.get("session_key")
            if key is None:
                continue
            try:
                n = int(key)
            except (TypeError, ValueError):
                continue
            if n not in keys:
                keys.append(n)
    fallback = _openf1_session_key(year)
    if fallback is not None and fallback not in keys:
        keys.append(fallback)
    for key in keys:
        drivers = _drivers_from_openf1_key(key)
        if len(drivers) >= 8:
            return drivers
    return []


def _drivers_from_openf1(year: int) -> list[Driver]:
    return _session_entry_drivers(year)


def _apply_weekend_lineup(
    drivers: list[Driver], year: int, round_number: int | None
) -> list[Driver]:
    from backend.calendar import weekend_excluded_codes, weekend_replacement_codes

    excluded = weekend_excluded_codes(year, round_number)
    replacements = weekend_replacement_codes(year, round_number)
    if not excluded and not replacements:
        return drivers
    removed = [drv for drv in drivers if drv.driver_code in excluded]
    filled = [drv for drv in drivers if drv.driver_code not in excluded]
    present = {drv.driver_code for drv in filled}
    lookup = list(filled) + _drivers_estimated(year)
    for absent, repl in replacements.items():
        if repl in present:
            continue
        if not any(drv.driver_code == absent for drv in removed):
            continue
        meta = next((drv for drv in lookup if drv.driver_code == repl), None)
        if meta is None:
            meta = Driver(driver_code=repl, full_name=repl, team_name="", estimated=True)
        filled.append(meta)
        present.add(repl)
    return filled


def _drivers_from_fastf1(year: int) -> list[Driver]:
    try:
        from backend.cache import enable_fastf1_cache
        from backend.calendar import get_calendar

        enable_fastf1_cache()
        import fastf1

        cal = get_calendar(year)
        completed = [r for r in cal.rounds if r.status == "COMPLETED"]
        if not completed:
            return []
        rnd = completed[-1]
        from backend.fastf1_guard import FASTF1_LOCK

        sess = fastf1.get_session(year, rnd.round_number, "R")
        with FASTF1_LOCK:
            sess.load(laps=True, telemetry=False, weather=False, messages=False)
        out: list[Driver] = []
        seen: set[str] = set()
        for _, row in sess.results.iterrows():
            code = str(row.get("Abbreviation") or "")
            if not code or code in seen:
                continue
            seen.add(code)
            out.append(
                Driver(
                    driver_code=code,
                    full_name=str(row.get("FullName") or code),
                    team_name=str(row.get("TeamName") or ""),
                    team_colour=team_colour(str(row.get("TeamName") or "")),
                    driver_number=int(row["DriverNumber"]) if row.get("DriverNumber") == row.get("DriverNumber") else None,
                    estimated=False,
                )
            )
        return out
    except Exception:
        return []


def _drivers_estimated(year: int) -> list[Driver]:
    notes = load_notes()
    block = (notes.get("estimated_rosters") or {}).get(year) or (
        notes.get("estimated_rosters") or {}
    ).get(str(year))
    if not block:
        return []
    out: list[Driver] = []
    for row in block.get("drivers") or []:
        out.append(
            Driver(
                driver_code=str(row["code"]),
                full_name=str(row["name"]),
                team_name=str(row.get("team") or ""),
                team_colour=_hex(row.get("colour")),
                driver_number=row.get("number"),
                estimated=True,
            )
        )
    return out


def get_drivers(
    year: int, round_number: int | None = None, session_type: str | None = None
) -> DriversResponse:
    from backend.calendar import next_race

    rnd = round_number
    if rnd is None:
        try:
            nxt = next_race()
            if nxt.year == year:
                rnd = nxt.round_number
        except Exception:
            rnd = None
    drivers = _session_entry_drivers(year, rnd, session_type)
    source: str = "openf1"
    label = None
    if not drivers:
        drivers = _drivers_from_fastf1(year)
        source = "fastf1"
    if not drivers:
        drivers = _drivers_estimated(year)
        source = "estimated"
        label = "[ESTIMATED — API unavailable]"
    filled: list[Driver] = []
    for drv in drivers:
        if drv.team_colour:
            filled.append(drv)
            continue
        filled.append(drv.model_copy(update={"team_colour": team_colour(drv.team_name)}))
    try:
        filled = _apply_weekend_lineup(filled, year, rnd)
    except Exception:
        pass
    return DriversResponse(
        year=year,
        drivers=filled,
        source=source,  # type: ignore[arg-type]
        estimated_label=label,
    )


def team_colour(team_name: str) -> str | None:
    if not team_name:
        return None
    needle = team_name.lower().strip()
    if needle in _TEAM_COLOUR_FALLBACK:
        return _TEAM_COLOUR_FALLBACK[needle]
    notes = load_notes()
    for year_block in (notes.get("estimated_rosters") or {}).values():
        for t in year_block.get("teams") or []:
            name = str(t.get("name") or "").lower()
            if not name:
                continue
            if name == needle or name in needle or needle in name:
                return _hex(t.get("colour"))
    return None


def _jolpica(path: str) -> dict[str, Any] | None:
    from backend.http_client import jolpica

    try:
        return cached(f"jolpica:{path}", TTL_STANDINGS, lambda: jolpica(path))
    except Exception:
        return None


def _season_result_extras(year: int) -> dict[str, dict[str, int]]:
    """Podiums, fastest laps, and DNFs from Jolpica race results."""
    from backend.http_client import JOLPICA, get_json

    def _fetch() -> dict[str, Any]:
        try:
            return get_json(f"{JOLPICA}/{year}/results.json", {"limit": 1000})
        except Exception:
            return {}

    data = cached(f"jolpica:{year}:results", TTL_STANDINGS, _fetch)
    extras: dict[str, dict[str, int]] = {}
    try:
        races = data["MRData"]["RaceTable"]["Races"]
    except (KeyError, TypeError):
        return extras
    for race in races:
        for res in race.get("Results") or []:
            driver = res.get("Driver") or {}
            code = str(driver.get("code") or driver.get("driverId") or "")[:3].upper()
            if not code:
                continue
            bucket = extras.setdefault(code, {"podiums": 0, "fastest_laps": 0, "dnfs": 0})
            try:
                pos = int(res.get("position") or 99)
            except (TypeError, ValueError):
                pos = 99
            if pos <= 3:
                bucket["podiums"] += 1
            fl = res.get("FastestLap") or {}
            if str(fl.get("rank") or "") == "1":
                bucket["fastest_laps"] += 1
            status = str(res.get("status") or "")
            finished = status.lower() == "finished" or status.startswith("+")
            if not finished:
                bucket["dnfs"] += 1
    return extras


def driver_standings(year: int) -> DriverStandingsResponse:
    data = _jolpica(f"{year}/driverStandings")
    unavailable_msg = STANDINGS_2026_UNAVAILABLE if year == 2026 else None
    if not data:
        return DriverStandingsResponse(
            year=year, standings=[], source="unavailable", message=unavailable_msg
        )
    try:
        lists = data["MRData"]["StandingsTable"]["StandingsLists"]
        table = lists[0]["DriverStandings"] if lists else []
    except (KeyError, IndexError, TypeError):
        return DriverStandingsResponse(
            year=year, standings=[], source="unavailable", message=unavailable_msg
        )
    extras = _season_result_extras(year)
    rows: list[DriverStanding] = []
    leader_pts = 0.0
    for entry in table:
        driver = entry.get("Driver") or {}
        cons = (entry.get("Constructors") or [{}])[0]
        pts = float(entry.get("points") or 0)
        if not rows:
            leader_pts = pts
        wins = int(entry.get("wins") or 0)
        code = str(driver.get("code") or driver.get("driverId") or "")[:3].upper()
        team = str(cons.get("name") or "")
        extra = extras.get(code, {})
        rows.append(
            DriverStanding(
                position=int(entry.get("position") or len(rows) + 1),
                driver_code=code,
                full_name=f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
                team_name=team,
                team_colour=team_colour(team),
                points=pts,
                wins=wins,
                podiums=int(extra.get("podiums") or 0),
                fastest_laps=int(extra.get("fastest_laps") or 0),
                dnfs=int(extra.get("dnfs") or 0),
                gap_to_leader=round(leader_pts - pts, 1),
            )
        )
    if not rows:
        return DriverStandingsResponse(
            year=year, standings=[], source="unavailable", message=unavailable_msg
        )
    champ = rows[0].driver_code if year < 2026 else None
    leader = rows[0].driver_code
    return DriverStandingsResponse(
        year=year,
        standings=rows,
        source="jolpica",
        champion_code=champ if year <= 2025 else None,
        leader_code=leader,
    )


def constructor_standings(year: int) -> ConstructorStandingsResponse:
    data = _jolpica(f"{year}/constructorStandings")
    unavailable_msg = STANDINGS_2026_UNAVAILABLE if year == 2026 else None
    if not data:
        return ConstructorStandingsResponse(
            year=year, standings=[], source="unavailable", message=unavailable_msg
        )
    try:
        lists = data["MRData"]["StandingsTable"]["StandingsLists"]
        table = lists[0]["ConstructorStandings"] if lists else []
    except (KeyError, IndexError, TypeError):
        return ConstructorStandingsResponse(
            year=year, standings=[], source="unavailable", message=unavailable_msg
        )
    rows: list[ConstructorStanding] = []
    leader = 0.0
    for entry in table:
        cons = entry.get("Constructor") or {}
        pts = float(entry.get("points") or 0)
        if not rows:
            leader = pts
        name = str(cons.get("name") or "")
        rows.append(
            ConstructorStanding(
                position=int(entry.get("position") or len(rows) + 1),
                team_name=name,
                team_colour=team_colour(name),
                points=pts,
                wins=int(entry.get("wins") or 0),
                gap_to_leader=round(leader - pts, 1),
            )
        )
    if not rows:
        return ConstructorStandingsResponse(
            year=year, standings=[], source="unavailable", message=unavailable_msg
        )
    champ_name = rows[0].team_name if year <= 2025 else None
    dstand = driver_standings(year)
    by_team: dict[str, list[str]] = {}
    podiums_by_team: dict[str, int] = {}
    for d in dstand.standings:
        by_team.setdefault(d.team_name, []).append(d.driver_code)
        podiums_by_team[d.team_name] = podiums_by_team.get(d.team_name, 0) + int(d.podiums or 0)
    for row in rows:
        row.drivers = by_team.get(row.team_name, [])
        row.podiums = podiums_by_team.get(row.team_name, 0)
    return ConstructorStandingsResponse(
        year=year,
        standings=rows,
        source="jolpica",
        champion_name=champ_name,
    )


def get_teams(year: int) -> TeamsResponse:
    cons = constructor_standings(year)
    if cons.standings:
        teams = [
            Team(
                team_name=r.team_name,
                team_colour=r.team_colour,
                position=r.position,
                points=r.points,
            )
            for r in cons.standings
        ]
        return TeamsResponse(year=year, teams=teams, source=cons.source)
    drivers = get_drivers(year)
    seen: dict[str, Team] = {}
    for d in drivers.drivers:
        if d.team_name and d.team_name not in seen:
            seen[d.team_name] = Team(
                team_name=d.team_name,
                team_colour=d.team_colour,
                estimated=d.estimated,
            )
    source = "estimated" if drivers.source == "estimated" else "unavailable"
    return TeamsResponse(year=year, teams=list(seen.values()), source=source)  # type: ignore[arg-type]
