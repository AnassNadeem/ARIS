#!/usr/bin/env python
"""Time a heavy FastF1 session load (no ARIS pack / OpenF1).

Helps separate FastF1/network slowness from ARIS replay-pack logic.

Usage:
    python scripts/test_fastf1_load.py
    python scripts/test_fastf1_load.py --year 2025 --round 15 --session R
    python scripts/test_fastf1_load.py --full
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Time FastF1 load of a known heavy session.")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--round", type=int, default=15, help="Calendar round (Netherlands 2025 = 15)")
    parser.add_argument("--session", default="R")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also load telemetry/weather/messages (slow). Default is laps-only.",
    )
    args = parser.parse_args()

    from backend.cache import enable_fastf1_cache
    from backend.sessions import _pack_cache_key, build_ff1_replay_assets, load_session

    cache_path = enable_fastf1_cache()
    key = _pack_cache_key(args.year, args.round, args.session)
    print(f"FastF1 cache: {cache_path}", flush=True)
    print(f"key={key} memory_hit=False disk_hit=False (script process starts empty)", flush=True)
    print(
        f"Loading replay session {args.year} R{args.round} {args.session} via FastF1",
        flush=True,
    )

    t0 = time.monotonic()
    sess = load_session(
        args.year,
        args.round,
        args.session,
        telemetry=args.full,
        weather=args.full,
        messages=args.full,
    )
    t_load = time.monotonic() - t0
    laps = getattr(sess, "laps", None)
    n_laps = 0 if laps is None or getattr(laps, "empty", True) else int(len(laps))
    drivers: list[str] = []
    if laps is not None and not getattr(laps, "empty", True) and "Driver" in laps.columns:
        drivers = sorted({str(d) for d in laps["Driver"].dropna().unique()})
    print(f"Metadata loaded in {t_load:.2f}s", flush=True)
    print(f"Basic laps loaded in {t_load:.2f}s", flush=True)
    if args.full:
        print(f"GPS loaded in {t_load:.2f}s", flush=True)
    print(
        f"load_session laps-only={not args.full} in {t_load:.2f}s",
        flush=True,
    )
    print(f"  laps={n_laps} drivers={len(drivers)} {drivers[:8]}{'…' if len(drivers) > 8 else ''}", flush=True)

    t1 = time.monotonic()
    assets = build_ff1_replay_assets(
        args.year,
        args.round,
        args.session,
        None,
        telemetry=args.full,
        weather=args.full,
        messages=args.full,
    )
    t_assets = time.monotonic() - t1
    gps_n = len(assets.get("pos_samples") or {})
    stage = "full" if gps_n else ("minimal" if assets.get("laps") else "metadata")
    print(
        f"build_ff1_replay_assets ok={assets.get('ok')} in {t_assets:.2f}s "
        f"laps={len(assets.get('laps') or [])} "
        f"gps_drivers={gps_n} "
        f"weather={len(assets.get('weather') or [])}",
        flush=True,
    )
    print(f"Replay pack stage = {stage}", flush=True)
    total = time.monotonic() - t0
    print(f"total {total:.2f}s", flush=True)
    return 0 if assets.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
