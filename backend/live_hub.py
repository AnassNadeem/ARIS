"""Live hub: current session vs next event, countdown, circuit briefing."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from backend import analytics, calendar, live, sessions
from backend.calendar import country_flag, now_utc
from backend.models import (
    CalendarRound,
    CircuitMapResponse,
    HubCircuitInfo,
    HubMode,
    HubRaceHistoryRow,
    HubSession,
    HubStrategyPattern,
    LiveHubResponse,
    LiveStatus,
    NextRaceResponse,
    SessionInfo,
    WeekendSession,
)
from backend.utils import run_sync

_DEFAULT_PATTERNS = [
    HubStrategyPattern(label="1-Stop: Medium → Hard", note="Default dry pattern when history is unavailable"),
    HubStrategyPattern(label="2-Stop: Soft → Medium → Hard", note="Used when degradation is high"),
]


def classify_hub_mode(
    *,
    is_live: bool,
    session_ended: bool,
    weekend_sessions: list[SessionInfo] | list[WeekendSession] | list[HubSession],
    is_this_weekend: bool,
) -> tuple[HubMode, str | None]:
    """Pure weekend state machine — no I/O."""
    statuses = [(str(getattr(s, "session_type", "")), str(getattr(s, "status", ""))) for s in weekend_sessions]
    live_sess = any(st == "LIVE" for _, st in statuses)
    if is_live or live_sess:
        return "live_session", None

    race = next((s for s in weekend_sessions if str(getattr(s, "session_type", "")) == "R"), None)
    next_open = next(
        (
            s
            for s in weekend_sessions
            if str(getattr(s, "status", "")) in {"UPCOMING", "LIVE"}
        ),
        None,
    )

    if is_this_weekend:
        race_status = str(getattr(race, "status", "") or "")
        if race is not None and race_status == "UPCOMING":
            nxt_type = str(getattr(next_open, "session_type", "") or "R") if next_open else "R"
            nxt_name = str(getattr(next_open, "session_name", "") or "the next session") if next_open else "the next session"
            if nxt_type == "R":
                return (
                    "waiting_for_session",
                    "Race hasn't started yet — waiting for race data.",
                )
            return "waiting_for_session", f"Waiting for {nxt_name}."
        if any(st == "UPCOMING" for _, st in statuses):
            nxt_name = str(getattr(next_open, "session_name", "") or "the next session") if next_open else "the next session"
            return "waiting_for_session", f"Waiting for {nxt_name}."

    if session_ended:
        return "session_ended", None
    return "next_weekend", None


def _hub_sessions(weekend: list[SessionInfo]) -> list[HubSession]:
    out: list[HubSession] = []
    for s in weekend:
        out.append(
            HubSession(
                session_type=s.session_type,
                session_name=s.session_name,
                datetime_utc=s.datetime_utc,
                status=s.status,
                replayable=s.status == "COMPLETED",
                live=s.status == "LIVE",
            )
        )
    return out


def _strategy_patterns(hist: Any, chars: Any) -> list[HubStrategyPattern]:
    patterns: list[HubStrategyPattern] = []
    if hist is not None and getattr(hist, "typical_stop_count", None) is not None:
        n = int(round(float(hist.typical_stop_count)))
        first = getattr(hist, "median_first_stop_lap", None)
        first_note = f"first stop ~lap {first}" if first else "historical median"
        label = "1-stop" if n <= 1 else f"{n}-stop"
        patterns.append(HubStrategyPattern(label=f"{label} ({first_note})", note="Typical winning pattern at this circuit"))
    notes = getattr(chars, "aris_notes", None) if chars is not None else None
    if notes is not None:
        tend = getattr(notes, "tyre_compound_tendencies", "") or ""
        if tend:
            patterns.append(HubStrategyPattern(label=tend, note="ARIS circuit note"))
        und = getattr(notes, "undercut_effectiveness", "") or ""
        if und:
            patterns.append(HubStrategyPattern(label=und, note="Undercut / overtake"))
    return patterns or list(_DEFAULT_PATTERNS)


def _circuit_info_fast(nxt: NextRaceResponse) -> HubCircuitInfo:
    """YAML / calendar only — never FastF1 or Jolpica."""
    laps = None
    length = None
    pit = None
    try:
        laps = calendar.scheduled_laps(nxt.year, nxt.round_number, nxt.country, nxt.circuit_key)
    except Exception:
        laps = None
    try:
        from aris.tracks import load_track_config

        cfg = load_track_config(nxt.country or nxt.circuit_key, year=nxt.year, round_no=nxt.round_number)
        pit_raw = getattr(cfg, "pit_loss_s", None)
        pit = float(pit_raw) if pit_raw else None
        metres = getattr(cfg, "lap_length_m", None)
        length = float(metres) / 1000.0 if metres else None
    except Exception:
        pass
    return HubCircuitInfo(
        circuit_key=nxt.circuit_key,
        circuit_name=nxt.circuit_name,
        country=nxt.country,
        country_flag=country_flag(nxt.country, nxt.circuit_key),
        length_km=length,
        total_laps=laps,
        pit_loss_seconds=pit,
        strategy_patterns=list(_DEFAULT_PATTERNS),
        race_history=[],
        notes=list(nxt.notes or []),
    )


def _circuit_info(nxt: NextRaceResponse) -> HubCircuitInfo:
    chars = None
    try:
        chars = analytics.circuit_characteristics(nxt.circuit_key, nxt.year)
    except Exception:
        chars = None
    hist = None
    try:
        hist = analytics.peek_circuit_history(nxt.circuit_key)
    except Exception:
        hist = None
    history_rows: list[HubRaceHistoryRow] = []
    if hist is not None:
        for row in list(getattr(hist, "years", None) or [])[:8]:
            history_rows.append(
                HubRaceHistoryRow(
                    year=int(row.year),
                    winner=row.winner,
                    pole=row.pole,
                    fastest_lap=row.fastest_lap,
                    race_name=row.race_name,
                )
            )
    length = getattr(chars, "lap_length_km", None) if chars is not None else None
    total = getattr(chars, "total_laps", None) if chars is not None else None
    if not total:
        try:
            total = calendar.scheduled_laps(nxt.year, nxt.round_number, nxt.country, nxt.circuit_key)
        except Exception:
            total = None
    return HubCircuitInfo(
        circuit_key=nxt.circuit_key,
        circuit_name=nxt.circuit_name,
        country=nxt.country,
        country_flag=country_flag(nxt.country, nxt.circuit_key),
        length_km=length,
        total_laps=total,
        turns=getattr(chars, "turns", None) if chars is not None else None,
        pit_loss_seconds=getattr(chars, "pit_loss_seconds", None) if chars is not None else None,
        tyre_stress_rating=getattr(chars, "tyre_stress_rating", None) if chars is not None else None,
        strategy_patterns=_strategy_patterns(hist, chars),
        race_history=history_rows,
        notes=list(nxt.notes or []),
    )


def _weekend_from_next(nxt: NextRaceResponse) -> list[SessionInfo]:
    return [
        SessionInfo(
            session_type=s.session_type,
            session_name=s.session_name,
            status=s.status,
            datetime_utc=s.datetime_utc,
        )
        for s in nxt.sessions_this_weekend
    ]


def build_live_hub_fast(as_of: datetime | None = None) -> LiveHubResponse:
    """Calendar-only hub so /live never waits on OpenF1 / FastF1."""
    as_of = now_utc(as_of)
    nxt = calendar.next_race(as_of=as_of)
    infos = _weekend_from_next(nxt)
    status = LiveStatus(
        is_live=False,
        year=nxt.year,
        round_number=nxt.round_number,
        session_name=nxt.next_session_name,
        gp_name=nxt.name,
        session_remaining_seconds=nxt.countdown_seconds,
    )
    mode, reason = classify_hub_mode(
        is_live=False,
        session_ended=False,
        weekend_sessions=infos,
        is_this_weekend=bool(nxt.is_this_weekend),
    )
    return LiveHubResponse(
        mode=mode,
        waiting_reason=reason,
        countdown_seconds=int(nxt.countdown_seconds or 0),
        countdown_target=nxt.next_session_datetime,
        live=status,
        next=nxt,
        weekend_sessions=_hub_sessions(infos),
        circuit=_circuit_info_fast(nxt),
        as_of=as_of,
    )


async def build_live_hub(as_of: datetime | None = None) -> LiveHubResponse:
    as_of = now_utc(as_of)
    nxt = await run_sync(calendar.next_race, as_of=as_of)

    async def _status() -> LiveStatus:
        try:
            return await asyncio.wait_for(live.live_status(as_of), timeout=2.5)
        except Exception:
            return LiveStatus(
                is_live=False,
                year=nxt.year,
                round_number=nxt.round_number,
                error="live status unavailable",
            )

    async def _weekend() -> list[SessionInfo]:
        try:
            weekend = await asyncio.wait_for(
                run_sync(calendar.get_round_sessions, nxt.year, nxt.round_number, as_of),
                timeout=2.0,
            )
            return list(weekend.sessions)
        except Exception:
            return _weekend_from_next(nxt)

    status, infos = await asyncio.gather(_status(), _weekend())
    circuit = _circuit_info_fast(nxt)
    try:
        rich = await asyncio.wait_for(run_sync(_circuit_info, nxt), timeout=1.2)
        if rich is not None:
            circuit = rich
    except Exception:
        pass
    mode, reason = classify_hub_mode(
        is_live=bool(status.is_live),
        session_ended=bool(status.session_ended),
        weekend_sessions=infos,
        is_this_weekend=bool(nxt.is_this_weekend),
    )
    return LiveHubResponse(
        mode=mode,
        waiting_reason=reason,
        countdown_seconds=int(nxt.countdown_seconds or 0),
        countdown_target=nxt.next_session_datetime,
        live=status,
        next=nxt,
        weekend_sessions=_hub_sessions(infos),
        circuit=circuit,
        as_of=as_of,
    )


def resolve_layout_round(
    circuit_id: str,
    year: int | None = None,
    round_number: int | None = None,
    as_of: datetime | None = None,
) -> tuple[int, int]:
    """Map a circuit key to a year/round that can serve a FastF1 outline."""
    as_of = now_utc(as_of)
    if year is not None and round_number is not None:
        return int(year), int(round_number)
    needle = str(circuit_id or "").strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    years = [year] if year is not None else [as_of.year, as_of.year - 1, 2025, 2024]
    seen: set[int] = set()
    for y in years:
        if y is None or y in seen or y < 2018:
            continue
        seen.add(int(y))
        try:
            cal = calendar.get_calendar(int(y), as_of=as_of)
        except Exception:
            continue
        matches: list[CalendarRound] = []
        for rnd in cal.rounds:
            if rnd.status == "CANCELLED":
                continue
            key = (rnd.circuit_key or "").lower().replace(" ", "").replace("_", "").replace("-", "")
            name = (rnd.circuit_name or "").lower().replace(" ", "")
            if needle in {key, name} or needle in key or key in needle or needle in name:
                matches.append(rnd)
        if not matches:
            continue
        completed = [r for r in matches if r.status == "COMPLETED"]
        pick = (completed or matches)[-1]
        return int(y), int(pick.round_number)
    raise KeyError(f"No calendar round for circuit '{circuit_id}'")


def circuit_layout(
    circuit_id: str,
    year: int | None = None,
    round_number: int | None = None,
) -> CircuitMapResponse:
    y, rnd = resolve_layout_round(circuit_id, year, round_number)
    return sessions.circuit_map_quick(y, rnd)
