#!/usr/bin/env python
"""Prebuild FastF1 replay packs into diskcache for instant /replay loads.

Writes the same keys the backend reads:

    replay_pack_v1:{year}:{round}:{session}

Usage (from repo root, venv on, PYTHONPATH set):

    python scripts/prebuild_replay_packs.py
    python scripts/prebuild_replay_packs.py --dry-run
    python scripts/prebuild_replay_packs.py --year 2025 --round 15
    python scripts/prebuild_replay_packs.py --force --year 2024
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

DEFAULT_YEARS = (2024, 2025, 2026)
SESSION_TYPE = "R"

_log = logging.getLogger("aris.prebuild")


@dataclass(frozen=True)
class PrebuildJob:
    year: int
    round_number: int
    session_type: str
    name: str
    status: str


def _label(job: PrebuildJob) -> str:
    return f"{job.year} R{job.round_number} {job.session_type}"


def iter_prebuild_jobs(
    years: tuple[int, ...] = DEFAULT_YEARS,
    *,
    round_number: int | None = None,
    session_type: str = SESSION_TYPE,
) -> list[PrebuildJob]:
    """Calendar R sessions for 2024–2026. Upcoming / live / cancelled are included so the CLI can skip them with a reason."""
    from backend.calendar import ALLOWED_REPLAY_YEARS, get_calendar, get_round_sessions

    jobs: list[PrebuildJob] = []
    stype = "R"
    for year in years:
        if int(year) not in ALLOWED_REPLAY_YEARS:
            _log.info("Replay request for year %s — blocked (not in 2024–2026)", year)
            continue
        cal = get_calendar(int(year))
        for rnd in cal.rounds:
            if round_number is not None and int(rnd.round_number) != int(round_number):
                continue
            name = str(rnd.name or rnd.circuit_name or f"R{rnd.round_number}")
            if str(rnd.status or "").upper() == "CANCELLED":
                jobs.append(
                    PrebuildJob(int(year), int(rnd.round_number), stype, name, "CANCELLED")
                )
                continue
            try:
                weekend = get_round_sessions(int(year), int(rnd.round_number))
            except Exception as exc:
                jobs.append(
                    PrebuildJob(int(year), int(rnd.round_number), stype, name, f"ERROR:{exc}")
                )
                continue
            match = next((s for s in weekend.sessions if s.session_type == stype), None)
            status = str(match.status) if match is not None else str(rnd.status or "UPCOMING")
            jobs.append(PrebuildJob(int(year), int(rnd.round_number), stype, name, status))
    return jobs


def _pack_is_full_gps(pack: dict[str, Any] | None) -> bool:
    from backend.live import _ff1_pack_ready, replay_pack_stage

    return bool(pack) and replay_pack_stage(pack) == "full" and _ff1_pack_ready(pack)


async def prebuild_one(job: PrebuildJob, *, force: bool) -> str:
    """Build one pack via the same staged FastF1 path as the API. Returns a status verb."""
    from backend.cache import enable_fastf1_cache
    from backend.live import (
        _REPLAY_PACKS,
        _SESSION_HOURS,
        _calendar_session_status,
        _ff1_pack_ready,
        _new_replay_pack,
        _normalize_session_type,
        _staged_fastf1_fill,
        calendar_session_window,
        hydrate_replay_pack_cache,
        invalidate_replay_pack,
        replay_pack_disk_key,
        replay_pack_stage,
        save_replay_pack_disk,
        synthetic_session_key,
    )

    enable_fastf1_cache()
    mapped = _normalize_session_type(job.session_type)
    session_key = synthetic_session_key(job.year, job.round_number, mapped)
    cache_key = replay_pack_disk_key(session_key, job.year, job.round_number, mapped)

    if force:
        invalidate_replay_pack(session_key)
        _REPLAY_PACKS.pop(session_key, None)

    cached, memory_hit, disk_hit = hydrate_replay_pack_cache(
        session_key, job.year, job.round_number, mapped, log_hits=True
    )
    if not force and _pack_is_full_gps(cached):
        print(
            f"Skipped {_label(job)} (already cached) key={cache_key} "
            f"memory_hit={memory_hit} disk_hit={disk_hit}",
            flush=True,
        )
        return "cached"

    start, end = calendar_session_window(job.year, job.round_number, mapped)
    if end is None and start is not None:
        end = start + timedelta(hours=_SESSION_HOURS.get(mapped, 1.5))
    if cached is None or not cached.get("laps"):
        pack = _new_replay_pack(session_key, job.year, job.round_number, mapped, start, end)
        pack["session_status"] = (
            _calendar_session_status(job.year, job.round_number, mapped) or "COMPLETED"
        )
        _REPLAY_PACKS[session_key] = pack
    else:
        pack = cached
        pack["session_status"] = pack.get("session_status") or "COMPLETED"

    t0 = time.monotonic()
    print(f"Building {_label(job)} ({job.name}) key={cache_key} …", flush=True)
    pack = await _staged_fastf1_fill(pack, session_key)
    pack = _REPLAY_PACKS.get(session_key) or pack
    elapsed = time.monotonic() - t0

    if not _ff1_pack_ready(pack) or not pack.get("laps"):
        stage = replay_pack_stage(pack)
        print(
            f"Failed {_label(job)} stage={stage} laps={len(pack.get('laps') or [])} "
            f"in {elapsed:.1f}s (FastF1 GPS/laps missing)",
            flush=True,
        )
        return "failed"

    saved = save_replay_pack_disk(session_key, pack)
    print(
        f"Prebuilt {_label(job)} stage={replay_pack_stage(pack)} "
        f"laps={len(pack.get('laps') or [])} "
        f"gps_drivers={len((pack.get('ff1') or {}).get('pos_samples') or {})} "
        f"saved={saved} in {elapsed:.1f}s key={cache_key}",
        flush=True,
    )
    return "built" if saved else "failed"


async def run_prebuild(jobs: list[PrebuildJob], *, force: bool, dry_run: bool) -> int:
    built = cached = skipped = failed = 0
    for job in jobs:
        if job.status != "COMPLETED":
            reason = job.status.lower() if job.status else "not completed"
            print(f"Skipped {_label(job)} ({reason})", flush=True)
            skipped += 1
            continue
        if dry_run:
            print(f"Would prebuild {_label(job)} ({job.name})", flush=True)
            skipped += 1
            continue
        try:
            result = await prebuild_one(job, force=force)
        except Exception as exc:
            print(f"Failed {_label(job)}: {exc}", flush=True)
            _log.exception("prebuild failed %s", _label(job))
            failed += 1
            continue
        if result == "built":
            built += 1
        elif result == "cached":
            cached += 1
        else:
            failed += 1
    print(
        f"\nDone. built={built} cached={cached} skipped={skipped} failed={failed} total={len(jobs)}",
        flush=True,
    )
    return 1 if failed else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="List sessions without building.")
    parser.add_argument("--year", type=int, action="append", help="Limit to this year (repeatable).")
    parser.add_argument("--round", type=int, dest="round_number", help="Limit to this round number.")
    parser.add_argument(
        "--session",
        default=SESSION_TYPE,
        help="Ignored: Replay/ARIS packs are Race-only (R).",
    )
    parser.add_argument("--force", action="store_true", help="Rebuild even if diskcache already has a full pack.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    years = tuple(args.year) if args.year else DEFAULT_YEARS
    stype = str(session_type or "R").upper()
    if stype != "R":
        print(
            f"Replay/ARIS packs are Race-only; ignoring --session {stype}",
            flush=True,
        )
        stype = SESSION_TYPE
    jobs = iter_prebuild_jobs(years, round_number=args.round_number, session_type=stype)
    if not jobs:
        print("No calendar sessions matched.", flush=True)
        return 1
    print(f"Jobs: {len(jobs)} years={list(years)} session={args.session} dry_run={args.dry_run}", flush=True)
    return asyncio.run(run_prebuild(jobs, force=args.force, dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
