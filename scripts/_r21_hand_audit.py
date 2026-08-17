"""R21.5: hand-audit 2024 Austria VER and 2025 Canada LEC.

Print ARIS Strat B vs team pit list, compounds, stint lengths, SC/red
on those laps, and the HARD-deg cost the model assigned to the long stint.

  python scripts/_r21_hand_audit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.eval.postrace import actual_schedule  # noqa: E402
from aris.io import db  # noqa: E402
from aris.physics.tires import DEFAULT_COMPOUND_SLOPE, tire_pace_loss  # noqa: E402
from aris.plan.prewrite import generate_strat_plans  # noqa: E402
from aris.tracks import load_track_config  # noqa: E402

CASES = (
    (2024, 11, "Austria", "VER"),
    (2025, 10, "Canada", "LEC"),
)


def _stints(laps) -> list[dict]:
    ordered = laps.sort_values("lap_number")
    stints: list[dict] = []
    start = None
    compound = None
    n = 0
    pit_end = False
    for _, row in ordered.iterrows():
        lap = int(row["lap_number"])
        comp = str(row["compound"]) if row.get("compound") == row.get("compound") else "?"
        ts = str(row.get("track_status") or "")
        if start is None:
            start = lap
            compound = comp
            n = 0
        n += 1
        if bool(row.get("pit_in")):
            stints.append(
                {
                    "start": start,
                    "end": lap,
                    "laps": n,
                    "compound": compound,
                    "pit_out": lap,
                    "track_statuses": [],
                }
            )
            start = None
            compound = None
            n = 0
            pit_end = True
            continue
        pit_end = False
        _ = ts
    if start is not None:
        last = int(ordered.iloc[-1]["lap_number"])
        stints.append(
            {
                "start": start,
                "end": last,
                "laps": n,
                "compound": compound,
                "pit_out": None,
                "track_statuses": [],
            }
        )
    # attach statuses per stint
    for s in stints:
        chunk = ordered[
            (ordered["lap_number"] >= s["start"]) & (ordered["lap_number"] <= s["end"])
        ]
        s["n_sc"] = int(chunk["track_status"].astype(str).str.contains("4").sum())
        s["n_red"] = int(chunk["track_status"].astype(str).str.contains("5").sum())
        s["n_green"] = int((chunk["track_status"].astype(str) == "1").sum())
        s["mean_lap_s"] = float(chunk["lap_time_s"].dropna().mean()) if chunk["lap_time_s"].notna().any() else None
    return stints


def _deg_table(n_laps: int, compound: str, slopes: dict) -> float:
    """Sum of tire_pace_loss over a stint of n_laps (life 1..n)."""
    return float(sum(tire_pace_loss(compound, i, slopes=slopes) for i in range(1, n_laps + 1)))


def main() -> int:
    print("=== R21.5 hand-audit ===", flush=True)
    for year, round_no, gp, code in CASES:
        sid = db.fetch_race_session_id(year, round_no)
        drv = db.fetch_driver_by_code(sid, code)
        did = int(drv["driver_id"])
        laps = db.fetch_laps(sid, did)
        races = db.fetch_races(year)
        country = str(races[races["round_no"] == round_no].iloc[0]["country"])
        track = load_track_config(country, year=year, round_no=round_no)
        plans = generate_strat_plans(
            sid, did, year=year, round_no=round_no, country=country, driver_code=code
        )
        rec = next(p for p in plans.plans if p.recommended)
        team = actual_schedule(laps)
        print(f"\n--- {year} {gp} {code} session={sid} cfg_laps={track.total_laps} ---", flush=True)
        print(f"  slopes={track.compound_slopes}", flush=True)
        print(
            f"  ARIS Strat {rec.id}: start={rec.start_compound} pits={list(rec.pit_laps)} "
            f"compounds={list(rec.pit_compounds)} recommended={rec.recommended} "
            f"expected_s={rec.expected_race_time_s:.1f}",
            flush=True,
        )
        for p in plans.plans:
            print(
                f"    {p.id} rec={p.recommended} pits={list(p.pit_laps)} "
                f"comp={list(p.pit_compounds)} start={p.start_compound} "
                f"t={p.expected_race_time_s:.1f}",
                flush=True,
            )
        print(
            f"  Team: start={team.start_compound} pits={list(team.pit_laps)} "
            f"compounds={list(team.pit_compounds)}",
            flush=True,
        )
        stints = _stints(laps)
        print("  actual stints:", flush=True)
        for s in stints:
            deg = _deg_table(int(s["laps"]), str(s["compound"]), track.compound_slopes)
            last = tire_pace_loss(str(s["compound"]), int(s["laps"]), slopes=track.compound_slopes)
            print(
                f"    L{s['start']}-{s['end']} n={s['laps']} {s['compound']} "
                f"green={s['n_green']} sc={s['n_sc']} red={s['n_red']} "
                f"mean_lap={s['mean_lap_s']:.3f}s  model_deg_sum={deg:.2f}s "
                f"last_lap_deg={last:.2f}s",
                flush=True,
            )
        # ARIS implied stints from start + pits
        pits = [1] + list(rec.pit_laps) + [track.total_laps + 1]
        print("  ARIS implied stints (config laps, G1.5 slopes):", flush=True)
        for i in range(len(pits) - 1):
            a, b = pits[i], pits[i + 1]
            n = b - a
            if i == 0:
                comp = rec.start_compound
            else:
                comp = rec.pit_compounds[i - 1]
            deg = _deg_table(n, comp, track.compound_slopes)
            last = tire_pace_loss(comp, n, slopes=track.compound_slopes)
            print(
                f"    L{a}-{b - 1} n={n} {comp}  model_deg_sum={deg:.2f}s "
                f"last_lap_deg={last:.2f}s  (HARD slope={DEFAULT_COMPOUND_SLOPE['HARD']})",
                flush=True,
            )
        # extra team pit-loss vs ARIS
        extra_stops = len(team.pit_laps) - len(rec.pit_laps)
        print(
            f"  extra team stops vs ARIS: {extra_stops}  "
            f"pit_loss_s={track.pit_loss_s}  extra_pit_cost~={extra_stops * track.pit_loss_s:.1f}s",
            flush=True,
        )
        timed = int(laps["lap_time_s"].notna().sum())
        print(f"  timed laps={timed} cfg={track.total_laps}", flush=True)
        # late pits: any pit in last 8 laps
        late = [p for p in team.pit_laps if p >= track.total_laps - 8 or p >= timed - 8]
        print(f"  team pits in last 8 laps (cfg or timed): {late}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
