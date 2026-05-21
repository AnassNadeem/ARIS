"""CLI: ingest every race (session type R) of a season into Postgres.

    python scripts/ingest_season.py 2024

Iterates the season's FastF1 event schedule and ingests each round's race.
The ingest is idempotent, so re-running the whole season is a no-op. A
per-race failure — a round not in the local FastF1 cache and unreachable, or
a malformed session — is logged and skipped, never fatal: one network hiccup
must not abort the rest of the season.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `aris` importable when the package is not installed into the environment.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import fastf1  # noqa: E402

from aris.io.ingest import ingest_session  # noqa: E402

CACHE = ROOT / "fastf1_cache"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: ingest_season.py <year>", file=sys.stderr)
        return 2

    year = int(argv[0])
    CACHE.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE))
    schedule = fastf1.get_event_schedule(year, include_testing=False)

    ok = failed = total_laps = 0
    for _, event in schedule.iterrows():
        round_no = int(event["RoundNumber"])
        name = str(event["EventName"])
        try:
            counts = ingest_session(year, round_no, "R")
        except Exception as exc:  # one race must not abort the rest of the season
            print(f"[fail] {year} R{round_no:<2} {name}: {type(exc).__name__}: {exc}")
            failed += 1
            continue
        ok += 1
        total_laps += counts["laps"]
        print(
            f"[ok]   {year} R{round_no:<2} {name}: +{counts['laps']} laps "
            f"(+{counts['sessions']} session, +{counts['drivers']} drivers)"
        )

    print(f"\nseason {year}: {ok} ingested, {failed} failed, +{total_laps} laps total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
