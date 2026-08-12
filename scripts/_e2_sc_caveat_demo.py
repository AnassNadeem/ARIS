"""E2.12 — find a real SC-affected stint and show the caveat string in output."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402
import pandas as pd

from aris.io import db  # noqa: E402
from aris.recommend import recommend  # noqa: E402
from aris.state import SC_PACE_CAVEAT, build_race_state  # noqa: E402
from aris.narrate import narrate_recommendation  # noqa: E402


def _find_sc_lap(year: int, gp: str) -> tuple[str, int, str] | None:
    fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    laps = session.laps
    # TrackStatus containing SC codes
    mask = laps["TrackStatus"].astype(str).str.contains(r"[467]", regex=True, na=False)
    sc = laps[mask & laps["LapTime"].notna()]
    if sc.empty:
        return None
    row = sc.iloc[len(sc) // 2]
    return str(row["Driver"]), int(row["LapNumber"]), str(row["TrackStatus"])


def main() -> None:
    candidates = [
        (2024, "Netherlands"),
        (2024, "Austria"),
        (2023, "Netherlands"),
        (2022, "Austria"),
    ]
    hit = None
    for year, gp in candidates:
        print(f"Scanning {year} {gp} for SC/VSC laps...", flush=True)
        try:
            found = _find_sc_lap(year, gp)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip: {exc!r}", flush=True)
            continue
        if found:
            hit = (year, gp, *found)
            break
    if not hit:
        raise SystemExit("no SC/VSC lap found in candidates")
    year, gp, driver, lap, status = hit
    print(f"HIT: {year} {gp} driver={driver} lap={lap} TrackStatus={status}", flush=True)

    races = db.fetch_races(year)
    if races.empty:
        raise SystemExit("no races in DB — ingest first")
    needle = gp.lower()
    key = "nether" if "nether" in needle else ("austria" if "austria" in needle else needle)
    match = races[races["country"].astype(str).str.lower().str.contains(key)]
    if match.empty:
        raise SystemExit(f"no DB race for {gp}: countries={races['country'].unique().tolist()}")
    session_id = int(match.iloc[0]["session_id"])
    drivers = db.fetch_drivers(session_id)
    drow = drivers[drivers["code"].astype(str) == driver]
    if drow.empty:
        driver_id = int(drivers.iloc[0]["driver_id"])
        driver = str(drivers.iloc[0]["code"])
        print(f"driver code not in DB; falling back to {driver}", flush=True)
    else:
        driver_id = int(drow.iloc[0]["driver_id"])

    state = build_race_state(session_id, driver_id, lap)
    print(f"recent_sc_pace={state.recent_sc_pace}", flush=True)
    print(f"confidence_caveat={state.confidence_caveat!r}", flush=True)
    print(f"SC_PACE_CAVEAT constant={SC_PACE_CAVEAT!r}", flush=True)

    result = recommend(state, top_k=3)
    recs = result.recommendations
    print("\n--- recommend() evidence / narration_context ---", flush=True)
    for i, rec in enumerate(recs, 1):
        print(f"[{i}] evidence={rec.evidence}", flush=True)
        print(f"    narration_context={rec.narration_context}", flush=True)
        text = narrate_recommendation(rec, use_llm=False)
        print(f"    narrate_output={text!r}", flush=True)

    out = _ROOT / "results" / "e2_12_sc_caveat_output.txt"
    narr = narrate_recommendation(recs[0], use_llm=False) if recs else None
    lines = [
        f"HIT: {year} {gp} driver={driver} lap={lap} TrackStatus={status}",
        f"confidence_caveat={state.confidence_caveat}",
        f"recommend_evidence={recs[0].evidence if recs else None}",
        f"narrate={narr}",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {out}", flush=True)
    if not state.confidence_caveat:
        raise SystemExit("FAIL: expected confidence_caveat on SC lap")
    if SC_PACE_CAVEAT not in (state.confidence_caveat or ""):
        raise SystemExit("FAIL: caveat string mismatch")
    print("PASS: caveat present in state and narration path", flush=True)


if __name__ == "__main__":
    main()
