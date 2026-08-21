"""T2-B audit: empirical SC/VSC net pit-loss ratios (flagged; not the default).

Default ``simulate()`` / ``recommend()`` still use napkin 0.35 / 0.55
(UNSOURCED). This module measures FastF1/DB pits against YAML green pit_loss
and, behind ``ARIS_USE_MEASURED_SC_PIT_LOSS``, substitutes the median ratio.

Heilmeier 2020 Table 6 (PEER-REVIEWED, 2018–19 video, four circuits) sits
beside the table and is never averaged into the global median. Heilmeier's
VSC ~1.4× / SC ~1.6× fastest-green *lap times* are not pit-loss multipliers.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aris.state import (
    SC_PIT_LOSS_MULT,
    VSC_PIT_LOSS_MULT,
    track_status_is_sc_vsc,
)

logger = logging.getLogger(__name__)

MEASURED_SC_PIT_LOSS_ENV = "ARIS_USE_MEASURED_SC_PIT_LOSS"
MEASURED_SC_PIT_LOSS_PATH_ENV = "ARIS_SC_PIT_LOSS_PATH"
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TABLE_PATH = _REPO_ROOT / "results" / "t2b" / "sc_vsc_pit_loss.json"

MIN_CIRCUIT_N = 5
MIN_STAYERS = 3
MIN_NET_S = 0.5
MAX_NET_S = 40.0
MIN_GREEN_PIT_S = 5.0

# Heilmeier 2020 Table 6 — pit transit seconds. Do not average. Do not mix
# into the FastF1 global median. Ratios are implied vs that row's green.
HEILMEIER_TABLE_6: dict[str, dict[str, Any]] = {
    "spain": {
        "heilmeier_name": "Catalunya",
        "green_s": 19.04,
        "vsc_s": 10.03,
        "sc_s": 7.88,
        "source": "Heilmeier 2020 Table 6 PEER-REVIEWED 2018-19 video",
    },
    "australia": {
        "heilmeier_name": "Melbourne",
        "green_s": 17.85,
        "vsc_s": 12.95,
        "sc_s": 12.61,
        "source": "Heilmeier 2020 Table 6 PEER-REVIEWED 2018-19 video",
    },
    "italy": {
        "heilmeier_name": "Monza",
        "green_s": 20.60,
        "vsc_s": 15.42,
        "sc_s": 10.16,
        "source": "Heilmeier 2020 Table 6 PEER-REVIEWED 2018-19 video",
    },
    "japan": {
        "heilmeier_name": "Suzuka",
        "green_s": 19.48,
        "vsc_s": 15.05,
        "sc_s": 13.60,
        "source": "Heilmeier 2020 Table 6 PEER-REVIEWED 2018-19 video",
    },
}


def heilmeier_implied_ratios() -> dict[str, dict[str, float | str]]:
    """Per-circuit SC/VSC pit-transit / green. Not a global replacement."""
    out: dict[str, dict[str, float | str]] = {}
    for key, row in HEILMEIER_TABLE_6.items():
        green = float(row["green_s"])
        out[key] = {
            "heilmeier_name": str(row["heilmeier_name"]),
            "sc_ratio": float(row["sc_s"]) / green,
            "vsc_ratio": float(row["vsc_s"]) / green,
            "green_s": green,
            "sc_s": float(row["sc_s"]),
            "vsc_s": float(row["vsc_s"]),
            "source": str(row["source"]),
        }
    return out


def measured_sc_pit_loss_enabled(raw: str | bool | None = None) -> bool:
    """True only for explicit opt-in. ``0`` / ``false`` / unset are off."""
    if raw is True:
        return True
    if raw is False:
        return False
    if raw is None:
        raw = os.getenv(MEASURED_SC_PIT_LOSS_ENV, "")
    token = str(raw).strip().lower()
    return token in ("1", "true", "yes", "on")


def classify_sc_vsc(status: str | None) -> str | None:
    """``sc`` if TrackStatus contains 4, else ``vsc`` for 6/7, else None."""
    if not track_status_is_sc_vsc(status):
        return None
    return "sc" if "4" in str(status) else "vsc"


def circuit_key_for(country: str) -> str:
    """YAML stem when a track file matches; else a normalized country token."""
    from aris.physics.tires import _normalize_circuit_key
    from aris.tracks import _match_track_file

    path = _match_track_file(country)
    if path is not None:
        return path.stem
    return _normalize_circuit_key(country)


def _median_iqr(vals: list[float]) -> dict[str, float | int | None]:
    if not vals:
        return {"n": 0, "median": None, "q1": None, "q3": None, "iqr": None}
    arr = np.asarray(vals, dtype=float)
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    return {
        "n": int(len(arr)),
        "median": float(np.median(arr)),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
    }


def _stayer_median(
    field: pd.DataFrame,
    *,
    lap: int,
    pitter_id: object,
    kind: str,
) -> float | None:
    """Median lap time of same-lap non-pit cars under the same SC/VSC kind."""
    same = field[field["lap_number"].astype(int) == int(lap)]
    if same.empty:
        return None
    times: list[float] = []
    id_col = "driver_id" if "driver_id" in same.columns else None
    for _, row in same.iterrows():
        if id_col is not None and row[id_col] == pitter_id:
            continue
        if bool(row.get("pit_in")) or bool(row.get("pit_out")):
            continue
        row_kind = classify_sc_vsc(row.get("track_status"))
        if row_kind != kind:
            continue
        t = row.get("lap_time_s")
        if t is None or (isinstance(t, float) and np.isnan(t)):
            continue
        try:
            times.append(float(t))
        except (TypeError, ValueError):
            continue
    if len(times) < MIN_STAYERS:
        return None
    return float(np.median(times))


def measure_sc_vsc_pit_events(
    field: pd.DataFrame,
    *,
    green_pit_loss_s: float,
    circuit_key: str,
    year: int | None = None,
    gp: str | None = None,
    rainfall: bool = False,
) -> list[dict[str, Any]]:
    """Net SC/VSC pit cost vs YAML green for one race field.

    Net = pitting car's pit-lap time minus the median same-lap stayer
    (non-pit, same SC/VSC). That is the T2-B quantity (pit-loss vs a
    slowed field), not pit-lap minus a green flying lap (gross, includes
    the SC delta). Heilmeier Table 6 seconds sit beside the summary; they
    are not this numerator.

    ``green_pit_loss_s`` is the circuit YAML (or same-weekend green median
    passed by the caller). Ratio = net / green_pit_loss_s.
    """
    if rainfall or field.empty or green_pit_loss_s < MIN_GREEN_PIT_S:
        return []
    work = field.copy()
    if "compound" in work.columns:
        wet = work["compound"].astype("string").str.upper()
        if wet.isin(["INTERMEDIATE", "WET"]).any() and wet.isin(
            ["INTERMEDIATE", "WET"]
        ).sum() >= max(8, int(0.15 * len(work))):
            return []
    events: list[dict[str, Any]] = []
    if "pit_in" not in work.columns:
        return []
    pits = work[work["pit_in"] == True]  # noqa: E712
    id_col = "driver_id" if "driver_id" in work.columns else None
    code_col = "code" if "code" in work.columns else None
    for _, row in pits.iterrows():
        kind = classify_sc_vsc(row.get("track_status"))
        if kind is None:
            continue
        compound = str(row.get("compound") or "").upper()
        if compound in {"INTERMEDIATE", "WET"}:
            continue
        try:
            pit_lap = int(row["lap_number"])
            pit_time = float(row["lap_time_s"])
        except (TypeError, ValueError):
            continue
        if not np.isfinite(pit_time):
            continue
        pitter = row[id_col] if id_col else None
        stayer = _stayer_median(work, lap=pit_lap, pitter_id=pitter, kind=kind)
        if stayer is None:
            continue
        net = pit_time - stayer
        if not (MIN_NET_S < net < MAX_NET_S):
            continue
        ratio = net / float(green_pit_loss_s)
        events.append(
            {
                "kind": kind,
                "circuit": circuit_key,
                "year": year,
                "gp": gp,
                "driver_id": int(pitter) if pitter is not None and pd.notna(pitter) else None,
                "driver_code": (
                    str(row[code_col]) if code_col and pd.notna(row.get(code_col)) else None
                ),
                "lap": pit_lap,
                "observed_net_s": round(net, 4),
                "stayer_median_s": round(stayer, 4),
                "pit_lap_time_s": round(pit_time, 4),
                "green_pit_loss_s": float(green_pit_loss_s),
                "ratio": round(ratio, 4),
                "track_status": str(row.get("track_status") or ""),
            }
        )
    return events


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Median / IQR by SC vs VSC and by circuit. Heilmeier sits beside."""
    sc_ratios = [float(e["ratio"]) for e in events if e.get("kind") == "sc"]
    vsc_ratios = [float(e["ratio"]) for e in events if e.get("kind") == "vsc"]
    by_circuit: dict[str, dict[str, Any]] = {}
    circuits = sorted({str(e.get("circuit") or "") for e in events if e.get("circuit")})
    for key in circuits:
        subset = [e for e in events if e.get("circuit") == key]
        sc = [float(e["ratio"]) for e in subset if e.get("kind") == "sc"]
        vsc = [float(e["ratio"]) for e in subset if e.get("kind") == "vsc"]
        sc_stats = _median_iqr(sc)
        vsc_stats = _median_iqr(vsc)
        by_circuit[key] = {
            "sc": sc_stats["median"],
            "vsc": vsc_stats["median"],
            "n_sc": sc_stats["n"],
            "n_vsc": vsc_stats["n"],
            "sc_iqr": {"q1": sc_stats["q1"], "q3": sc_stats["q3"], "iqr": sc_stats["iqr"]},
            "vsc_iqr": {"q1": vsc_stats["q1"], "q3": vsc_stats["q3"], "iqr": vsc_stats["iqr"]},
        }
    global_sc = _median_iqr(sc_ratios)
    global_vsc = _median_iqr(vsc_ratios)
    return {
        "meta": {
            "min_circuit_n": MIN_CIRCUIT_N,
            "method": (
                "net = pit-lap time minus median same-lap SC/VSC stayers; "
                "ratio vs YAML green pit_loss. Not pit-lap minus green flying."
            ),
            "uncalibrated_default": {"sc": SC_PIT_LOSS_MULT, "vsc": VSC_PIT_LOSS_MULT},
            "kill_gate": (
                "flagged replay must not lose stay-out 0.276 or G1.5 0.322; "
                "Zandvoort default identity must not move with the flag off"
            ),
            "do_not_average_heilmeier": True,
        },
        "global": {
            "sc": global_sc["median"],
            "vsc": global_vsc["median"],
            "n_sc": global_sc["n"],
            "n_vsc": global_vsc["n"],
            "sc_iqr": {"q1": global_sc["q1"], "q3": global_sc["q3"], "iqr": global_sc["iqr"]},
            "vsc_iqr": {"q1": global_vsc["q1"], "q3": global_vsc["q3"], "iqr": global_vsc["iqr"]},
        },
        "by_circuit": by_circuit,
        "heilmeier_table_6": heilmeier_implied_ratios(),
        "n_events": len(events),
    }


