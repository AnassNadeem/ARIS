"""Fit the G4 pooled context-aware tyre degradation GBT.

E3.2 data prep (fuel-corrected race laps, Stint/pit-out split, green-flag
filter, drop first lap of stint). One pooled XGBoost across mapped C-codes.
Hyperparameters by LORO on pre-2024 events only — never the 2024 held-out.

  python scripts/fit_pooled_deg.py
  python scripts/fit_pooled_deg.py --write
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

import fastf1  # noqa: E402
from fastf1.exceptions import RateLimitExceededError  # noqa: E402

from aris.models.pooled_deg import (  # noqa: E402
    C_CODES,
    DEFAULT_MODEL_PATH,
    ERAS,
    FEATURE_COLS,
    NUM_COLS,
    PooledDegModel,
    SLOPE_LIFE_HI,
    SLOPE_LIFE_LO,
    build_session_frame,
    enable_fastf1_cache,
    monotonicity_at_context,
    tune_hyperparams,
)
from aris.physics.compounds import (  # noqa: E402
    all_nominations,
    clear_compound_caches,
    pooled_event_key,
)
from aris.tracks import clear_track_config_cache, n_corners_for_event  # noqa: E402

_CACHE = _ROOT / "fastf1_cache"
_CSV = _ROOT / "results" / "g4" / "pooled_deg_laps.csv"
_REPORT = _ROOT / "results" / "g4" / "pooled_deg_report.json"
_SHIPPED = _ROOT / "data" / "compounds" / "true_compound_slopes_pooled.json"
_RACE_SESSION_TYPES = frozenset({"R"})


def _load(year: int, gp: str, session_type: str):
    want_weather = True
    while True:
        try:
            session = fastf1.get_session(year, gp, session_type)
            session.load(laps=True, telemetry=False, weather=want_weather, messages=False)
            return session
        except RateLimitExceededError:
            if want_weather:
                print(
                    f"  weather rate-limited {year} {gp} {session_type} — loading laps without weather",
                    flush=True,
                )
                want_weather = False
                continue
            print(
                f"  rate-limited {year} {gp} {session_type} — skip session",
                flush=True,
            )
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


def collect_frames(noms, *, min_year: int | None = None) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    checkpoint = _ROOT / "results" / "g4" / "pooled_deg_laps_collecting.csv"
    for nom in noms:
        if min_year is not None and nom.year < min_year:
            continue
        print(
            f"\n=== {nom.year} {nom.event} r{nom.round} {nom.hard}/{nom.medium}/{nom.soft} ===",
            flush=True,
        )
        for stype in _sessions_for_event(nom.year, nom.event):
            print(f"  Loading {nom.year} {nom.event} {stype} ...", flush=True)
            try:
                session = _load(nom.year, nom.event, stype)
            except Exception as exc:  # noqa: BLE001
                print(f"    SKIP: {exc!r}", flush=True)
                continue
            try:
                frame = build_session_frame(
                    session,
                    year=nom.year,
                    event=nom.event,
                    session_type=stype,
                    round_no=nom.round,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"    SKIP frame: {exc!r}", flush=True)
                continue
            if frame.empty:
                print("    empty frame", flush=True)
                continue
            print(
                f"    laps={len(frame)} codes={sorted(frame['compound_id'].dropna().unique())} "
                f"weather={int(frame['air_temp_c'].notna().sum())}/{len(frame)} "
                f"gap={int(frame['gap_to_nearest_s'].notna().sum())}/{len(frame)}",
                flush=True,
            )
            rows.append(frame)
        if rows:
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            pd.concat(rows, ignore_index=True).to_csv(checkpoint, index=False)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def _event_context(frame: pd.DataFrame) -> dict[str, float]:
    ctx: dict[str, float] = {}
    for col in NUM_COLS:
        if col == "tyre_life" or col not in frame.columns:
            continue
        vals = pd.to_numeric(frame[col], errors="coerce")
        if vals.notna().any():
            ctx[col] = float(vals.median())
    return ctx


def _era_slopes(model: PooledDegModel, era: str, context: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for code in C_CODES:
        try:
            out[code] = round(float(model.slope_at_context(code, era, context)), 4)
        except Exception:  # noqa: BLE001
            continue
    return out


def zandvoort_check(era_slopes: dict[str, dict[str, float]]) -> dict:
    from aris.physics.compounds import lookup_nomination

    out: dict = {}
    for year in (2021, 2022, 2023, 2024, 2025, 2026):
        nom = lookup_nomination(year, "Netherlands")
        if nom is None:
            out[str(year)] = {"mapped": False}
            continue
        fitted = era_slopes.get(nom.era) or {}
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
    parser.add_argument("--reuse-laps-csv", action="store_true")
    parser.add_argument(
        "--append-years",
        type=int,
        nargs="*",
        help="Collect these years and merge into the existing laps CSV",
    )
    parser.add_argument("--skip-tune", action="store_true", help="Use residual default knobs")
    parser.add_argument("--collect-only", action="store_true", help="Stop after writing the laps CSV")
    parser.add_argument("--year", type=int, nargs="*")
    args = parser.parse_args()

    enable_fastf1_cache(_CACHE)
    noms = all_nominations()
    if args.year:
        want = set(args.year)
        noms = [n for n in noms if n.year in want]
    elif args.append_years:
        want = set(args.append_years)
        noms = [n for n in noms if n.year in want]

    if args.reuse_laps_csv and _CSV.exists() and not args.append_years:
        print(f"Reusing {_CSV}", flush=True)
        frame = pd.read_csv(_CSV, dtype={"era": str, "compound_id": str, "event": str})
    else:
        collected = collect_frames(noms)
        if args.append_years and _CSV.exists():
            old = pd.read_csv(_CSV, dtype={"era": str, "compound_id": str, "event": str})
            drop_years = set(args.append_years)
            old = old[~old["year"].isin(drop_years)]
            parts = [old]
            if not collected.empty:
                parts.append(collected)
            frame = pd.concat(parts, ignore_index=True)
            print(
                f"Merged years {sorted(drop_years)} into CSV: n={len(frame)} "
                f"(kept {len(old)} prior rows)",
                flush=True,
            )
        else:
            frame = collected
        if frame.empty:
            print("NO DATA", flush=True)
            sys.exit(1)
        _CSV.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(_CSV, index=False)
        print(f"Wrote {_CSV} n={len(frame)}", flush=True)

    pre2024 = frame[frame["year"] < 2024].copy()
    print(
        f"\nFrame n={len(frame)} events={frame['event_id'].nunique()} "
        f"pre2024 n={len(pre2024)} events={pre2024['event_id'].nunique()}",
        flush=True,
    )
    print(f"  by code: {frame.groupby('compound_id').size().to_dict()}", flush=True)
    print(f"  by era: {frame.groupby('era').size().to_dict()}", flush=True)

    if args.collect_only:
        print("collect-only: stopping before LORO/fit", flush=True)
        return

    if args.skip_tune or pre2024["event_id"].nunique() < 3:
        best = {"max_depth": 4, "eta": 0.1, "num_boost_round": 80, "cv_mae_mean": None, "note": "default knobs"}
        tune_rows: list = []
        print("Skipping LORO tune (flag or too few pre-2024 events)", flush=True)
    else:
        best, tune_rows = tune_hyperparams(pre2024)
        # Drop extra keys that aren't booster knobs.
        best = {
            "max_depth": int(best["max_depth"]),
            "eta": float(best["eta"]),
            "num_boost_round": int(best["num_boost_round"]),
            "cv_mae_mean": float(best["cv_mae_mean"]),
            "cv_mae_std": float(best.get("cv_mae_std") or 0.0),
        }

    params = {"max_depth": int(best["max_depth"]), "eta": float(best["eta"]), "seed": 42}
    model = PooledDegModel(xgb_params=params, num_boost_round=int(best["num_boost_round"]))
    # Final fit-all on the mapped corpus (same events G2 pooled). LORO already
    # chose knobs on pre-2024 only.
    cv = model.fit(frame, loro=False)
    model_path = model.save(DEFAULT_MODEL_PATH)
    results_model = _ROOT / "results" / "g4" / "pooled_deg_xgb.json"
    model.save(results_model)
    print(f"Saved booster {model_path} and {results_model}", flush=True)

    importances = model.feature_importances("gain")
    print("\n=== feature importances (gain, normalised) ===", flush=True)
    for k, v in importances.items():
        print(f"  {k}: {v:.4f}", flush=True)

    global_ctx = model.context_medians
    print(f"\nGlobal median context: {global_ctx}", flush=True)
    mono_reports = []
    era_slopes: dict[str, dict[str, float]] = {}
    for era in ERAS:
        if era not in set(frame["era"].astype(str)):
            continue
        rep = monotonicity_at_context(model, era, global_ctx)
        mono_reports.append(rep)
        era_slopes[era] = rep["slopes"]
        print(f"  era {era}: {rep['reason']}", flush=True)

    # Extra fixed-context probes (same confounders, vary only C-code).
    extra_contexts = {
        "free_air": {**global_ctx, "gap_to_nearest_s": 5.0},
        "traffic": {**global_ctx, "gap_to_nearest_s": 0.8},
        "hot_track": {**global_ctx, "track_temp_c": 50.0, "air_temp_c": 35.0},
        "cool_track": {**global_ctx, "track_temp_c": 20.0, "air_temp_c": 15.0},
    }
    italy_n = n_corners_for_event("Italy")
    nl_n = n_corners_for_event("Netherlands")
    if italy_n:
        extra_contexts["monza_corners"] = {**global_ctx, "n_corners": float(italy_n)}
    if nl_n:
        extra_contexts["zandvoort_corners"] = {**global_ctx, "n_corners": float(nl_n)}
    extra_mono = {}
    probe_era = "2023-2025" if "2023-2025" in era_slopes else next(iter(era_slopes), "2023-2025")
    for name, ctx in extra_contexts.items():
        extra_mono[name] = monotonicity_at_context(model, probe_era, ctx)
        print(f"  context {name}: {extra_mono[name]['reason']}", flush=True)

    # Per-event slopes at that event's own median context.
    events: dict[str, dict] = {}
    for event_id, grp in frame.groupby("event_id"):
        year = int(grp["year"].iloc[0])
        event = str(grp["event"].iloc[0])
        era = str(grp["era"].iloc[0])
        ctx = {**global_ctx, **_event_context(grp)}
        key = pooled_event_key(year, event)
        from aris.physics.compounds import lookup_nomination

        nom = lookup_nomination(year, event)
        if nom is None:
            continue
        code_slopes = _era_slopes(model, era, ctx)
        rel = {
            "HARD": code_slopes.get(nom.hard),
            "MEDIUM": code_slopes.get(nom.medium),
            "SOFT": code_slopes.get(nom.soft),
        }
        if any(v is None for v in rel.values()):
            continue
        events[key] = {
            "year": year,
            "event": nom.event,
            "round": nom.round,
            "era": era,
            "nomination": {"HARD": nom.hard, "MEDIUM": nom.medium, "SOFT": nom.soft},
            "context": ctx,
            "slopes": {k: round(float(v), 4) for k, v in rel.items()},
            "n_laps": int(len(grp)),
        }

    zv = zandvoort_check(era_slopes)
    n_by_code = {str(k): int(v) for k, v in frame.groupby("compound_id").size().items()}
    n_by_era = {str(k): int(v) for k, v in frame.groupby("era").size().items()}

    coverage = {}
    for col in (*NUM_COLS,):
        s = pd.to_numeric(frame[col], errors="coerce")
        coverage[col] = {
            "n_present": int(s.notna().sum()),
            "frac": float(s.notna().mean()) if len(s) else None,
            "median": float(s.median()) if s.notna().any() else None,
        }

    report = {
        "fit_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": (
            "G4 pooled GBT: E3.2 prep (fuel-corrected race LapTimeS, clean-lap + "
            "not-first-of-stint), target = time minus early-stint baseline; one "
            "XGBoost across mapped C-codes with compound_id + era categorical and "
            "tyre_life, weather, gap-to-nearest, n_corners, stint_position. "
            f"Slopes are finite differences at tyre_life {SLOPE_LIFE_LO}→{SLOPE_LIFE_HI}."
        ),
        "n_laps": int(len(frame)),
        "n_events": int(frame["event_id"].nunique()),
        "n_by_code": n_by_code,
        "n_by_era": n_by_era,
        "feature_cols": list(FEATURE_COLS),
        "hyperparams": best,
        "tune_rows": tune_rows,
        "final_fit": cv,
        "feature_importances_gain": importances,
        "global_context": global_ctx,
        "monotonicity_global_context": mono_reports,
        "monotonicity_extra_contexts": extra_mono,
        "coverage_on_fit_frame": coverage,
        "zandvoort": zv,
        "n_event_slopes": len(events),
    }
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {_REPORT}", flush=True)

    if args.write:
        shipped = {
            "method": report["method"],
            "fit_utc": report["fit_utc"],
            "hyperparams": best,
            "feature_importances_gain": importances,
            "life_window": [SLOPE_LIFE_LO, SLOPE_LIFE_HI],
            "eras": {
                era: {
                    "slopes": slopes,
                    "n_laps": n_by_era.get(era, 0),
                    "monotonic_ok": next(
                        (r["monotonic_ok"] for r in mono_reports if r["era"] == era),
                        False,
                    ),
                    "reason": next(
                        (r["reason"] for r in mono_reports if r["era"] == era),
                        "",
                    ),
                    "context": global_ctx,
                }
                for era, slopes in era_slopes.items()
            },
            "events": events,
        }
        _SHIPPED.write_text(json.dumps(shipped, indent=2), encoding="utf-8")
        print(f"Wrote {_SHIPPED}", flush=True)
        clear_compound_caches()
        clear_track_config_cache()
    else:
        print("(dry run — pass --write to persist true_compound_slopes_pooled.json)", flush=True)


if __name__ == "__main__":
    main()
