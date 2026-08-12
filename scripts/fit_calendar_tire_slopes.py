"""Calendar-wide per-track compound degradation slopes (Phase E3.2 / E2.3).

Race DegSlope fits are fuel-corrected; practice/sprint left raw for fuel.
E3.1 root cause: stints now split on pit-outs / FastF1 Stint (not compound
alone), and DegSlope fits use clean green-flag laps only. Track-evolution
and matched early-window fits were tested and did NOT broadly restore
ordering — not applied here.

Per track: fit → SOFT > MEDIUM > HARD sanity check → ship fitted slopes or
fall back to DEFAULT_COMPOUND_SLOPE for that track only. Failed fits are
recorded under source.compound_slopes_fitted_pre_sanity for audit.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
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
from aris.physics.deg_corrections import detrend_fuel_pace  # noqa: E402
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
_TRACKS = _ROOT / "data" / "tracks"
_MIN_LONG_RUN_LAPS = 5
# Per-stint DegSlope clip before pooling (drop SC/traffic outliers).
_SLOPE_CLIP = (-0.5, 1.0)
# Fitted dry-compound magnitude band. Outside this → fallback even if ordering
# holds (Bahrain first-pass SOFT=0.70 was ordered but physically absurd).
_FITTED_SLOPE_MIN = 0.0
_FITTED_SLOPE_MAX = 0.25
_SESSIONS = ("FP2", "FP1", "S", "R")
_RACE_SESSION_TYPES = frozenset({"R"})
_YEARS = tuple(range(2018, 2026))  # 2018–2025 inclusive

# FastF1 get_session GP arg + yaml stem. Skip one-off / historical-only where
# long-run tyre data is not useful for the modern calendar demo.
_CIRCUITS: list[dict[str, object]] = [
    {"gp": "Bahrain", "stem": "bahrain", "years": _YEARS},
    {"gp": "Saudi Arabia", "stem": "saudi_arabia", "years": (2021, 2022, 2023, 2024, 2025)},
    {"gp": "Australia", "stem": "australia", "years": (2018, 2019, 2022, 2023, 2024, 2025)},
    {"gp": "Japan", "stem": "japan", "years": (2018, 2019, 2022, 2023, 2024, 2025)},
    {"gp": "China", "stem": "china", "years": (2018, 2019, 2024, 2025)},
    {"gp": "Miami", "stem": "miami", "years": (2022, 2023, 2024, 2025)},
    {"gp": "Emilia Romagna", "stem": "imola", "years": (2020, 2021, 2022, 2024, 2025)},
    {"gp": "Monaco", "stem": "monaco", "years": _YEARS},
    {"gp": "Canada", "stem": "canada", "years": (2018, 2019, 2022, 2023, 2024, 2025)},
    {"gp": "Spain", "stem": "spain", "years": _YEARS},
    {"gp": "Austria", "stem": "austria", "years": _YEARS},
    {"gp": "Britain", "stem": "britain", "years": _YEARS},
    {"gp": "Hungary", "stem": "hungary", "years": _YEARS},
    {"gp": "Belgium", "stem": "belgium", "years": _YEARS},
    {"gp": "Netherlands", "stem": "netherlands", "years": (2021, 2022, 2023, 2024, 2025)},
    {"gp": "Italy", "stem": "italy", "years": _YEARS},
    {"gp": "Azerbaijan", "stem": "azerbaijan", "years": (2018, 2019, 2021, 2022, 2023, 2024, 2025)},
    {"gp": "Singapore", "stem": "singapore", "years": (2018, 2019, 2022, 2023, 2024, 2025)},
    {"gp": "United States", "stem": "usa", "years": (2018, 2019, 2021, 2022, 2023, 2024, 2025)},
    {"gp": "Mexico City", "stem": "mexico", "years": (2018, 2019, 2021, 2022, 2023, 2024, 2025)},
    {"gp": "Sao Paulo", "stem": "brazil", "years": (2018, 2019, 2021, 2022, 2023, 2024, 2025)},
    {"gp": "Las Vegas", "stem": "las_vegas", "years": (2023, 2024, 2025)},
    {"gp": "Qatar", "stem": "qatar", "years": (2021, 2023, 2024, 2025)},
    {"gp": "Abu Dhabi", "stem": "abu_dhabi", "years": _YEARS},
]


def _load(year: int, gp: str, session_type: str):
    attempts = 0
    while True:
        attempts += 1
        try:
            session = fastf1.get_session(year, gp, session_type)
            session.load(laps=True, telemetry=False, weather=False, messages=False)
            return session
        except RateLimitExceededError:
            # Prefer a long single wait over many short retries that burn the hour.
            wait_s = 900 if attempts == 1 else min(1800, 900 * attempts)
            print(f"  rate-limited {year} {gp} {session_type}; sleep {wait_s}s", flush=True)
            time.sleep(wait_s)
            if attempts >= 3:
                raise


def _ordering_ok(slopes: dict[str, float]) -> bool:
    soft = float(slopes.get("SOFT", float("nan")))
    med = float(slopes.get("MEDIUM", float("nan")))
    hard = float(slopes.get("HARD", float("nan")))
    if not all(np.isfinite(v) for v in (soft, med, hard)):
        return False
    return soft > med > hard


def _magnitude_ok(slopes: dict[str, float]) -> bool:
    """Reject absurd fitted means (wet/SC contamination masquerading as dry deg)."""
    for key in ("SOFT", "MEDIUM", "HARD"):
        v = float(slopes.get(key, float("nan")))
        if not np.isfinite(v):
            return False
        if v <= _FITTED_SLOPE_MIN or v > _FITTED_SLOPE_MAX:
            return False
    return True


def _sanity_ok(slopes: dict[str, float]) -> tuple[bool, str]:
    if not _ordering_ok(slopes):
        return False, (
            f"ordering failed (SOFT={slopes.get('SOFT')}, MEDIUM={slopes.get('MEDIUM')}, "
            f"HARD={slopes.get('HARD')}; need SOFT > MEDIUM > HARD)"
        )
    if not _magnitude_ok(slopes):
        return False, (
            f"magnitude failed (SOFT={slopes.get('SOFT')}, MEDIUM={slopes.get('MEDIUM')}, "
            f"HARD={slopes.get('HARD')}; need ({_FITTED_SLOPE_MIN}, {_FITTED_SLOPE_MAX}])"
        )
    return True, "ok"


def _sessions_for_event(year: int, gp: str, *, race_only: bool = False) -> list[str]:
    """Prefer FP2+R; on sprint weekends (no FP2) fall back to FP1+S+R.

    Avoids probing every session type (each miss still burns FastF1 schedule calls).
    ``race_only`` skips practice entirely (rate-limit recovery path).
    """
    if race_only:
        return ["R"]
    # Lightweight schedule peek — cached by FastF1 after first hit.
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


def collect_metrics(
    gp: str,
    years: tuple[int, ...],
    *,
    min_laps: int,
    stem: str | None = None,
    reuse_csv: bool = False,
    race_only: bool = False,
) -> pd.DataFrame:
    if reuse_csv and stem:
        cached = _ROOT / "results" / "e3_2_deg_stints" / f"{stem}.csv"
        if not cached.exists():
            cached = _ROOT / "results" / "e2_3_deg_stints" / f"{stem}.csv"
        if cached.exists():
            print(f"  Reusing cached stints {cached}", flush=True)
            return pd.read_csv(cached)
    rows: list[pd.DataFrame] = []
    for year in years:
        session_order = _sessions_for_event(year, gp, race_only=race_only)
        for stype in session_order:
            print(f"  Loading {year} {gp} {stype} ...", flush=True)
            try:
                session = _load(year, gp, stype)
            except Exception as exc:  # noqa: BLE001
                print(f"    SKIP: {exc!r}", flush=True)
                continue
            try:
                enriched = detect_stints(session.laps)
            except Exception as exc:  # noqa: BLE001 — DataNotLoadedError etc.
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
            metrics["SessionType"] = stype
            metrics["SessionKey"] = f"{year}-{stype}"
            metrics["FuelCorrected"] = fuel_corrected
            metrics["Compound"] = metrics["Compound"].map(normalize_compound)
            print(
                f"    stints={len(metrics)} compounds={sorted(metrics['Compound'].unique())}",
                flush=True,
            )
            rows.append(metrics)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def fit_one(
    gp: str,
    stem: str,
    years: tuple[int, ...],
    *,
    min_laps: int,
    reuse_csv: bool = False,
    race_only: bool = False,
) -> dict:
    print(f"\n=== {gp} ({stem}) years={list(years)} ===", flush=True)
    metrics = collect_metrics(
        gp,
        years,
        min_laps=min_laps,
        stem=stem,
        reuse_csv=reuse_csv,
        race_only=race_only,
    )
    yaml_path = _TRACKS / f"{stem}.yaml"
    if metrics.empty:
        print("  NO DATA — leave YAML unchanged (implicit global defaults)", flush=True)
        return {
            "gp": gp,
            "stem": stem,
            "n_stints": 0,
            "fitted": None,
            "shipped": {k: float(DEFAULT_COMPOUND_SLOPE[k]) for k in ("SOFT", "MEDIUM", "HARD")},
            "ordering_ok": False,
            "used_fallback": True,
            "reason": "no_long_run_data",
            "wrote": False,
        }

    slopes = fit_track_compound_slopes(metrics)
    dry = {k: round(float(slopes.get(k, DEFAULT_COMPOUND_SLOPE[k])), 4) for k in ("SOFT", "MEDIUM", "HARD")}
    for k in ("SOFT", "MEDIUM", "HARD"):
        dry.setdefault(k, round(float(DEFAULT_COMPOUND_SLOPE[k]), 4))
    fitted_pre = dict(dry)
    ok, reason = _sanity_ok(dry)
    used_fallback = False
    if not ok:
        used_fallback = True
        print(f"  FALLBACK: {reason}", flush=True)
        dry = {k: round(float(DEFAULT_COMPOUND_SLOPE[k]), 4) for k in ("SOFT", "MEDIUM", "HARD")}
    else:
        print(
            f"  Sanity OK: SOFT={dry['SOFT']} > MED={dry['MEDIUM']} > HARD={dry['HARD']}",
            flush=True,
        )

    n_fuel = int(metrics["FuelCorrected"].sum())
    return {
        "gp": gp,
        "stem": stem,
        "n_stints": int(len(metrics)),
        "n_fuel_corrected": n_fuel,
        "years_requested": list(years),
        "years_seen": sorted(int(y) for y in metrics["Year"].unique()),
        "fitted": fitted_pre,
        "shipped": dry,
        "ordering_ok": _ordering_ok(fitted_pre),
        "magnitude_ok": _magnitude_ok(fitted_pre),
        "sanity_ok": ok,
        "used_fallback": used_fallback,
        "reason": reason if used_fallback else "fitted_ok",
        "yaml_path": str(yaml_path),
        "metrics": metrics,
    }


def write_yaml(result: dict, *, min_laps: int) -> None:
    path = Path(result["yaml_path"])
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    dry = result["shipped"]
    doc["compound_slopes"] = dry
    src = dict(doc.get("source") or {})
    if result["used_fallback"]:
        src["compound_slopes_method"] = (
            "FALLBACK to DEFAULT_COMPOUND_SLOPE after fuel-corrected DegSlope fit "
            f"failed sanity ({result.get('reason')}; E3.2; FP2+R long runs "
            f"NumLaps>={min_laps}, DegSlope in {_SLOPE_CLIP}; Race fuel detrend; "
            "stint split on FastF1 Stint/pit-out; clean-lap DegSlope; "
            f"fitted magnitude must be in ({_FITTED_SLOPE_MIN}, {_FITTED_SLOPE_MAX}])"
        )
    else:
        src["compound_slopes_method"] = (
            "session-level inverse-variance pool of fuel-corrected DegSlope "
            f"(E3.2; FP2+R long runs NumLaps>={min_laps}, DegSlope in {_SLOPE_CLIP}; "
            "Race LapTimeS -= FUEL_PENALTY*estimate_fuel_kg; "
            "stint split on FastF1 Stint/pit-out; clean-lap DegSlope fit)"
        )
    src["compound_slopes_n_stints"] = result["n_stints"]
    src["compound_slopes_fuel_corrected_stints"] = result.get("n_fuel_corrected", 0)
    src["compound_slopes_track_evolution_corrected"] = False
    src["compound_slopes_clean_lap_fit"] = True
    src["compound_slopes_pit_split"] = True
    src["compound_slopes_defaults"] = {
        k: float(DEFAULT_COMPOUND_SLOPE[k]) for k in ("SOFT", "MEDIUM", "HARD")
    }
    src["compound_slopes_fitted_pre_sanity"] = result["fitted"]
    src["compound_slopes_used_global_fallback"] = result["used_fallback"]
    src["compound_slopes_fit_utc"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    doc["source"] = src
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"  Wrote {path} compound_slopes={dry}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Update track YAMLs")
    parser.add_argument("--min-laps", type=int, default=_MIN_LONG_RUN_LAPS)
    parser.add_argument("--only", nargs="*", help="Optional GP name filter")
    parser.add_argument(
        "--reuse-stints-csv",
        action="store_true",
        help="Reuse results/e2_3_deg_stints/<stem>.csv when present (skip FastF1 reload)",
    )
    parser.add_argument(
        "--race-only",
        action="store_true",
        help="Only load Race sessions (rate-limit recovery / faster path)",
    )
    args = parser.parse_args()

    fastf1.Cache.enable_cache(str(_CACHE))
    targets = _CIRCUITS
    if args.only:
        want = {x.lower() for x in args.only}
        targets = [c for c in _CIRCUITS if str(c["gp"]).lower() in want or str(c["stem"]).lower() in want]
        if not targets:
            raise SystemExit(f"no circuits matched --only {args.only}")

    report: list[dict] = []
    for circ in targets:
        gp = str(circ["gp"])
        stem = str(circ["stem"])
        years = tuple(int(y) for y in circ["years"])  # type: ignore[arg-type]
        result = fit_one(
            gp,
            stem,
            years,
            min_laps=args.min_laps,
            reuse_csv=args.reuse_stints_csv,
            race_only=args.race_only,
        )
        metrics = result.pop("metrics", None)
        if metrics is not None and not getattr(metrics, "empty", True):
            out_csv = _ROOT / "results" / "e3_2_deg_stints" / f"{stem}.csv"
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            metrics.to_csv(out_csv, index=False)
            result["stints_csv"] = str(out_csv)
        if args.write and result.get("yaml_path") and result["n_stints"] > 0:
            write_yaml(result, min_laps=args.min_laps)
            result["wrote"] = True
        else:
            result["wrote"] = False
        report.append(result)

    out_json = _ROOT / "results" / "e3_2_tire_slopes_report.json"
    # Drop non-serializable leftovers
    serializable = []
    for r in report:
        serializable.append({k: v for k, v in r.items() if k != "metrics"})
    out_json.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"\nWrote {out_json}", flush=True)

    print("\nSUMMARY", flush=True)
    print(
        f"{'GP':<18} {'n':>5} {'SOFT':>8} {'MED':>8} {'HARD':>8} {'ok':>5} {'ship':>10}",
        flush=True,
    )
    for r in report:
        fit = r.get("fitted") or {}
        print(
            f"{r['gp']:<18} {r['n_stints']:5d} "
            f"{fit.get('SOFT', float('nan')):8.4f} "
            f"{fit.get('MEDIUM', float('nan')):8.4f} "
            f"{fit.get('HARD', float('nan')):8.4f} "
            f"{'Y' if r.get('sanity_ok') else 'N':>5} "
            f"{'fitted' if not r['used_fallback'] else 'fallback':>10}",
            flush=True,
        )
    n_ok = sum(1 for r in report if r.get("sanity_ok"))
    n_fb = sum(1 for r in report if r["used_fallback"])
    print(f"\nsanity_ok={n_ok}/{len(report)}  fallback={n_fb}/{len(report)}", flush=True)
    if not args.write:
        print("(dry run — pass --write to update YAMLs)", flush=True)


if __name__ == "__main__":
    main()
