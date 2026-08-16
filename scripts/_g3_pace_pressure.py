"""G3.3 — do harder-compound stints happen in lower traffic pressure?

Uses existing DB laps (compound, stint, lap_time_s) plus the same cumulative-time
gap construction RaceState already uses. No new ingest.

  python scripts/_g3_pace_pressure.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from aris.eval.backtest import resolve_calendar  # noqa: E402
from aris.io import db  # noqa: E402
from aris.physics.compounds import join_compound_identity, lookup_nomination  # noqa: E402
from aris.physics.traffic import gaps_from_db_laps  # noqa: E402

_OUT = _ROOT / "results" / "g3" / "pace_pressure.json"
_NEAR_S = 1.5
_FREE_S = 2.0
_DRY = ("SOFT", "MEDIUM", "HARD")
_HARDNESS = ("C1", "C2", "C3", "C4", "C5", "C6")


def _gaps_at_completed_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """G3.3 construction — implemented in ``aris.physics.traffic`` (reused by G4)."""
    return gaps_from_db_laps(laps)


def _summarise(frame: pd.DataFrame, col: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    clean = frame[(~frame["pit"]) & (~frame["sc"]) & frame["min_nearby_s"].notna()]
    for key, grp in clean.groupby(col):
        nearby = grp["min_nearby_s"].to_numpy(dtype=float)
        ahead = grp["gap_ahead_s"].dropna().to_numpy(dtype=float)
        behind = grp["gap_behind_s"].dropna().to_numpy(dtype=float)
        out[str(key)] = {
            "n_laps": int(len(grp)),
            "median_min_nearby_s": float(np.median(nearby)) if len(nearby) else None,
            "median_gap_ahead_s": float(np.median(ahead)) if len(ahead) else None,
            "median_gap_behind_s": float(np.median(behind)) if len(behind) else None,
            "frac_free_air_ge_2s": float(np.mean(nearby >= _FREE_S)) if len(nearby) else None,
            "frac_battle_lt_1_5s": float(np.mean(nearby < _NEAR_S)) if len(nearby) else None,
        }
    return out


def main() -> int:
    calendars: list[dict[str, Any]] = []
    for year in (2024, 2025):
        calendars.extend(resolve_calendar(year))

    rel_frames: list[pd.DataFrame] = []
    ident_frames: list[pd.DataFrame] = []
    for meta in calendars:
        print(f"  {meta['year']} {meta['gp']} ...", flush=True)
        laps = db.fetch_all_laps(int(meta["session_id"]))
        if laps.empty:
            continue
        gaps = _gaps_at_completed_laps(laps)
        if gaps.empty:
            continue
        gaps["year"] = int(meta["year"])
        gaps["gp"] = meta["gp"]
        rel_frames.append(gaps)
        nom = lookup_nomination(int(meta["year"]), str(meta["gp"]), round_no=int(meta["round_no"]))
        if nom is None:
            continue
        ident = gaps.copy()
        ident["Compound"] = ident["compound"]
        ident = join_compound_identity(
            ident, year=int(meta["year"]), event=str(meta["gp"]), round_no=int(meta["round_no"])
        )
        ident_frames.append(ident)

    rel = pd.concat(rel_frames, ignore_index=True) if rel_frames else pd.DataFrame()
    ident = pd.concat(ident_frames, ignore_index=True) if ident_frames else pd.DataFrame()

    relative = _summarise(rel[rel["compound"].isin(_DRY)], "compound") if not rel.empty else {}
    c_code = {}
    if not ident.empty and "CompoundIdentity" in ident.columns:
        c_code = _summarise(
            ident[ident["CompoundIdentity"].isin(_HARDNESS)],
            "CompoundIdentity",
        )

    # Stint-level: median min_nearby per stint, then by compound.
    stint_rel: dict[str, Any] = {}
    if not rel.empty:
        clean = rel[(~rel["pit"]) & (~rel["sc"]) & rel["min_nearby_s"].notna()]
        clean = clean[clean["compound"].isin(_DRY)]
        st = (
            clean.groupby(["year", "gp", "driver_id", "stint", "compound"], dropna=False)[
                "min_nearby_s"
            ]
            .median()
            .reset_index()
        )
        for compound, grp in st.groupby("compound"):
            stint_rel[str(compound)] = {
                "n_stints": int(len(grp)),
                "median_stint_min_nearby_s": float(grp["min_nearby_s"].median()),
                "frac_stints_free_air_ge_2s": float((grp["min_nearby_s"] >= _FREE_S).mean()),
            }

    def _hold(harder: dict | None, softer: dict | None, key: str) -> bool | None:
        if not harder or not softer:
            return None
        h, s = harder.get(key), softer.get(key)
        if h is None or s is None:
            return None
        return bool(h > s)

    holds_relative = {
        "HARD_median_nearby_gt_SOFT": _hold(relative.get("HARD"), relative.get("SOFT"), "median_min_nearby_s"),
        "HARD_median_nearby_gt_MEDIUM": _hold(relative.get("HARD"), relative.get("MEDIUM"), "median_min_nearby_s"),
        "HARD_free_air_gt_SOFT": _hold(relative.get("HARD"), relative.get("SOFT"), "frac_free_air_ge_2s"),
        "HARD_free_air_gt_MEDIUM": _hold(relative.get("HARD"), relative.get("MEDIUM"), "frac_free_air_ge_2s"),
    }
    c1 = c_code.get("C1")
    c5 = c_code.get("C5") or c_code.get("C6")
    holds_identity = {
        "C1_median_nearby_gt_softest": _hold(c1, c5, "median_min_nearby_s"),
        "C1_free_air_gt_softest": _hold(c1, c5, "frac_free_air_ge_2s"),
        "softest_code": "C5" if "C5" in c_code else ("C6" if "C6" in c_code else None),
    }

    report = {
        "n_races": len(calendars),
        "n_gap_laps": int(len(rel)),
        "near_s": _NEAR_S,
        "free_s": _FREE_S,
        "by_relative_compound": relative,
        "by_c_code": c_code,
        "stint_level_relative": stint_rel,
        "holds_relative": holds_relative,
        "holds_identity": holds_identity,
        "verdict": (
            "HARDER compounds run in larger gaps / more free air than SOFT"
            if holds_relative.get("HARD_median_nearby_gt_SOFT")
            and holds_relative.get("HARD_free_air_gt_SOFT")
            else "NOT confirmed: harder compounds are not systematically in lower-pressure air"
        ),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str), flush=True)
    print(f"Wrote {_OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
