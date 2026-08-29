"""Build the SC/VSC risk training table from FastF1 2024–2025 Race sessions.

Also precomputes per-circuit historical SC rates from 2022–2024.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.eval.backtest import BACKTEST_GPS_2025  # noqa: E402
from aris.eval.laptime import HELD_OUT_RACES  # noqa: E402
from aris.io.fastf1_session import DEFAULT_CACHE, load_race_session  # noqa: E402

import fastf1  # noqa: E402

fastf1.Cache.enable_cache(str(DEFAULT_CACHE))
from aris.risk.sc_risk_model import (  # noqa: E402
    DATASET_PATH,
    RATES_PATH,
    circuit_key,
    extras_from_fastf1,
    label_windows,
    sc_event_laps,
    train_and_evaluate,
    weather_at_lap,
)

HIST_YEARS = (2022, 2023, 2024)


def _gps_for_year(year: int) -> list[str]:
    if year == 2024:
        return [gp for y, gp in HELD_OUT_RACES if y == 2024]
    if year == 2025:
        return list(BACKTEST_GPS_2025)
    import fastf1

    schedule = fastf1.get_event_schedule(year, include_testing=False)
    names: list[str] = []
    for _, row in schedule.iterrows():
        name = str(row.get("EventName") or "")
        if name:
            names.append(name)
    return names


def _circuit_from_session(session) -> str:
    event = session.event
    location = str(event.get("Location") or "")
    country = str(event.get("Country") or "")
    name = str(event.get("EventName") or "")
    return circuit_key(location or country or name)


def _load(year: int, gp: str, *, laps: bool, weather: bool, messages: bool):
    return load_race_session(
        year,
        gp,
        laps=laps,
        weather=weather,
        telemetry=False,
        messages=messages,
    )


def compute_historical_rates() -> dict[str, float]:
    """Fraction of 2022–2024 races at each circuit with ≥1 SC/VSC deployment."""
    hits: dict[str, list[int]] = {}
    for year in HIST_YEARS:
        for gp in _gps_for_year(year):
            try:
                session = _load(year, gp, laps=False, weather=False, messages=True)
            except Exception as exc:
                print(f"  HIST skip {year} {gp}: {exc}", flush=True)
                continue
            circuit = _circuit_from_session(session)
            rcm = getattr(session, "race_control_messages", None)
            flagged = 1 if sc_event_laps(rcm) else 0
            hits.setdefault(circuit, []).append(flagged)
            print(
                f"  HIST {year} {gp:20s} {circuit:16s} sc={flagged}",
                flush=True,
            )
    rates = {k: float(sum(v) / len(v)) for k, v in hits.items() if v}
    rates["_mean"] = float(sum(rates.values()) / len(rates)) if rates else 0.5
    RATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RATES_PATH.write_text(json.dumps(rates, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {RATES_PATH} ({len(rates) - 1} circuits)", flush=True)
    return rates


def _rows_for_session(year: int, gp: str, rates: dict[str, float]) -> list[dict]:
    session = _load(year, gp, laps=True, weather=True, messages=True)
    laps = session.laps
    if laps is None or laps.empty:
        return []
    rcm = getattr(session, "race_control_messages", None)
    weather = getattr(session, "weather_data", None)
    results = getattr(session, "results", None)
    sc_laps = sc_event_laps(rcm)
    circuit = _circuit_from_session(session)
    total_laps = int(laps["LapNumber"].max())
    hist = float(rates.get(circuit, rates.get("_mean", 0.5)))

    rows: list[dict] = []
    for lap_number in range(1, total_laps + 1):
        at_lap = laps[laps["LapNumber"] == lap_number]
        lap_time = None
        if not at_lap.empty and "Time" in at_lap.columns:
            lap_time = at_lap["Time"].dropna()
            lap_time = lap_time.iloc[0] if not lap_time.empty else None
        rain, track_temp = weather_at_lap(weather, lap_time)
        extras = extras_from_fastf1(laps, lap_number, rcm=rcm, results=results)
        y5, y10 = label_windows(lap_number, sc_laps)
        rows.append(
            {
                "year": year,
                "gp": gp,
                "circuit_id": circuit,
                "lap_number": lap_number,
                "total_laps": total_laps,
                "race_frac": lap_number / max(total_laps, 1),
                "rain_flag": 1.0 if rain else 0.0,
                "track_temp_c": float(track_temp) if track_temp is not None else 30.0,
                "retirements_last_5_laps": extras["retirements_last_5_laps"],
                "yellow_flags_last_3_laps": extras["yellow_flags_last_3_laps"],
                "field_density": extras["field_density"],
                "historical_sc_rate": hist,
                "sc_in_next_5": y5,
                "sc_in_next_10": y10,
            }
        )
    print(
        f"  {year} {gp:20s} {circuit:16s} laps={total_laps} "
        f"sc_laps={sorted(sc_laps) or '-'} pos5={sum(r['sc_in_next_5'] for r in rows)}",
        flush=True,
    )
    return rows


def build_dataset(years: list[int], rates: dict[str, float]) -> pd.DataFrame:
    rows: list[dict] = []
    for year in years:
        for gp in _gps_for_year(year):
            try:
                rows.extend(_rows_for_session(year, gp, rates))
            except Exception as exc:
                print(f"  DATA skip {year} {gp}: {exc}", flush=True)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SC/VSC risk dataset")
    parser.add_argument("--years", type=int, nargs="+", default=[2024, 2025])
    parser.add_argument("--skip-hist", action="store_true")
    parser.add_argument("--skip-train", action="store_true")
    args = parser.parse_args()

    if args.skip_hist and RATES_PATH.is_file():
        rates = json.loads(RATES_PATH.read_text(encoding="utf-8"))
        print(f"loaded existing rates ({len(rates) - 1} circuits)", flush=True)
    else:
        print("computing 2022–2024 historical SC rates", flush=True)
        rates = compute_historical_rates()

    print(f"building dataset years={args.years}", flush=True)
    df = build_dataset(list(args.years), rates)
    if df.empty:
        print("no rows built")
        return 1
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATASET_PATH, index=False)
    n = len(df)
    print(f"wrote {DATASET_PATH} n={n}", flush=True)
    print(
        f"class balance sc_in_next_5={df['sc_in_next_5'].mean():.3f} "
        f"({int(df['sc_in_next_5'].sum())}/{n})  "
        f"sc_in_next_10={df['sc_in_next_10'].mean():.3f} "
        f"({int(df['sc_in_next_10'].sum())}/{n})",
        flush=True,
    )
    for year, grp in df.groupby("year"):
        print(
            f"  {year}: n={len(grp)} pos5={grp['sc_in_next_5'].mean():.3f} "
            f"pos10={grp['sc_in_next_10'].mean():.3f}",
            flush=True,
        )

    if not args.skip_train:
        print("training logistic models (2024 train / 2025 test)", flush=True)
        metrics = train_and_evaluate(df)
        print(json.dumps(metrics, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
