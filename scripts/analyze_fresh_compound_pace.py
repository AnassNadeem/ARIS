"""Calibrate global fresh-compound pace offsets vs HARD (T9.1).

For each 2024–2025 dry race stint, take the first 3 green-flag clean laps
and their median lap time. Report global medians and (more useful) the
median within-circuit delta vs HARD.

Usage:
  python scripts/analyze_fresh_compound_pace.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

_DRY = frozenset({"SOFT", "MEDIUM", "HARD"})
_WET = frozenset({"INTERMEDIATE", "INTER", "WET"})


def _norm_compound(raw: object) -> str | None:
    token = str(raw or "").strip().upper()
    if token in _DRY:
        return token
    if token in _WET or not token or token in {"NONE", "NAN"}:
        return None
    return None


def _is_green(status: object) -> bool:
    return str(status or "").strip() == "1"


def _stint_fresh_rows(laps: pd.DataFrame, *, circuit_id: str, year: int, round_no: int) -> list[dict]:
    """One row per stint with median of the first 3 clean green laps."""
    if laps.empty:
        return []
    work = laps.copy()
    if "compound" in work.columns and "Compound" not in work.columns:
        work = work.rename(columns={"compound": "Compound"})
    if "lap_time_s" in work.columns and "LapTimeS" not in work.columns:
        work["LapTimeS"] = pd.to_numeric(work["lap_time_s"], errors="coerce")
    if "lap_number" in work.columns and "LapNumber" not in work.columns:
        work["LapNumber"] = pd.to_numeric(work["lap_number"], errors="coerce")
    if "code" in work.columns and "Driver" not in work.columns:
        work["Driver"] = work["code"].astype(str)
    if "stint" in work.columns and "StintId" not in work.columns:
        work["StintId"] = work["stint"]
    if "track_status" in work.columns and "TrackStatus" not in work.columns:
        work["TrackStatus"] = work["track_status"]
    if "Driver" not in work.columns or "LapTimeS" not in work.columns:
        return []

    work["Compound"] = work["Compound"].map(_norm_compound)
    work = work[work["Compound"].notna()]
    work = work[pd.to_numeric(work["LapTimeS"], errors="coerce").notna()]
    work = work[work["LapTimeS"] > 0]

    if "TrackStatus" in work.columns:
        work = work[work["TrackStatus"].map(_is_green)]

    if "pit_in" in work.columns:
        work = work[~work["pit_in"].fillna(False).astype(bool)]
    elif "PitInTime" in work.columns:
        work = work[work["PitInTime"].isna()]
    if "pit_out" in work.columns:
        work = work[~work["pit_out"].fillna(False).astype(bool)]
    elif "PitOutTime" in work.columns:
        work = work[work["PitOutTime"].isna()]

    if work.empty:
        return []

    if "StintId" not in work.columns or work["StintId"].isna().all():
        work = work.sort_values(["Driver", "LapNumber"])
        changed = work.groupby("Driver")["Compound"].transform(lambda s: s != s.shift(1))
        work["StintId"] = changed.groupby(work["Driver"]).cumsum()

    rows: list[dict] = []
    for (driver, stint_id), grp in work.groupby(["Driver", "StintId"], sort=False):
        grp = grp.sort_values("LapNumber")
        fresh = grp.head(3)
        if len(fresh) < 3:
            continue
        compound = str(fresh["Compound"].iloc[0])
        if compound not in _DRY:
            continue
        rows.append(
            {
                "year": year,
                "round_no": round_no,
                "circuit_id": circuit_id,
                "driver": str(driver),
                "stint_id": int(stint_id) if pd.notna(stint_id) else 0,
                "compound": compound,
                "n_fresh": int(len(fresh)),
                "median_fresh_s": float(fresh["LapTimeS"].median()),
                "opening_stint": int(stint_id) == 1 if pd.notna(stint_id) else False,
            }
        )
    return rows


def _load_from_db(years: list[int]) -> pd.DataFrame:
    from aris.io import db

    rows: list[dict] = []
    for year in years:
        races = db.fetch_races(year)
        if races.empty:
            continue
        for rec in races.itertuples(index=False):
            session_id = int(rec.session_id)
            circuit_id = str(rec.country)
            round_no = int(rec.round_no)
            weather = db.fetch_session_weather(session_id)
            if weather and weather.get("rainfall"):
                continue
            laps = db.fetch_all_laps(session_id)
            if laps.empty:
                continue
            # Skip races that are predominantly wet compounds.
            if "compound" in laps.columns:
                compounds = laps["compound"].astype(str).str.upper()
                wet_frac = compounds.isin(_WET).mean()
                if wet_frac > 0.4:
                    continue
            rows.extend(
                _stint_fresh_rows(
                    laps, circuit_id=circuit_id, year=year, round_no=round_no
                )
            )
            print(
                f"  DB {year} R{round_no:<2} {circuit_id:<18} "
                f"stints={sum(1 for r in rows if r['year']==year and r['round_no']==round_no)}",
                flush=True,
            )
    return pd.DataFrame(rows)


def _load_from_fastf1(years: list[int]) -> pd.DataFrame:
    from aris.eval.backtest import BACKTEST_GPS_2025
    from aris.eval.laptime import HELD_OUT_RACES
    from aris.io.fastf1_session import load_race_session
    from aris.physics.stint import detect_stints

    gps = {
        2024: [gp for y, gp in HELD_OUT_RACES if y == 2024],
        2025: list(BACKTEST_GPS_2025),
    }
    rows: list[dict] = []
    for year in years:
        for i, gp in enumerate(gps.get(year, []), start=1):
            try:
                session = load_race_session(year, gp, round_no=i)
            except Exception as exc:  # noqa: BLE001
                print(f"  SKIP FastF1 {year} {gp}: {exc!r}", flush=True)
                continue
            try:
                rainfall = False
                weather = getattr(session, "weather_data", None)
                if weather is not None and not getattr(weather, "empty", True):
                    if "Rainfall" in weather.columns:
                        rainfall = bool(weather["Rainfall"].fillna(False).astype(bool).any())
                if rainfall:
                    print(f"  SKIP wet {year} {gp}", flush=True)
                    continue
                enriched = detect_stints(session.laps)
            except Exception as exc:  # noqa: BLE001
                print(f"  SKIP laps {year} {gp}: {exc!r}", flush=True)
                continue
            frame = enriched.rename(columns={"StintId": "StintId"})
            n_before = len(rows)
            rows.extend(
                _stint_fresh_rows(
                    frame, circuit_id=str(gp), year=year, round_no=i
                )
            )
            print(
                f"  FastF1 {year} {gp:<18} stints={len(rows) - n_before}",
                flush=True,
            )
    return pd.DataFrame(rows)


def _suggest_offset(value: float, *, lo: float, hi: float, fallback: float) -> float:
    if not np.isfinite(value):
        return fallback
    clipped = min(hi, max(lo, float(value)))
    return round(clipped * 20.0) / 20.0  # 0.05 s


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate COMPOUND_PACE_OFFSET")
    parser.add_argument("--years", type=int, nargs="+", default=[2024, 2025])
    parser.add_argument(
        "--source",
        choices=["auto", "db", "fastf1"],
        default="auto",
        help="auto: DB first, FastF1 on empty/failure",
    )
    args = parser.parse_args()

    frame = pd.DataFrame()
    source = args.source
    if source in {"auto", "db"}:
        try:
            print("Loading 2024–2025 dry races from DB ...", flush=True)
            frame = _load_from_db(list(args.years))
        except Exception as exc:  # noqa: BLE001
            print(f"DB load failed: {exc!r}", flush=True)
            if source == "db":
                return 1
            frame = pd.DataFrame()
    if frame.empty and source in {"auto", "fastf1"}:
        print("Loading 2024–2025 dry races from FastF1 ...", flush=True)
        frame = _load_from_fastf1(list(args.years))
    if frame.empty:
        print("No fresh-stint rows — cannot calibrate.", flush=True)
        return 1

    print(f"\nStints with 3 clean green laps: {len(frame)}", flush=True)

    # Naive global medians (circuit mix confounds absolute lap times).
    global_med = frame.groupby("compound")["median_fresh_s"].median()
    median_h = float(global_med.get("HARD", float("nan")))
    median_m = float(global_med.get("MEDIUM", float("nan")))
    median_s = float(global_med.get("SOFT", float("nan")))
    naive_m = median_m - median_h
    naive_s = median_s - median_h

    print("\n| Compound | Median fresh lap (s) | Offset vs HARD (s) |", flush=True)
    print("|---|---:|---:|", flush=True)
    for name, med, delta in (
        ("HARD", median_h, 0.0),
        ("MEDIUM", median_m, naive_m),
        ("SOFT", median_s, naive_s),
    ):
        n = int((frame["compound"] == name).sum())
        print(f"| {name} (n={n}) | {med:.3f} | {delta:+.3f} |", flush=True)

    # Circuit-paired: median of (compound median − HARD median) per circuit.
    paired_rows = []
    for (year, circuit), grp in frame.groupby(["year", "circuit_id"]):
        by_c = grp.groupby("compound")["median_fresh_s"].median()
        if "HARD" not in by_c:
            continue
        hard = float(by_c["HARD"])
        for compound in ("MEDIUM", "SOFT"):
            if compound not in by_c:
                continue
            paired_rows.append(
                {
                    "year": year,
                    "circuit_id": circuit,
                    "compound": compound,
                    "delta_vs_hard": float(by_c[compound]) - hard,
                    "n_stints": int((grp["compound"] == compound).sum()),
                }
            )
    paired = pd.DataFrame(paired_rows)
    later = frame[~frame["opening_stint"].astype(bool)]
    later_paired_rows = []
    for (year, circuit), grp in later.groupby(["year", "circuit_id"]):
        by_c = grp.groupby("compound")["median_fresh_s"].median()
        if "HARD" not in by_c:
            continue
        hard = float(by_c["HARD"])
        for compound in ("MEDIUM", "SOFT"):
            if compound not in by_c:
                continue
            later_paired_rows.append(
                {
                    "compound": compound,
                    "delta_vs_hard": float(by_c[compound]) - hard,
                }
            )
    later_paired = pd.DataFrame(later_paired_rows)

    def _paired_median(df: pd.DataFrame, compound: str) -> float:
        if df.empty:
            return float("nan")
        sub = df[df["compound"] == compound]["delta_vs_hard"]
        return float(sub.median()) if not sub.empty else float("nan")

    circ_m = _paired_median(paired, "MEDIUM")
    circ_s = _paired_median(paired, "SOFT")
    later_m = _paired_median(later_paired, "MEDIUM")
    later_s = _paired_median(later_paired, "SOFT")

    print("\nWithin-circuit paired offsets (median of circuit deltas vs HARD):", flush=True)
    print(f"  MEDIUM: {circ_m:+.3f} s   SOFT: {circ_s:+.3f} s", flush=True)
    print(
        "Excluding opening stints (similar fuel, preferred for calibration):",
        flush=True,
    )
    print(f"  MEDIUM: {later_m:+.3f} s   SOFT: {later_s:+.3f} s", flush=True)

    # Prefer later-stint paired; fall back to all-stint paired; then examples.
    rec_m = later_m if np.isfinite(later_m) else circ_m
    rec_s = later_s if np.isfinite(later_s) else circ_s
    suggest_m = _suggest_offset(rec_m, lo=-0.70, hi=-0.20, fallback=-0.40)
    suggest_s = _suggest_offset(rec_s, lo=-1.20, hi=-0.40, fallback=-0.80)
    if suggest_s >= suggest_m:
        suggest_s = min(-0.45, suggest_m - 0.30)

    print("\nSuggested COMPOUND_PACE_OFFSET (clipped, 0.05 s):", flush=True)
    print("  HARD:    0.00", flush=True)
    print(f"  MEDIUM: {suggest_m:+.2f}", flush=True)
    print(f"  SOFT:   {suggest_s:+.2f}", flush=True)
    print(
        "\nNaive global medians mix circuit lap lengths; use the paired "
        "later-stint offsets in tires.py.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
