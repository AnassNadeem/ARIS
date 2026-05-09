"""Pre-warm the FastF1 cache for ARIS Phase 0.

Runs `session.load()` once for each session in SESSIONS so the data is
pickled to disk under `fastf1_cache/`. Subsequent reads (from notebooks,
training scripts, the dashboard) are then near-instant.

Run once, ideally overnight. Safe to re-run — already-cached sessions
return in ~1 second.
"""

from __future__ import annotations

import time
from pathlib import Path

import fastf1

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "fastf1_cache"
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

# (year, event-name, session-type). Event name is the GP location/country
# as FastF1 fuzzy-matches it. Session type: R=Race, Q=Quali, S=Sprint, FPn.
SESSIONS: list[tuple[int, str, str]] = [
    (2024, "Bahrain", "R"),
    (2024, "Saudi Arabia", "R"),
    (2024, "Australia", "R"),
    (2024, "Japan", "R"),
    (2024, "Miami", "R"),
    (2023, "Bahrain", "R"),
    (2023, "Belgium", "R"),       # Spa
    (2023, "Abu Dhabi", "R"),
]


def prewarm_one(year: int, gp: str, session_type: str) -> bool:
    label = f"{year} {gp:<14} {session_type}"
    print(f"[ ] {label} ...", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        s = fastf1.get_session(year, gp, session_type)
        s.load(laps=True, telemetry=True, weather=True, messages=False)
        n_laps = len(s.laps) if s.laps is not None else 0
        n_drivers = s.laps["Driver"].nunique() if n_laps else 0
        print(f"OK  ({n_drivers} drivers, {n_laps} laps, {time.perf_counter() - t0:5.1f}s)")
        return True
    except Exception as exc:
        print(f"FAIL after {time.perf_counter() - t0:5.1f}s -> {exc!r}")
        return False


def main() -> None:
    print(f"Cache dir: {CACHE_DIR}")
    print(f"Pre-warming {len(SESSIONS)} sessions...\n")
    t0 = time.perf_counter()
    results = [prewarm_one(y, gp, st) for (y, gp, st) in SESSIONS]
    ok, total = sum(results), len(results)
    print(f"\n{ok}/{total} sessions cached in {time.perf_counter() - t0:.1f}s")
    if ok < total:
        print("Re-run the script to retry the failed sessions; the cached ones will skip fast.")


if __name__ == "__main__":
    main()
