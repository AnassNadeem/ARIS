"""R21.3: per-race team_sim - actual offset, disruptions, exclusion test.

Diagnosis only. Does not change simulate()/recommend().

  python scripts/_r21_offset_breakdown.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.io import db  # noqa: E402

_R23 = _ROOT / "results" / "r2" / "r23_bias_cancel.json"
_OUT = _ROOT / "results" / "r21"
STREET_GPS = frozenset({
    "Monaco", "Singapore", "Azerbaijan", "Miami", "Las Vegas", "Canada", "Australia",
})


def _stats(vals: list[float]) -> dict[str, float | int]:
    arr = np.array(vals, dtype=float)
    if len(arr) == 0:
        return {"n": 0, "mean": float("nan"), "std": float("nan"), "median": float("nan")}
    return {
        "n": int(len(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=0)),
        "median": float(np.median(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def _print_stats(label: str, vals: list[float]) -> None:
    s = _stats(vals)
    print(
        f"  {label}: n={s['n']} mean={s['mean']:+.1f}s std={s['std']:.1f}s "
        f"median={s['median']:+.1f}s min={s.get('min', float('nan')):+.1f} "
        f"max={s.get('max', float('nan')):+.1f}",
        flush=True,
    )


def _disruption(session_id: int, driver_id: int) -> dict:
    laps = db.fetch_laps(session_id, driver_id)
    if laps.empty:
        return {
            "n_laps_timed": 0,
            "n_red": 0,
            "n_sc": 0,
            "n_vsc": 0,
            "n_yellow": 0,
            "n_green": 0,
            "n_other": 0,
            "red_laps": [],
            "sc_laps": [],
            "longest_sc_run": 0,
            "statuses": [],
        }
    ts = laps["track_status"].astype("string").fillna("")
    lap_no = laps["lap_number"].astype(int)
    red_laps = [int(n) for n, s in zip(lap_no, ts) if "5" in str(s)]
    sc_laps = [int(n) for n, s in zip(lap_no, ts) if "4" in str(s)]
    vsc_laps = [int(n) for n, s in zip(lap_no, ts) if any(c in str(s) for c in ("6", "7"))]
    yellow_laps = [
        int(n) for n, s in zip(lap_no, ts)
        if "2" in str(s) and "4" not in str(s) and "5" not in str(s)
    ]
    green = int((ts == "1").sum())
    # longest consecutive SC run
    longest = 0
    run = 0
    for s in ts:
        if "4" in str(s):
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return {
        "n_laps_timed": int(laps["lap_time_s"].notna().sum()),
        "n_red": len(red_laps),
        "n_sc": len(sc_laps),
        "n_vsc": len(vsc_laps),
        "n_yellow": len(yellow_laps),
        "n_green": green,
        "n_other": int(len(laps) - green),
        "red_laps": red_laps,
        "sc_laps": sc_laps,
        "longest_sc_run": int(longest),
        "unique_statuses": sorted({str(s) for s in ts if str(s)}),
    }


def main() -> int:
    _OUT.mkdir(parents=True, exist_ok=True)
    raw = json.loads(_R23.read_text(encoding="utf-8"))
    rows = [r for r in raw["rows"] if "error" not in r]

    print("=== R21.3 team_sim - actual offset breakdown ===", flush=True)
    print(
        f"  aimed: explain std 544s (all) / 384s (permanent) / 807s (street); "
        f"n={len(rows)}",
        flush=True,
    )

    enriched: list[dict] = []
    for r in rows:
        sid = db.fetch_race_session_id(int(r["year"]), int(r["round_no"]))
        drv = db.fetch_driver_by_code(sid, r["driver_code"]) if sid is not None else None
        did = int(drv["driver_id"]) if drv is not None else None
        dist = _disruption(sid, did) if sid is not None and did is not None else {}
        per_lap = r["team_minus_actual_s"] / r["total_laps"]
        per_timed = (
            r["team_minus_actual_s"] / dist["n_laps_timed"]
            if dist.get("n_laps_timed")
            else float("nan")
        )
        shortened = bool(
            dist.get("n_laps_timed") and dist["n_laps_timed"] < int(r["total_laps"]) - 2
        )
        major = bool(dist.get("n_red") or (dist.get("longest_sc_run") or 0) >= 5)
        row = {
            **r,
            "session_id": sid,
            "per_lap_offset_s": per_lap,
            "per_timed_lap_offset_s": per_timed,
            "shortened": shortened,
            "major_disruption": major,
            **{f"d_{k}": v for k, v in dist.items()},
        }
        enriched.append(row)

    print("\n  per-race (sorted by offset):", flush=True)
    print(
        "  year gp driver group laps timed red sc longestSC offset per_cfg per_timed major short",
        flush=True,
    )
    for r in sorted(enriched, key=lambda x: x["team_minus_actual_s"]):
        print(
            f"  {r['year']} {r['gp']:<18} {r['driver_code']} {r['track_group']:<10} "
            f"cfg={r['total_laps']:<3} timed={r.get('d_n_laps_timed', 0):<3} "
            f"red={r.get('d_n_red', 0):<2} sc={r.get('d_n_sc', 0):<3} "
            f"scRun={r.get('d_longest_sc_run', 0):<2} "
            f"off={r['team_minus_actual_s']:+8.1f} "
            f"perCfg={r['per_lap_offset_s']:+6.2f} "
            f"perT={r['per_timed_lap_offset_s']:+6.2f} "
            f"major={int(r['major_disruption'])} short={int(r['shortened'])}",
            flush=True,
        )

    offsets = [r["team_minus_actual_s"] for r in enriched]
    per_cfg = [r["per_lap_offset_s"] for r in enriched]
    print("\n  all races (absolute offset):", flush=True)
    _print_stats("all", offsets)
    _print_stats("all per configured lap", per_cfg)

    for group in ("permanent", "street"):
        sub = [r["team_minus_actual_s"] for r in enriched if r["track_group"] == group]
        subp = [r["per_lap_offset_s"] for r in enriched if r["track_group"] == group]
        _print_stats(group, sub)
        _print_stats(f"{group} per configured lap", subp)

    print("\n  by configured race length (bins):", flush=True)
    bins = [(0, 50), (50, 60), (60, 70), (70, 90)]
    for lo, hi in bins:
        sub = [
            r["team_minus_actual_s"]
            for r in enriched
            if lo <= int(r["total_laps"]) < hi
        ]
        _print_stats(f"cfg laps [{lo},{hi})", sub)

    print("\n  by circuit (pooled years, mean offset):", flush=True)
    by_gp: dict[str, list[float]] = {}
    for r in enriched:
        by_gp.setdefault(r["gp"], []).append(r["team_minus_actual_s"])
    for gp, vals in sorted(by_gp.items(), key=lambda kv: np.mean(kv[1])):
        s = _stats(vals)
        print(
            f"  {gp:<18} n={s['n']} mean={s['mean']:+8.1f} std={s['std']:7.1f}",
            flush=True,
        )

    print("\n  disruption slices:", flush=True)
    red = [r["team_minus_actual_s"] for r in enriched if r.get("d_n_red", 0) > 0]
    nored = [r["team_minus_actual_s"] for r in enriched if r.get("d_n_red", 0) == 0]
    major = [r["team_minus_actual_s"] for r in enriched if r["major_disruption"]]
    noma = [r["team_minus_actual_s"] for r in enriched if not r["major_disruption"]]
    short = [r["team_minus_actual_s"] for r in enriched if r["shortened"]]
    full = [r["team_minus_actual_s"] for r in enriched if not r["shortened"]]
    long_sc = [
        r["team_minus_actual_s"]
        for r in enriched
        if (r.get("d_longest_sc_run") or 0) >= 5
    ]
    no_long_sc = [
        r["team_minus_actual_s"]
        for r in enriched
        if (r.get("d_longest_sc_run") or 0) < 5
    ]
    _print_stats("has red flag", red)
    _print_stats("no red flag", nored)
    _print_stats("major (red or SC run>=5)", major)
    _print_stats("not major", noma)
    _print_stats("shortened (timed < cfg-2)", short)
    _print_stats("not shortened", full)
    _print_stats("longest SC run >=5", long_sc)
    _print_stats("longest SC run <5", no_long_sc)

    print("\n  exclusion test — does dropping major disruptions stabilize?", flush=True)
    print(
        f"  aimed: std of remaining offset clearly tighter than 544s "
        f"(and street 807s / permanent 384s).",
        flush=True,
    )
    all_std = float(np.std(offsets))
    keep_std = float(np.std(noma)) if noma else float("nan")
    nored_std = float(np.std(nored)) if nored else float("nan")
    full_std = float(np.std(full)) if full else float("nan")
    print(
        f"  drop major: n {len(offsets)}->{len(noma)}  "
        f"mean {np.mean(offsets):+.1f}->{np.mean(noma) if noma else float('nan'):+.1f}  "
        f"std {all_std:.1f}->{keep_std:.1f}",
        flush=True,
    )
    print(
        f"  drop red only: n {len(offsets)}->{len(nored)}  "
        f"std {all_std:.1f}->{nored_std:.1f}",
        flush=True,
    )
    print(
        f"  drop shortened: n {len(offsets)}->{len(full)}  "
        f"std {all_std:.1f}->{full_std:.1f}",
        flush=True,
    )
    for group in ("permanent", "street"):
        g_all = [r["team_minus_actual_s"] for r in enriched if r["track_group"] == group]
        g_keep = [
            r["team_minus_actual_s"]
            for r in enriched
            if r["track_group"] == group and not r["major_disruption"]
        ]
        print(
            f"  {group} drop major: n {len(g_all)}->{len(g_keep)}  "
            f"mean {np.mean(g_all):+.1f}->{np.mean(g_keep) if g_keep else float('nan'):+.1f}  "
            f"std {float(np.std(g_all)):.1f}->{float(np.std(g_keep)) if g_keep else float('nan'):.1f}",
            flush=True,
        )

    # correlation with race length / disruption counts
    df = pd.DataFrame(enriched)
    print("\n  Pearson vs offset:", flush=True)
    for col in (
        "total_laps",
        "d_n_laps_timed",
        "d_n_red",
        "d_n_sc",
        "d_longest_sc_run",
        "d_n_vsc",
        "per_lap_offset_s",
    ):
        if col not in df.columns:
            continue
        x = pd.to_numeric(df[col], errors="coerce")
        y = df["team_minus_actual_s"]
        mask = x.notna()
        if mask.sum() < 3:
            continue
        r = float(np.corrcoef(x[mask], y[mask])[0, 1])
        print(f"  r(offset, {col}) = {r:+.3f}", flush=True)

    out = {
        "n": len(enriched),
        "all": _stats(offsets),
        "per_configured_lap": _stats(per_cfg),
        "drop_major": _stats(noma),
        "drop_red": _stats(nored),
        "drop_shortened": _stats(full),
        "has_red": _stats(red),
        "major": _stats(major),
        "shortened": _stats(short),
        "rows": enriched,
    }
    (_OUT / "r213_offset_breakdown.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nWrote {_OUT / 'r213_offset_breakdown.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
