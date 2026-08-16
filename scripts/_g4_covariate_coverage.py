"""G4.1 — real covariate coverage on the residual train + 2024 held-out corpus.

Does not fabricate missing weather, gaps, or corner counts. Nearest-timestamp
weather join; G3.3 gap construction; YAML corner counts (None if not genuine).

  python scripts/_g4_covariate_coverage.py
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import fastf1  # noqa: E402
from fastf1.exceptions import RateLimitExceededError  # noqa: E402

from aris.eval.laptime import HELD_OUT_RACES  # noqa: E402
from aris.models.features import estimate_fuel_kg  # noqa: E402
from aris.models.pooled_deg import (  # noqa: E402
    enable_fastf1_cache,
    join_weather_nearest,
)
from aris.models.residual import REFERENCE_RACES  # noqa: E402
from aris.physics.compounds import compound_era, join_compound_identity, lookup_nomination  # noqa: E402
from aris.physics.stint import detect_stints  # noqa: E402
from aris.physics.traffic import gaps_from_fastf1_laps  # noqa: E402
from aris.tracks import n_corners_for_event  # noqa: E402

_OUT = _ROOT / "results" / "g4" / "covariate_coverage.json"
_C_CODES = ("C1", "C2", "C3", "C4", "C5", "C6")


def _load(year: int, gp: str, session_type: str = "R"):
    attempts = 0
    while True:
        attempts += 1
        try:
            session = fastf1.get_session(year, gp, session_type)
            session.load(laps=True, telemetry=False, weather=True, messages=False)
            return session
        except RateLimitExceededError:
            wait_s = 180
            print(f"  rate-limited {year} {gp} {session_type}; sleep {wait_s}s", flush=True)
            time.sleep(wait_s)
            if attempts >= 2:
                raise


def _frac(n_ok: int, n: int) -> float | None:
    if n <= 0:
        return None
    return float(n_ok) / float(n)


def _summarise(frame: pd.DataFrame) -> dict[str, Any]:
    n = int(len(frame))
    out: dict[str, Any] = {"n_laps": n}
    for col, label in (
        ("air_temp_c", "air_temp"),
        ("track_temp_c", "track_temp"),
        ("humidity_pct", "humidity"),
        ("gap_to_nearest_s", "gap_to_nearest"),
        ("n_corners", "n_corners"),
        ("fuel_kg", "fuel"),
        ("tyre_life", "tyre_life"),
        ("stint_position", "stint_position"),
    ):
        if col not in frame.columns:
            out[label] = {"n_present": 0, "frac": None}
            continue
        present = int(frame[col].notna().sum())
        rec: dict[str, Any] = {"n_present": present, "frac": _frac(present, n)}
        if col in ("air_temp_c", "track_temp_c", "humidity_pct") and "weather_delta_s" in frame.columns:
            delta = pd.to_numeric(frame.loc[frame[col].notna(), "weather_delta_s"], errors="coerce")
            rec["median_join_abs_s"] = float(delta.median()) if len(delta) else None
            rec["frac_join_within_60s"] = (
                float((delta <= 60).mean()) if len(delta) else None
            )
            rec["frac_join_within_120s"] = (
                float((delta <= 120).mean()) if len(delta) else None
            )
        out[label] = rec
    if "compound_id" in frame.columns:
        c = frame["compound_id"]
        out["c_code_identity"] = {
            "n_present": int(c.isin(_C_CODES).sum()),
            "frac": _frac(int(c.isin(_C_CODES).sum()), n),
        }
    return out


def annotate_all_laps(session, *, year: int, gp: str) -> pd.DataFrame:
    enriched = detect_stints(session.laps)
    if enriched.empty:
        return pd.DataFrame()
    weather = getattr(session, "weather_data", None)
    work = join_weather_nearest(enriched, weather)
    gaps = gaps_from_fastf1_laps(enriched)
    if not gaps.empty:
        g = gaps.rename(columns={"LapNumber": "_gap_lap", "Driver": "_gap_drv"})
        g["_gap_lap"] = pd.to_numeric(g["_gap_lap"], errors="coerce").astype("Int64")
        work["_lap_i"] = pd.to_numeric(work["LapNumber"], errors="coerce").astype("Int64")
        work = work.merge(
            g[["_gap_drv", "_gap_lap", "min_nearby_s"]],
            left_on=["Driver", "_lap_i"],
            right_on=["_gap_drv", "_gap_lap"],
            how="left",
        )
        work["gap_to_nearest_s"] = pd.to_numeric(work["min_nearby_s"], errors="coerce")
        work = work.drop(columns=["_gap_drv", "_gap_lap", "min_nearby_s", "_lap_i"], errors="ignore")
    else:
        work["gap_to_nearest_s"] = np.nan
    n_corners = n_corners_for_event(gp)
    work["n_corners"] = n_corners if n_corners is not None else np.nan
    total_laps = int(getattr(session, "total_laps", None) or 57)
    work["fuel_kg"] = work["LapNumber"].map(
        lambda n: estimate_fuel_kg(int(n), total_laps=total_laps) if pd.notna(n) else np.nan
    )
    work["tyre_life"] = pd.to_numeric(work.get("TyreLife"), errors="coerce")
    work["stint_position"] = pd.to_numeric(work.get("StintId"), errors="coerce")
    work = join_compound_identity(work, year=year, event=gp)
    work["compound_id"] = work["CompoundIdentity"]
    work["year"] = year
    work["gp"] = gp
    work["era"] = compound_era(year)
    work["mapped"] = lookup_nomination(year, gp) is not None
    return work


def main() -> int:
    enable_fastf1_cache(_ROOT / "fastf1_cache")
    corpus = [("train", y, gp) for y, gp in REFERENCE_RACES] + [
        ("heldout", y, gp) for y, gp in HELD_OUT_RACES
    ]
    frames: list[pd.DataFrame] = []
    failed: list[str] = []
    n_weather_empty = 0
    n_ok = 0
    by_split_n = defaultdict(int)

    for i, (split, year, gp) in enumerate(corpus, start=1):
        label = f"{year} {gp}"
        print(f"[{i}/{len(corpus)}] {split} {label} ...", flush=True)
        try:
            session = _load(year, gp, "R")
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{label} ({type(exc).__name__}: {exc})")
            print(f"  FAIL {exc!r}", flush=True)
            continue
        weather = getattr(session, "weather_data", None)
        if weather is None or weather.empty:
            n_weather_empty += 1
        try:
            frame = annotate_all_laps(session, year=year, gp=gp)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{label} annotate ({type(exc).__name__}: {exc})")
            print(f"  FAIL annotate {exc!r}", flush=True)
            continue
        if frame.empty:
            failed.append(f"{label} (empty laps)")
            print("  empty", flush=True)
            continue
        frame["split"] = split
        frames.append(frame)
        n_ok += 1
        by_split_n[split] += len(frame)
        wx = int(frame["air_temp_c"].notna().sum()) if "air_temp_c" in frame.columns else 0
        print(
            f"  laps={len(frame)} weather={wx}/{len(frame)} "
            f"n_corners={frame['n_corners'].iloc[0] if 'n_corners' in frame.columns else None}",
            flush=True,
        )

    all_laps = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    report: dict[str, Any] = {
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": "REFERENCE_RACES (2018-2023 train) + HELD_OUT_RACES (2024)",
        "n_events_attempted": len(corpus),
        "n_events_loaded": n_ok,
        "n_events_failed": len(failed),
        "n_events_weather_empty": n_weather_empty,
        "failed": failed,
        "n_laps_by_split": dict(by_split_n),
        "all_laps": _summarise(all_laps) if not all_laps.empty else {},
    }
    if not all_laps.empty:
        report["train"] = _summarise(all_laps[all_laps["split"] == "train"])
        report["heldout_2024"] = _summarise(all_laps[all_laps["split"] == "heldout"])
        mapped = all_laps[all_laps["mapped"].astype(bool)]
        report["mapped_nomination"] = _summarise(mapped)
        c_code = all_laps[all_laps["compound_id"].isin(_C_CODES)]
        report["mapped_c_code_laps"] = _summarise(c_code)
        # Honest note: residual train years 2018-2021 are almost entirely unmapped.
        report["n_corners_missing_events"] = (
            all_laps.groupby(["year", "gp"])["n_corners"]
            .first()
            .isna()
            .sum()
        )
        report["n_corners_missing_event_list"] = [
            f"{int(y)} {g}"
            for (y, g), val in all_laps.groupby(["year", "gp"])["n_corners"].first().items()
            if pd.isna(val)
        ]

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("all_laps", "train", "heldout_2024") if k in report}, indent=2))
    print(f"Wrote {_OUT}", flush=True)
    return 0 if n_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
