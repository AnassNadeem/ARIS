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

# OpenF1 team colours are hex without '#'.
_TEAM_COLOUR_FALLBACK: dict[str, str] = {}


def _hex(colour: str | None) -> str | None:
    if not colour:
        return None
    c = str(colour).strip()
    if not c:
        return None
    if not c.startswith("#"):
        c = f"#{c}"
    return c.upper()


def _openf1_session_key(year: int) -> int | None:
    def _meetings() -> list[dict[str, Any]]:
        try:
            data = openf1("meetings", {"year": year})
        except Exception:
            return []
        return data if isinstance(data, list) else []

    meetings = cached(f"openf1:meetings:{year}", TTL_METADATA, _meetings)
    if not meetings:
        return None

    def _sessions() -> list[dict[str, Any]]:
        try:
            data = openf1("sessions", {"year": year})
        except Exception:
            return []
        return data if isinstance(data, list) else []

    sessions = cached(f"openf1:sessions-year:{year}", TTL_METADATA, _sessions)
    if not sessions:
        return None
    # Prefer a race session so the full grid is present.
    races = [s for s in sessions if str(s.get("session_name") or "").lower() == "race"]
    pool = races or sessions
    pool = sorted(pool, key=lambda s: str(s.get("date_start") or ""))
    key = pool[-1].get("session_key") if pool else None
    return int(key) if key is not None else None


def _drivers_from_openf1(year: int) -> list[Driver]:
    session_key = _openf1_session_key(year)
    if session_key is None:
        return []

    def _fetch() -> list[dict[str, Any]]:
        try:
            data = openf1("drivers", {"session_key": session_key})
        except Exception:
            return []
        return data if isinstance(data, list) else []

    rows = cached(f"openf1:drivers:{year}:{session_key}", TTL_METADATA, _fetch)
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
                driver_number=int(row["driver_number"]) if row.get("driver_number") is not None else None,
                country_code=row.get("country_code"),
                headshot_url=row.get("headshot_url"),
                estimated=False,
            )
        )
    return out


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
        sess = fastf1.get_session(year, rnd.round_number, "R")
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
                    team_colour=None,
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


def get_drivers(year: int) -> DriversResponse:
    drivers = _drivers_from_openf1(year)
    source: str = "openf1"
    label = None
    if not drivers:
        drivers = _drivers_from_fastf1(year)
        source = "fastf1"
    if not drivers:
        drivers = _drivers_estimated(year)
        source = "estimated"
        label = "[ESTIMATED — API unavailable]"
    return DriversResponse(
        year=year,
        drivers=drivers,
        source=source,  # type: ignore[arg-type]
        estimated_label=label,
    )


def team_colour(team_name: str) -> str | None:
    if not team_name:
        return None
    if team_name.lower() in _TEAM_COLOUR_FALLBACK:
        return _TEAM_COLOUR_FALLBACK[team_name.lower()]
    notes = load_notes()
    for year_block in (notes.get("estimated_rosters") or {}).values():
        for t in year_block.get("teams") or []:
            if str(t.get("name") or "").lower() == team_name.lower():
                return _hex(t.get("colour"))
    return None


def _jolpica(path: str) -> dict[str, Any] | None:
    from backend.http_client import jolpica

    try:
        return cached(f"jolpica:{path}", TTL_STANDINGS, lambda: jolpica(path))
    except Exception:
        return None


def driver_standings(year: int) -> DriverStandingsResponse:
    data = _jolpica(f"{year}/driverStandings")
    if not data:
        return DriverStandingsResponse(year=year, standings=[], source="unavailable")
    try:
        lists = data["MRData"]["StandingsTable"]["StandingsLists"]
        table = lists[0]["DriverStandings"] if lists else []
    except (KeyError, IndexError, TypeError):
        return DriverStandingsResponse(year=year, standings=[], source="unavailable")
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
        rows.append(
            DriverStanding(
                position=int(entry.get("position") or len(rows) + 1),
                driver_code=code,
                full_name=f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
                team_name=team,
                team_colour=team_colour(team),
                points=pts,
                wins=wins,
                gap_to_leader=round(leader_pts - pts, 1),
            )
        )
    champ = rows[0].driver_code if rows and year < 2026 else None
    leader = rows[0].driver_code if rows else None
    return DriverStandingsResponse(
        year=year,
        standings=rows,
        source="jolpica",
        champion_code=champ if year <= 2025 else None,
        leader_code=leader,
    )


def constructor_standings(year: int) -> ConstructorStandingsResponse:
    data = _jolpica(f"{year}/constructorStandings")
    if not data:
        return ConstructorStandingsResponse(year=year, standings=[], source="unavailable")
    try:
        lists = data["MRData"]["StandingsTable"]["StandingsLists"]
        table = lists[0]["ConstructorStandings"] if lists else []
    except (KeyError, IndexError, TypeError):
        return ConstructorStandingsResponse(year=year, standings=[], source="unavailable")
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
    return ConstructorStandingsResponse(
        year=year,
        standings=rows,
        source="jolpica",
        champion_name=rows[0].team_name if rows and year <= 2025 else None,
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
