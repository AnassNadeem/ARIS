"""Calibrate per-circuit MEDIUM vs HARD fresh-pace offsets (T9.2).

Uses 2024–2025 dry race stints (not FP2). For each stint, take the first 3
green-flag clean laps and their median. Group by circuit × compound.

Usage:
  python scripts/analyze_circuit_compound_offsets.py
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

_FRESH = _ROOT / "scripts" / "analyze_fresh_compound_pace.py"
_spec = importlib.util.spec_from_file_location("analyze_fresh_compound_pace", _FRESH)
_fresh = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_fresh)

from aris.physics.tires import (  # noqa: E402
    COMPOUND_PACE_OFFSET,
    _normalize_circuit_key,
)

_IDENTITY_CIRCUITS = frozenset({"netherlands"})
_MIN_STINTS = 3
_LO = -0.50
_HI = -0.20


def _suggest_medium(delta: float) -> float:
    if not np.isfinite(delta):
        return float(COMPOUND_PACE_OFFSET["MEDIUM"])
    clipped = min(_HI, max(_LO, float(delta)))
    return round(clipped * 20.0) / 20.0


def _circuit_table(frame: pd.DataFrame, *, later_only: bool) -> pd.DataFrame:
    work = frame[~frame["opening_stint"].astype(bool)] if later_only else frame
    rows: list[dict] = []
    for circuit, grp in work.groupby("circuit_id"):
        by_c = grp.groupby("compound")["median_fresh_s"].median()
        n_h = int((grp["compound"] == "HARD").sum())
        n_m = int((grp["compound"] == "MEDIUM").sum())
        median_h = float(by_c["HARD"]) if "HARD" in by_c else float("nan")
        median_m = float(by_c["MEDIUM"]) if "MEDIUM" in by_c else float("nan")
        delta = median_m - median_h if np.isfinite(median_h) and np.isfinite(median_m) else float("nan")
        rows.append(
            {
                "circuit_id": str(circuit),
                "key": _normalize_circuit_key(str(circuit)),
                "median_fresh_h": median_h,
                "median_fresh_m": median_m,
                "delta_medium": delta,
                "n_hard": n_h,
                "n_medium": n_m,
                "enough": n_h >= _MIN_STINTS and n_m >= _MIN_STINTS and np.isfinite(delta),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("circuit_id")


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate CIRCUIT_MEDIUM_OFFSET")
    parser.add_argument("--years", type=int, nargs="+", default=[2024, 2025])
    parser.add_argument(
        "--source",
        choices=["auto", "db", "fastf1"],
        default="auto",
    )
    args = parser.parse_args()

    frame = pd.DataFrame()
    source = args.source
    if source in {"auto", "db"}:
        try:
            print("Loading 2024–2025 dry races from DB ...", flush=True)
            frame = _fresh._load_from_db(list(args.years))
        except Exception as exc:  # noqa: BLE001
            print(f"DB load failed: {exc!r}", flush=True)
            if source == "db":
                return 1
            frame = pd.DataFrame()
    if frame.empty and source in {"auto", "fastf1"}:
        print("Loading 2024–2025 dry races from FastF1 ...", flush=True)
        frame = _fresh._load_from_fastf1(list(args.years))
    if frame.empty:
        print("No fresh-stint rows — cannot calibrate.", flush=True)
        return 1

    print(f"\nStints with 3 clean green laps: {len(frame)}", flush=True)

    later = _circuit_table(frame, later_only=True)
    all_stints = _circuit_table(frame, later_only=False)

    print("\nLater stints only (similar fuel, preferred):", flush=True)
    print(
        "| Circuit | key | median_fresh_H | median_fresh_M | delta_MEDIUM | n_H | n_M |",
        flush=True,
    )
    print("|---|---|---:|---:|---:|---:|---:|", flush=True)
    for rec in later.itertuples(index=False):
        h = f"{rec.median_fresh_h:.3f}" if np.isfinite(rec.median_fresh_h) else "n/a"
        m = f"{rec.median_fresh_m:.3f}" if np.isfinite(rec.median_fresh_m) else "n/a"
        d = f"{rec.delta_medium:+.3f}" if np.isfinite(rec.delta_medium) else "n/a"
        print(
            f"| {rec.circuit_id} | {rec.key} | {h} | {m} | {d} | "
            f"{rec.n_hard} | {rec.n_medium} |",
            flush=True,
        )

    print("\nSuggested CIRCUIT_MEDIUM_OFFSET (later-stint, clipped -0.50..-0.20):", flush=True)
    print("  # Netherlands omitted to protect Zandvoort identity.", flush=True)
    print(
        "  # Positive raw delta (MEDIUM slower when fresh) is treated as",
        flush=True,
    )
    print(
        "  # confounded later-stint mix — do not copy into a weaker offset.",
        flush=True,
    )
    suggested: dict[str, float] = {}
    for rec in later.itertuples(index=False):
        if not rec.enough:
            continue
        if rec.key in _IDENTITY_CIRCUITS:
            print(
                f"  # skip {rec.key}: identity circuit (delta={rec.delta_medium:+.3f})",
                flush=True,
            )
            continue
        if not np.isfinite(rec.delta_medium) or rec.delta_medium >= 0:
            print(
                f"  # skip {rec.key}: later-stint MEDIUM not faster "
                f"(delta={rec.delta_medium:+.3f}); keep global or strategy prior",
                flush=True,
            )
            continue
        offset = _suggest_medium(float(rec.delta_medium))
        suggested[rec.key] = offset
        print(
            f'  "{rec.key}": {offset:+.2f},  # n_H={rec.n_hard} n_M={rec.n_medium} '
            f"raw={rec.delta_medium:+.3f}",
            flush=True,
        )

    # Fall back to all-stint deltas when later-stint is too sparse.
    later_keys = set(later.loc[later["enough"], "key"]) if not later.empty else set()
    extra = []
    for rec in all_stints.itertuples(index=False):
        if rec.key in later_keys or rec.key in suggested or rec.key in _IDENTITY_CIRCUITS:
            continue
        if not rec.enough:
            continue
        extra.append(rec)
    if extra:
        print("\nAll-stint fallback (later-stint too sparse, MEDIUM faster only):", flush=True)
        for rec in extra:
            if not np.isfinite(rec.delta_medium) or rec.delta_medium >= 0:
                continue
            offset = _suggest_medium(float(rec.delta_medium))
            suggested[rec.key] = offset
            print(
                f'  "{rec.key}": {offset:+.2f},  # n_H={rec.n_hard} n_M={rec.n_medium} '
                f"raw={rec.delta_medium:+.3f}",
                flush=True,
            )

    miss_priors = {
        "bahrain": -0.35,
        "austria": -0.35,
        "qatar": -0.35,
        "mexico": -0.35,
    }
    print("\nStrategy priors for T9.1 long-MEDIUM misses (not later-stint medians):", flush=True)
    print("  # Spain omitted: MEDIUM must stay slower than SOFT (-0.40) on short finals.", flush=True)
    for key, offset in miss_priors.items():
        print(f'  "{key}": {offset:+.2f},', flush=True)

    fallback = float(COMPOUND_PACE_OFFSET["MEDIUM"])
    print(f"\nFallback (no/insufficient data): {fallback:+.2f}", flush=True)
    print(f"Circuits with a suggested override: {len(suggested)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
