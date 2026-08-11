"""Derive data/tracks/<track>.yaml from FastF1 — same fields as bahrain.yaml,
plus optional corners/lap_length so the bicycle model can stop falling back
to Bahrain geometry.

Method:
  - total_laps: session.total_laps
  - pit_loss_s: median (pit in/out lap time - matched clean lap time) at similar
    tyre life within the same race
  - corners: get_circuit_info() markers + local circle fit on fastest-lap
    telemetry XY (Corner radius_m / arc_length_m), matching bicycle.Corner
  - bahrain.yaml itself is left untouched (physics_profile path) unless
    --strict-pit is used to refresh pit_loss_s only via --pit-loss-only
"""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import numpy as np
import yaml

import aris  # noqa: F401 — requests/forward-ref shim before fastf1
import fastf1
from fastf1.exceptions import RateLimitExceededError

_REPO = Path(__file__).resolve().parents[1]
_TRACKS = _REPO / "data" / "tracks"
_CACHE = _REPO / "fastf1_cache"

# GP name (FastF1 get_session arg) -> yaml stem / display metadata
_TRACK_META: dict[str, dict[str, object]] = {
    "China": {
        "stem": "china",
        "name": "China",
        "country": "China",
        "aliases": ["china", "shanghai", "chinese"],
    },
    "Monaco": {
        "stem": "monaco",
        "name": "Monaco",
        "country": "Monaco",
        "aliases": ["monaco", "montecarlo", "monte carlo"],
    },
    "Spain": {
        "stem": "spain",
        "name": "Spain",
        "country": "Spain",
        # No "spanish" alias — 2026 Spanish GP is Madrid (held off / separate).
        "aliases": ["spain", "barcelona", "catalunya"],
    },
    "Belgium": {
        "stem": "belgium",
        "name": "Belgium",
        "country": "Belgium",
        "aliases": ["belgium", "spa", "belgian", "spa-francorchamps"],
    },
    "Abu Dhabi": {
        "stem": "abu_dhabi",
        "name": "Abu Dhabi",
        "country": "UAE",
        "aliases": [
            "abu dhabi",
            "abudhabi",
            "yas marina",
            "yas island",
            "uae",
            "united arab emirates",
        ],
    },
    "Bahrain": {
        "stem": "bahrain",
        "name": "Bahrain",
        "country": "Bahrain",
        "aliases": ["bahrain", "sakhir"],
        "physics_profile": "bahrain_2024",
    },
    "Australia": {
        "stem": "australia",
        "name": "Australia",
        "country": "Australia",
        "aliases": ["australia", "melbourne", "albert park", "australian"],
    },
    "Saudi Arabia": {
        "stem": "saudi_arabia",
        "name": "Saudi Arabia",
        "country": "Saudi Arabia",
        "aliases": ["saudi arabia", "saudi", "jeddah", "saudi arabian"],
    },
    "Japan": {
        "stem": "japan",
        "name": "Japan",
        "country": "Japan",
        "aliases": ["japan", "suzuka", "japanese"],
    },
    "Miami": {
        "stem": "miami",
        "name": "Miami",
        "country": "United States",
        "aliases": ["miami", "miami gardens"],
    },
    "Emilia Romagna": {
        "stem": "imola",
        "name": "Imola",
        "country": "Italy",
        "aliases": ["imola", "emilia romagna", "emilia-romagna"],
    },
    "Canada": {
        "stem": "canada",
        "name": "Canada",
        "country": "Canada",
        "aliases": ["canada", "montreal", "montréal", "canadian", "gilles villeneuve"],
    },
    "Austria": {
        "stem": "austria",
        "name": "Austria",
        "country": "Austria",
        "aliases": ["austria", "spielberg", "red bull ring", "austrian", "styrian"],
    },
    "Britain": {
        "stem": "britain",
        "name": "Britain",
        "country": "United Kingdom",
        "aliases": [
            "britain",
            "british",
            "silverstone",
            "united kingdom",
            "great britain",
            "uk",
            "70th anniversary",
        ],
    },
    "Hungary": {
        "stem": "hungary",
        "name": "Hungary",
        "country": "Hungary",
        "aliases": ["hungary", "budapest", "hungaroring", "hungarian"],
    },
    "Netherlands": {
        "stem": "netherlands",
        "name": "Netherlands",
        "country": "Netherlands",
        "aliases": ["netherlands", "zandvoort", "dutch"],
    },
    "Italy": {
        "stem": "italy",
        "name": "Italy",
        "country": "Italy",
        "aliases": ["italy", "monza", "italian"],
    },
    "Azerbaijan": {
        "stem": "azerbaijan",
        "name": "Azerbaijan",
        "country": "Azerbaijan",
        "aliases": ["azerbaijan", "baku", "azerbaijani"],
    },
    "Singapore": {
        "stem": "singapore",
        "name": "Singapore",
        "country": "Singapore",
        "aliases": ["singapore", "marina bay"],
    },
    "United States": {
        "stem": "usa",
        "name": "United States",
        "country": "United States",
        "aliases": ["united states", "usa", "austin", "cota", "americas"],
    },
    "Mexico City": {
        "stem": "mexico",
        "name": "Mexico",
        "country": "Mexico",
        "aliases": ["mexico", "mexico city", "mexican"],
    },
    "Mexico": {
        "stem": "mexico",
        "name": "Mexico",
        "country": "Mexico",
        "aliases": ["mexico", "mexico city", "mexican"],
    },
    "Sao Paulo": {
        "stem": "brazil",
        "name": "Brazil",
        "country": "Brazil",
        "aliases": ["brazil", "brasil", "sao paulo", "são paulo", "interlagos", "brazilian"],
    },
    "Brazil": {
        "stem": "brazil",
        "name": "Brazil",
        "country": "Brazil",
        "aliases": ["brazil", "brasil", "sao paulo", "são paulo", "interlagos", "brazilian"],
    },
    "Las Vegas": {
        "stem": "las_vegas",
        "name": "Las Vegas",
        "country": "United States",
        "aliases": ["las vegas", "vegas"],
    },
    "Qatar": {
        "stem": "qatar",
        "name": "Qatar",
        "country": "Qatar",
        "aliases": ["qatar", "lusail"],
    },
    "France": {
        "stem": "france",
        "name": "France",
        "country": "France",
        "aliases": ["france", "le castellet", "paul ricard", "french"],
    },
    "Germany": {
        "stem": "hockenheim",
        "name": "Hockenheim",
        "country": "Germany",
        "aliases": ["hockenheim", "hockenheimring", "german grand prix"],
    },
    "Eifel": {
        "stem": "nurburgring",
        "name": "Nürburgring",
        "country": "Germany",
        "aliases": ["nurburgring", "nürburgring", "eifel"],
    },
    "Tuscany": {
        "stem": "mugello",
        "name": "Mugello",
        "country": "Italy",
        "aliases": ["mugello", "tuscany", "tuscan"],
    },
    "Portugal": {
        "stem": "portugal",
        "name": "Portugal",
        "country": "Portugal",
        "aliases": ["portugal", "portimao", "portimão", "algarve", "portuguese"],
    },
    "Turkey": {
        "stem": "turkey",
        "name": "Turkey",
        "country": "Turkey",
        "aliases": ["turkey", "istanbul", "turkish"],
    },
    "Russia": {
        "stem": "russia",
        "name": "Russia",
        "country": "Russia",
        "aliases": ["russia", "sochi", "russian"],
    },
}

