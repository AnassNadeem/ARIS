"""Leave-one-era-out per-circuit OLS tyre deg slopes (T2-A).

Fits slope-only ``np.polyfit(tyre_age, lap_time, 1)`` on FastF1 laps
(2018–2023 by default). Does not write track YAML. Output is consumed by
``aris.physics.tires.get_compound_slopes`` behind ``ARIS_USE_CIRCUIT_DEG``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

import pandas as pd
from fastf1.core import Session
from fastf1.events import Event

from aris.physics.stint import detect_stints, filter_clean_laps  # noqa: E402
from aris.physics.tires import normalize_compound  # noqa: E402
from fit_calendar_tire_slopes import _CACHE, _CIRCUITS  # noqa: E402

_DRY = frozenset({"SOFT", "MEDIUM", "HARD"})
_MIN_STINT_LAPS = 5
_MIN_STINTS = 3
_SESSION_CLIP = 1.10
_DEFAULT_YEARS = tuple(range(2018, 2024))
_SESSIONS = ("R", "FP2")
_SESSION_FOLDER = {
    "R": "Race",
    "FP2": "Practice_2",
    "FP1": "Practice_1",
    "S": "Sprint",
    "Q": "Qualifying",
}
_EVENT_STEM_ALIASES = {
    "saudi arabian grand prix": "saudi_arabia",
    "dutch grand prix": "netherlands",
    "british grand prix": "britain",
    "united states grand prix": "usa",
    "sao paulo grand prix": "brazil",
    "brazilian grand prix": "brazil",
    "mexican grand prix": "mexico",
    "emilia romagna grand prix": "imola",
    "las vegas grand prix": "las_vegas",
    "abu dhabi grand prix": "abu_dhabi",
    "mexico city grand prix": "mexico",
    "italian grand prix": "italy",
    "spanish grand prix": "spain",
    "australian grand prix": "australia",
    "japanese grand prix": "japan",
    "chinese grand prix": "china",
    "hungarian grand prix": "hungary",
    "belgian grand prix": "belgium",
    "austrian grand prix": "austria",
    "canadian grand prix": "canada",
    "azerbaijan grand prix": "azerbaijan",
    "monaco grand prix": "monaco",
    "singapore grand prix": "singapore",
    "qatar grand prix": "qatar",
    "bahrain grand prix": "bahrain",
    "miami grand prix": "miami",
}


def _enable_cache() -> None:
    _CACHE.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(_CACHE))


def _circuit_allowlist() -> dict[str, set[int]]:
    allowed: dict[str, set[int]] = {}
    for spec in _CIRCUITS:
        allowed[str(spec["stem"])] = {int(y) for y in spec["years"]}  # type: ignore[arg-type]
    return allowed


def _stem_from_event_folder(folder_name: str) -> str | None:
    parts = folder_name.split("_")
    if len(parts) < 2:
        return None
    event = " ".join(parts[1:]).lower()
    if event in _EVENT_STEM_ALIASES:
        return _EVENT_STEM_ALIASES[event]
    for spec in _CIRCUITS:
        gp = str(spec["gp"]).lower()
        if event == f"{gp} grand prix":
            return str(spec["stem"])
    return None


def _load_cached_session(year: int, event_dir: Path, session_dir: Path):
    """Load laps from FastF1 on-disk cache without the season schedule API."""
    event_date = event_dir.name.split("_")[0]
    sess_date = session_dir.name.split("_")[0]
    raw_name = session_dir.name.split("_", 1)[1].replace("_", " ")
    event_name = " ".join(event_dir.name.split("_")[1:])
    ts = pd.Timestamp(sess_date)
    data = {
        "RoundNumber": 0,
        "Country": "",
        "Location": "",
        "EventName": event_name,
        "EventDate": pd.Timestamp(event_date),
        "EventFormat": "conventional",
        "Session1": "Practice 1",
        "Session1Date": ts,
        "Session1DateUtc": ts,
        "Session2": "Practice 2",
        "Session2Date": ts,
        "Session2DateUtc": ts,
        "Session3": "Practice 3",
        "Session3Date": ts,
        "Session3DateUtc": ts,
        "Session4": "Qualifying",
        "Session4Date": ts,
        "Session4DateUtc": ts,
        "Session5": "Race",
        "Session5Date": ts,
        "Session5DateUtc": ts,
        "F1ApiSupport": True,
    }
    if raw_name not in ("Race", "Practice 1", "Practice 2", "Practice 3", "Qualifying", "Sprint"):
        data["Session5"] = raw_name
        data["Session5Date"] = ts
        data["Session5DateUtc"] = ts
    elif raw_name != "Race":
        # Keep Race on Session5; put this session on its numbered slot.
        slot = {
            "Practice 1": "Session1",
            "Practice 2": "Session2",
            "Practice 3": "Session3",
            "Qualifying": "Session4",
            "Sprint": "Session4",
        }.get(raw_name, "Session5")
        data[slot] = raw_name
        data[f"{slot}Date"] = ts
        data[f"{slot}DateUtc"] = ts
    event = Event(pd.Series(data), year=year)
    sess = Session(event=event, session_name=raw_name, f1_api_support=True)
    sess.load(laps=True, telemetry=False, weather=False, messages=False)
    return sess


def _tyre_age(grp) -> np.ndarray:
    if "TyreLife" in grp.columns and grp["TyreLife"].notna().any():
        age = grp["TyreLife"].astype(float).to_numpy()
        if np.isfinite(age).sum() >= _MIN_STINT_LAPS:
            return age
    return np.arange(1, len(grp) + 1, dtype=float)


def _fit_session_stints(laps) -> list[tuple[str, float]]:
    if laps is None or len(laps) == 0:
        return []
    try:
        enriched = detect_stints(laps)
    except Exception:
        return []
    finite = enriched[enriched["LapTimeS"].notna()]
    if finite.empty:
        return []
    session_median = float(finite["LapTimeS"].median())
    if not np.isfinite(session_median) or session_median <= 0:
        return []
    clean = filter_clean_laps(enriched)
    clean = clean[clean["LapTimeS"] <= _SESSION_CLIP * session_median]
    if clean.empty or "StintId" not in clean.columns:
        return []
    out: list[tuple[str, float]] = []
    for _key, grp in clean.groupby(["Driver", "StintId"], sort=False):
        grp = grp.sort_values("LapNumber")
        if len(grp) < _MIN_STINT_LAPS:
            continue
        compound = normalize_compound(str(grp["Compound"].iloc[0]) if "Compound" in grp.columns else "")
        if compound not in _DRY:
            continue
        if grp["Compound"].map(lambda c: normalize_compound(str(c))).nunique() != 1:
            continue
        age = _tyre_age(grp)
        times = grp["LapTimeS"].to_numpy(dtype=float)
        mask = np.isfinite(age) & np.isfinite(times)
        if int(mask.sum()) < _MIN_STINT_LAPS:
            continue
        try:
            slope = float(np.polyfit(age[mask], times[mask], 1)[0])
        except (np.linalg.LinAlgError, TypeError, ValueError):
            continue
        if not np.isfinite(slope):
            continue
        out.append((compound, slope))
    return out


def train(
    *,
    years: list[int],
    output: Path,
    dry_run: bool = False,
    sessions: tuple[str, ...] = _SESSIONS,
) -> dict:
    _enable_cache()
    year_set = {int(y) for y in years}
    allow = _circuit_allowlist()
    suffixes = tuple(_SESSION_FOLDER[s] for s in sessions if s in _SESSION_FOLDER)
    planned: list[tuple[int, str, Path, Path]] = []
    for year in sorted(year_set):
        year_dir = _CACHE / str(year)
        if not year_dir.is_dir():
            continue
        for event_dir in sorted(year_dir.iterdir()):
            if not event_dir.is_dir() or "Grand_Prix" not in event_dir.name:
                continue
            stem = _stem_from_event_folder(event_dir.name)
            if stem is None or year not in allow.get(stem, set()):
                continue
            for sess_dir in sorted(event_dir.iterdir()):
                if not sess_dir.is_dir():
                    continue
                if not any(sess_dir.name.endswith(suf) for suf in suffixes):
                    continue
                planned.append((year, stem, event_dir, sess_dir))

    if dry_run:
        print(f"dry-run: {len(planned)} cached session loads", flush=True)
        for year, stem, event_dir, sess_dir in planned:
            print(f"  {year} {event_dir.name} {sess_dir.name} -> {stem}", flush=True)
        return {"meta": {"dry_run": True, "n_sessions": len(planned)}}

    samples: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    skipped = 0
    fitted_sessions = 0
    for i, (year, stem, event_dir, sess_dir) in enumerate(planned, start=1):
        print(f"[{i}/{len(planned)}] {year} {event_dir.name} {sess_dir.name}", flush=True)
        try:
            sess = _load_cached_session(year, event_dir, sess_dir)
        except Exception as extra:
            skipped += 1
            print(f"  skip: {extra}", flush=True)
            continue
        try:
            rows = _fit_session_stints(sess.laps)
        except Exception as extra:
            skipped += 1
            print(f"  fit skip: {extra}", flush=True)
            continue
        if not rows:
            skipped += 1
            continue
        fitted_sessions += 1
        for compound, slope in rows:
            samples[stem][compound].append(slope)
        if i % 10 == 0:
            _write_payload(
                output, samples, years, skipped=skipped, fitted_sessions=fitted_sessions
            )
            print(f"  checkpoint -> {output}", flush=True)

    payload = _write_payload(
        output, samples, years, skipped=skipped, fitted_sessions=fitted_sessions
    )
    print(f"wrote {output} circuits={len(payload) - 1} skipped={skipped}", flush=True)
    return payload


def _write_payload(
    output: Path,
    samples: dict[str, dict[str, list[float]]],
    years: list[int],
    *,
    skipped: int,
    fitted_sessions: int,
) -> dict:
    payload: dict = {
        "meta": {
            "train_years": sorted(int(y) for y in years),
            "max_year": max(int(y) for y in years) if years else 2023,
            "fit_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "method": "ols_tyre_age_lap_time",
            "min_stints": _MIN_STINTS,
            "skipped_sessions": skipped,
            "fitted_sessions": fitted_sessions,
        }
    }
    for stem, by_compound in sorted(samples.items()):
        circuit: dict[str, dict[str, float | int]] = {}
        for compound, slopes in sorted(by_compound.items()):
            arr = np.asarray(slopes, dtype=float)
            arr = arr[np.isfinite(arr)]
            if arr.size < _MIN_STINTS:
                continue
            circuit[compound] = {
                "slope": round(float(np.mean(arr)), 6),
                "n_stints": int(arr.size),
                "std": round(float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0, 6),
            }
        if circuit:
            payload[stem] = circuit
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Train leave-one-era-out circuit deg slopes")
    parser.add_argument("--years", type=int, nargs="+", default=list(_DEFAULT_YEARS))
    parser.add_argument("--output", type=Path, default=_ROOT / "models" / "circuit_deg_slopes.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--sessions",
        nargs="+",
        default=list(_SESSIONS),
        help="FastF1 session types (default: R FP2)",
    )
    args = parser.parse_args()
    train(
        years=list(args.years),
        output=args.output,
        dry_run=args.dry_run,
        sessions=tuple(str(s).upper() for s in args.sessions),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
