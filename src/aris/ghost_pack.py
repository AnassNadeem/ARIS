"""On-demand R2-shaped ghost for any driver who raced in a weekend pack.

``compute_ghost`` is the same pipeline the offline baker uses (recommend +
score_parallel_ghost over ``race_field.json``). ``get_or_compute_ghost``
serves a baked ``ghost_{DRIVER}.json`` when present, otherwise computes and
persists next to the pack so the next request is a file read.

Does not load FastF1. If the race pack itself is missing, callers get
``RacePackUnavailable`` and must not attempt a ghost.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACK_ROOT = REPO_ROOT / "data" / "replay_r2"

# Keep this string identical to frontend-next/lib/r2Replay.ts R2_RACE_UNAVAILABLE.
RACE_UNAVAILABLE_MSG = "Race data unavailable — check back soon"

_FILE_CACHE: dict[tuple[int, int, str], dict[str, Any]] = {}
_CACHE_LOCK = threading.Lock()
_COMPUTE_LOCKS: dict[tuple[int, int, str], threading.Lock] = {}


class GhostPackError(Exception):
    """Typed failure for the ghost-pack endpoint (never a silent empty ghost)."""

    code = "ghost_error"
    status = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def as_detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class RacePackUnavailable(GhostPackError):
    code = "race_unavailable"
    status = 404

    def __init__(self, message: str = RACE_UNAVAILABLE_MSG):
        super().__init__(message)


class DriverDidNotRace(GhostPackError):
    code = "driver_did_not_race"
    status = 422


class GhostDataGap(GhostPackError):
    code = "ghost_data_gap"
    status = 422


def pack_root() -> Path:
    raw = (os.environ.get("ARIS_REPLAY_R2_ROOT") or "").strip()
    return Path(raw) if raw else DEFAULT_PACK_ROOT


def _remote_allowed(explicit: bool) -> bool:
    # A test/dev override of the pack root must not leak HTTP fetches to public R2.
    if (os.environ.get("ARIS_REPLAY_R2_ROOT") or "").strip():
        return False
    return explicit


def local_pack_path(year: int, round_number: int, name: str) -> Path:
    return pack_root() / "replay" / str(int(year)) / str(int(round_number)) / name


def clear_ghost_pack_cache() -> None:
    with _CACHE_LOCK:
        _FILE_CACHE.clear()


def _r2_public_base() -> str:
    for key in ("R2_PUBLIC_BASE_URL", "R2_PUBLIC_ORIGIN"):
        val = (os.environ.get(key) or "").strip().rstrip("/")
        if val.startswith("http"):
            return val
    val = (os.environ.get("NEXT_PUBLIC_R2_BASE_URL") or "").strip().rstrip("/")
    if val.startswith("http"):
        return val
    return "https://pub-9429cde26be84c4c8034f0b5873b9a7d.r2.dev"


def _http_json(url: str) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                # Public R2 rejects Python-urllib's default User-Agent (HTTP 403).
                "User-Agent": "ARIS-ghost-pack/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = int(getattr(resp, "status", 200))
            if status == 404:
                return None
            raw = resp.read()
        payload = json.loads(raw.decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except urllib.error.HTTPError as extra:
        if extra.code == 404:
            return None
        _log.info("ghost-pack HTTP %s for %s: %s", extra.code, url, extra)
        return None
    except Exception as extra:
        _log.info("ghost-pack fetch failed for %s: %s", url, extra)
        return None


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as extra:
        _log.warning("ghost-pack unreadable %s: %s", path, extra)
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    if path.is_file():
        tmp.unlink(missing_ok=True)
        return
    tmp.replace(path)


def load_race_field(
    year: int, round_number: int, *, allow_remote: bool = True
) -> dict[str, Any] | None:
    local = _read_json(local_pack_path(year, round_number, "race_field.json"))
    if local is not None:
        return local
    if not _remote_allowed(allow_remote):
        return None
    base = _r2_public_base()
    if not base:
        return None
    return _http_json(f"{base}/replay/{int(year)}/{int(round_number)}/race_field.json")


def load_baked_ghost(
    year: int, round_number: int, driver: str, *, allow_remote: bool = True
) -> dict[str, Any] | None:
    code = str(driver).upper()
    local = _read_json(local_pack_path(year, round_number, f"ghost_{code}.json"))
    if local is not None:
        return local
    if not _remote_allowed(allow_remote):
        return None
    base = _r2_public_base()
    if not base:
        return None
    return _http_json(f"{base}/replay/{int(year)}/{int(round_number)}/ghost_{code}.json")


def _driver_entry(field: dict[str, Any], code: str) -> dict[str, Any] | None:
    for row in field.get("drivers") or []:
        if str(row.get("code") or "").upper() == code:
            return row if isinstance(row, dict) else None
    return None


def _focus_laps(field: dict[str, Any], code: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in field.get("laps") or []:
        if str(row.get("driver") or "").upper() != code:
            continue
        if isinstance(row, dict):
            out.append(row)
    out.sort(key=lambda r: int(r.get("lap") or 0))
    return out


def assert_driver_raced(field: dict[str, Any], driver: str) -> list[dict[str, Any]]:
    """Validate the driver started this race and has classified laps.

    Returns the driver's lap rows. Raises DriverDidNotRace or GhostDataGap.
    """
    code = str(driver).upper()
    if not code:
        raise DriverDidNotRace("No driver selected")
    entry = _driver_entry(field, code)
    laps = _focus_laps(field, code)
    dns = bool(entry.get("is_dns")) if entry else False
    if dns and not laps:
        raise DriverDidNotRace(f"{code} did not start this race")
    if not entry and not laps:
        raise DriverDidNotRace(f"{code} did not race this weekend")
    if not laps:
        raise GhostDataGap(
            f"No classified laps for {code} this weekend — cannot compute a ghost"
        )
    has_time = any(row.get("lap_time_s") for row in laps)
    if not has_time:
        raise GhostDataGap(
            f"Lap times for {code} are missing this weekend — cannot compute a ghost"
        )
    return laps


def _country_for(year: int, round_number: int, field: dict[str, Any]) -> str:
    try:
        from backend.calendar import get_round

        country = str(get_round(int(year), int(round_number)).country or "")
        if country:
            return country
    except Exception:
        pass
    meta = field.get("meta") or {}
    return str(meta.get("circuit_name") or "Unknown")


def compute_ghost(
    year: int,
    round_number: int,
    driver: str,
    field: dict[str, Any] | None = None,
    *,
    recommend_fn: Any | None = None,
) -> dict[str, Any]:
    """Build the R2 ``ghost_{DRIVER}.json`` payload from a race pack.

    Callable from the offline baker and the live endpoint. Does not write files.
    ``recommend_fn`` is a test seam; production uses ``aris.recommend.recommend``.
    """
    from aris.ghost import (
        field_cumulative_by_lap,
        field_gap_snapshot_by_lap,
        pick_strategy_recommendation,
        plan_from_pits,
        r2_ghost_tick,
        schedule_from_recommendation,
        score_parallel_ghost,
    )
    from aris.physics.tires import normalize_compound
    from aris.state import RaceState

    if field is None:
        field = load_race_field(year, round_number)
        if field is None:
            raise RacePackUnavailable()

    code = str(driver).upper()
    focus_laps = assert_driver_raced(field, code)
    start_compound = normalize_compound(str(focus_laps[0].get("compound") or "MEDIUM"))
    total = int((field.get("meta") or {}).get("total_laps") or len(focus_laps) or 1)
    country = _country_for(year, round_number, field)

    template = RaceState(
        session_id=int((field.get("meta") or {}).get("session_key") or 0),
        driver_id=0,
        driver_code=code,
        driver_name=code,
        year=int(year),
        round_no=int(round_number),
        country=country or "Unknown",
        lap_number=1,
        compound=start_compound,
        tyre_life=1,
        fuel_kg=110.0,
        laps_remaining=max(0, total - 1),
        total_laps=total,
        position=int(focus_laps[0].get("position") or 1),
        track_status=str(focus_laps[0].get("track_status") or "1"),
    )

    rec_fn = recommend_fn
    if rec_fn is None:
        from aris.recommend import recommend as rec_fn

    card = None
    try:
        for decision_lap in (1, 2):
            try:
                state = template.model_copy(update={"lap_number": decision_lap})
                rec = rec_fn(state, top_k=3, mc_draws=0)
                card = pick_strategy_recommendation(rec)
                if card and str(card.get("label") or "") != "STRATEGY_RESET":
                    break
            except Exception as extra:
                _log.info("recommend() lap %s failed for %s: %s", decision_lap, code, extra)
                card = None
    except Exception as extra:
        raise GhostDataGap(f"Could not compute a strategy for {code}: {extra}") from extra

    if card:
        plan = schedule_from_recommendation(card, start_compound=start_compound, lap_number=1)
        label = str(card.get("label") or "")
    else:
        plan = plan_from_pits([], [], start_compound, label="STAY_OUT")
        label = "STAY_OUT"

    lap_rows = []
    for row in focus_laps:
        lap_rows.append(
            {
                "lap_number": int(row["lap"]),
                "compound": str(row.get("compound") or start_compound),
                "tyre_life": int(row.get("tyre_life") or 1),
                "real_action": (
                    f"PIT_NOW_{row.get('compound') or 'HARD'}"
                    if row.get("pit_this_lap")
                    else "STAY_OUT"
                ),
                "position": int(row.get("position") or 10),
                "lap_time_s": row.get("lap_time_s"),
                "track_status": str(row.get("track_status") or "1"),
                "gap_to_leader_s": row.get("gap_to_leader_s"),
            }
        )
    times: dict[str, dict[int, float]] = {}
    for row in field.get("laps") or []:
        t = row.get("lap_time_s")
        if not t:
            continue
        times.setdefault(str(row["driver"]).upper(), {})[int(row["lap"])] = float(t)
    field_cum = field_cumulative_by_lap(times)
    field_gap = field_gap_snapshot_by_lap(field.get("laps") or [])
    typical = 90.0
    raw_times = [float(r["lap_time_s"]) for r in focus_laps if r.get("lap_time_s")]
    if raw_times:
        typical = float(sorted(raw_times)[len(raw_times) // 2])
        if typical < 30:
            typical = 90.0
    try:
        ticks_map = score_parallel_ghost(
            template_state=template,
            lap_rows=lap_rows,
            plan=plan,
            typical_lap_s=typical,
            field_cum_by_lap=field_cum,
            field_gap_by_lap=field_gap,
        )
    except Exception as extra:
        raise GhostDataGap(f"Ghost simulation failed for {code}: {extra}") from extra

    ticks = [
        r2_ghost_tick(int(lap), tick, plan.pit_laps)
        for lap, tick in sorted(ticks_map.items())
        if isinstance(tick, dict)
    ]
    if not ticks:
        raise GhostDataGap(f"Ghost simulation produced no laps for {code}")
    last = next((ticks_map[k] for k in sorted(ticks_map, reverse=True) if ticks_map[k]), {}) or {}
    return {
        "driver": code,
        "strategy": {
            "pit_laps": list(plan.pit_laps),
            "compounds": list(plan.pit_compounds),
            "label": label,
        },
        "ticks": ticks,
        "outcome": {
            "aris_action": last.get("aris_action") or label,
            "real_action": last.get("real_action") or "STAY_OUT",
            "verdict": last.get("outcome"),
        },
    }


def _lock_for(key: tuple[int, int, str]) -> threading.Lock:
    with _CACHE_LOCK:
        lock = _COMPUTE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _COMPUTE_LOCKS[key] = lock
        return lock


def get_or_compute_ghost(
    year: int,
    round_number: int,
    driver: str,
    *,
    allow_remote: bool = True,
    compute: bool = True,
    recommend_fn: Any | None = None,
) -> dict[str, Any]:
    """Serve baked ghost if present; otherwise compute and persist.

    Never overwrites an existing ``ghost_{DRIVER}.json``.
    """
    y, rnd = int(year), int(round_number)
    code = str(driver).upper()
    key = (y, rnd, code)
    with _CACHE_LOCK:
        hit = _FILE_CACHE.get(key)
    if hit is not None:
        return dict(hit)

    lock = _lock_for(key)
    with lock:
        with _CACHE_LOCK:
            hit = _FILE_CACHE.get(key)
        if hit is not None:
            return dict(hit)

        baked = load_baked_ghost(y, rnd, code, allow_remote=allow_remote)
        if baked is not None:
            out = dict(baked)
            out["source"] = "baked"
            with _CACHE_LOCK:
                _FILE_CACHE[key] = out
            return dict(out)

        field = load_race_field(y, rnd, allow_remote=allow_remote)
        if field is None:
            raise RacePackUnavailable()

        assert_driver_raced(field, code)
        if not compute:
            raise GhostDataGap(f"No baked ghost for {code} and compute is disabled")

        ghost = compute_ghost(y, rnd, code, field, recommend_fn=recommend_fn)
        path = local_pack_path(y, rnd, f"ghost_{code}.json")
        try:
            _write_json(path, ghost)
        except OSError as extra:
            _log.warning("could not persist ghost %s: %s", path, extra)

        out = dict(ghost)
        out["source"] = "computed"
        with _CACHE_LOCK:
            _FILE_CACHE[key] = out
        return dict(out)
