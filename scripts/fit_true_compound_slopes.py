"""Fit tyre degradation slopes keyed by true C-code identity within each era.

Re-keys the E3.2 method (fuel-corrected race DegSlope, clean-lap filter,
stint split on FastF1 Stint/pit-out, session-level inverse-variance pool).
Does not redesign the fitter: ``fit_track_compound_slopes`` is called on a
frame whose Compound column is the C-code, pooled across all mapped races
in an era.

  python scripts/fit_true_compound_slopes.py
  python scripts/fit_true_compound_slopes.py --write
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402
from fastf1.exceptions import RateLimitExceededError  # noqa: E402

from aris.physics.compounds import (  # noqa: E402
    all_nominations,
    compound_era,
    join_compound_identity,
)
from aris.physics.deg_corrections import detrend_fuel_pace  # noqa: E402
from aris.physics.stint import compute_stint_metrics, detect_stints, filter_clean_laps  # noqa: E402
from aris.physics.tires import (  # noqa: E402
    DEFAULT_COMPOUND_SLOPE,
    fit_track_compound_slopes,
    normalize_compound,
)

_CACHE = _ROOT / "fastf1_cache"
_MIN_LONG_RUN_LAPS = 5
_SLOPE_CLIP = (-0.5, 1.0)
_RACE_SESSION_TYPES = frozenset({"R"})
_C_ORDER = ("C1", "C2", "C3", "C4", "C5", "C6")


def _load(year: int, gp: str, session_type: str):
    attempts = 0
    while True:
        attempts += 1
        try:
            session = fastf1.get_session(year, gp, session_type)
            session.load(laps=True, telemetry=False, weather=False, messages=False)
            return session
        except RateLimitExceededError:
            wait_s = 900 if attempts == 1 else min(1800, 900 * attempts)
            print(f"  rate-limited {year} {gp} {session_type}; sleep {wait_s}s", flush=True)
            time.sleep(wait_s)
            if attempts >= 3:
                raise


def _sessions_for_event(year: int, gp: str) -> list[str]:
    try:
        event = fastf1.get_event(year, gp)
        names = []
        for i in range(1, 6):
            key = f"Session{i}"
            try:
                val = event[key] if key in event else None
            except Exception:  # noqa: BLE001
                val = None
            if val is not None and str(val) not in ("None", "nan"):
                names.append(str(val).lower())
        joined = " | ".join(names)
        has_fp2 = "practice 2" in joined or "fp2" in joined
        has_sprint = "sprint" in joined
        if has_fp2:
            return ["FP2", "R"]
        if has_sprint:
            return ["FP1", "S", "R"]
        return ["FP1", "R"]
    except Exception:  # noqa: BLE001
        return ["FP2", "R"]


def collect_event_metrics(year: int, gp: str, *, min_laps: int) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for stype in _sessions_for_event(year, gp):
        print(f"  Loading {year} {gp} {stype} ...", flush=True)
        try:
            session = _load(year, gp, stype)
        except Exception as exc:  # noqa: BLE001
            print(f"    SKIP: {exc!r}", flush=True)
            continue
        try:
            enriched = detect_stints(session.laps)
        except Exception as exc:  # noqa: BLE001
            print(f"    SKIP laps: {exc!r}", flush=True)
            continue
        if filter_clean_laps(enriched).empty:
            print("    no clean laps", flush=True)
            continue
        fuel_corrected = False
        if stype in _RACE_SESSION_TYPES:
            total_laps = int(getattr(session, "total_laps", None) or 57)
            enriched = detrend_fuel_pace(enriched, total_laps=total_laps)
            fuel_corrected = True
        metrics = compute_stint_metrics(enriched, min_laps=3)
        metrics = metrics[
            metrics["DegSlope"].notna() & (metrics["NumLaps"] >= min_laps)
        ].copy()
        lo, hi = _SLOPE_CLIP
        metrics = metrics[(metrics["DegSlope"] >= lo) & (metrics["DegSlope"] <= hi)].copy()
        if metrics.empty:
            print("    no long-run slopes", flush=True)
            continue
        metrics["Year"] = year
        metrics["Event"] = gp
        metrics["SessionType"] = stype
        metrics["SessionKey"] = f"{year}-{gp}-{stype}"
        metrics["FuelCorrected"] = fuel_corrected
        metrics["Compound"] = metrics["Compound"].map(normalize_compound)
        metrics = join_compound_identity(metrics, year=year, event=gp)
        print(
            f"    stints={len(metrics)} relative={sorted(metrics['Compound'].unique())} "
            f"identity={sorted(metrics['CompoundIdentity'].astype(str).unique())}",
            flush=True,
        )
        rows.append(metrics)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def _monotonic_ok(slopes: dict[str, float], codes: list[str]) -> tuple[bool, str]:
    """C1 (hardest) should degrade slower than C2 … C5/C6 (softest). Strict <."""
    present = [c for c in codes if c in slopes and np.isfinite(slopes[c])]
    if len(present) < 2:
        return False, f"need >=2 C-codes, have {present}"
    vals = [float(slopes[c]) for c in present]
    pairs = list(zip(present, vals, strict=True))
    for (a, va), (b, vb) in zip(pairs, pairs[1:], strict=False):
        if not (vb > va):
            return False, (
                f"ordering failed {a}={va:.4f} not < {b}={vb:.4f} "
                f"(need degradation increasing C1..C5/C6); full={pairs}"
            )
    return True, "ok " + " < ".join(f"{c}={slopes[c]:.4f}" for c in present)


def _nondecreasing_ok(slopes: dict[str, float], codes: list[str]) -> tuple[bool, str]:
    """Isotonic: C1 <= C2 <= ... (ties allowed)."""
    present = [c for c in codes if c in slopes and np.isfinite(slopes[c])]
    if len(present) < 2:
        return False, f"need >=2 C-codes, have {present}"
    vals = [float(slopes[c]) for c in present]
    pairs = list(zip(present, vals, strict=True))
    for (a, va), (b, vb) in zip(pairs, pairs[1:], strict=False):
        if vb < va - 1e-9:
            return False, (
                f"non-decreasing failed {a}={va:.4f} > {b}={vb:.4f}; full={pairs}"
            )
    return True, "ok " + " <= ".join(f"{c}={slopes[c]:.4f}" for c in present)


def fit_era(metrics: pd.DataFrame, era: str) -> dict:
    work = metrics.copy()
    # Fit on true identity; keep INTERMEDIATE/WET out.
    work = work[work["CompoundIdentity"].isin(_C_ORDER)].copy()
    work["Compound"] = work["CompoundIdentity"]
    if work.empty:
        return {
            "era": era,
            "n_stints": 0,
            "slopes": {},
            "n_by_code": {},
            "monotonic_ok": False,
            "reason": "no_c_code_stints",
        }
    slopes_raw = fit_track_compound_slopes(work)
    n_by = work.groupby("CompoundIdentity").size().to_dict()
    fitted = {}
    for code in _C_ORDER:
        n = int(n_by.get(code, 0))
        if n < 3:
            continue
        if code not in slopes_raw:
            continue
        fitted[code] = round(float(slopes_raw[code]), 4)
    ok, reason = _monotonic_ok(fitted, list(_C_ORDER))
    print(f"\n=== era {era} n_stints={len(work)} ===", flush=True)
    print(f"  n_by_code={ {k: int(v) for k, v in n_by.items()} }", flush=True)
    print(f"  fitted={fitted}", flush=True)
    print(f"  monotonic: {reason}", flush=True)
    return {
        "era": era,
        "n_stints": int(len(work)),
        "n_fuel_corrected": int(work["FuelCorrected"].sum()) if "FuelCorrected" in work else 0,
        "n_by_code": {str(k): int(v) for k, v in n_by.items()},
        "slopes": fitted,
        "monotonic_ok": ok,
        "reason": reason,
        "years": sorted(int(y) for y in work["Year"].unique()),
    }


def zandvoort_check(era_fits: dict[str, dict]) -> dict:
    """Event-relative SOFT>MEDIUM>HARD using true-compound slopes at Zandvoort."""
    from aris.physics.compounds import lookup_nomination

    out: dict[str, dict] = {}
    for year in (2021, 2022, 2023, 2024, 2025, 2026):
        nom = lookup_nomination(year, "Netherlands")
        if nom is None:
            out[str(year)] = {"mapped": False}
            continue
        fitted = (era_fits.get(nom.era) or {}).get("slopes") or {}
        rel = {
            "HARD": fitted.get(nom.hard),
            "MEDIUM": fitted.get(nom.medium),
            "SOFT": fitted.get(nom.soft),
        }
        vals = [rel["SOFT"], rel["MEDIUM"], rel["HARD"]]
        ok = all(v is not None and np.isfinite(v) for v in vals) and (
            rel["SOFT"] > rel["MEDIUM"] > rel["HARD"]
        )
        out[str(year)] = {
            "mapped": True,
            "era": nom.era,
            "nomination": {"HARD": nom.hard, "MEDIUM": nom.medium, "SOFT": nom.soft},
            "slopes": rel,
            "ordering_ok": bool(ok),
            "source_url": nom.source_url,
        }
        print(
            f"Zandvoort {year} {nom.hard}/{nom.medium}/{nom.soft} -> "
            f"H={rel['HARD']} M={rel['MEDIUM']} S={rel['SOFT']} "
            f"SOFT>MED>HARD={'YES' if ok else 'NO'}",
            flush=True,
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--min-laps", type=int, default=_MIN_LONG_RUN_LAPS)
    parser.add_argument("--reuse-stints-csv", action="store_true")
    parser.add_argument("--year", type=int, nargs="*", help="Restrict to these years")
    parser.add_argument(
        "--isotonic",
        action="store_true",
        help="After the unconstrained IV fit, apply PAVA so C1 <= C2 <= ... C6",
    )
    args = parser.parse_args()

    fastf1.Cache.enable_cache(str(_CACHE))
    noms = all_nominations()
    if args.year:
        want = set(args.year)
        noms = [n for n in noms if n.year in want]

    csv_path = _ROOT / "results" / "g2" / "true_compound_stints.csv"
    if args.reuse_stints_csv and csv_path.exists():
        print(f"Reusing {csv_path}", flush=True)
        all_metrics = pd.read_csv(csv_path)
    else:
        frames: list[pd.DataFrame] = []
        for nom in noms:
            print(f"\n=== {nom.year} {nom.event} r{nom.round} {nom.hard}/{nom.medium}/{nom.soft} ===", flush=True)
            try:
                metrics = collect_event_metrics(nom.year, nom.event, min_laps=args.min_laps)
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL {exc!r}", flush=True)
                continue
            if metrics.empty:
                print("  no metrics", flush=True)
                continue
            metrics["Era"] = nom.era
            frames.append(metrics)
        if not frames:
            print("NO DATA — nothing to fit", flush=True)
            sys.exit(1)
        all_metrics = pd.concat(frames, ignore_index=True)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        all_metrics.to_csv(csv_path, index=False)
        print(f"Wrote {csv_path} n={len(all_metrics)}", flush=True)

    if "Era" not in all_metrics.columns:
        all_metrics["Era"] = all_metrics["Year"].map(compound_era)

    era_fits: dict[str, dict] = {}
    for era, grp in all_metrics.groupby("Era"):
        era_fits[str(era)] = fit_era(grp, str(era))

    if args.isotonic:
        from aris.physics.compounds import constrain_slopes_isotonic

        print("\n=== G3.4 isotonic (PAVA) constraint C1 <= C2 <= ... ===", flush=True)
        for era, payload in era_fits.items():
            unconstrained = dict(payload.get("slopes") or {})
            weights = {str(k): float(v) for k, v in (payload.get("n_by_code") or {}).items()}
            constrained, notes = constrain_slopes_isotonic(unconstrained, weights)
            ok, reason = _nondecreasing_ok(constrained, list(_C_ORDER))
            payload["unconstrained_slopes"] = unconstrained
            payload["slopes"] = constrained
            payload["isotonic_notes"] = notes
            payload["monotonic_ok"] = ok
            payload["reason"] = reason
            print(f"\n  era {era}", flush=True)
            print(f"    unconstrained={unconstrained}", flush=True)
            print(f"    constrained  ={constrained}", flush=True)
            for note in notes:
                print(f"    {note['pair']}: {note['kind']}", flush=True)
            print(f"    nondecreasing: {reason}", flush=True)

    zv = zandvoort_check(era_fits)
    report = {
        "fit_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": (
            "E3.2 re-keyed + G3.4 isotonic: fuel-corrected race DegSlope, "
            "clean-lap filter, stint split on FastF1 Stint/pit-out, session IV "
            "pool, keyed by CompoundIdentity within era, then PAVA so "
            "C1 <= C2 <= ... C6 (weighted by n_stints)."
            if args.isotonic
            else (
                "E3.2 re-keyed: fuel-corrected race DegSlope, clean-lap filter, "
                "stint split on FastF1 Stint/pit-out, session IV pool, keyed by "
                "CompoundIdentity within era (not SOFT/MEDIUM/HARD)."
            )
        ),
        "n_stints_total": int(len(all_metrics)),
        "eras": era_fits,
        "zandvoort": zv,
        "2026_note": (
            "2026 cache dir existed but was empty at G2 start. "
            "This run includes 2026 only if FastF1 sessions loaded."
        ),
    }
    out_json = (
        _ROOT / "results" / "g3" / "true_compound_slopes_isotonic_report.json"
        if args.isotonic
        else _ROOT / "results" / "g2" / "true_compound_slopes_report.json"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {out_json}", flush=True)

    if args.write:
        shipped = {
            "method": report["method"],
            "fit_utc": report["fit_utc"],
            "eras": {
                era: {
                    "slopes": payload["slopes"],
                    "unconstrained_slopes": payload.get("unconstrained_slopes"),
                    "isotonic_notes": payload.get("isotonic_notes"),
                    "n_stints": payload["n_stints"],
                    "n_by_code": payload["n_by_code"],
                    "monotonic_ok": payload["monotonic_ok"],
                    "reason": payload["reason"],
                }
                for era, payload in era_fits.items()
            },
        }
        dest = (
            _ROOT / "data" / "compounds" / "true_compound_slopes_isotonic.json"
            if args.isotonic
            else _ROOT / "data" / "compounds" / "true_compound_slopes.json"
        )
        dest.write_text(json.dumps(shipped, indent=2), encoding="utf-8")
        print(f"Wrote {dest}", flush=True)
        from aris.physics.compounds import clear_compound_caches
        from aris.tracks import clear_track_config_cache

        clear_compound_caches()
        clear_track_config_cache()
    else:
        print("(dry run — pass --write to persist true_compound_slopes.json)", flush=True)


if __name__ == "__main__":
    main()
