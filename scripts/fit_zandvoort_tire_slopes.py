"""Fit Zandvoort track-specific compound degradation slopes (Phase E1.2 / E1b / E2.2).

Pulls FP2 + Race long-run DegSlope samples for Dutch GP 2021–2025, then
precision-weight blends session-level inverse-variance estimates.

Phase E1b: Race-session DegSlope fits detrend lap times by the existing
fuel-burn pace effect (``FUEL_PENALTY_S_PER_KG`` × ``estimate_fuel_kg``) so
fuel lightening is not mistaken for tyre degradation. Practice / sprint
sessions are left raw for fuel — their fuel schedule is not the race burn model.

Phase E2.2: optionally also remove a session-level track-evolution
(rubbering-in) trend estimated from fresh flying laps vs LapNumber (between
stints), applied to all session types. Within-stint LapNumber/TyreLife
collinearity means this must NOT be a naive within-stint LapNumber detrend.

Live-write policy (E1b.5): default is observe/log only. YAML writes require
``--write``, and during the event window an additional ``--allow-live-write``
flag is required so a normal weekend run cannot clobber netherlands.yaml.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402
from fastf1.exceptions import RateLimitExceededError  # noqa: E402

from aris.physics.bicycle import FUEL_PENALTY_S_PER_KG  # noqa: E402
from aris.physics.deg_corrections import (  # noqa: E402
    detrend_fuel_pace,
    detrend_track_evolution,
)
from aris.physics.stint import (  # noqa: E402
    compute_stint_metrics,
    detect_stints,
    filter_clean_laps,
)
from aris.physics.tires import (  # noqa: E402
    DEFAULT_COMPOUND_SLOPE,
    fit_track_compound_slopes,
    normalize_compound,
)

_CACHE = _ROOT / "fastf1_cache"
_YAML = _ROOT / "data" / "tracks" / "netherlands.yaml"
_YEARS = (2021, 2022, 2023, 2024, 2025)
# Prefer FP2 when present; on sprint weekends FastF1 has no FP2 — use FP1 + Sprint.
_SESSIONS = ("FP2", "FP1", "S", "R")
_MIN_LONG_RUN_LAPS = 5  # long-run filter for FP2/R stints
# DegSlope outliers (traffic / cool-down / SC leakage) — drop before pooling.
_SLOPE_CLIP = (-0.5, 1.0)
_GP = "Netherlands"
# 2026 Dutch GP event window (Fri–Sun). Inside this range, --write alone is refused.
_EVENT_WINDOW = (date(2026, 8, 21), date(2026, 8, 23))
_RACE_SESSION_TYPES = frozenset({"R"})


def _load(year: int, session_type: str):
    attempts = 0
    while True:
        attempts += 1
        try:
            session = fastf1.get_session(year, _GP, session_type)
            session.load(laps=True, telemetry=False, weather=False, messages=False)
            return session
        except RateLimitExceededError:
            wait_s = 120 * attempts
            print(f"  rate-limited {year} {_GP} {session_type}; sleep {wait_s}s", flush=True)
            time.sleep(wait_s)
            if attempts >= 6:
                raise


def _in_event_window(today: date | None = None) -> bool:
    d = today or date.today()
    start, end = _EVENT_WINDOW
    return start <= d <= end


def collect_long_run_metrics(
    *,
    min_laps: int = _MIN_LONG_RUN_LAPS,
    track_evolution: bool = False,
) -> pd.DataFrame:
    """FP2/Race stints with a fitted DegSlope across 2021–2025 Zandvoort."""
    fastf1.Cache.enable_cache(str(_CACHE))
    rows: list[pd.DataFrame] = []
    for year in _YEARS:
        for stype in _SESSIONS:
            print(f"Loading {year} {_GP} {stype} ...", flush=True)
            try:
                session = _load(year, stype)
            except Exception as exc:  # noqa: BLE001 — report and continue other years
                print(f"  SKIP: {exc!r}", flush=True)
                continue
            enriched = detect_stints(session.laps)
            # DegSlope fit uses out-lap-dropped pool inside compute_stint_metrics;
            # clean-lap filter removes SC etc. before metrics.
            clean = filter_clean_laps(enriched)
            if clean.empty:
                print("  no clean laps", flush=True)
                continue
            fuel_corrected = False
            evo_slope = 0.0
            evo_corrected = False
            if stype in _RACE_SESSION_TYPES:
                total_laps = int(getattr(session, "total_laps", None) or 72)
                enriched = detrend_fuel_pace(enriched, total_laps=total_laps)
                fuel_corrected = True
                print(
                    f"  fuel-detrended Race laps "
                    f"(penalty={FUEL_PENALTY_S_PER_KG} s/kg, total_laps={total_laps})",
                    flush=True,
                )
            if track_evolution:
                enriched, evo_slope = detrend_track_evolution(enriched)
                evo_corrected = True
                print(
                    f"  track-evolution detrended "
                    f"(fresh-flying LapNumber slope={evo_slope:+.4f} s/lap)",
                    flush=True,
                )
            # Re-attach pit flags from enriched for metrics (filter_clean drops pits,
            # but compute_stint_metrics expects the enriched frame). Fit on enriched
            # then keep long clean-ish stints via NumLaps.
            metrics = compute_stint_metrics(enriched, min_laps=3)
            metrics = metrics[metrics["DegSlope"].notna() & (metrics["NumLaps"] >= min_laps)].copy()
            lo, hi = _SLOPE_CLIP
            metrics = metrics[(metrics["DegSlope"] >= lo) & (metrics["DegSlope"] <= hi)].copy()
            if metrics.empty:
                print("  no long-run slopes", flush=True)
                continue
            metrics["Year"] = year
            metrics["SessionType"] = stype
            metrics["SessionKey"] = f"{year}-{stype}"
            metrics["FuelCorrected"] = fuel_corrected
            metrics["TrackEvolutionCorrected"] = evo_corrected
            metrics["TrackEvolutionSlope"] = evo_slope
            metrics["Compound"] = metrics["Compound"].map(normalize_compound)
            print(
                f"  stints={len(metrics)} compounds={sorted(metrics['Compound'].unique())}",
                flush=True,
            )
            rows.append(metrics)
    if not rows:
        raise RuntimeError("no Zandvoort long-run DegSlope samples collected")
    return pd.concat(rows, ignore_index=True)


def _ordering_ok(slopes: dict[str, float]) -> bool:
    """SOFT should degrade faster than MEDIUM, MEDIUM faster than HARD."""
    soft = float(slopes.get("SOFT", float("nan")))
    med = float(slopes.get("MEDIUM", float("nan")))
    hard = float(slopes.get("HARD", float("nan")))
    if not all(np.isfinite(v) for v in (soft, med, hard)):
        return False
    return soft > med > hard


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Update netherlands.yaml (observe/log only is the default)",
    )
    parser.add_argument(
        "--allow-live-write",
        action="store_true",
        help=(
            "Required together with --write during the Dutch GP event window "
            f"({_EVENT_WINDOW[0].isoformat()}..{_EVENT_WINDOW[1].isoformat()}). "
            "Normal weekend ops should log blended slopes only."
        ),
    )
    parser.add_argument("--min-laps", type=int, default=_MIN_LONG_RUN_LAPS)
    parser.add_argument(
        "--force-defaults",
        action="store_true",
        help="Write global DEFAULT_COMPOUND_SLOPE instead of the empirical fit",
    )
    parser.add_argument(
        "--track-evolution",
        action="store_true",
        help=(
            "Also apply E2.2 track-evolution detrend (tested; did NOT restore "
            "SOFT>MEDIUM>HARD on Zandvoort — off by default)"
        ),
    )
    parser.add_argument(
        "--no-track-evolution",
        action="store_true",
        help=argparse.SUPPRESS,  # kept for older CLI invocations; default is already off
    )
    args = parser.parse_args()

    use_evo = bool(args.track_evolution) and not args.no_track_evolution
    metrics = collect_long_run_metrics(min_laps=args.min_laps, track_evolution=use_evo)
    out_csv = _ROOT / "results" / (
        "e2_zandvoort_deg_stints.csv" if use_evo else "e1_zandvoort_deg_stints.csv"
    )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(out_csv, index=False)
    n_fuel = int(metrics["FuelCorrected"].sum()) if "FuelCorrected" in metrics.columns else 0
    n_evo = (
        int(metrics["TrackEvolutionCorrected"].sum())
        if "TrackEvolutionCorrected" in metrics.columns
        else 0
    )
    print(
        f"\nWrote {out_csv} ({len(metrics)} stints, {n_fuel} fuel-corrected Race stints, "
        f"{n_evo} track-evolution-corrected stints)",
        flush=True,
    )

    print("\nPer-session compound means:", flush=True)
    summary = (
        metrics.groupby(["SessionKey", "Compound"])["DegSlope"]
        .agg(["count", "mean", "std"])
        .reset_index()
    )
    print(summary.to_string(index=False), flush=True)

    slopes = fit_track_compound_slopes(metrics)
    print("\nFitted track compound_slopes (vs defaults):", flush=True)
    for compound in sorted(set(DEFAULT_COMPOUND_SLOPE) | set(slopes)):
        fitted = slopes.get(compound, float("nan"))
        default = DEFAULT_COMPOUND_SLOPE.get(compound, float("nan"))
        n = int((metrics["Compound"] == compound).sum()) if compound in set(metrics["Compound"]) else 0
        print(f"  {compound:14s}  fitted={fitted:+.4f}  default={default:.4f}  n_stints={n}", flush=True)

    # Only persist dry compounds we actually observed; leave INTERmediate/WET as defaults
    # by omitting them from YAML (loader merges with globals).
    dry = {k: round(float(v), 4) for k, v in slopes.items() if k in {"SOFT", "MEDIUM", "HARD"}}
    # Always write the three dry compounds so the override is explicit.
    for k in ("SOFT", "MEDIUM", "HARD"):
        dry.setdefault(k, round(float(DEFAULT_COMPOUND_SLOPE[k]), 4))

    used_defaults = False
    if args.force_defaults or not _ordering_ok(dry):
        used_defaults = True
        reason = (
            "--force-defaults"
            if args.force_defaults
            else (
                f"ordering check failed "
                f"(SOFT={dry['SOFT']}, MEDIUM={dry['MEDIUM']}, HARD={dry['HARD']}; "
                "need SOFT > MEDIUM > HARD)"
            )
        )
        print(f"\nFALLBACK to global defaults: {reason}", flush=True)
        dry = {k: round(float(DEFAULT_COMPOUND_SLOPE[k]), 4) for k in ("SOFT", "MEDIUM", "HARD")}
    else:
        print(
            f"\nOrdering OK: SOFT ({dry['SOFT']}) > MEDIUM ({dry['MEDIUM']}) > HARD ({dry['HARD']})",
            flush=True,
        )

    if args.write:
        if _in_event_window() and not args.allow_live_write:
            print(
                "\nREFUSED write: Dutch GP event window is active "
                f"({_EVENT_WINDOW[0]}..{_EVENT_WINDOW[1]}). "
                "Default policy is observe/log only. Pass --allow-live-write "
                "together with --write only if you deliberately accept a mid-weekend YAML change.",
                flush=True,
            )
            print(f"would have written compound_slopes={dry}", flush=True)
            sys.exit(2)
        doc = yaml.safe_load(_YAML.read_text(encoding="utf-8")) or {}
        doc["compound_slopes"] = dry
        src = dict(doc.get("source") or {})
        corr_bits = ["Race fuel detrend (FUEL_PENALTY_S_PER_KG*estimate_fuel_kg)"]
        if use_evo:
            corr_bits.append(
                "session track-evolution detrend from fresh-flying LapNumber slope"
            )
        corr_desc = " + ".join(corr_bits)
        if used_defaults:
            src["compound_slopes_method"] = (
                "FALLBACK to DEFAULT_COMPOUND_SLOPE after DegSlope fit "
                f"({corr_desc}) failed SOFT>MEDIUM>HARD sanity check "
                f"(FP2+R long runs NumLaps>={args.min_laps}, DegSlope in {_SLOPE_CLIP}, "
                f"years={list(_YEARS)})"
            )
        else:
            src["compound_slopes_method"] = (
                "session-level inverse-variance pool of DegSlope mean/var "
                f"({corr_desc}; FP2+R long runs NumLaps>={args.min_laps}, "
                f"DegSlope in {_SLOPE_CLIP}, years={list(_YEARS)}); "
                "live update via blend_slope_prior"
            )
        src["compound_slopes_n_stints"] = int(len(metrics))
        src["compound_slopes_fuel_corrected_stints"] = n_fuel
        src["compound_slopes_track_evolution_corrected"] = use_evo
        src["compound_slopes_track_evolution_stints"] = n_evo
        src["compound_slopes_defaults"] = {
            k: float(DEFAULT_COMPOUND_SLOPE[k]) for k in ("SOFT", "MEDIUM", "HARD")
        }
        src["compound_slopes_fitted_pre_sanity"] = {
            k: round(float(slopes.get(k, DEFAULT_COMPOUND_SLOPE[k])), 4)
            for k in ("SOFT", "MEDIUM", "HARD")
        }
        src["compound_slopes_used_global_fallback"] = used_defaults
        src["compound_slopes_fit_utc"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        doc["source"] = src
        _YAML.write_text(
            yaml.safe_dump(doc, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        print(f"\nUpdated {_YAML} with compound_slopes={dry}", flush=True)
    else:
        print("\n(dry run — pass --write to update netherlands.yaml)", flush=True)
        if _in_event_window():
            print(
                "(event window active: --write also needs --allow-live-write)",
                flush=True,
            )
        print(f"would write compound_slopes={dry}", flush=True)


if __name__ == "__main__":
    main()
