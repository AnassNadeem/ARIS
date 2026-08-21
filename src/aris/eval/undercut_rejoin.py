"""Empirical undercut / first-flying-lap rejoin table (2024–2025 green pits).

Does not change T2-D (22 s window, −0.3 / −0.6 / cap −0.8). Does not ship
dirty-air +0.6..+1.2 s. Dolan 0.018 s/s is a following-distance lap-time
preprint, not a pit-rejoin cost — not used here.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from aris.physics.tires import normalize_compound
from aris.physics.traffic import gaps_at_completed_laps
from aris.state import track_status_is_sc_vsc

# Bin edges match the T2-D heuristic window for *reporting*, not a new constant.
GAP_BINS: tuple[tuple[str, float, float], ...] = (
    ("<1s", 0.0, 1.0),
    ("1-3s", 1.0, 3.0),
    ("3-8s", 3.0, 8.0),
    ("8-22s", 8.0, 22.0),
)
SWAP_TIMEOUT_LAPS = 5


def gap_bin(gap: float | None) -> str | None:
    if gap is None or not np.isfinite(gap) or gap <= 0:
        return None
    for label, lo, hi in GAP_BINS:
        if lo <= gap < hi:
            return label
    return ">=22s"


def _driver_rows(laps: pd.DataFrame, driver_id: object) -> pd.DataFrame:
    return laps[laps["driver_id"] == driver_id].sort_values("lap_number")


def _pitted_on(laps: pd.DataFrame, driver_id: object, lap: int) -> bool:
    hit = laps[
        (laps["driver_id"] == driver_id) & (laps["lap_number"].astype(int) == int(lap))
    ]
    if hit.empty:
        return False
    return bool(hit.iloc[0].get("pit_in"))


def first_clean_flying(
    driver_laps: pd.DataFrame, pit_lap: int
) -> pd.Series | None:
    after = driver_laps[driver_laps["lap_number"].astype(int) > int(pit_lap)]
    for _, row in after.iterrows():
        if bool(row.get("pit_in")) or bool(row.get("pit_out")):
            continue
        if track_status_is_sc_vsc(row.get("track_status")):
            continue
        t = row.get("lap_time_s")
        if t is None or (isinstance(t, float) and np.isnan(t)):
            continue
        return row
    return None


def _stint_median_after(driver_laps: pd.DataFrame, flying_lap: int) -> float | None:
    later = driver_laps[driver_laps["lap_number"].astype(int) > int(flying_lap)]
    times: list[float] = []
    for _, row in later.iterrows():
        if bool(row.get("pit_in")) or bool(row.get("pit_out")):
            break
        if track_status_is_sc_vsc(row.get("track_status")):
            continue
        t = row.get("lap_time_s")
        if t is None or (isinstance(t, float) and np.isnan(t)):
            continue
        times.append(float(t))
    if len(times) < 2:
        return None
    return float(np.median(times))


def _gap_row(gaps: pd.DataFrame, driver_id: object, lap: int) -> pd.Series | None:
    hit = gaps[
        (gaps["driver_id"] == driver_id) & (gaps["lap_number"].astype(int) == int(lap))
    ]
    if hit.empty:
        return None
    return hit.iloc[0]


def find_undercut_attempts(
    laps: pd.DataFrame,
    *,
    circuit: str | None = None,
    year: int | None = None,
    gp: str | None = None,
) -> list[dict[str, Any]]:
    """Green-flag undercut attempts: A pits, B (car ahead) stays ≥ 1 lap."""
    if laps.empty or "pit_in" not in laps.columns:
        return []
    gaps = gaps_at_completed_laps(laps)
    if gaps.empty or "ahead_driver" not in gaps.columns:
        return []
    attempts: list[dict[str, Any]] = []
    pits = laps[laps["pit_in"] == True]  # noqa: E712
    for _, row in pits.iterrows():
        if track_status_is_sc_vsc(row.get("track_status")):
            continue
        compound = normalize_compound(row.get("compound"))
        if compound in {"INTERMEDIATE", "WET"}:
            continue
        try:
            pit_lap = int(row["lap_number"])
            a_id = row["driver_id"]
        except (TypeError, ValueError, KeyError):
            continue
        pre_lap = pit_lap - 1
        pre = _gap_row(gaps, a_id, pre_lap)
        if pre is None:
            continue
        b_id = pre.get("ahead_driver")
        if b_id is None or (isinstance(b_id, float) and np.isnan(b_id)):
            continue
        pre_gap = pre.get("gap_ahead_s")
        try:
            pre_gap_f = float(pre_gap)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(pre_gap_f) or pre_gap_f <= 0:
            continue
        if _pitted_on(laps, b_id, pit_lap) or _pitted_on(laps, b_id, pit_lap + 1):
            continue
        a_laps = _driver_rows(laps, a_id)
        flying = first_clean_flying(a_laps, pit_lap)
        if flying is None:
            continue
        fly_lap = int(flying["lap_number"])
        fly_time = float(flying["lap_time_s"])
        b_compound = None
        b_at_fly = laps[
            (laps["driver_id"] == b_id) & (laps["lap_number"].astype(int) == fly_lap)
        ]
        if not b_at_fly.empty:
            b_compound = normalize_compound(b_at_fly.iloc[0].get("compound"))
        a_new = normalize_compound(flying.get("compound"))
        rejoin = _gap_row(gaps, a_id, fly_lap)
        rejoin_gap = None
        rejoin_pos = None
        b_pos = None
        swapped = False
        swap_laps: int | None = None
        timeout = True
        if rejoin is not None:
            rejoin_pos = int(rejoin["position"]) if pd.notna(rejoin.get("position")) else None
            if rejoin.get("ahead_driver") == b_id:
                try:
                    rejoin_gap = float(rejoin.get("gap_ahead_s"))
                except (TypeError, ValueError):
                    rejoin_gap = None
            elif rejoin.get("behind_driver") == b_id:
                try:
                    rejoin_gap = -float(rejoin.get("gap_behind_s"))
                except (TypeError, ValueError):
                    rejoin_gap = None
        b_rejoin = _gap_row(gaps, b_id, fly_lap)
        if b_rejoin is not None and pd.notna(b_rejoin.get("position")):
            b_pos = int(b_rejoin["position"])
        deadline = pit_lap + SWAP_TIMEOUT_LAPS
        for lap in range(fly_lap, deadline + 1):
            a_g = _gap_row(gaps, a_id, lap)
            b_g = _gap_row(gaps, b_id, lap)
            if a_g is None or b_g is None:
                continue
            try:
                pa, pb = int(a_g["position"]), int(b_g["position"])
            except (TypeError, ValueError):
                continue
            if pa < pb:
                swapped = True
                swap_laps = int(lap - pit_lap)
                timeout = False
                break
        stint_med = _stint_median_after(a_laps, fly_lap)
        out_vs_stint = (fly_time - stint_med) if stint_med is not None else None
        a_code = str(row.get("code") or "")
        b_code = ""
        b_rows = laps[laps["driver_id"] == b_id]
        if not b_rows.empty and "code" in b_rows.columns:
            b_code = str(b_rows.iloc[0].get("code") or "")
        attempts.append(
            {
                "year": year,
                "gp": gp,
                "circuit": circuit,
                "a_driver_id": int(a_id) if pd.notna(a_id) else None,
                "b_driver_id": int(b_id) if pd.notna(b_id) else None,
                "a_code": a_code,
                "b_code": b_code,
                "pit_lap": pit_lap,
                "first_flying_lap": fly_lap,
                "pre_gap_s": round(pre_gap_f, 4),
                "gap_bin": gap_bin(pre_gap_f),
                "rejoin_gap_s": round(rejoin_gap, 4) if rejoin_gap is not None else None,
                "a_compound": a_new,
                "b_compound": b_compound,
                "compound_delta": f"{a_new}-{b_compound}" if b_compound else a_new,
                "first_flying_s": round(fly_time, 4),
                "outlap_minus_stint_median_s": (
                    round(out_vs_stint, 4) if out_vs_stint is not None else None
                ),
                "swapped": swapped,
                "swap_laps": swap_laps,
                "timeout": timeout,
                "a_rejoin_position": rejoin_pos,
                "b_rejoin_position": b_pos,
            }
        )
    return attempts


def summarize_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    by_bin: dict[str, dict[str, Any]] = {}
    labels = [lab for lab, _, _ in GAP_BINS] + [">=22s"]
    for label in labels:
        subset = [a for a in attempts if a.get("gap_bin") == label]
        n = len(subset)
        n_swap = sum(1 for a in subset if a.get("swapped"))
        gaps = [float(a["rejoin_gap_s"]) for a in subset if a.get("rejoin_gap_s") is not None]
        outlaps = [
            float(a["outlap_minus_stint_median_s"])
            for a in subset
            if a.get("outlap_minus_stint_median_s") is not None
        ]
        by_bin[label] = {
            "n": n,
            "n_swapped": n_swap,
            "swap_rate": (n_swap / n) if n else None,
            "median_rejoin_gap_s": float(np.median(gaps)) if gaps else None,
            "median_outlap_vs_stint_s": float(np.median(outlaps)) if outlaps else None,
        }
    by_circuit: dict[str, dict[str, Any]] = {}
    for key in sorted({str(a.get("circuit") or "") for a in attempts if a.get("circuit")}):
        subset = [a for a in attempts if a.get("circuit") == key]
        n = len(subset)
        n_swap = sum(1 for a in subset if a.get("swapped"))
        by_circuit[key] = {
            "n": n,
            "n_swapped": n_swap,
            "swap_rate": (n_swap / n) if n else None,
        }
    return {
        "meta": {
            "years": "2024-2025",
            "exclude": "SC/VSC pits (TrackStatus 4/6/7)",
            "timeout_laps": SWAP_TIMEOUT_LAPS,
            "t2d_window_s_heuristic": 22.0,
            "do_not_ship_dirty_air": "+0.6..+1.2 UNSOURCED; not applied",
            "kill_gate": (
                "flagged bonus table must beat T2 0.345 and not lose 0.276/0.322; "
                "Zandvoort identity must not move on the default path"
            ),
        },
        "n_attempts": len(attempts),
        "n_swapped": sum(1 for a in attempts if a.get("swapped")),
        "by_gap_bin": by_bin,
        "by_circuit": by_circuit,
    }
