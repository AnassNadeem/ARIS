#!/usr/bin/env python
"""Pre-process completed races into static JSON for Cloudflare R2.

    python scripts/prebuild_race_r2.py --year 2025 --round 15 --driver VER
    python scripts/prebuild_race_r2.py --all-completed --skip-existing

Reads FastF1 (and optionally Postgres) directly — no running Heroku backend.
Fails with exit 1 on a FastF1 error for a single race. --all-completed logs
the error and continues so a partial calendar still ships.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
# Do not prepend ROOT/.deps — that tree is a Heroku vendor bundle and can
# shadow a working site-packages pydantic (pydantic_core native module).

LOCAL_ROOT = ROOT / "data" / "replay_r2"
MAX_FIELD_BYTES = 3 * 1024 * 1024
DEFAULT_HZ = 2.0

_log = logging.getLogger("aris.prebuild_r2")


def _r2_ready() -> bool:
    keys = (
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_NAME",
    )
    return all((os.environ.get(k) or "").strip() for k in keys)


def _local_key(year: int, round_number: int, name: str) -> Path:
    return LOCAL_ROOT / "replay" / str(year) / str(round_number) / name


def _r2_exists(year: int, round_number: int, name: str) -> bool:
    if not _r2_ready():
        return _local_key(year, round_number, name).is_file()
    try:
        from deploy.r2_upload import object_exists, r2_client

        client = r2_client()
        bucket = os.environ["R2_BUCKET_NAME"]
        key = f"replay/{year}/{round_number}/{name}"
        return object_exists(client, bucket, key)
    except Exception as extra:
        _log.warning("R2 exists check failed (%s); falling back to local", extra)
        return _local_key(year, round_number, name).is_file()


def _upload(path: Path, key: str) -> None:
    if not _r2_ready():
        _log.info("R2 env unset — kept local copy at %s", path)
        return
    from deploy.r2_upload import r2_client, upload_file

    upload_file(r2_client(), os.environ["R2_BUCKET_NAME"], path, key)


def _write_json(path: Path, payload: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _td_s(v: Any) -> float | None:
    if v is None:
        return None
    try:
        import pandas as pd

        if pd.isna(v):
            return None
    except Exception:
        pass
    if hasattr(v, "total_seconds"):
        try:
            return float(v.total_seconds())
        except Exception:
            return None
    return _num(v)


def completed_jobs(
    years: tuple[int, ...] = (2024, 2025, 2026),
    *,
    year: int | None = None,
    round_number: int | None = None,
) -> list[tuple[int, int, str]]:
    from backend.calendar import ALLOWED_REPLAY_YEARS, get_calendar

    out: list[tuple[int, int, str]] = []
    want_years = (int(year),) if year else years
    for y in want_years:
        if int(y) not in ALLOWED_REPLAY_YEARS:
            continue
        cal = get_calendar(int(y), for_replay=True)
        for rnd in cal.rounds:
            if round_number is not None and int(rnd.round_number) != int(round_number):
                continue
            if str(rnd.status or "").upper() != "COMPLETED":
                continue
            name = str(rnd.circuit_name or rnd.name or f"R{rnd.round_number}")
            out.append((int(y), int(rnd.round_number), name))
    return out


def _load_session(year: int, round_number: int):
    from backend.cache import enable_fastf1_cache
    from backend.sessions import load_session

    enable_fastf1_cache()
    sess = load_session(
        int(year), int(round_number), "R", telemetry=False, weather=True, messages=True
    )
    if sess is None:
        raise RuntimeError(f"FastF1 session missing for {year} R{round_number}")
    return sess


def _code_by_num(sess: Any) -> dict[int, str]:
    out: dict[int, str] = {}
    laps = getattr(sess, "laps", None)
    if laps is None or getattr(laps, "empty", True):
        return out
    for rec in laps.itertuples(index=False):
        code = str(getattr(rec, "Driver", "") or "")
        num = getattr(rec, "DriverNumber", None)
        try:
            if code and num is not None and str(num) != "nan":
                out[int(float(num))] = code
        except (TypeError, ValueError):
            continue
    return out


def _race_leader_code(sess: Any) -> str | None:
    import pandas as pd

    results = getattr(sess, "results", None)
    if results is not None and not getattr(results, "empty", True):
        for col in ("ClassifiedPosition", "Position"):
            if col not in results.columns:
                continue
            for rec in results.itertuples(index=False):
                pos = getattr(rec, col, None)
                try:
                    if pos is None or pd.isna(pos) or int(float(pos)) != 1:
                        continue
                except (TypeError, ValueError):
                    continue
                code = str(getattr(rec, "Abbreviation", "") or "")
                if code:
                    return code
    laps = getattr(sess, "laps", None)
    if laps is None or getattr(laps, "empty", True) or "Position" not in laps.columns:
        return None
    for lap_n in (3, 2, 4, 1):
        hit = laps[(laps["LapNumber"] == lap_n) & (laps["Position"] == 1)]
        if hit.empty:
            continue
        code = str(hit.iloc[0].get("Driver") or "")
        if code:
            return code
    return None


def _pos_df_for_code(raw: dict[str, Any], code: str, code_by_num: dict[int, str]) -> Any:
    if code in raw:
        return raw[code]
    num_by_code = {v: k for k, v in code_by_num.items()}
    num = num_by_code.get(code)
    if num is not None:
        for key in (str(num), num):
            if key in raw:
                return raw[key]
    for drv_key, df in raw.items():
        mapped = str(drv_key)
        if str(drv_key).isdigit():
            try:
                mapped = code_by_num.get(int(drv_key), mapped)
            except (TypeError, ValueError):
                pass
        if mapped == code:
            return df
    return None


def _aware(ts: Any) -> Any:
    import pandas as pd

    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        return t.tz_localize("UTC")
    return t.tz_convert("UTC")


def _lap_window(sess: Any, code: str, lap_n: int) -> tuple[Any, Any] | tuple[None, None]:
    import pandas as pd

    laps = getattr(sess, "laps", None)
    if laps is None or getattr(laps, "empty", True):
        return None, None
    rows = laps[(laps["Driver"] == code) & (laps["LapNumber"] == lap_n)]
    if rows.empty or "LapStartDate" not in laps.columns:
        return None, None
    start = rows["LapStartDate"].iloc[0]
    if start is None or pd.isna(start):
        return None, None
    start = _aware(start)
    lap_time = rows["LapTime"].iloc[0] if "LapTime" in rows.columns else None
    if lap_time is not None and not pd.isna(lap_time):
        return start, start + lap_time
    nxt = laps[(laps["Driver"] == code) & (laps["LapNumber"] == lap_n + 1)]
    if not nxt.empty:
        nxt_start = nxt["LapStartDate"].iloc[0]
        if nxt_start is not None and not pd.isna(nxt_start):
            return start, _aware(nxt_start)
    return start, start + pd.Timedelta(seconds=120)


def _xy_from_df(df: Any, start: Any = None, end: Any = None) -> tuple[list[float], list[float]]:
    import pandas as pd

    if df is None or getattr(df, "empty", True) or "X" not in df.columns or "Y" not in df.columns:
        return [], []
    if start is not None and end is not None and "Date" in df.columns:
        dates = pd.to_datetime(df["Date"], utc=True, errors="coerce")
        mask = (dates >= start) & (dates < end)
        sliced = df.loc[mask]
    else:
        sliced = df
    xs = [float(v) for v in sliced["X"].dropna().tolist()]
    ys = [float(v) for v in sliced["Y"].dropna().tolist()]
    n = min(len(xs), len(ys))
    return xs[:n], ys[:n]


def _downsample_close(xs: list[float], ys: list[float]) -> dict[str, list[float]]:
    from backend.sessions import close_circuit_loop

    n = min(len(xs), len(ys))
    if n < 2:
        return {"x": [], "y": []}
    xs, ys = xs[:n], ys[:n]
    step = max(1, n // 400)
    xs, ys = xs[::step], ys[::step]
    xs, ys = close_circuit_loop(xs, ys)
    return {"x": xs, "y": ys}


def _one_lap_gps(sess: Any, *, lap_n: int = 3) -> dict[str, list[float]]:
    """One flying lap of GPS for the race leader. Avoids formation-lap chaos."""
    from backend.sessions import load_position_data_only

    raw = load_position_data_only(sess)
    if not raw:
        return {"x": [], "y": []}
    codes = _code_by_num(sess)
    leader = _race_leader_code(sess)
    candidates: list[str] = []
    if leader:
        candidates.append(leader)
    for code in codes.values():
        if code not in candidates:
            candidates.append(code)
    for drv_key in raw:
        mapped = str(drv_key)
        if str(drv_key).isdigit():
            try:
                mapped = codes.get(int(drv_key), mapped)
            except (TypeError, ValueError):
                pass
        if mapped not in candidates:
            candidates.append(mapped)
    for code in candidates:
        df = _pos_df_for_code(raw, code, codes)
        if df is None:
            continue
        for try_lap in (lap_n, 2, 4, 5, 1):
            start, end = _lap_window(sess, code, try_lap)
            xs, ys = _xy_from_df(df, start, end)
            if len(xs) >= 20:
                return _downsample_close(xs, ys)
    for df in raw.values():
        xs, ys = _xy_from_df(df)
        if len(xs) < 40:
            continue
        chunk = max(40, len(xs) // 8)
        mid = min(len(xs) - chunk, max(0, chunk))
        return _downsample_close(xs[mid : mid + chunk], ys[mid : mid + chunk])
    return {"x": [], "y": []}


def _outline_is_map_space(outline: dict[str, list[float]]) -> bool:
    xs = outline.get("x") or []
    if len(xs) < 2:
        return False
    return (max(xs) - min(xs)) < 800.0


def _outline_with_source(
    sess: Any, year: int, round_number: int
) -> tuple[dict[str, list[float]], str]:
    """Single-lap circuit path. Prefer FastF1 circuit_map_quick; else leader lap 3 GPS."""
    try:
        from backend.sessions import circuit_map_quick

        cmap = circuit_map_quick(int(year), int(round_number))
        if cmap is not None:
            xs = list(getattr(cmap, "x", None) or [])
            ys = list(getattr(cmap, "y", None) or [])
            if getattr(cmap, "available", False) and len(xs) >= 2 and len(ys) >= 2:
                n = min(len(xs), len(ys))
                return {"x": xs[:n], "y": ys[:n]}, "circuit_map_quick"
    except Exception as extra:
        _log.warning("circuit_map_quick failed for %s R%s: %s", year, round_number, extra)
    return _one_lap_gps(sess, lap_n=3), "gps_fallback"


def _outline(sess: Any, year: int, round_number: int) -> dict[str, list[float]]:
    outline, _source = _outline_with_source(sess, year, round_number)
    return outline


def _drivers(sess: Any) -> list[dict[str, Any]]:
    from backend.standings import team_colour

    out: list[dict[str, Any]] = []
    results = getattr(sess, "results", None)
    if results is None or getattr(results, "empty", True):
        return out
    ordered = results.sort_values("GridPosition") if "GridPosition" in results.columns else results
    for rec in ordered.itertuples(index=False):
        code = str(getattr(rec, "Abbreviation", "") or "")
        if not code:
            continue
        grid = getattr(rec, "GridPosition", None)
        try:
            grid_n = int(grid) if grid is not None and str(grid) != "nan" else None
        except (TypeError, ValueError):
            grid_n = None
        team = str(getattr(rec, "TeamName", "") or "")
        name = str(getattr(rec, "FullName", "") or getattr(rec, "BroadcastName", "") or code)
        colour = team_colour(team) or "#888888"
        num = getattr(rec, "DriverNumber", None)
        try:
            number = int(float(num)) if num is not None and str(num) != "nan" else None
        except (TypeError, ValueError):
            number = None
        out.append(
            {
                "code": code,
                "name": name,
                "team": team,
                "colour": colour,
                "grid_position": grid_n,
                "number": number,
            }
        )
    return out


def _laps_stints(sess: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import pandas as pd

    laps_out: list[dict[str, Any]] = []
    stints: dict[tuple[str, int], dict[str, Any]] = {}
    laps = getattr(sess, "laps", None)
    if laps is None or laps.empty:
        raise RuntimeError("FastF1 laps empty")
    for rec in laps.itertuples(index=False):
        code = str(getattr(rec, "Driver", "") or "")
        lap_n = int(getattr(rec, "LapNumber", 0) or 0)
        if not code or lap_n < 1:
            continue
        compound = getattr(rec, "Compound", None)
        try:
            compound_s = None if compound is None or pd.isna(compound) else str(compound)
        except (TypeError, ValueError):
            compound_s = str(compound) if compound is not None else None
        pos = getattr(rec, "Position", None)
        try:
            pos_n = int(pos) if pos is not None and not pd.isna(pos) else None
        except (TypeError, ValueError):
            pos_n = None
        tyre = getattr(rec, "TyreLife", None)
        try:
            tyre_n = int(tyre) if tyre is not None and not pd.isna(tyre) else None
        except (TypeError, ValueError):
            tyre_n = None
        stint_n = getattr(rec, "Stint", None)
        try:
            stint_i = int(stint_n) if stint_n is not None and not pd.isna(stint_n) else 1
        except (TypeError, ValueError):
            stint_i = 1
        pit_in = pd.notna(getattr(rec, "PitInTime", None))
        status = getattr(rec, "TrackStatus", None)
        try:
            track = None if status is None or pd.isna(status) else str(status)
        except (TypeError, ValueError):
            track = str(status) if status is not None else None
        result_status = str(getattr(rec, "Deleted", "") or "")
        laps_out.append(
            {
                "lap": lap_n,
                "driver": code,
                "position": pos_n,
                "gap_to_leader_s": None,
                "gap_ahead_s": None,
                "compound": compound_s,
                "tyre_life": tyre_n,
                "stint_number": stint_i,
                "pit_this_lap": bool(pit_in),
                "is_dnf": False,
                "is_dsq": "DSQ" in result_status.upper() or "DISQUAL" in result_status.upper(),
                "track_status": track,
                "lap_time_s": _td_s(getattr(rec, "LapTime", None)),
                "sector_1_s": _td_s(getattr(rec, "Sector1Time", None)),
                "sector_2_s": _td_s(getattr(rec, "Sector2Time", None)),
                "sector_3_s": _td_s(getattr(rec, "Sector3Time", None)),
            }
        )
        key = (code, stint_i)
        if key not in stints:
            stints[key] = {
                "driver": code,
                "stint": stint_i,
                "compound": compound_s,
                "lap_start": lap_n,
                "lap_end": lap_n,
            }
        else:
            stints[key]["lap_end"] = lap_n
    _fill_gaps(laps_out)
    _mark_dnf(laps_out, sess)
    return laps_out, list(stints.values())


def _fill_gaps(laps: list[dict[str, Any]]) -> None:
    per: dict[str, float] = {}
    for row in sorted(laps, key=lambda r: (int(r["lap"]), int(r.get("position") or 99))):
        code = str(row["driver"])
        t = row.get("lap_time_s")
        if t:
            per[code] = per.get(code, 0.0) + float(t)
        row["_cum"] = per.get(code)
    by_lap: dict[int, list[dict[str, Any]]] = {}
    for row in laps:
        by_lap.setdefault(int(row["lap"]), []).append(row)
    for rows in by_lap.values():
        ranked = sorted(
            [r for r in rows if r.get("_cum") is not None],
            key=lambda r: float(r["_cum"]),
        )
        if not ranked:
            continue
        leader = float(ranked[0]["_cum"])
        prev = leader
        for i, row in enumerate(ranked):
            cum = float(row["_cum"])
            row["gap_to_leader_s"] = round(cum - leader, 3)
            row["gap_ahead_s"] = round(cum - prev, 3) if i else 0.0
            prev = cum
    for row in laps:
        row.pop("_cum", None)


def _mark_dnf(laps: list[dict[str, Any]], sess: Any) -> None:
    results = getattr(sess, "results", None)
    if results is None or getattr(results, "empty", True):
        return
    dnf: set[str] = set()
    for rec in results.itertuples(index=False):
        code = str(getattr(rec, "Abbreviation", "") or "")
        status = str(getattr(rec, "Status", "") or "").upper()
        finished = status in {"FINISHED", "FINISHED LAP", ""} or "+" in status
        if not code or not status or finished:
            continue
        tokens = ("DNF", "RETIRE", "ACCIDENT", "ENGINE", "COLLISION", "WITHDREW")
        named = any(tok in status for tok in tokens)
        other = not status[0].isdigit() and "LAP" not in status
        if named or other:
            dnf.add(code)
    if not dnf:
        return
    last_lap: dict[str, int] = {}
    for row in laps:
        last_lap[str(row["driver"])] = max(last_lap.get(str(row["driver"]), 0), int(row["lap"]))
    for row in laps:
        code = str(row["driver"])
        if code in dnf and int(row["lap"]) == last_lap.get(code, 0):
            row["is_dnf"] = True


def _weather(sess: Any, laps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import pandas as pd

    wd = getattr(sess, "weather_data", None)
    total = max((int(r["lap"]) for r in laps), default=0)
    if wd is None or getattr(wd, "empty", True) or total < 1:
        return [
            {"lap": i, "rainfall": False, "track_temp_c": None, "air_temp_c": None}
            for i in range(1, total + 1)
        ]
    rain = wd["Rainfall"] if "Rainfall" in wd.columns else None
    track = wd["TrackTemp"] if "TrackTemp" in wd.columns else None
    air = wd["AirTemp"] if "AirTemp" in wd.columns else None
    n = len(wd)
    out = []
    for lap in range(1, total + 1):
        idx = min(n - 1, int(round((lap - 1) / max(1, total) * (n - 1))))
        rflag = False
        if rain is not None:
            try:
                rflag = bool(rain.iloc[idx]) if not pd.isna(rain.iloc[idx]) else False
            except Exception:
                rflag = False
        out.append(
            {
                "lap": lap,
                "rainfall": rflag,
                "track_temp_c": _num(track.iloc[idx]) if track is not None else None,
                "air_temp_c": _num(air.iloc[idx]) if air is not None else None,
            }
        )
    return out


def _race_control(sess: Any) -> list[dict[str, Any]]:
    from backend.sessions import _ff1_race_control_rows

    rows = _ff1_race_control_rows(sess)
    out = []
    for row in rows:
        out.append(
            {
                "lap": int(row.get("lap_number") or 0) or None,
                "message": str(row.get("message") or ""),
                "flag": row.get("flag"),
                "category": row.get("category"),
            }
        )
    return out


def _green_flag_s(sess: Any, rc: list[dict[str, Any]]) -> float | None:
    start = None
    # t0_date needs telemetry; this prebuild loads weather/messages only.
    try:
        start = object.__getattribute__(sess, "_t0_date")
    except Exception:
        start = None
    if start is None:
        try:
            start = sess.date
        except Exception:
            start = None
    if start is None:
        return 0.0
    try:
        from backend.sessions import _parse_maybe_dt

        t0 = _parse_maybe_dt(start)
    except Exception:
        t0 = None
    if t0 is None:
        return 0.0
    laps = getattr(sess, "laps", None)
    if laps is not None and not laps.empty and "LapStartDate" in laps.columns:
        first = laps[laps["LapNumber"] == 1]["LapStartDate"].dropna()
        if not first.empty:
            try:
                from backend.sessions import _parse_maybe_dt

                ds = _parse_maybe_dt(first.min())
                if ds is not None:
                    return max(0.0, (ds - t0).total_seconds())
            except Exception:
                pass
    return 0.0


def _clock_s(v: Any) -> float | None:
    """SessionTime timedelta or Date timestamp → seconds on that clock."""
    s = _td_s(v)
    if s is not None:
        return s
    try:
        if hasattr(v, "timestamp"):
            return float(v.timestamp())
    except Exception:
        return None
    return None


def _lap_fracs_for_times(
    times: list[float], starts: list[tuple[float, int, float]]
) -> list[float]:
    """Map sample clocks onto (t0, lap_n, dur). Shift if the clocks do not overlap."""
    if not times:
        return []
    if not starts:
        n = max(1, len(times) - 1)
        return [round(0.999 * i / n, 4) for i in range(len(times))]
    tmin, tmax = times[0], times[-1]
    smin = starts[0][0]
    smax = starts[-1][0] + max(1.0, starts[-1][2])
    offset = 0.0
    if tmax < smin or tmin > smax:
        offset = smin - tmin
    out: list[float] = []
    si = 0
    for t in times:
        tt = t + offset
        while si + 1 < len(starts) and starts[si + 1][0] <= tt:
            si += 1
        t0, lap_n, dur = starts[min(si, len(starts) - 1)]
        into = max(0.0, tt - t0)
        out.append((lap_n - 1) + min(0.999, into / max(1.0, dur)))
    return out


def _pos_samples(
    sess: Any, outline: dict[str, list[float]], hz: float
) -> dict[str, list[dict[str, float]]]:
    from backend.sessions import (
        load_position_data_only,
        project_points_along_path,
        stabilize_path_fracs,
    )

    path_x = outline.get("x") or []
    path_y = outline.get("y") or []
    raw = load_position_data_only(sess)
    min_dt = 1.0 / max(0.5, hz)
    laps = getattr(sess, "laps", None)
    code_by_num: dict[int, str] = {}
    abs_starts: dict[str, list[tuple[float, int, float]]] = {}
    rel_starts: dict[str, list[tuple[float, int, float]]] = {}
    acc_by: dict[str, float] = {}
    if laps is not None and not laps.empty:
        import pandas as pd

        for rec in laps.itertuples(index=False):
            code = str(getattr(rec, "Driver", "") or "")
            num = getattr(rec, "DriverNumber", None)
            try:
                if code and num is not None and str(num) != "nan":
                    code_by_num[int(float(num))] = code
            except (TypeError, ValueError):
                pass
            lap_n = int(getattr(rec, "LapNumber", 0) or 0)
            dur = _td_s(getattr(rec, "LapTime", None)) or 90.0
            if not code or lap_n < 1:
                continue
            t_abs = _clock_s(getattr(rec, "LapStartTime", None))
            if t_abs is None:
                t_abs = _clock_s(getattr(rec, "LapStartDate", None))
            if t_abs is not None:
                try:
                    if pd.isna(t_abs):
                        t_abs = None
                except Exception:
                    pass
            if t_abs is not None:
                abs_starts.setdefault(code, []).append((float(t_abs), lap_n, float(dur)))
            acc = acc_by.get(code, 0.0)
            rel_starts.setdefault(code, []).append((acc, lap_n, float(dur)))
            acc_by[code] = acc + float(dur)
        for bucket in (abs_starts, rel_starts):
            for code in bucket:
                bucket[code].sort()

    out: dict[str, list[dict[str, float]]] = {}
    for drv_key, df in raw.items():
        if df is None or getattr(df, "empty", True) or "X" not in getattr(df, "columns", []):
            continue
        code = str(drv_key)
        if str(drv_key).isdigit():
            code = code_by_num.get(int(drv_key), code)
        xs: list[float] = []
        ys: list[float] = []
        times: list[float] = []
        last_t: float | None = None
        n = len(df)
        cols = getattr(df, "columns", [])
        for i in range(n):
            rec = df.iloc[i]
            t = None
            for col in ("SessionTime", "Time", "Date"):
                if col not in cols:
                    continue
                t = _clock_s(rec[col])
                if t is not None:
                    break
            if t is None:
                continue
            if last_t is not None and (t - last_t) < min_dt:
                continue
            last_t = t
            try:
                x = float(rec["X"])
                y = float(rec["Y"])
            except (TypeError, ValueError):
                continue
            times.append(float(t))
            xs.append(x)
            ys.append(y)
        if len(times) < 2:
            continue
        speeds: list[float] = [0.0] * len(times)
        for i in range(1, len(times)):
            dt = times[i] - times[i - 1]
            if dt <= 0:
                speeds[i] = speeds[i - 1]
                continue
            # FastF1 position X/Y are 1/10 metre.
            dist_m = math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]) / 10.0
            kph = dist_m / dt * 3.6
            if not math.isfinite(kph) or kph < 0:
                kph = 0.0
            speeds[i] = min(360.0, kph)
        for i in range(1, len(speeds)):
            speeds[i] = 0.35 * speeds[i] + 0.65 * speeds[i - 1]
        if path_x and path_y:
            fracs = stabilize_path_fracs(project_points_along_path(xs, ys, path_x, path_y))
        else:
            fracs = [i / max(1, len(times) - 1) for i in range(len(times))]
        starts = abs_starts.get(code) or rel_starts.get(code) or []
        lap_fracs = _lap_fracs_for_times(times, starts)
        if lap_fracs and max(lap_fracs) < 1.0 and rel_starts.get(code):
            lap_fracs = _lap_fracs_for_times(times, rel_starts[code])
        samples = [
            {
                "lap_frac": round(float(lf), 4),
                "path_frac": round(float(frac), 5),
                "speed_kph": int(round(float(spd))),
            }
            for lf, frac, spd in zip(lap_fracs, fracs, speeds, strict=False)
        ]
        if samples:
            out[code] = samples
    return out


def _session_key(sess: Any) -> int | None:
    for attr in ("session_key", "sessionKey"):
        v = getattr(sess, attr, None)
        if v:
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    ident = getattr(sess, "api_path", None) or ""
    digits = "".join(ch for ch in str(ident) if ch.isdigit())
    if digits:
        try:
            return int(digits[-8:])
        except ValueError:
            return None
    return None


def build_race_field(year: int, round_number: int, sess: Any) -> dict[str, Any]:
    from backend.calendar import get_round

    rnd = get_round(int(year), int(round_number))
    outline, outline_source = _outline_with_source(sess, year, round_number)
    drivers = _drivers(sess)
    laps, stints = _laps_stints(sess)
    weather = _weather(sess, laps)
    rc = _race_control(sess)
    proj = outline
    if _outline_is_map_space(outline):
        gps_path = _one_lap_gps(sess, lap_n=3)
        if gps_path.get("x"):
            proj = gps_path
    pos = _pos_samples(sess, proj, DEFAULT_HZ)
    date_race = getattr(rnd, "date_race", None)
    payload = {
        "meta": {
            "year": int(year),
            "round": int(round_number),
            "session_type": "R",
            "circuit_name": str(rnd.circuit_name or rnd.name or ""),
            "total_laps": int(max((int(r["lap"]) for r in laps), default=rnd.total_laps or 0)),
            "date_race": (
                date_race.isoformat()
                if hasattr(date_race, "isoformat")
                else str(date_race or "")
            ),
            "green_flag_s": _green_flag_s(sess, rc),
            "session_key": _session_key(sess),
            "outline_source": outline_source,
        },
        "outline": outline,
        "drivers": drivers,
        "laps": laps,
        "stints": stints,
        "weather": weather,
        "race_control": rc,
        "pos_samples": pos,
    }
    return payload


def _fit_pos_under_budget(field: dict[str, Any], max_bytes: int) -> bytes:
    """Thin pos_samples from the original 2Hz series until JSON is under max_bytes."""
    original = {
        code: list(rows)
        for code, rows in (field.get("pos_samples") or {}).items()
        if isinstance(rows, list)
    }
    raw = json.dumps(field, separators=(",", ":")).encode("utf-8")
    if len(raw) <= max_bytes or not original:
        return raw
    for step, label in ((2, "1Hz"), (4, "0.5Hz"), (8, "0.25Hz"), (16, "0.125Hz")):
        field["pos_samples"] = {code: rows[::step] for code, rows in original.items()}
        raw = json.dumps(field, separators=(",", ":")).encode("utf-8")
        _log.info("pos_samples %s (step=%s) → %.1fKB", label, step, len(raw) / 1024)
        if len(raw) <= max_bytes:
            return raw
    raise RuntimeError(
        f"race_field.json still {len(raw)} bytes after thinning pos_samples"
    )


def build_ghost(
    year: int,
    round_number: int,
    driver: str,
    sess: Any,
    field: dict[str, Any],
) -> dict[str, Any]:
    from aris.ghost import (
        field_cumulative_by_lap,
        pick_strategy_recommendation,
        plan_from_pits,
        r2_ghost_tick,
        schedule_from_recommendation,
        score_parallel_ghost,
    )
    from aris.physics.tires import normalize_compound
    from aris.recommend import recommend as aris_recommend
    from aris.state import RaceState

    code = str(driver).upper()
    focus_laps = [r for r in field["laps"] if str(r["driver"]).upper() == code]
    if not focus_laps:
        raise RuntimeError(f"no laps for driver {code}")
    focus_laps = sorted(focus_laps, key=lambda r: int(r["lap"]))
    start_compound = normalize_compound(str(focus_laps[0].get("compound") or "MEDIUM"))
    total = int(field["meta"]["total_laps"])
    country = ""
    try:
        from backend.calendar import get_round

        country = str(get_round(int(year), int(round_number)).country or "")
    except Exception:
        country = str(field["meta"].get("circuit_name") or "")

    template = RaceState(
        session_id=int(field["meta"].get("session_key") or 0),
        driver_id=0,
        driver_code=code,
        driver_name=code,
        year=int(year),
        round_no=int(round_number),
        country=country or "Netherlands",
        lap_number=1,
        compound=start_compound,
        tyre_life=1,
        fuel_kg=110.0,
        laps_remaining=max(0, total - 1),
        total_laps=total,
        position=int(focus_laps[0].get("position") or 1),
        track_status=str(focus_laps[0].get("track_status") or "1"),
    )
    card = None
    for decision_lap in (1, 2):
        try:
            state = template.model_copy(update={"lap_number": decision_lap})
            rec = aris_recommend(state, top_k=3, mc_draws=0)
            card = pick_strategy_recommendation(rec)
            if card and str(card.get("label") or "") != "STRATEGY_RESET":
                break
        except Exception as extra:
            _log.info("recommend() lap %s failed: %s", decision_lap, extra)
            card = None
    if card:
        plan = schedule_from_recommendation(card, start_compound=start_compound, lap_number=1)
        label = str(card.get("label") or "")
    else:
        plan = plan_from_pits([], [], start_compound, label="STAY_OUT")
        label = "STAY_OUT"

    lap_rows = []
    for row in focus_laps:
        lap_rows.append(
            {
                "lap_number": int(row["lap"]),
                "compound": str(row.get("compound") or start_compound),
                "tyre_life": int(row.get("tyre_life") or 1),
                "real_action": (
                    f"PIT_NOW_{row.get('compound') or 'HARD'}"
                    if row.get("pit_this_lap")
                    else "STAY_OUT"
                ),
                "position": int(row.get("position") or 10),
                "lap_time_s": row.get("lap_time_s"),
                "track_status": str(row.get("track_status") or "1"),
            }
        )
    times: dict[str, dict[int, float]] = {}
    for row in field["laps"]:
        t = row.get("lap_time_s")
        if not t:
            continue
        times.setdefault(str(row["driver"]).upper(), {})[int(row["lap"])] = float(t)
    field_cum = field_cumulative_by_lap(times)
    typical = 90.0
    raw_times = [float(r["lap_time_s"]) for r in focus_laps if r.get("lap_time_s")]
    if raw_times:
        typical = float(sorted(raw_times)[len(raw_times) // 2])
        if typical < 30:
            typical = 90.0
    ticks_map = score_parallel_ghost(
        template_state=template,
        lap_rows=lap_rows,
        plan=plan,
        typical_lap_s=typical,
        field_cum_by_lap=field_cum,
    )
    ticks = [
        r2_ghost_tick(int(lap), tick, plan.pit_laps)
        for lap, tick in sorted(ticks_map.items())
        if isinstance(tick, dict)
    ]
    last = next((ticks_map[k] for k in sorted(ticks_map, reverse=True) if ticks_map[k]), {}) or {}
    return {
        "driver": code,
        "strategy": {
            "pit_laps": list(plan.pit_laps),
            "compounds": list(plan.pit_compounds),
            "label": label,
        },
        "ticks": ticks,
        "outcome": {
            "aris_action": last.get("aris_action") or label,
            "real_action": last.get("real_action") or "STAY_OUT",
            "verdict": last.get("outcome"),
        },
    }


def _default_driver(sess: Any, requested: str | None) -> str:
    if requested:
        return str(requested).upper()
    results = getattr(sess, "results", None)
    if results is not None and not getattr(results, "empty", True):
        try:
            if "GridPosition" in results.columns:
                ordered = results.sort_values("GridPosition")
                code = str(ordered.iloc[0]["Abbreviation"] or "")
                if code:
                    return code
            code = str(results.iloc[0]["Abbreviation"] or "")
            if code:
                return code
        except Exception:
            pass
    return "VER"


def build_one(
    year: int,
    round_number: int,
    driver: str | None,
    *,
    skip_existing: bool,
    no_upload: bool,
) -> dict[str, Any]:
    field_path = _local_key(year, round_number, "race_field.json")
    if skip_existing and _r2_exists(year, round_number, "race_field.json"):
        _log.info("skip existing %s R%s", year, round_number)
        return {"year": year, "round": round_number, "skipped": True}

    t0 = time.monotonic()
    sess = _load_session(year, round_number)
    field = build_race_field(year, round_number, sess)
    raw = _fit_pos_under_budget(field, MAX_FIELD_BYTES)
    if len(raw) > MAX_FIELD_BYTES:
        raise RuntimeError(
            f"{year} R{round_number} race_field.json still {len(raw)} bytes after downsample"
        )
    field_bytes = _write_json(field_path, field)
    code = _default_driver(sess, driver)
    ghost = build_ghost(year, round_number, code, sess, field)
    ghost_path = _local_key(year, round_number, f"ghost_{code}.json")
    ghost_bytes = _write_json(ghost_path, ghost)
    _log.info(
        "built %s R%s driver=%s field=%.1fKB ghost=%.1fKB in %.1fs",
        year,
        round_number,
        code,
        field_bytes / 1024,
        ghost_bytes / 1024,
        time.monotonic() - t0,
    )
    if not no_upload:
        _upload(field_path, f"replay/{year}/{round_number}/race_field.json")
        _upload(ghost_path, f"replay/{year}/{round_number}/ghost_{code}.json")
    return {
        "year": year,
        "round": round_number,
        "driver": code,
        "field_bytes": field_bytes,
        "ghost_bytes": ghost_bytes,
        "skipped": False,
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Prebuild race JSON for R2 replay")
    parser.add_argument("--year", type=int)
    parser.add_argument("--round", type=int, dest="round_number")
    parser.add_argument("--driver", default=None)
    parser.add_argument("--all-completed", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--no-upload", action="store_true")
    args = parser.parse_args(argv)

    if args.all_completed:
        jobs = completed_jobs()
    elif args.year and args.round_number:
        jobs = completed_jobs(year=args.year, round_number=args.round_number)
        if not jobs:
            jobs = [(int(args.year), int(args.round_number), "")]
    else:
        parser.error("pass --year and --round, or --all-completed")
        return 2

    failures: list[str] = []
    for year, rnd, name in jobs:
        _log.info("building %s R%s %s", year, rnd, name)
        try:
            build_one(
                year,
                rnd,
                args.driver,
                skip_existing=args.skip_existing,
                no_upload=args.no_upload,
            )
        except Exception as extra:
            _log.exception("FAILED %s R%s: %s", year, rnd, extra)
            failures.append(f"{year} R{rnd}: {extra}")
            if not args.all_completed:
                return 1
    if failures:
        _log.error("%s race(s) failed (continued): %s", len(failures), "; ".join(failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