def table_path() -> Path:
    raw = os.getenv(MEASURED_SC_PIT_LOSS_PATH_ENV, "")
    if raw.strip():
        return Path(raw)
    return DEFAULT_TABLE_PATH


@lru_cache(maxsize=4)
def _load_table_file(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as extra:
        logger.warning("SC pit-loss JSON unreadable (%s): %s", path, extra)
        return {}
    return data if isinstance(data, dict) else {}


def clear_measured_sc_pit_loss_cache() -> None:
    _load_table_file.cache_clear()


def measured_multiplier(kind: str, circuit_key: str | None = None) -> float | None:
    """Opt-in measured ratio, or None so the caller keeps 0.35 / 0.55.

    Circuit median if that circuit's n >= ``min_circuit_n`` (default 5);
    else global median; else None (napkin). Flag off always returns None.
    """
    if not measured_sc_pit_loss_enabled():
        return None
    token = str(kind).strip().lower()
    if token not in ("sc", "vsc"):
        return None
    data = _load_table_file(str(table_path()))
    if not data:
        return None
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    min_n = int(meta.get("min_circuit_n") or MIN_CIRCUIT_N)
    if circuit_key:
        from aris.physics.tires import _normalize_circuit_key

        key = _normalize_circuit_key(circuit_key)
        by_circuit = data.get("by_circuit") if isinstance(data.get("by_circuit"), dict) else {}
        rec = by_circuit.get(key)
        if rec is None:
            # YAML stem vs country alias (zandvoort → netherlands).
            rec = by_circuit.get(circuit_key_for(circuit_key))
        if isinstance(rec, dict):
            n_key = "n_sc" if token == "sc" else "n_vsc"
            try:
                n = int(rec.get(n_key) or 0)
            except (TypeError, ValueError):
                n = 0
            val = rec.get(token)
            if n >= min_n and val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass
    glob = data.get("global") if isinstance(data.get("global"), dict) else {}
    val = glob.get(token)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def pit_status_by_lap(laps: pd.DataFrame) -> dict[int, str]:
    """Map lap_number → track_status for analysis-only full-race replay."""
    if laps.empty or "lap_number" not in laps.columns:
        return {}
    out: dict[int, str] = {}
    ordered = laps.sort_values("lap_number")
    for _, row in ordered.iterrows():
        try:
            lap = int(row["lap_number"])
        except (TypeError, ValueError):
            continue
        out[lap] = str(row.get("track_status") or "")
    return out
