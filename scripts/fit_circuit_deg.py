"""Fit per-circuit degradation slopes from 2023–2025 FastF1 stint data.

For each circuit in the ingested data:
  1. Extract all clean stint data: (driver, compound, tyre_age, lap_time_delta)
     where lap_time_delta = lap_time - stint_median_lap_time.
  2. Fit a linear regression: lap_time_delta ~ tyre_age (per compound).
  3. Record the slope per (circuit_id, compound).
  4. Output a CSV: circuit_id, compound, fitted_slope, n_obs, r_squared.

DO NOT integrate the results into the model in T7 — data collection only.
Results are saved to data/circuit_deg_priors.csv for use in T8/T9 per-circuit
slope fitting.

Usage:
  python scripts/fit_circuit_deg.py
  python scripts/fit_circuit_deg.py --years 2024 2025
  python scripts/fit_circuit_deg.py --min-obs 20   # require ≥ 20 clean laps per fit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd

_OUT_CSV = _ROOT / "data" / "circuit_deg_priors.csv"

# G1.5 global fallback slopes (do not change — for comparison only).
G1_5_SLOPES: dict[str, float] = {
    "SOFT": 0.08,
    "MEDIUM": 0.05,
    "HARD": 0.03,
}
DRY_COMPOUNDS = frozenset({"SOFT", "MEDIUM", "HARD", "C1", "C2", "C3", "C4", "C5"})

# Normalise C1–C5 to canonical G1.5 compound names.
_COMPOUND_NORM: dict[str, str] = {
    "C1": "HARD",
    "C2": "HARD",
    "C3": "MEDIUM",
    "C4": "MEDIUM",
    "C5": "SOFT",
}


def _normalise_compound(c: str) -> str | None:
    c = str(c).upper().strip()
    if c in G1_5_SLOPES:
        return c
    return _COMPOUND_NORM.get(c)


def _fetch_race_laps(year: int, session_id: int) -> pd.DataFrame:
    """Fetch all laps for one race session from ARIS DB."""
    from aris.io import db
    return db.fetch_all_laps(session_id)


def _clean_stint_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """Filter to clean, non-pitting dry laps for deg slope fitting.

    Removes:
    - Pit-in / pit-out laps (high variance, not representative)
    - SC / VSC laps (lap_time inflated by safety car pace)
    - Laps with missing lap_time_s
    - Laps on wet compounds
    """
    df = laps.copy()
    df = df[df["lap_time_s"].notna() & (df["lap_time_s"] > 0)]

    # Keep only dry compounds.
    df = df[df["compound"].isin(DRY_COMPOUNDS | set(_COMPOUND_NORM))]

    # Drop pit-in and pit-out laps.
    if "pit_in" in df.columns:
        df = df[~df["pit_in"].fillna(False).astype(bool)]
    if "pit_out" in df.columns:
        df = df[~df["pit_out"].fillna(False).astype(bool)]

    # Drop SC/VSC laps (track_status '4', '6', '7').
    if "track_status" in df.columns:
        sc_mask = df["track_status"].astype(str).str.contains("4|6|7", na=False)
        df = df[~sc_mask]

    # Normalise compound.
    df = df.copy()
    df["compound_norm"] = df["compound"].apply(_normalise_compound)
    df = df[df["compound_norm"].notna()]
    return df


def _compute_lap_delta(df: pd.DataFrame) -> pd.DataFrame:
    """Add lap_time_delta = lap_time_s - driver/stint median lap time."""
    if "stint" not in df.columns:
        df = df.copy()
        df["stint"] = 1  # fallback
    grp_cols = [c for c in ["code", "stint", "compound_norm"] if c in df.columns]
    medians = df.groupby(grp_cols)["lap_time_s"].transform("median")
    df = df.copy()
    df["lap_time_delta"] = df["lap_time_s"] - medians
    return df


def _fit_slope(tyre_ages: np.ndarray, deltas: np.ndarray) -> tuple[float, float]:
    """OLS slope for lap_time_delta ~ tyre_life. Returns (slope, r²)."""
    if len(tyre_ages) < 3:
        return float("nan"), float("nan")
    x = tyre_ages.astype(float)
    y = deltas.astype(float)
    x_c = x - x.mean()
    if x_c.std() < 1e-9:
        return float("nan"), float("nan")
    slope = float(np.cov(x_c, y)[0, 1] / np.var(x_c))
    y_pred = slope * x_c
    ss_res = float(np.sum((y - y.mean() - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return slope, r2


def fit_year(year: int, min_obs: int) -> list[dict]:
    """Fit per-circuit slopes for one calendar year.

    Returns list of dicts: {circuit_id, year, compound, fitted_slope,
    g15_slope, slope_delta, n_obs, r_squared}.
    """
    from aris.io import db
    from sqlalchemy import text

    rows = []
    with db.engine().connect() as conn:
        sess_rows = conn.execute(
            text(
                "SELECT session_id, country FROM sessions "
                "WHERE year = :y AND session_type = 'R' "
                "ORDER BY country"
            ),
            {"y": int(year)},
        ).fetchall()

    print(f"Year {year}: {len(sess_rows)} race sessions", flush=True)
    for sess_id, country in sess_rows:
        try:
            laps_raw = _fetch_race_laps(year, int(sess_id))
        except Exception as exc:
            print(f"  {country}: fetch failed — {exc}", flush=True)
            continue
        if laps_raw.empty:
            print(f"  {country}: no laps in DB", flush=True)
            continue

        df = _clean_stint_laps(laps_raw)
        if df.empty:
            continue
        df = _compute_lap_delta(df)

        for compound in ["SOFT", "MEDIUM", "HARD"]:
            sub = df[df["compound_norm"] == compound].dropna(subset=["tyre_life", "lap_time_delta"])
            if len(sub) < min_obs:
                continue
            ages = sub["tyre_life"].to_numpy()
            deltas = sub["lap_time_delta"].to_numpy()
            # Remove outliers beyond 3 s from median (gross errors / yellows).
            mask = np.abs(deltas - np.median(deltas)) < 3.0
            ages, deltas = ages[mask], deltas[mask]
            if len(ages) < min_obs:
                continue
            slope, r2 = _fit_slope(ages, deltas)
            g15 = G1_5_SLOPES.get(compound, float("nan"))
            rows.append(
                {
                    "circuit_id": str(country).lower().replace(" ", "_"),
                    "year": year,
                    "compound": compound,
                    "fitted_slope": round(slope, 5) if not np.isnan(slope) else None,
                    "g15_slope": g15,
                    "slope_delta": (
                        round(slope - g15, 5)
                        if not np.isnan(slope)
                        else None
                    ),
                    "n_obs": int(len(ages)),
                    "r_squared": round(r2, 4) if not np.isnan(r2) else None,
                }
            )
            print(
                f"  {country:<20} {compound:<8} "
                f"slope={slope:.4f}  g15={g15:.3f}  Δ={slope - g15:+.4f}  "
                f"n={len(ages)}  r²={r2:.3f}",
                flush=True,
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit per-circuit deg slopes (T7 data collection)")
    parser.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025])
    parser.add_argument("--min-obs", type=int, default=15, help="Min clean laps per fit")
    parser.add_argument("--out", type=Path, default=_OUT_CSV, help="Output CSV path")
    args = parser.parse_args()

    all_rows: list[dict] = []
    for year in args.years:
        all_rows.extend(fit_year(year, args.min_obs))

    if not all_rows:
        print("No rows fitted — check DB connection and ingested sessions.", flush=True)
        return 1

    out_df = pd.DataFrame(all_rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.out, index=False)
    print(f"\nSaved {len(out_df)} rows → {args.out}", flush=True)

    # Summary by compound.
    print("\n--- Summary (mean fitted slope vs G1.5) ---", flush=True)
    for compound in ["SOFT", "MEDIUM", "HARD"]:
        sub = out_df[(out_df["compound"] == compound) & out_df["fitted_slope"].notna()]
        if sub.empty:
            continue
        g15 = G1_5_SLOPES[compound]
        mean_fit = sub["fitted_slope"].mean()
        print(
            f"  {compound:<8} G1.5={g15:.3f}  mean_fitted={mean_fit:.4f}  "
            f"Δ={mean_fit - g15:+.4f}  circuits={len(sub)}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