# Phase D2 default build targets: (year, gp_key). Most recent year in scope
# for multi-year circuits; historical one-offs use their last appearance.
# Madrid 2026 held off (new circuit; must not reuse Catalunya).
# 2020 Sakhir outer held off (wrong-alias vs Bahrain GP — needs Anas).
PHASE_D2_BUILDS: list[tuple[int, str]] = [
    (2025, "Australia"),
    (2025, "Saudi Arabia"),
    (2025, "Japan"),
    (2025, "Miami"),
    (2025, "Emilia Romagna"),
    (2025, "Canada"),
    (2025, "Austria"),
    (2025, "Britain"),
    (2025, "Hungary"),
    (2025, "Netherlands"),
    (2025, "Italy"),
    (2025, "Azerbaijan"),
    (2025, "Singapore"),
    (2025, "United States"),
    (2025, "Mexico City"),
    (2025, "Sao Paulo"),
    (2025, "Las Vegas"),
    (2025, "Qatar"),
    (2022, "France"),
    (2019, "Germany"),
    (2020, "Eifel"),
    (2020, "Tuscany"),
    (2021, "Portugal"),
    (2021, "Turkey"),
    (2021, "Russia"),
]

# Existing six — D3 re-derives pit_loss with strict matcher.
PHASE_D3_PIT_REFRESH: list[tuple[int, str]] = [
    (2024, "Bahrain"),
    (2024, "China"),
    (2024, "Monaco"),
    (2024, "Spain"),
    (2024, "Belgium"),
    (2024, "Abu Dhabi"),
]


