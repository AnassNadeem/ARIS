"""Load a race Session, falling back to the local FastF1 pickle cache.

Live schedule backends (FastF1 / F1 timing / Ergast) can all fail at once.
The year folders under ``fastf1_cache/`` still hold the session pickles, so we
reconstruct a minimal Event whose ``api_path`` matches those folders.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE = _REPO_ROOT / "fastf1_cache"


def _enable_cache(cache_dir: Path | None = None) -> Path:
    import fastf1

    root = cache_dir or DEFAULT_CACHE
    root.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(root))
    return root


def _match_event_dir(year_dir: Path, gp: str) -> Path | None:
    if not year_dir.is_dir():
        return None
    full = gp.replace(" ", "_").lower()
    tokens = [
        t
        for t in gp.lower().replace("grand prix", "").replace("gp", "").replace("-", " ").split()
        if len(t) >= 4
    ]
    dirs = [p for p in year_dir.iterdir() if p.is_dir()]
    for path in dirs:
        if full in path.name.lower():
            return path
    for path in dirs:
        name = path.name.lower().replace("_", " ")
        if tokens and all(t in name for t in tokens):
            return path
    return None


def _session_from_cache(year: int, gp: str, cache_dir: Path, round_no: int = 0):
    from fastf1.core import Session
    from fastf1.events import Event

    event_dir = _match_event_dir(cache_dir / str(year), gp)
    if event_dir is None:
        raise FileNotFoundError(f"no pickle cache for {year} {gp}")
    race_dirs = [p for p in event_dir.iterdir() if p.is_dir() and p.name.endswith("_Race")]
    if not race_dirs:
        raise FileNotFoundError(f"no Race pickle dir in {event_dir}")
    race_dir = sorted(race_dirs)[0]
    event_date = pd.Timestamp(event_dir.name.split("_", 1)[0])
    session_date = pd.Timestamp(race_dir.name.split("_", 1)[0])
    event_name = event_dir.name.split("_", 1)[1].replace("_", " ")
    payload = {
        "RoundNumber": int(round_no),
        "Country": "",
        "Location": "",
        "OfficialEventName": event_name,
        "EventName": event_name,
        "EventDate": event_date,
        "EventFormat": "conventional",
        "F1ApiSupport": True,
    }
    for i, name in enumerate(
        ("Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"), start=1
    ):
        payload[f"Session{i}"] = name
        payload[f"Session{i}Date"] = session_date if name == "Race" else event_date
        payload[f"Session{i}DateUtc"] = session_date if name == "Race" else event_date
    event = Event(pd.Series(payload), year=year)
    return Session(event=event, session_name="Race", f1_api_support=True)


def load_race_session(
    year: int,
    gp: str,
    *,
    laps: bool = True,
    weather: bool = False,
    telemetry: bool = False,
    messages: bool = False,
    cache_dir: Path | None = None,
    round_no: int = 0,
):
    """``fastf1.get_session`` first; reconstruct from pickle cache on schedule miss."""
    import fastf1

    root = _enable_cache(cache_dir)
    try:
        session = fastf1.get_session(year, gp, "R")
    except Exception:
        session = _session_from_cache(year, gp, root, round_no=round_no)
    session.load(laps=laps, weather=weather, telemetry=telemetry, messages=messages)
    return session
