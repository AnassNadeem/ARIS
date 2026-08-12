#!/usr/bin/env python3
"""Ingest a full race weekend for one (year, round/event).

Supports conventional and sprint formats:

  conventional: FP1, FP2, FP3, Q, R
  sprint:       FP1, SQ, S, Q, R   (no FP2/FP3)

Usage:
    python scripts/ingest_weekend.py 2025 Bahrain
    python scripts/ingest_weekend.py 2024 Austria --sprint
    python scripts/ingest_weekend.py 2026 Netherlands --auto
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401 — requests/forward-ref shim before fastf1
import fastf1  # noqa: E402

from aris.io.ingest import ingest_session  # noqa: E402

CONVENTIONAL_SESSIONS = ("FP1", "FP2", "FP3", "Q", "R")
# 2023+ / 2026 Dutch-style sprint: FP1 → Sprint Qualifying → Sprint → Qualifying → Race
SPRINT_SESSIONS = ("FP1", "SQ", "S", "Q", "R")


def _detect_sprint(year: int, event: int | str) -> bool:
    """True when FastF1 says this event has no FP2 (sprint weekend)."""
    try:
        # Probe FP2 — sprint weekends raise ValueError for missing session type.
        fastf1.get_session(year, event, "FP2")
        return False
    except ValueError as exc:
        msg = str(exc).lower()
        if "does not exist" in msg or "invalid session" in msg:
            return True
        raise
    except Exception:
        # Schedule/backend blips — fall back to conventional list with soft-fail.
        return False


def _sessions_for(year: int, event: int | str, mode: str) -> tuple[str, ...]:
    if mode == "sprint":
        return SPRINT_SESSIONS
    if mode == "conventional":
        return CONVENTIONAL_SESSIONS
    # auto
    return SPRINT_SESSIONS if _detect_sprint(year, event) else CONVENTIONAL_SESSIONS


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a full race weekend")
    parser.add_argument("year", type=int)
    parser.add_argument("event", help="Round number or GP name (e.g. Netherlands)")
    parser.add_argument(
        "--telemetry",
        action="store_true",
        help="Include telemetry for race session only",
    )
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument(
        "--sprint",
        action="store_true",
        help="Sprint format: FP1, SQ, S, Q, R (no FP2/FP3)",
    )
    fmt.add_argument(
        "--conventional",
        action="store_true",
        help="Conventional format: FP1, FP2, FP3, Q, R",
    )
    fmt.add_argument(
        "--auto",
        action="store_true",
        help="Detect sprint vs conventional via FastF1 (default if no flag)",
    )
    args = parser.parse_args()

    event: int | str
    if str(args.event).isdigit():
        event = int(args.event)
    else:
        event = str(args.event)

    if args.sprint:
        mode = "sprint"
    elif args.conventional:
        mode = "conventional"
    else:
        mode = "auto"

    sessions = _sessions_for(args.year, event, mode)
    print(f"Weekend mode={mode} sessions={list(sessions)}", flush=True)

    totals: dict[str, int] = {"sessions": 0, "drivers": 0, "laps": 0}
    for session_type in sessions:
        print(f"Ingesting {args.year} {event} {session_type} ...", flush=True)
        try:
            include_telemetry = args.telemetry and session_type == "R"
            counts = ingest_session(
                args.year, event, session_type, include_telemetry=include_telemetry
            )
            for key, val in counts.items():
                totals[key] = totals.get(key, 0) + val
            print(f"  -> {counts}")
        except Exception as exc:
            print(f"  FAIL: {exc!r}")
            # Soft-fail practice/sprint/quali so a missing FP2 on a mis-detected
            # weekend does not abort; Race failure is fatal.
            if session_type == "R":
                raise

    print(f"\nWeekend totals: {totals}")


if __name__ == "__main__":
    main()
