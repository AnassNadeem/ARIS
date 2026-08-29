"""FP2 long-run degradation calibration (T9).

Fits a per-weekend, per-compound linear slope from FastF1 practice long runs
and exposes it through ``calibrate_race_weekend``. G1.5 constants are not
modified — they remain the fallback when practice data is insufficient.

FP2 (and FP1/FP3 fallback) runs start light, so the fitted slope is already
approximately fuel-corrected. Race OLS priors are not: fuel burn (~0.09 s/lap
early) biases those slopes shallow / negative.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_DRY = ("SOFT", "MEDIUM", "HARD")
_G15: dict[str, float] = {
    "SOFT": 0.08,
    "MEDIUM": 0.05,
    "HARD": 0.03,
    "INTERMEDIATE": 0.04,
    "INTER": 0.04,
    "WET": 0.02,
}
# Physical sanity cap on a fitted practice slope (s/lap). Above this the
# stint is almost certainly traffic / lift-and-coast, not tyre deg.
_MAX_SLOPE = 0.20
_MIN_STINT_R2 = 0.05
_FIT_R2 = 0.1
_CALIBRATION_CACHE: dict[str, dict] = {}

_NON_GREEN_CODES = ("2", "4", "5", "6", "7")


def clear_calibration_cache() -> None:
    """Drop weekend slope cache (tests / new FastF1 data)."""
    _CALIBRATION_CACHE.clear()


def _lap_time_seconds(series: pd.Series) -> pd.Series:
    if pd.api.types.is_timedelta64_dtype(series):
        return series.dt.total_seconds()
    return pd.to_numeric(series, errors="coerce")


def _is_green_status(status: object) -> bool:
    token = str(status).strip()
    if not token or token in ("None", "nan", "NaN"):
        return False
    if token == "1":
        return True
    # Multi-code strings like "12" / "24" include a yellow or SC.
    return token[0] == "1" and not any(code in token for code in _NON_GREEN_CODES)


def _is_sc_vsc_red(status: object) -> bool:
    """True for SC / VSC / red. Yellow-only (2) is not a session-wide wipe."""
    token = str(status).strip()
    if not token or token in ("None", "nan", "NaN", "1"):
        return False
    return any(code in token for code in ("4", "5", "6", "7"))


def _join_weather(laps: pd.DataFrame, weather: pd.DataFrame | None) -> pd.DataFrame:
    out = laps.copy()
    out["track_temp"] = np.nan
    out["air_temp"] = np.nan
    if weather is None or weather.empty or "Time" not in out.columns:
        return out
    cols = [c for c in ("Time", "TrackTemp", "AirTemp") if c in weather.columns]
    if "Time" not in cols:
        return out
    right = weather.loc[:, cols].sort_values("Time")
    left = out.sort_values("Time")
    try:
        merged = pd.merge_asof(left, right, on="Time", direction="nearest")
    except (TypeError, ValueError):
        return out
    if "TrackTemp" in merged.columns:
        merged["track_temp"] = pd.to_numeric(merged["TrackTemp"], errors="coerce")
    if "AirTemp" in merged.columns:
        merged["air_temp"] = pd.to_numeric(merged["AirTemp"], errors="coerce")
    return merged


def _split_tyre_sets(group: pd.DataFrame) -> list[pd.DataFrame]:
    """Split a driver/stint group on TyreLife gaps (new set)."""
    g = group.sort_values("LapNumber")
    if g.empty:
        return []
    life = pd.to_numeric(g["TyreLife"], errors="coerce").to_numpy()
    breaks = [0]
    for i in range(1, len(life)):
        prev, cur = life[i - 1], life[i]
        if not np.isfinite(prev) or not np.isfinite(cur) or abs(cur - prev - 1.0) > 0.6:
            breaks.append(i)
    breaks.append(len(g))
    idx = g.index.to_list()
    parts: list[pd.DataFrame] = []
    for a, b in zip(breaks[:-1], breaks[1:]):
        if b - a <= 0:
            continue
        parts.append(g.loc[idx[a:b]])
    return parts


def _stint_slope_r2(tyre_life: np.ndarray, lap_time: np.ndarray) -> tuple[float, float]:
    """Slope and R² of lap_time_delta ~ tyre_life (delta vs first-3 median)."""
    if len(tyre_life) < 3 or float(np.nanstd(tyre_life)) < 1e-9:
        return float("nan"), float("nan")
    baseline = float(np.nanmedian(lap_time[: min(3, len(lap_time))]))
    delta = lap_time - baseline
    try:
        from scipy.stats import linregress

        fit = linregress(tyre_life.astype(float), delta.astype(float))
    except Exception:
        return float("nan"), float("nan")
    r2 = float(fit.rvalue**2) if np.isfinite(fit.rvalue) else float("nan")
    return float(fit.slope), r2


def extract_fp2_long_runs(
    session,
    min_stint_laps: int = 8,
    compounds: tuple[str, ...] = _DRY,
) -> pd.DataFrame:
    """Extract clean long-run laps from a practice session.

    Returns columns
    ``[driver, compound, tyre_life, lap_time_s, track_temp, air_temp,
    lap_in_stint, stint_id]``.

    Filters: dry compounds, green flag, no pit-in/out, no Deleted laps,
    no laps > 110% of session median, no laps within 2 of a yellow/SC/VSC,
    stints with ``>= min_stint_laps`` consecutive clean laps, and per-stint
    ``lap_time_delta ~ tyre_life`` with R² ≥ 0.05 and slope > 0.
    Compounds with fewer than 2 valid stints or 15 laps are dropped
    (insufficient) — ``fit_fp2_slope`` re-checks the same gate.
    """
    empty = pd.DataFrame(
        columns=[
            "driver",
            "compound",
            "tyre_life",
            "lap_time_s",
            "track_temp",
            "air_temp",
            "lap_in_stint",
            "stint_id",
        ]
    )
    laps = getattr(session, "laps", None)
    if laps is None or laps.empty:
        return empty

    df = pd.DataFrame(laps.copy())
    if "LapTime" not in df.columns:
        return empty
    df["lap_time_s"] = _lap_time_seconds(df["LapTime"])
    session_median = float(df["lap_time_s"].median()) if df["lap_time_s"].notna().any() else float("nan")

    wanted = {str(c).upper() for c in compounds}
    if "Compound" in df.columns:
        df = df[df["Compound"].astype(str).str.upper().isin(wanted)]
    df = df[df["lap_time_s"].notna() & (df["lap_time_s"] > 0)]
    if "Deleted" in df.columns:
        deleted = df["Deleted"]
        if deleted.dtype == object:
            deleted = deleted.map(lambda v: bool(v) if pd.notna(v) else False)
        else:
            deleted = deleted.fillna(False).astype(bool)
        df = df[~deleted.astype(bool)]
    if "PitInTime" in df.columns:
        df = df[df["PitInTime"].isna()]
    if "PitOutTime" in df.columns:
        df = df[df["PitOutTime"].isna()]
    if "TrackStatus" in df.columns:
        green_mask = df["TrackStatus"].map(_is_green_status)
        df = df[green_mask]

    if df.empty or "lap_time_s" not in df.columns:
        return empty
    if np.isfinite(session_median) and session_median > 0:
        df = df[df["lap_time_s"] <= session_median * 1.10]

    # Exclude laps within 2 of SC/VSC/red. Yellow-only laps are already
    # dropped by the green-flag filter; applying ±2 to every FP yellow
    # wipes the first 10–15 laps of typical practice sessions.
    if "TrackStatus" in laps.columns and "LapNumber" in laps.columns:
        dirty_laps = set()
        for status, lap_no in zip(
            laps["TrackStatus"].tolist(), laps["LapNumber"].tolist(), strict=False
        ):
            if pd.isna(lap_no) or not _is_sc_vsc_red(status):
                continue
            n = int(lap_no)
            dirty_laps.update(range(n - 2, n + 3))
        if dirty_laps and "LapNumber" in df.columns:
            df = df[~df["LapNumber"].fillna(-999).astype(int).isin(dirty_laps)]

    if df.empty:
        return empty

    try:
        weather = getattr(session, "weather_data", None)
    except Exception:
        weather = None
    df = _join_weather(df, weather if isinstance(weather, pd.DataFrame) else None)

    group_keys = ["Driver"]
    if "Stint" in df.columns:
        group_keys.append("Stint")
    group_keys.append("Compound")

    rows: list[pd.DataFrame] = []
    stint_id = 0
    for _, grp in df.groupby(group_keys, sort=False):
        for part in _split_tyre_sets(grp):
            if len(part) < int(min_stint_laps):
                continue
            life = pd.to_numeric(part["TyreLife"], errors="coerce").to_numpy()
            times = part["lap_time_s"].to_numpy(dtype=float)
            slope, r2 = _stint_slope_r2(life, times)
            if not np.isfinite(slope) or not np.isfinite(r2):
                continue
            if r2 < _MIN_STINT_R2 or slope <= 0:
                continue
            stint_id += 1
            piece = pd.DataFrame(
                {
                    "driver": part["Driver"].astype(str).to_numpy(),
                    "compound": part["Compound"].astype(str).str.upper().to_numpy(),
                    "tyre_life": life,
                    "lap_time_s": times,
                    "track_temp": pd.to_numeric(part.get("track_temp"), errors="coerce").to_numpy()
                    if "track_temp" in part.columns
                    else np.full(len(part), np.nan),
                    "air_temp": pd.to_numeric(part.get("air_temp"), errors="coerce").to_numpy()
                    if "air_temp" in part.columns
                    else np.full(len(part), np.nan),
                    "lap_in_stint": np.arange(1, len(part) + 1),
                    "stint_id": stint_id,
                }
            )
            rows.append(piece)

    if not rows:
        return empty
    return pd.concat(rows, ignore_index=True)


def fit_fp2_slope(
    long_run_df: pd.DataFrame,
    compound: str,
    min_observations: int = 15,
) -> dict[str, Any]:
    """Fit lap_time_delta ~ tyre_life for one compound.

    ``lap_time_delta`` is vs the median of the first 3 laps of the same stint.
    Per-stint R² < 0.05 or slope ≤ 0 drops that stint. ``valid`` requires
    n_obs ≥ min_observations and pooled r² > 0.1, plus either ≥ 2 stints
    or a single quality stint (n ≥ 8 and r² > 0.2) — FP2 HARD is often one
    long run.
    """
    key = str(compound).upper().strip()
    result = {
        "compound": key,
        "slope": float("nan"),
        "intercept": float("nan"),
        "n_obs": 0,
        "r_squared": float("nan"),
        "valid": False,
        "n_stints": 0,
    }
    if long_run_df is None or long_run_df.empty:
        return result
    if "compound" not in long_run_df.columns:
        return result
    sub = long_run_df[long_run_df["compound"].astype(str).str.upper() == key].copy()
    if sub.empty:
        return result

    xs: list[float] = []
    ys: list[float] = []
    n_stints = 0
    stint_col = "stint_id" if "stint_id" in sub.columns else None
    groups = sub.groupby(stint_col) if stint_col else [(0, sub)]
    for _sid, stint in groups:
        stint = stint.sort_values("tyre_life") if "tyre_life" in stint.columns else stint
        if "tyre_life" not in stint.columns or "lap_time_s" not in stint.columns:
            continue
        times = pd.to_numeric(stint["lap_time_s"], errors="coerce").to_numpy(dtype=float)
        life = pd.to_numeric(stint["tyre_life"], errors="coerce").to_numpy(dtype=float)
        mask = np.isfinite(times) & np.isfinite(life)
        times, life = times[mask], life[mask]
        if len(times) < 3:
            continue
        baseline = float(np.median(times[: min(3, len(times))]))
        delta = times - baseline
        slope, r2 = _stint_slope_r2(life, times)
        if not np.isfinite(slope) or not np.isfinite(r2) or r2 < _MIN_STINT_R2 or slope <= 0:
            continue
        n_stints += 1
        xs.extend(life.tolist())
        ys.extend(delta.tolist())

    result["n_stints"] = n_stints
    result["n_obs"] = len(xs)
    if n_stints < 1 or len(xs) < 3:
        return result

    try:
        from scipy.stats import linregress

        fit = linregress(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))
    except Exception:
        return result
    slope = float(fit.slope)
    intercept = float(fit.intercept)
    r2 = float(fit.rvalue**2) if np.isfinite(fit.rvalue) else float("nan")
    if slope > _MAX_SLOPE and r2 > _FIT_R2:
        slope = _MAX_SLOPE
    result["slope"] = slope
    result["intercept"] = intercept
    result["r_squared"] = r2

    enough_obs = len(xs) >= int(min_observations)
    two_stints = n_stints >= 2 and enough_obs and r2 > _FIT_R2
    one_quality = (
        n_stints >= 1
        and len(xs) >= 8
        and r2 > 0.2
        and 0 < slope <= _MAX_SLOPE
    )
    valid = (two_stints or one_quality) and 0 < slope <= _MAX_SLOPE and r2 > _FIT_R2
    if n_stints < 2 and len(xs) < 15 and not one_quality:
        valid = False
    result["valid"] = bool(valid)
    return result


def _enable_fastf1_cache() -> Path:
    from aris.io.fastf1_session import DEFAULT_CACHE, _enable_cache

    return _enable_cache(DEFAULT_CACHE)


def _load_practice_session(year: int, round_number: int, session_type: str):
    try:
        import fastf1

        try:
            fastf1.set_log_level("ERROR")
        except Exception:
            pass
        _enable_fastf1_cache()
        session = fastf1.get_session(int(year), int(round_number), session_type)
        session.load(laps=True, weather=True, telemetry=False, messages=False)
        if session.laps is None or session.laps.empty:
            return None
        return session
    except Exception as extra:
        logger.info(
            "FP2 calibration: failed to load %s R%s %s (%s)",
            year,
            round_number,
            session_type,
            extra,
        )
        return None


def _circuit_id_from_session(session) -> str | None:
    event = getattr(session, "event", None)
    if event is None:
        return None
    for key in ("Country", "Location", "EventName"):
        try:
            val = event[key] if key in event else None
        except Exception:
            val = getattr(event, key, None)
        if val is not None and str(val).strip() and str(val).lower() != "nan":
            return str(val)
    return None


def _circuit_prior(circuit_id: str | None, compound: str) -> tuple[float | None, int]:
    """Return (slope, n_obs) from data/circuit_deg_priors.csv; (None, 0) if missing."""
    if not circuit_id:
        return None, 0
    try:
        from aris.physics.tires import (
            CIRCUIT_DEG_CSV_PATH,
            _normalize_circuit_key,
            normalize_compound,
        )
    except Exception:
        return None, 0
    path = CIRCUIT_DEG_CSV_PATH
    if not path.is_file():
        return None, 0
    try:
        df = pd.read_csv(str(path))
    except Exception:
        return None, 0
    if not {"circuit_id", "compound", "fitted_slope"}.issubset(df.columns):
        return None, 0
    key = _normalize_circuit_key(circuit_id)
    want = normalize_compound(compound)
    best: tuple[float | None, int] = (None, 0)
    for _, row in df.iterrows():
        cid = _normalize_circuit_key(str(row["circuit_id"]))
        comp = normalize_compound(str(row["compound"]))
        if cid != key or comp != want:
            continue
        try:
            slope = float(row["fitted_slope"])
            n_obs = int(row["n_obs"]) if "n_obs" in row and pd.notna(row["n_obs"]) else 0
        except (TypeError, ValueError):
            continue
        if not np.isfinite(slope) or slope <= 0:
            continue
        if n_obs >= best[1]:
            best = (slope, n_obs)
    return best


def _g15(compound: str) -> float:
    key = str(compound).upper().strip()
    if key == "INTER":
        key = "INTERMEDIATE"
    return float(_G15.get(key, 0.03))


def _scale_missing_from_slick(fitted: dict[str, dict], missing: str) -> float | None:
    """Scale G1.5[missing] by a valid SOFT/MEDIUM FP2 ratio (scale-up only).

    High-energy circuits often skip HARD race-sims in FP2. SOFT/MEDIUM long
    runs still measure circuit abrasion; we transfer that multiplier onto
    HARD rather than leaving G1.5 0.03 in place (Cause-A). Never scale down.
    """
    g_miss = _g15(missing)
    for ref in ("SOFT", "MEDIUM"):
        rec = fitted.get(ref)
        if not rec or not rec.get("valid"):
            continue
        g_ref = _g15(ref)
        if g_ref <= 0:
            continue
        ratio = float(rec["slope"]) / g_ref
        if ratio <= 1.0:
            continue
        scaled = g_miss * ratio
        return float(min(max(scaled, g_miss), _MAX_SLOPE))
    return None


def calibrate_race_weekend(
    year: int,
    round_number: int,
    session_type: str = "FP2",
) -> dict[str, Any]:
    """Return {compound: slope} for this weekend, plus ``_source`` and ``_valid``.

    Priority per dry compound:
      1. FP2 (then FP1, then FP3) long-run fit if valid
      2. HARD/MEDIUM scaled up from a valid slick FP2 slope when that
         compound had no long run
      3. Circuit prior from ``data/circuit_deg_priors.csv`` if n_obs ≥ 30
      4. G1.5 cross-circuit default

    INTER/WET always use G1.5. Cached per ``year_round_number``.
    """
    cache_key = f"{int(year)}_{int(round_number)}"
    if cache_key in _CALIBRATION_CACHE:
        return _CALIBRATION_CACHE[cache_key]

    order = [session_type]
    if str(session_type).upper() == "FP2":
        order = ["FP2", "FP1", "FP3"]
    else:
        for extra in ("FP2", "FP1", "FP3"):
            if extra not in order:
                order.append(extra)

    extracts: dict[str, pd.DataFrame] = {}
    circuit_id: str | None = None

    def _ensure_session(sess_name: str) -> pd.DataFrame:
        nonlocal circuit_id
        if sess_name in extracts:
            return extracts[sess_name]
        session = _load_practice_session(int(year), int(round_number), sess_name)
        if session is None:
            extracts[sess_name] = pd.DataFrame()
            return extracts[sess_name]
        if circuit_id is None:
            circuit_id = _circuit_id_from_session(session)
        extracts[sess_name] = extract_fp2_long_runs(session)
        return extracts[sess_name]

    fitted: dict[str, dict] = {}
    source: dict[str, str] = {}
    slopes: dict[str, Any] = {}
    missing = list(_DRY)

    for sess_name in order:
        if not missing:
            break
        df = _ensure_session(sess_name)
        still: list[str] = []
        for compound in missing:
            rec = fit_fp2_slope(df, compound) if df is not None and not df.empty else {
                "valid": False, "n_obs": 0
            }
            if rec.get("valid"):
                slopes[compound] = float(rec["slope"])
                source[compound] = "fp2" if sess_name == "FP2" else sess_name.lower()
                fitted[compound] = rec
            else:
                still.append(compound)
                fitted[compound] = rec
        missing = still

    if missing:
        frames = [df for df in extracts.values() if df is not None and not df.empty]
        if frames:
            pooled = pd.concat(frames, ignore_index=True)
            still = []
            for compound in missing:
                rec = fit_fp2_slope(pooled, compound)
                if rec.get("valid"):
                    slopes[compound] = float(rec["slope"])
                    source[compound] = "fp2"
                    fitted[compound] = rec
                else:
                    still.append(compound)
                    n_obs = int((pooled["compound"].astype(str).str.upper() == compound).sum())
                    logger.info(
                        "FP2 insufficient %s data (n_obs=%s); trying circuit prior.",
                        compound,
                        n_obs,
                    )
                    fitted[compound] = rec
            missing = still

    # Scale-up fallback for compounds with no long run (typically HARD).
    for compound in _DRY:
        if compound in slopes:
            continue
        scaled = _scale_missing_from_slick(fitted, compound)
        if scaled is not None:
            slopes[compound] = scaled
            source[compound] = "fp2_scaled"
            logger.info(
                "FP2 insufficient %s data; scaled from slick long-run (slope=%.4f).",
                compound,
                scaled,
            )
            continue
        prior, n_obs = _circuit_prior(circuit_id, compound)
        if prior is not None and n_obs >= 30:
            slopes[compound] = float(prior)
            source[compound] = "circuit_prior"
            continue
        if prior is not None:
            logger.info(
                "Circuit prior insufficient (n_obs=%s); using G1.5.",
                n_obs,
            )
        slopes[compound] = _g15(compound)
        source[compound] = "g15"

    slopes["INTERMEDIATE"] = _g15("INTERMEDIATE")
    slopes["INTER"] = _g15("INTER")
    slopes["WET"] = _g15("WET")
    source["INTERMEDIATE"] = "g15"
    source["INTER"] = "g15"
    source["WET"] = "g15"

    # Physical compound order from G1.5 ratios. A single noisy HARD long-run
    # must not out-degrade MEDIUM (that moved Zandvoort from Pit-HARD to a
    # MEDIUM plan). Cap, don't hardcode the identity labels.
    soft = float(slopes["SOFT"])
    med = float(slopes["MEDIUM"])
    hard = float(slopes["HARD"])
    med_cap = soft * (_g15("MEDIUM") / _g15("SOFT"))
    if med > med_cap > 0:
        med = med_cap
        slopes["MEDIUM"] = med
    hard_cap = med * (_g15("HARD") / _g15("MEDIUM"))
    if hard > hard_cap > 0:
        slopes["HARD"] = hard_cap

    slopes["_source"] = source
    slopes["_valid"] = True
    slopes["_circuit_id"] = circuit_id
    _CALIBRATION_CACHE[cache_key] = slopes
    return slopes
