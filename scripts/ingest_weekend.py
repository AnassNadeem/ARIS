#!/usr/bin/env python3
"""Ingest a full race weekend (FP1-3, Q, R) for one (year, round/event).

Usage:
    python scripts/ingest_weekend.py 2025 Bahrain
    python scripts/ingest_weekend.py 2024 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from aris.io.ingest import ingest_session  # noqa: E402

WEEKEND_SESSIONS = ("FP1", "FP2", "FP3", "Q", "R")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest FP1-3, Q, R for one weekend")
    parser.add_argument("year", type=int)
    parser.add_argument("event", help="Round number or GP name (e.g. Bahrain)")
    parser.add_argument(
        "--telemetry",
        action="store_true",
        help="Include telemetry for race session only",
    )
    args = parser.parse_args()

    event: int | str
    if str(args.event).isdigit():
        event = int(args.event)
    else:
        event = str(args.event)

    totals: dict[str, int] = {"sessions": 0, "drivers": 0, "laps": 0}
    for session_type in WEEKEND_SESSIONS:
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
            if session_type == "R":
                raise

    print(f"\nWeekend totals: {totals}")


if __name__ == "__main__":
    main()
