"""Rank 1: measure SC/VSC net pit-loss ratios vs YAML green (2018–2025).

Writes ``results/t2b/sc_vsc_pit_loss.json``. Does not change default 0.35/0.55.

Flagged replay (opt-in, after this table exists)::

    set ARIS_USE_MEASURED_SC_PIT_LOSS=1
    python scripts/backtest.py --years 2024 2025 --out-dir results/t2b/backtest

Kill gate: must not lose stay-out 0.276 or G1.5 0.322; Zandvoort identity
must not move with the flag off. No Poisson SC, no ghost car.

  python scripts/_t2b_sc_pit_loss.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "results" / "t2b" / "sc_vsc_pit_loss.json"
_YEARS = range(2018, 2026)


def main() -> int:
    from aris.eval.sc_pit_loss import (
        circuit_key_for,
        measure_sc_vsc_pit_events,
        summarize_events,
    )
    from aris.io import db
    from aris.tracks import load_track_config

    if not os.getenv("ARIS_DB_URL"):
        print("SKIP: ARIS_DB_URL unset - no measurement table written", flush=True)
        return 0

    try:
        seasons = db.fetch_seasons()
    except Exception as exc:
        print(f"SKIP: cannot reach DB ({exc})", flush=True)
        return 0

    years = [y for y in seasons if y in _YEARS]
    if not years:
        print("SKIP: no 2018-2025 races in DB", flush=True)
        return 0

    events: list[dict] = []
    n_races = 0
    n_skip_wet = 0
    for year in sorted(years):
        try:
            races = db.fetch_races(year)
        except Exception as exc:
            print(f"  SKIP {year}: {exc}", flush=True)
            continue
        if races.empty:
            continue
        for _, race in races.sort_values("round_no").iterrows():
            sid = int(race["session_id"])
            country = str(race["country"])
            round_no = int(race["round_no"])
            weather = db.fetch_session_weather(sid) or {}
            rainfall = bool(weather.get("rainfall"))
            if rainfall:
                n_skip_wet += 1
                continue
            field = db.fetch_all_laps(sid)
            if field.empty:
                continue
            track = load_track_config(country, year=year, round_no=round_no)
            key = circuit_key_for(country)
            race_events = measure_sc_vsc_pit_events(
                field,
                green_pit_loss_s=float(track.pit_loss_s),
                circuit_key=key,
                year=year,
                gp=country,
                rainfall=False,
            )
            events.extend(race_events)
            n_races += 1
            if race_events:
                print(
                    f"  {year} R{round_no} {country}: {len(race_events)} SC/VSC pits",
                    flush=True,
                )

    payload = summarize_events(events)
    payload["meta"]["n_dry_races"] = n_races
    payload["meta"]["n_skipped_rainfall"] = n_skip_wet
    payload["meta"]["years_requested"] = list(_YEARS)
    payload["meta"]["years_in_db"] = years
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    g = payload["global"]
    print(
        f"Wrote {_OUT}  n_events={payload['n_events']}  "
        f"SC median={g['sc']} (n={g['n_sc']})  VSC median={g['vsc']} (n={g['n_vsc']})",
        flush=True,
    )
    print("Heilmeier Table 6 is in the JSON beside this table -- do not average.", flush=True)
    print(
        "Default path keeps 0.35/0.55. Flagged replay: "
        "ARIS_USE_MEASURED_SC_PIT_LOSS=1 python scripts/backtest.py "
        "--years 2024 2025 --out-dir results/t2b/backtest",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
