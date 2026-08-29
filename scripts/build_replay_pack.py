"""Convert FastF1 session telemetry into static 60-second JSON chunks."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import fastf1

# Configuration
HZ = 5  # 5 frames per second (200ms intervals)
INTERVAL = pd.Timedelta(seconds=1 / HZ)
CHUNK_SIZE_SEC = 60  # 60 seconds per chunk

_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = str(_ROOT / "static_replays")
CACHE_DIR = str(_ROOT / "fastf1_cache")


def _to_timedelta_index(series: pd.Series) -> pd.Series:
    """Coerce FastF1 SessionTime into a TimedeltaIndex-compatible series."""
    if pd.api.types.is_timedelta64_dtype(series):
        return series
    if pd.api.types.is_datetime64_any_dtype(series):
        return series - series.min()
    sample = series.dropna()
    if sample.empty:
        return pd.to_timedelta(series, errors="coerce")
    first = sample.iloc[0]
    if isinstance(first, pd.Timedelta):
        return pd.to_timedelta(series)
    if isinstance(first, (np.timedelta64,)):
        return pd.to_timedelta(series)
    return pd.to_timedelta(series, errors="coerce")


def _resample_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    """Resample to a fixed 5 Hz clock and interpolate gaps."""
    df = df.sort_index()
    if not isinstance(df.index, pd.TimedeltaIndex):
        df.index = pd.to_timedelta(df.index, errors="coerce")
        df = df[~df.index.isna()].sort_index()
    if df.empty:
        raise ValueError("Empty SessionTime index after coercion")

    try:
        resampled = df.resample(INTERVAL).interpolate(method="linear").ffill().bfill()
    except (TypeError, ValueError):
        resampled = df.resample(INTERVAL).mean().interpolate(method="linear").ffill().bfill()
    return resampled


def build_static_replay(year: int, track: str, session_name: str):
    print(f"--- [ETL START] {year} {track} Session: {session_name} ---")

    os.makedirs(CACHE_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(CACHE_DIR)

    session = fastf1.get_session(year, track, session_name)
    session.load(telemetry=True, weather=False)

    drivers = session.drivers
    master_frames = {}  # { time_sec: { driver_code: { x, y, s } } }
    processed_drivers = []
    skipped_drivers = {}

    print(f"Resampling telemetry for {len(drivers)} drivers at {HZ} Hz...")

    for drv in drivers:
        try:
            laps = (
                session.laps.pick_drivers(drv)
                if hasattr(session.laps, "pick_drivers")
                else session.laps.pick_driver(drv)
            )
            if len(laps) == 0:
                skipped_drivers[drv] = "No laps found"
                continue

            tel = laps.get_telemetry()
            if tel is None or tel.empty or "X" not in tel.columns or "Y" not in tel.columns:
                skipped_drivers[drv] = "No X/Y telemetry available"
                continue

            # Select available required columns
            cols = ["SessionTime", "X", "Y", "Speed"]
            missing_session_time = "SessionTime" not in tel.columns
            if missing_session_time:
                skipped_drivers[drv] = "No SessionTime column"
                continue

            df = tel[[c for c in cols if c in tel.columns]].copy()
            df["SessionTime"] = _to_timedelta_index(df["SessionTime"])

            # Drop duplicate session timestamps
            df = df.drop_duplicates(subset=["SessionTime"]).dropna(subset=["SessionTime"])
            df = df.set_index("SessionTime")

            # Resample to fixed 5Hz clock and interpolate gaps
            resampled = _resample_telemetry(df)

            for time_val, row in resampled.iterrows():
                time_sec = round(time_val.total_seconds(), 2)
                if time_sec not in master_frames:
                    master_frames[time_sec] = {}

                master_frames[time_sec][drv] = {
                    "x": int(row["X"]) if ("X" in row and not pd.isna(row["X"])) else 0,
                    "y": int(row["Y"]) if ("Y" in row and not pd.isna(row["Y"])) else 0,
                    "s": int(row["Speed"]) if ("Speed" in row and not pd.isna(row["Speed"])) else 0,
                }

            processed_drivers.append(drv)
            print(f"  [ok] Processed Driver: {drv}")
        except Exception as e:
            skipped_drivers[drv] = str(e)
            print(f"  [fail] Failed Driver {drv}: {e}")

    if not master_frames:
        raise RuntimeError("No telemetry frames were generated. Check FastF1 load parameters.")

    sorted_times = sorted(master_frames.keys())
    session_slug = f"{year}_{track}_{session_name}".lower().replace(" ", "_")
    session_dir = os.path.join(OUTPUT_DIR, session_slug)
    os.makedirs(session_dir, exist_ok=True)

    print(f"Chunking {len(sorted_times)} total time steps into {CHUNK_SIZE_SEC}s blocks...")
    current_chunk_idx = 0
    current_chunk_data = []
    chunk_start_time = sorted_times[0]

    for t in sorted_times:
        current_chunk_data.append({"t": t, "cars": master_frames[t]})

        if t - chunk_start_time >= CHUNK_SIZE_SEC:
            _save_chunk(session_dir, current_chunk_idx, current_chunk_data)
            current_chunk_idx += 1
            current_chunk_data = []
            chunk_start_time = t

    if current_chunk_data:
        _save_chunk(session_dir, current_chunk_idx, current_chunk_data)
        current_chunk_idx += 1

    manifest = {
        "session": session_slug,
        "start_time": float(sorted_times[0]),
        "end_time": float(sorted_times[-1]),
        "total_chunks": current_chunk_idx,
        "hz": HZ,
        "chunk_size_sec": CHUNK_SIZE_SEC,
    }
    manifest_path = os.path.join(session_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote manifest: {manifest_path}")

    print(f"\n--- [ETL COMPLETE] ---")
    print(f"Saved: {current_chunk_idx} chunk files in '{session_dir}/'")
    print(f"Successful Drivers ({len(processed_drivers)}): {processed_drivers}")
    if skipped_drivers:
        print(f"Skipped Drivers ({len(skipped_drivers)}): {skipped_drivers}")

    return {
        "session_dir": session_dir,
        "chunks": current_chunk_idx,
        "processed_drivers": processed_drivers,
        "skipped_drivers": skipped_drivers,
        "time_steps": len(sorted_times),
    }


def _save_chunk(folder: str, idx: int, data: list):
    filename = os.path.join(folder, f"chunk_{idx}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))


if __name__ == "__main__":
    # Test session (Change if testing another race)
    build_static_replay(2024, "Zandvoort", "R")
