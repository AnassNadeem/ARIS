"""Day 4 cross-check: SQL MA(2) baseline vs the Week 2 pandas baseline.

Runs db/queries/baseline_ma2.sql against Postgres and diffs the per-race MAE
against results/wk2-baseline-mae.csv. A match within float precision proves
the FastF1 -> Postgres ingest neither dropped nor duplicated a lap; a mismatch
means it did, and blocks the Phase 2 deploy until it is found.

    python scripts/baseline_crosscheck.py

Exit code 0 = every race matched; 1 = at least one race is off.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `aris` importable when the package is not installed into the environment.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from aris.io.db import engine  # noqa: E402

QUERY_FILE = ROOT / "db" / "queries" / "baseline_ma2.sql"
WK2_CSV = ROOT / "results" / "wk2-baseline-mae.csv"
TOLERANCE_S = 1e-6  # a microsecond — far below any real lap-time signal

# The 8 Week 2 baseline races mapped to their (year, round_no) in `sessions`.
# Week 2's race_id used the FastF1 event name; the DB keys on round number, so
# the mapping is spelled out explicitly (Miami's country is "United States").
WK2_RACE_TO_SESSION = {
    "2024-Bahrain": (2024, 1),
    "2024-Saudi_Arabia": (2024, 2),
    "2024-Australia": (2024, 3),
    "2024-Japan": (2024, 4),
    "2024-Miami": (2024, 6),
    "2023-Bahrain": (2023, 1),
    "2023-Belgium": (2023, 12),
    "2023-Abu_Dhabi": (2023, 22),
}


def main() -> int:
    sql = QUERY_FILE.read_text(encoding="utf-8")
    with engine().connect() as conn:
        sql_df = pd.read_sql(text(sql), conn)
    sql_by_key = {(int(r.year), int(r.round_no)): r for r in sql_df.itertuples(index=False)}

    wk2 = pd.read_csv(WK2_CSV, comment="#")

    header = (
        f"{'race':22s} {'wk2 MAE':>10s} {'SQL MAE':>10s} {'abs diff':>11s} "
        f"{'wk2 n':>7s} {'SQL n':>7s}  status"
    )
    print(header)
    print("-" * len(header))

    max_diff = 0.0
    failures = 0
    for row in wk2.itertuples(index=False):
        key = WK2_RACE_TO_SESSION.get(row.race_id)
        if key is None:
            print(f"{row.race_id:22s}  no (year, round) mapping -- FAIL")
            failures += 1
            continue
        sql_row = sql_by_key.get(key)
        if sql_row is None:
            print(f"{row.race_id:22s}  not in SQL result (race not ingested?) -- FAIL")
            failures += 1
            continue

        diff = abs(float(sql_row.mae_s) - float(row.mae_s))
        max_diff = max(max_diff, diff)
        laps_match = int(sql_row.n_laps) == int(row.n_laps)
        ok = diff <= TOLERANCE_S and laps_match
        failures += 0 if ok else 1
        print(
            f"{row.race_id:22s} {row.mae_s:10.6f} {float(sql_row.mae_s):10.6f} "
            f"{diff:11.2e} {int(row.n_laps):7d} {int(sql_row.n_laps):7d}  "
            f"{'ok' if ok else 'MISMATCH'}"
        )

    print("-" * len(header))
    print(f"max abs diff = {max_diff:.2e} s   tolerance = {TOLERANCE_S:.0e} s")
    if failures:
        print(
            f"CROSS-CHECK FAILED -- {failures} race(s) off. The ingest dropped or "
            "duplicated laps; do not deploy until resolved."
        )
        return 1
    print("CROSS-CHECK PASSED -- the SQL baseline reproduces the Wk 2 pandas baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
