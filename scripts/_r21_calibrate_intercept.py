"""R21.4 probe: can a circuit intercept stabilize team_sim - actual?

Uses R21.3 rows. No simulate() changes. Leave-one-year-out and in-sample
checks for global / street-permanent / per-circuit intercepts.

  python scripts/_r21_calibrate_intercept.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

_IN = _ROOT / "results" / "r21" / "r213_offset_breakdown.json"
_OUT = _ROOT / "results" / "r21"


def _stats(vals: list[float]) -> dict[str, float | int]:
    arr = np.array(vals, dtype=float)
    if len(arr) == 0:
        return {"n": 0, "mean": float("nan"), "std": float("nan")}
    return {
        "n": int(len(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=0)),
        "median": float(np.median(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def _print(label: str, vals: list[float], aimed: str = "") -> None:
    s = _stats(vals)
    extra = f"  {aimed}" if aimed else ""
    print(
        f"  {label}: n={s['n']} mean={s['mean']:+.1f}s std={s['std']:.1f}s "
        f"median={s['median']:+.1f}s min={s['min']:+.1f} max={s['max']:+.1f}{extra}",
        flush=True,
    )


def _resid(rows: list[dict], intercept_s_per_lap: dict[str, float], key: str) -> list[float]:
    out = []
    for r in rows:
        k = str(r[key])
        b = intercept_s_per_lap.get(k)
        if b is None:
            b = float(np.mean(list(intercept_s_per_lap.values()))) if intercept_s_per_lap else 0.0
        out.append(float(r["team_minus_actual_s"]) - b * float(r["total_laps"]))
    return out


def _fit_per_lap(rows: list[dict], key: str) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for r in rows:
        buckets.setdefault(str(r[key]), []).append(
            float(r["team_minus_actual_s"]) / float(r["total_laps"])
        )
    return {k: float(np.mean(v)) for k, v in buckets.items()}


def main() -> int:
    raw = json.loads(_IN.read_text(encoding="utf-8"))
    rows = raw["rows"]
    clean = [r for r in rows if not r["major_disruption"]]
    print("=== R21.4 intercept calibration probe (offline numbers) ===", flush=True)
    print(
        f"  aimed: tighter, more stable common-mode offset than all-sample "
        f"std 544.0s / clean std {_stats([r['team_minus_actual_s'] for r in clean])['std']:.1f}s",
        flush=True,
    )
    _print("raw all", [r["team_minus_actual_s"] for r in rows])
    _print("raw clean (not major)", [r["team_minus_actual_s"] for r in clean])

    # Global intercept from clean 2024, applied to all / 2025
    y2024_clean = [r for r in clean if int(r["year"]) == 2024]
    y2025 = [r for r in rows if int(r["year"]) == 2025]
    y2024 = [r for r in rows if int(r["year"]) == 2024]
    global_b = float(
        np.mean([r["team_minus_actual_s"] / r["total_laps"] for r in y2024_clean])
    )
    print(f"\n  global s/lap from 2024 clean: {global_b:+.3f} (aimed ~G1.2 +18)", flush=True)
    _print("global on all", _resid(rows, {"_": global_b}, key="gp") if False else [
        r["team_minus_actual_s"] - global_b * r["total_laps"] for r in rows
    ])
    _print(
        "global on 2025 (OOS)",
        [r["team_minus_actual_s"] - global_b * r["total_laps"] for r in y2025],
    )

    # Street / permanent from 2024 clean
    type_b = _fit_per_lap(y2024_clean, "track_group")
    print(f"  street/permanent s/lap from 2024 clean: {type_b}", flush=True)
    type_resid_all = []
    type_resid_2025 = []
    for r in rows:
        b = type_b.get(r["track_group"], global_b)
        type_resid_all.append(r["team_minus_actual_s"] - b * r["total_laps"])
    for r in y2025:
        b = type_b.get(r["track_group"], global_b)
        type_resid_2025.append(r["team_minus_actual_s"] - b * r["total_laps"])
    _print("type on all", type_resid_all)
    _print("type on 2025 (OOS)", type_resid_2025)

    # Per-circuit from 2024 clean; fallback global
    circ_b = _fit_per_lap(y2024_clean, "gp")
    print(f"\n  per-circuit s/lap from 2024 clean ({len(circ_b)} circuits):", flush=True)
    for gp, b in sorted(circ_b.items(), key=lambda kv: kv[1]):
        print(f"    {gp:<18} {b:+7.2f} s/lap", flush=True)

    circ_resid_all = []
    circ_resid_2025 = []
    circ_resid_2025_matched = []
    for r in rows:
        b = circ_b.get(r["gp"], global_b)
        circ_resid_all.append(r["team_minus_actual_s"] - b * r["total_laps"])
    for r in y2025:
        b = circ_b.get(r["gp"], global_b)
        val = r["team_minus_actual_s"] - b * r["total_laps"]
        circ_resid_2025.append(val)
        if r["gp"] in circ_b:
            circ_resid_2025_matched.append(val)
    _print("circuit on all (2024 in-sample, 2025 OOS, missing->global)", circ_resid_all)
    _print("circuit on 2025 OOS", circ_resid_2025)
    _print("circuit on 2025 OOS, circuit seen in 2024 clean", circ_resid_2025_matched)

    # LORO: each year uses the other year's clean intercepts
    b_2025_clean = _fit_per_lap([r for r in clean if int(r["year"]) == 2025], "gp")
    loro = []
    for r in rows:
        other = circ_b if int(r["year"]) == 2025 else b_2025_clean
        b = other.get(r["gp"], global_b)
        loro.append(r["team_minus_actual_s"] - b * r["total_laps"])
    _print("LORO per-circuit (other year clean)", loro)

    # Same but only clean evaluation races
    loro_clean = []
    for r in clean:
        other = circ_b if int(r["year"]) == 2025 else b_2025_clean
        b = other.get(r["gp"], global_b)
        loro_clean.append(r["team_minus_actual_s"] - b * r["total_laps"])
    _print("LORO per-circuit, eval on clean only", loro_clean)

    # Distance mismatch: extra simulated laps (cfg - timed)
    extra = [r["total_laps"] - r.get("d_n_laps_timed", r["total_laps"]) for r in rows]
    print("\n  YAML laps vs timed laps:", flush=True)
    print(
        f"  mean cfg-timed = {float(np.mean(extra)):+.2f}  "
        f"|extra|>=3 n={sum(1 for x in extra if abs(x) >= 3)}",
        flush=True,
    )
    for r in sorted(rows, key=lambda x: abs(x["total_laps"] - x.get("d_n_laps_timed", 0)), reverse=True)[:12]:
        d = r["total_laps"] - r.get("d_n_laps_timed", 0)
        print(
            f"    {r['year']} {r['gp']:<18} cfg={r['total_laps']} "
            f"timed={r.get('d_n_laps_timed')} extra={d:+d} off={r['team_minus_actual_s']:+.1f}",
            flush=True,
        )

    out = {
        "global_s_per_lap_2024_clean": global_b,
        "type_s_per_lap_2024_clean": type_b,
        "circuit_s_per_lap_2024_clean": circ_b,
        "raw_all": _stats([r["team_minus_actual_s"] for r in rows]),
        "global_all": _stats([r["team_minus_actual_s"] - global_b * r["total_laps"] for r in rows]),
        "type_all": _stats(type_resid_all),
        "circuit_all": _stats(circ_resid_all),
        "circuit_2025": _stats(circ_resid_2025),
        "loro": _stats(loro),
        "loro_clean": _stats(loro_clean),
    }
    (_OUT / "r214_intercept_probe.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nWrote {_OUT / 'r214_intercept_probe.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
