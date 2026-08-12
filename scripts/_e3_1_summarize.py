"""Summarize E3.1 pooled methods + cliff test across races."""
from __future__ import annotations

import json
from pathlib import Path

d = json.loads(Path("results/e3_1_raw_stint_diagnosis.json").read_text(encoding="utf-8"))

print(f"{'Race':<22} {'method':<14} {'SOFT':>8} {'MED':>8} {'HARD':>8} {'ok':>4} {'n':>4}")
for r in d["races"]:
    if "error" in r:
        continue
    label = f"{r['year']} {r['gp']}"
    for m, v in (r.get("pooled_methods") or {}).items():
        if not v:
            print(f"{label:<22} {m:<14} {'—':>8}")
            continue
        s = v["slopes"]
        print(
            f"{label:<22} {m:<14} {s['SOFT']:8.4f} {s['MEDIUM']:8.4f} "
            f"{s['HARD']:8.4f} {'Y' if v['ordering_ok'] else 'N':>4} {v['n']:4d}"
        )
    # length + dirty
    ld = r["length_dist"]
    ret = r["retention_by_compound"]
    soft_n = ld.get("SOFT", {}).get("mean_num_laps")
    hard_n = ld.get("HARD", {}).get("mean_num_laps")
    soft_d = ret.get("SOFT", {}).get("mean_dirty_retained_in_fitpool")
    hard_d = ret.get("HARD", {}).get("mean_dirty_retained_in_fitpool")
    print(
        f"  lengths SOFT={soft_n} HARD={hard_n} | "
        f"dirty_retained SOFT={soft_d} HARD={hard_d}"
    )
    print()

# Cliff concrete: for HARD stints with NumLaps>=20, compare early vs late slope
print("=== CLIFF TEST (per-race HARD stints with enough length) ===")
print("If cliff: late_window_slope > early_window_slope (acceleration late)")
for r in d["races"]:
    if "error" in r:
        continue
    # We don't have late-window in JSON; compute from examples + note from length
    # Use examples' early vs full slopes as proxy
    for comp in ("SOFT", "HARD"):
        for ex in r["examples"].get(comp) or []:
            full = (ex["slopes"].get("clean") or {}).get("slope")
            early = (ex["slopes"].get("early_clean") or {}).get("slope")
            if full is None or early is None:
                continue
            # Approximate: if full > early meaningfully on long HARD → cliff contamination
            delta = full - early
            print(
                f"{r['year']} {r['gp']} {comp} {ex['driver']}: "
                f"full={full:.4f} early={early:.4f} delta(full-early)={delta:+.4f} "
                f"n_raw={ex['n_laps_raw']}"
            )
