"""Rank 3: realized undercut / first-flying-lap rejoin table (2024–2025 green pits).

Does not change T2-D defaults. Does not ship dirty-air +0.6..+1.2 s.

  python scripts/_undercut_rejoin.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "results" / "undercut" / "rejoin.json"


def main() -> int:
    from aris.eval.backtest import resolve_calendar
    from aris.eval.sc_pit_loss import circuit_key_for
    from aris.eval.undercut_rejoin import find_undercut_attempts, summarize_attempts
    from aris.io import db

    if not os.getenv("ARIS_DB_URL"):
        print("SKIP: ARIS_DB_URL unset - no undercut table written", flush=True)
        return 0

    attempts: list[dict] = []
    for year in (2024, 2025):
        try:
            calendar = resolve_calendar(year)
        except Exception as exc:
            print(f"  SKIP {year}: {exc}", flush=True)
            continue
        for meta in calendar:
            sid = int(meta["session_id"])
            country = str(meta["country"])
            weather = db.fetch_session_weather(sid) or {}
            if weather.get("rainfall"):
                continue
            field = db.fetch_all_laps(sid)
            if field.empty:
                continue
            key = circuit_key_for(country)
            found = find_undercut_attempts(
                field, circuit=key, year=year, gp=str(meta["gp"])
            )
            attempts.extend(found)
            print(
                f"  {year} {meta['gp']}: {len(found)} green undercut attempts",
                flush=True,
            )

    summary = summarize_attempts(attempts)
    payload = {"summary": summary, "attempts": attempts}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(
        f"Wrote {_OUT}  n={summary['n_attempts']} swapped={summary['n_swapped']}",
        flush=True,
    )
    print("T2-D (22 s / -0.8 cap) is unchanged. Do not ship +0.6..+1.2.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
