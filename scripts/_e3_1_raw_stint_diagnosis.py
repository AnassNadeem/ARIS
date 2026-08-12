"""Phase E3.1 — raw SOFT vs HARD stint diagnosis (read-only).

Inspects individual stints from several circuits: lap times, tyre life,
race lap, track status, clean-lap retention, stint-length distribution,
and matched early-window re-fits vs full-stint slopes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

from aris.physics.deg_corrections import detrend_fuel_pace  # noqa: E402
from aris.physics.stint import compute_stint_metrics, detect_stints, filter_clean_laps  # noqa: E402
from aris.physics.tires import (  # noqa: E402
    DEFAULT_COMPOUND_SLOPE,
    fit_track_compound_slopes,
    normalize_compound,
)

_CACHE = _ROOT / "fastf1_cache"
_OUT = _ROOT / "results" / "e3_1_raw_stint_diagnosis.json"

# Diverse circuits: ordering-fail (NL, Spain, Italy) + ordering-pass (China, Japan)
_RACES: list[tuple[int, str, str]] = [
    (2024, "Netherlands", "netherlands"),
    (2023, "Netherlands", "netherlands"),
    (2024, "Spain", "spain"),
    (2023, "Spain", "spain"),
    (2024, "Italy", "italy"),
    (2023, "Italy", "italy"),
    (2024, "China", "china"),
    (2024, "Japan", "japan"),
    (2024, "Bahrain", "bahrain"),
    (2023, "Bahrain", "bahrain"),
]

_EARLY_WINDOW = 10  # matched early-stint TyreLife max (inclusive), after out-lap drop
_MIN_LAPS_FIT = 5


def _is_green(ts) -> bool:
    s = str(ts) if ts is not None and not (isinstance(ts, float) and np.isnan(ts)) else ""
    return s == "1"


def _stint_lap_table(grp: pd.DataFrame, *, fuel_corrected: bool) -> list[dict]:
    rows = []
    first = int(grp["LapNumber"].min())
    for r in grp.itertuples(index=False):
        pit_out = getattr(r, "PitOutTime", None)
        pit_in = getattr(r, "PitInTime", None)
        ts = getattr(r, "TrackStatus", None)
        is_out = int(r.LapNumber) == first or (pit_out is not None and not pd.isna(pit_out))
        is_in = pit_in is not None and not pd.isna(pit_in)
        green = _is_green(ts)
        would_keep_clean = (
            pd.notna(r.LapTimeS)
            and not is_out
            and not is_in
            and green
        )
        # What compute_stint_metrics currently keeps in fit_pool:
        would_keep_fitpool = (
            pd.notna(r.LapTimeS)
            and int(r.LapNumber) != first
            and (pit_in is None or pd.isna(pit_in))
        )
        rows.append(
            {
                "LapNumber": int(r.LapNumber),
                "TyreLife": int(r.TyreLife) if pd.notna(r.TyreLife) else None,
                "LapTimeS": None if pd.isna(r.LapTimeS) else round(float(r.LapTimeS), 3),
                "TrackStatus": str(ts) if ts is not None and not pd.isna(ts) else None,
                "green": green,
                "is_out_lap": bool(is_out),
                "is_in_lap": bool(is_in),
                "kept_by_filter_clean_laps": bool(would_keep_clean),
                "kept_by_compute_stint_metrics": bool(would_keep_fitpool),
                "fuel_corrected_frame": fuel_corrected,
            }
        )
    return rows


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 3 or np.unique(x[mask]).size < 2:
        return float("nan")
    try:
        s, _ = np.polyfit(x[mask], y[mask], 1)
        return float(s) if np.isfinite(s) else float("nan")
    except np.linalg.LinAlgError:
        return float("nan")


def _fit_slopes_for_stint(
    grp: pd.DataFrame,
    *,
    mode: str,
    early_max_tyre_life: int = _EARLY_WINDOW,
) -> dict:
    """mode: fitpool (current), clean (filter_clean_laps), early_clean, early_fitpool."""
    first = int(grp["LapNumber"].min())
    if mode in ("fitpool", "early_fitpool"):
        pool = grp[
            (grp["LapNumber"] != first)
            & grp["PitInTime"].isna()
            & grp["LapTimeS"].notna()
        ].copy()
    else:
        # Apply filter_clean_laps logic on this stint alone (needs PitOut/In + TrackStatus)
        pool = filter_clean_laps(grp)
        # Also drop first lap of stint if somehow retained (filter already drops PitOut)
        pool = pool[pool["LapNumber"] != first].copy()

    if mode.startswith("early_"):
        pool = pool[pool["TyreLife"].notna() & (pool["TyreLife"] <= early_max_tyre_life)]

    n = len(pool)
    if n < 3 or pool["TyreLife"].nunique() < 2:
        return {"n": n, "slope": None, "tyre_life_max": None, "dirty_retained": None}

    slope = _slope(
        pool["TyreLife"].to_numpy(dtype=float),
        pool["LapTimeS"].to_numpy(dtype=float),
    )
    dirty = None
    if "TrackStatus" in pool.columns:
        dirty = int((~pool["TrackStatus"].astype(str).eq("1")).sum())
    return {
        "n": n,
        "slope": None if not np.isfinite(slope) else round(slope, 5),
        "tyre_life_max": int(pool["TyreLife"].max()),
        "dirty_retained": dirty,
    }


def analyse_race(year: int, gp: str, stem: str) -> dict:
    print(f"\n=== {year} {gp} ===", flush=True)
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    enriched = detect_stints(session.laps)
    total_laps = int(getattr(session, "total_laps", None) or enriched["LapNumber"].max())
    fuelled = detrend_fuel_pace(enriched, total_laps=total_laps)

    clean = filter_clean_laps(fuelled)
    # Current calendar fit path: metrics on FULL fuelled frame (not clean-filtered)
    metrics_fitpool = compute_stint_metrics(fuelled, min_laps=3)
    metrics_clean = compute_stint_metrics(clean, min_laps=3)

    # Attach compound normalize
    for m in (metrics_fitpool, metrics_clean):
        m["Compound"] = m["Compound"].map(normalize_compound)

    # Length distribution by compound (all stints with NumLaps>=5)
    length_dist = {}
    for comp in ("SOFT", "MEDIUM", "HARD"):
        sub = metrics_fitpool[
            (metrics_fitpool["Compound"] == comp) & (metrics_fitpool["NumLaps"] >= _MIN_LAPS_FIT)
        ]
        if sub.empty:
            length_dist[comp] = {"n": 0}
            continue
        length_dist[comp] = {
            "n": int(len(sub)),
            "mean_num_laps": round(float(sub["NumLaps"].mean()), 2),
            "median_num_laps": round(float(sub["NumLaps"].median()), 2),
            "p75_num_laps": round(float(sub["NumLaps"].quantile(0.75)), 2),
            "mean_start_lap": round(float(sub["StartLap"].mean()), 2),
            "mean_deg_fitpool": round(float(sub["DegSlope"].mean()), 5)
            if sub["DegSlope"].notna().any()
            else None,
        }

    # Clean-lap retention asymmetry: for each long SOFT/HARD stint, compare
    # how many non-green / pit laps fitpool retains vs filter_clean_laps.
    retention_rows = []
    examples = {"SOFT": [], "HARD": []}
    per_stint_slopes = []

    for (drv, sid), grp in fuelled.groupby(["Driver", "StintId"]):
        comp = normalize_compound(str(grp["Compound"].iloc[0]))
        if comp not in ("SOFT", "MEDIUM", "HARD"):
            continue
        n_all = len(grp)
        if n_all < _MIN_LAPS_FIT:
            continue
        laps = _stint_lap_table(grp, fuel_corrected=True)
        n_fitpool = sum(1 for L in laps if L["kept_by_compute_stint_metrics"])
        n_clean = sum(1 for L in laps if L["kept_by_filter_clean_laps"])
        n_dirty_in_fitpool = sum(
            1
            for L in laps
            if L["kept_by_compute_stint_metrics"] and not L["green"]
        )
        n_nongreen = sum(1 for L in laps if not L["green"] and L["LapTimeS"] is not None)
        slopes = {
            mode: _fit_slopes_for_stint(grp, mode=mode)
            for mode in ("fitpool", "clean", "early_fitpool", "early_clean")
        }
        row = {
            "driver": drv,
            "stint": int(sid),
            "compound": comp,
            "start_lap": int(grp["LapNumber"].min()),
            "end_lap": int(grp["LapNumber"].max()),
            "n_laps_raw": n_all,
            "n_fitpool": n_fitpool,
            "n_clean": n_clean,
            "n_dirty_retained_in_fitpool": n_dirty_in_fitpool,
            "n_nongreen_with_time": n_nongreen,
            "clean_frac_of_fitpool": round(n_clean / n_fitpool, 3) if n_fitpool else None,
            "slopes": slopes,
        }
        retention_rows.append(row)
        per_stint_slopes.append(row)

        # Keep 2 concrete examples per compound with interesting dirt or length
        if comp in examples and len(examples[comp]) < 2:
            # Prefer stints that retain dirty laps OR are long HARD / short SOFT
            if n_dirty_in_fitpool > 0 or (comp == "HARD" and n_all >= 15) or (
                comp == "SOFT" and n_all <= 12
            ):
                examples[comp].append(
                    {
                        **{k: row[k] for k in row if k != "slopes"},
                        "slopes": slopes,
                        "laps": laps,
                    }
                )

    # If examples empty, take first two long stints
    for comp in ("SOFT", "HARD"):
        if len(examples[comp]) < 2:
            cands = [r for r in retention_rows if r["compound"] == comp]
            cands = sorted(cands, key=lambda r: -r["n_laps_raw"])
            for r in cands:
                if len(examples[comp]) >= 2:
                    break
                # rebuild laps
                grp = fuelled[
                    (fuelled["Driver"] == r["driver"]) & (fuelled["StintId"] == r["stint"])
                ]
                examples[comp].append(
                    {
                        **{k: r[k] for k in r if k != "slopes"},
                        "slopes": r["slopes"],
                        "laps": _stint_lap_table(grp, fuel_corrected=True),
                    }
                )

    def _agg_retention(comp: str) -> dict:
        sub = [r for r in retention_rows if r["compound"] == comp]
        if not sub:
            return {"n_stints": 0}
        dirty = [r["n_dirty_retained_in_fitpool"] for r in sub]
        clean_frac = [r["clean_frac_of_fitpool"] for r in sub if r["clean_frac_of_fitpool"] is not None]
        start = [r["start_lap"] for r in sub]
        return {
            "n_stints": len(sub),
            "mean_dirty_retained_in_fitpool": round(float(np.mean(dirty)), 3),
            "pct_stints_with_any_dirty": round(
                100.0 * sum(1 for d in dirty if d > 0) / len(dirty), 1
            ),
            "mean_clean_frac_of_fitpool": round(float(np.mean(clean_frac)), 3) if clean_frac else None,
            "mean_start_lap": round(float(np.mean(start)), 2),
            "mean_n_laps_raw": round(float(np.mean([r["n_laps_raw"] for r in sub])), 2),
        }

    # Pooled compound slopes under four methods (long runs only)
    def _pool_method(mode: str) -> dict:
        rows = []
        for r in per_stint_slopes:
            s = r["slopes"][mode]["slope"]
            n = r["slopes"][mode]["n"]
            if s is None or n < _MIN_LAPS_FIT:
                continue
            if not (-0.5 <= s <= 1.0):
                continue
            rows.append({"Compound": r["compound"], "DegSlope": s, "SessionKey": f"{year}-R"})
        if not rows:
            return {}
        df = pd.DataFrame(rows)
        fitted = fit_track_compound_slopes(df)
        dry = {k: round(float(fitted.get(k, float("nan"))), 5) for k in ("SOFT", "MEDIUM", "HARD")}
        ok = (
            np.isfinite(dry["SOFT"])
            and np.isfinite(dry["MEDIUM"])
            and np.isfinite(dry["HARD"])
            and dry["SOFT"] > dry["MEDIUM"] > dry["HARD"]
            and all(0 < dry[k] <= 0.25 for k in dry)
        )
        return {"slopes": dry, "n": len(df), "ordering_ok": bool(ok)}

    pooled = {m: _pool_method(m) for m in ("fitpool", "clean", "early_fitpool", "early_clean")}

    # Also compare metrics_fitpool vs metrics_clean medians
    def _median_slopes(m: pd.DataFrame) -> dict:
        out = {}
        for comp in ("SOFT", "MEDIUM", "HARD"):
            sub = m[(m["Compound"] == comp) & (m["NumLaps"] >= _MIN_LAPS_FIT) & m["DegSlope"].notna()]
            sub = sub[(sub["DegSlope"] >= -0.5) & (sub["DegSlope"] <= 1.0)]
            out[comp] = None if sub.empty else round(float(sub["DegSlope"].median()), 5)
        return out

    return {
        "year": year,
        "gp": gp,
        "stem": stem,
        "total_laps": total_laps,
        "n_clean_laps": int(len(clean)),
        "n_raw_laps": int(len(fuelled)),
        "length_dist": length_dist,
        "retention_by_compound": {c: _agg_retention(c) for c in ("SOFT", "MEDIUM", "HARD")},
        "median_deg_fitpool_path": _median_slopes(metrics_fitpool),
        "median_deg_if_clean_filtered_first": _median_slopes(metrics_clean),
        "pooled_methods": pooled,
        "examples": examples,
    }


def main() -> None:
    fastf1.Cache.enable_cache(str(_CACHE))
    races = []
    for year, gp, stem in _RACES:
        try:
            races.append(analyse_race(year, gp, stem))
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {year} {gp}: {exc!r}", flush=True)
            races.append({"year": year, "gp": gp, "stem": stem, "error": repr(exc)})

    # Cross-race summary
    summary = {
        "finding_clean_filter_asymmetry": {},
        "finding_stint_length": {},
        "finding_early_window_ordering": {},
    }

    # Aggregate dirty retention SOFT vs HARD
    soft_dirty, hard_dirty = [], []
    soft_len, hard_len = [], []
    early_wins = 0
    fitpool_wins = 0
    early_ok = 0
    fitpool_ok = 0
    clean_ok = 0
    n_compared = 0
    for r in races:
        if "error" in r:
            continue
        ret = r["retention_by_compound"]
        if ret.get("SOFT", {}).get("n_stints"):
            soft_dirty.append(ret["SOFT"]["mean_dirty_retained_in_fitpool"])
            soft_len.append(ret["SOFT"]["mean_n_laps_raw"])
        if ret.get("HARD", {}).get("n_stints"):
            hard_dirty.append(ret["HARD"]["mean_dirty_retained_in_fitpool"])
            hard_len.append(ret["HARD"]["mean_n_laps_raw"])
        pm = r.get("pooled_methods") or {}
        fp = pm.get("fitpool") or {}
        cl = pm.get("clean") or {}
        ef = pm.get("early_fitpool") or {}
        ec = pm.get("early_clean") or {}
        if fp.get("ordering_ok"):
            fitpool_ok += 1
        if cl.get("ordering_ok"):
            clean_ok += 1
        if ef.get("ordering_ok") or ec.get("ordering_ok"):
            early_ok += 1
        # Does early restore ordering when fitpool fails?
        if fp and (ef or ec):
            n_compared += 1
            if not fp.get("ordering_ok") and (ef.get("ordering_ok") or ec.get("ordering_ok")):
                early_wins += 1
            if fp.get("ordering_ok") and not (ef.get("ordering_ok") or ec.get("ordering_ok")):
                fitpool_wins += 1

    summary["finding_clean_filter_asymmetry"] = {
        "note": (
            "compute_stint_metrics does NOT apply filter_clean_laps; it only drops "
            "first-lap-of-stint + PitInTime + NaN. TrackStatus dirty laps stay in DegSlope."
        ),
        "mean_dirty_laps_retained_SOFT": None
        if not soft_dirty
        else round(float(np.mean(soft_dirty)), 3),
        "mean_dirty_laps_retained_HARD": None
        if not hard_dirty
        else round(float(np.mean(hard_dirty)), 3),
        "hard_retains_more_dirty_than_soft": (
            bool(np.mean(hard_dirty) > np.mean(soft_dirty) + 0.05)
            if soft_dirty and hard_dirty
            else None
        ),
    }
    summary["finding_stint_length"] = {
        "mean_SOFT_laps": None if not soft_len else round(float(np.mean(soft_len)), 2),
        "mean_HARD_laps": None if not hard_len else round(float(np.mean(hard_len)), 2),
        "hard_longer_than_soft": (
            bool(np.mean(hard_len) > np.mean(soft_len) + 1.0)
            if soft_len and hard_len
            else None
        ),
    }
    summary["finding_early_window_ordering"] = {
        "early_window_tyre_life_max": _EARLY_WINDOW,
        "races_fitpool_ordering_ok": fitpool_ok,
        "races_clean_ordering_ok": clean_ok,
        "races_early_any_ordering_ok": early_ok,
        "races_where_early_fixes_fitpool_fail": early_wins,
        "races_compared": n_compared,
        "n_races": sum(1 for r in races if "error" not in r),
    }

    payload = {"summary": summary, "races": races, "defaults": dict(DEFAULT_COMPOUND_SLOPE)}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {_OUT}", flush=True)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