def _local_radius_m(x: np.ndarray, y: np.ndarray) -> float | None:
    """Median circumradius of consecutive point triples (metres)."""
    rs: list[float] = []
    for i in range(1, len(x) - 1):
        x1, y1 = float(x[i - 1]), float(y[i - 1])
        x2, y2 = float(x[i]), float(y[i])
        x3, y3 = float(x[i + 1]), float(y[i + 1])
        a = math.hypot(x1 - x2, y1 - y2)
        b = math.hypot(x2 - x3, y2 - y3)
        c = math.hypot(x3 - x1, y3 - y1)
        area = abs((x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2.0)
        if area < 1e-6:
            continue
        r = a * b * c / (4.0 * area)
        if 8.0 < r < 450.0:
            rs.append(r)
    return float(np.median(rs)) if rs else None


def _angle_delta_deg(a: float, b: float) -> float:
    return abs(((b - a + 180.0) % 360.0) - 180.0)


def derive_corners(session) -> tuple[list[dict[str, float]], float]:
    """Return (corners as {radius_m, arc_length_m}, lap_length_m)."""
    ci = session.get_circuit_info().corners.copy()
    lap = session.laps.pick_fastest()
    tel = lap.get_telemetry().add_distance()
    # FastF1 position channels are in 1/10 metre.
    xs = tel["X"].to_numpy(dtype=float) / 10.0
    ys = tel["Y"].to_numpy(dtype=float) / 10.0
    dist = tel["Distance"].to_numpy(dtype=float)
    lap_length = float(np.nanmax(dist))

    corners: list[dict[str, float]] = []
    distances = ci["Distance"].to_numpy(dtype=float)
    for i, d in enumerate(distances):
        if np.isnan(d):
            # Fall back to equal spacing along the lap.
            d = lap_length * (i + 0.5) / max(len(distances), 1)
        mask = (dist > d - 40.0) & (dist < d + 40.0)
        if int(mask.sum()) < 6:
            mask = (dist > d - 90.0) & (dist < d + 90.0)
        r = _local_radius_m(xs[mask], ys[mask]) if int(mask.sum()) >= 5 else None
        if r is None:
            r = 70.0  # bahrain-like default when fit fails
        if int(mask.sum()) >= 3:
            path = float(dist[mask][-1] - dist[mask][0])
            ang = float(ci.iloc[i]["Angle"])
            if i + 1 < len(ci):
                dang = _angle_delta_deg(ang, float(ci.iloc[i + 1]["Angle"]))
            elif i > 0:
                dang = _angle_delta_deg(float(ci.iloc[i - 1]["Angle"]), ang)
            else:
                dang = 60.0
            arc = max(15.0, min(path, r * math.radians(max(dang, 25.0))))
        else:
            arc = 40.0
        corners.append({"radius_m": round(float(r), 1), "arc_length_m": round(float(arc), 1)})
    return corners, round(lap_length, 1)


def derive_pit_loss_s(session, *, strict: bool = False) -> float:
    """Empirical pit-lane time loss vs clean laps at similar tyre/fuel state.

    Default (Phase B): median (pit lap − clean @ tyre_life ±2), TrackStatus
    startswith ``1``, any compound.

    Strict (Phase C Belgium / Phase D consistency):
      - TrackStatus exactly ``1`` (exclude mixed codes like ``12``)
      - tyre_life ±1 (tighter window)
      - same compound as the pit lap
      - fuel-state match via LapNumber ±5
      - exclude traffic-affected clean refs (lap > driver-stint median + 1.0 s)
      - prefer same-driver free-air refs when ≥2 exist
    """
    laps = session.laps.copy()
    if "LapTimeS" not in laps.columns:
        laps["LapTimeS"] = laps["LapTime"].dt.total_seconds()

    pit_in = laps["PitInTime"].notna() if "PitInTime" in laps.columns else False
    pit_out = laps["PitOutTime"].notna() if "PitOutTime" in laps.columns else False
    is_pit = pit_in | pit_out
    if "TrackStatus" in laps.columns:
        status = laps["TrackStatus"].astype(str)
        green = status == "1" if strict else status.str.startswith("1")
    else:
        green = True
    clean = laps.loc[~is_pit & green & laps["LapTimeS"].notna()].copy()
    # Pit samples also restricted to green when strict (avoid SC-inflated pit deltas).
    pit_mask = is_pit & laps["LapTimeS"].notna()
    if strict:
        pit_mask = pit_mask & green
    pit_laps = laps.loc[pit_mask].copy()
    if clean.empty or pit_laps.empty:
        return 21.0  # bahrain fallback only if no pit samples

    life_tol = 1 if strict else 2
    if strict:
        # Stint ids for within-stint free-air filter.
        clean = clean.sort_values(["Driver", "LapNumber"]).copy()
        clean["CompoundChange"] = clean.groupby("Driver")["Compound"].transform(
            lambda s: s != s.shift(1)
        )
        clean["StintId"] = clean.groupby("Driver")["CompoundChange"].cumsum()
        stint_med = clean.groupby(["Driver", "StintId"])["LapTimeS"].transform("median")
        clean = clean[clean["LapTimeS"] <= stint_med + 1.0].copy()

    deltas: list[float] = []
    for _, row in pit_laps.iterrows():
        life = int(row["TyreLife"]) if not np.isnan(row.get("TyreLife", np.nan)) else 1
        band = clean[(clean["TyreLife"] >= life - life_tol) & (clean["TyreLife"] <= life + life_tol)]
        if strict:
            if "Compound" in band.columns:
                band = band[band["Compound"] == row["Compound"]]
            ln = float(row["LapNumber"])
            band = band[(band["LapNumber"] >= ln - 5) & (band["LapNumber"] <= ln + 5)]
            same_drv = band[band["Driver"] == row["Driver"]] if "Driver" in band.columns else band
            if len(same_drv) >= 2:
                band = same_drv
        if band.empty:
            continue
        ref = float(band["LapTimeS"].median())
        delta = float(row["LapTimeS"]) - ref
        # Pit loss should be positive and sub-minute; discard SC-contaminated outliers.
        if 5.0 < delta < 45.0:
            deltas.append(delta)
    if not deltas:
        return 21.0
    return round(float(np.median(deltas)), 1)


def _load_session(year: int, gp: str, *, telemetry: bool):
    """Load a race session with rate-limit retries (same spirit as residual corpus)."""
    attempts = 0
    while True:
        attempts += 1
        try:
            session = fastf1.get_session(year, gp, "R")
            session.load(laps=True, telemetry=telemetry, weather=False, messages=False)
            return session
        except RateLimitExceededError:
            wait_s = 120 * attempts
            print(
                f"  rate-limited on {year} {gp}; sleeping {wait_s}s (attempt {attempts})",
                flush=True,
            )
            time.sleep(wait_s)
            if attempts >= 6:
                raise


def build_one(
    year: int,
    gp: str,
    *,
    write: bool = True,
    strict_pit: bool = True,
    pit_loss_only: bool = False,
) -> dict:
    if gp not in _TRACK_META:
        raise KeyError(f"no metadata for {gp!r} — add to _TRACK_META")
    meta = _TRACK_META[gp]
    stem = str(meta["stem"])
    path = _TRACKS / f"{stem}.yaml"

    if pit_loss_only:
        if not path.exists():
            raise FileNotFoundError(f"pit-loss-only requires existing config: {path}")
        session = _load_session(year, gp, telemetry=False)
        pit_loss = derive_pit_loss_s(session, strict=strict_pit)
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        previous = doc.get("pit_loss_s")
        doc["pit_loss_s"] = pit_loss
        src = dict(doc.get("source") or {})
        src["pit_loss_year"] = year
        src["pit_loss_gp"] = gp
        src["pit_loss_previous_s"] = previous
        src["pit_loss_method"] = (
            "strict: median(pit_lap - clean@tyre_life±1,same_compound,"
            "LapNumber±5,TrackStatus==1,free-air≤stint_med+1s)"
            if strict_pit
            else "median(pit_lap - clean@similar_tyre_life)"
        )
        doc["source"] = src
        if write:
            path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            print(
                f"Updated pit_loss {path.name}: {previous} -> {pit_loss}s "
                f"(strict={strict_pit}, year={year})",
                flush=True,
            )
        return doc

    session = _load_session(year, gp, telemetry=True)

    total_laps = int(session.total_laps)
    pit_loss = derive_pit_loss_s(session, strict=strict_pit)
    corners, lap_length = derive_corners(session)

    if strict_pit:
        pit_method = (
            "pit_loss=median(pit_lap - clean@tyre_life±1,same_compound,"
            "LapNumber±5,TrackStatus==1,free-air≤stint_med+1s)"
        )
    else:
        pit_method = "pit_loss=median(pit_lap - clean@similar_tyre_life)"

    doc: dict[str, object] = {
        "name": meta["name"],
        "country": meta["country"],
        "total_laps": total_laps,
        "pit_loss_s": pit_loss,
        "lap_length_m": lap_length,
        "corners": corners,
        "round_aliases": list(meta["aliases"]),  # type: ignore[arg-type]
        "source": {
            "year": year,
            "gp": gp,
            "method": (
                f"total_laps=session.total_laps; {pit_method}; "
                "corners=get_circuit_info + telemetry circle fit"
            ),
            "layout_note": (
                "Built from most recent year in Phase D scope; "
                "see PHASE-D-SUMMARY for multi-year layout flags."
            ),
        },
    }
    if "physics_profile" in meta:
        doc["physics_profile"] = meta["physics_profile"]
        # Bahrain keeps profile path; corners optional overlay not written here
        # when pit_loss_only. Full rebuild of bahrain is unusual.
    if write:
        _TRACKS.mkdir(parents=True, exist_ok=True)
        # Preserve bahrain physics_profile-only shape if rebuilding Bahrain fully
        if stem == "bahrain" and "physics_profile" in meta:
            # Keep existing corner-less profile unless corners already desired
            existing = {}
            if path.exists():
                existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            slim = {
                "name": meta["name"],
                "country": meta["country"],
                "total_laps": total_laps,
                "pit_loss_s": pit_loss,
                "physics_profile": meta["physics_profile"],
                "round_aliases": list(meta["aliases"]),  # type: ignore[arg-type]
                "source": doc["source"],
            }
            if existing.get("lap_length_m") is not None:
                slim["lap_length_m"] = existing["lap_length_m"]
            if existing.get("corners"):
                slim["corners"] = existing["corners"]
            doc = slim
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        print(
            f"Wrote {path}  laps={total_laps} pit_loss={pit_loss}s  "
            f"corners={len(corners)} lap_len={lap_length}m  year={year}",
            flush=True,
        )
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument(
        "--gps",
        nargs="+",
        default=None,
        help="GP names to build (default: PHASE_D2_BUILDS or --year all meta)",
    )
    parser.add_argument(
        "--phase-d2",
        action="store_true",
        help="Build all Phase D2 missing configs from PHASE_D2_BUILDS",
    )
    parser.add_argument(
        "--phase-d3-pit",
        action="store_true",
        help="Re-derive strict pit_loss_s for the six existing configs",
    )
    parser.add_argument(
        "--strict-pit",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use Phase C strict pit-loss matcher (default: True)",
    )
    parser.add_argument(
        "--pit-loss-only",
        action="store_true",
        help="Only refresh pit_loss_s on an existing YAML",
    )
    args = parser.parse_args()
    _CACHE.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(_CACHE))

    if args.phase_d3_pit:
        targets = PHASE_D3_PIT_REFRESH
        for year, gp in targets:
            build_one(
                year,
                gp,
                write=True,
                strict_pit=True,
                pit_loss_only=True,
            )
        return

    if args.phase_d2:
        targets = PHASE_D2_BUILDS
    elif args.gps and args.year is not None:
        targets = [(args.year, gp) for gp in args.gps]
    elif args.gps:
        raise SystemExit("--gps requires --year (or use --phase-d2)")
    else:
        year = args.year or 2024
        targets = [(year, gp) for gp in _TRACK_META if gp not in ("Mexico", "Brazil", "Bahrain")]

    for year, gp in targets:
        print(f"\n=== Building {year} {gp} ===", flush=True)
        try:
            build_one(
                year,
                gp,
                write=True,
                strict_pit=args.strict_pit,
                pit_loss_only=args.pit_loss_only,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {year} {gp}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
