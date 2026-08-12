"""Pretty-print E3.1 diagnosis JSON."""
from __future__ import annotations

import json
from pathlib import Path

d = json.loads(Path("results/e3_1_raw_stint_diagnosis.json").read_text(encoding="utf-8"))
print("=== SUMMARY ===")
print(json.dumps(d["summary"], indent=2))

for r in d["races"]:
    if "error" in r:
        print(f"{r['year']} {r['gp']}: ERROR {r['error']}")
        continue
    print(f"\n===== {r['year']} {r['gp']} =====")
    print("length_dist:", json.dumps(r["length_dist"], indent=2))
    print("retention:", json.dumps(r["retention_by_compound"], indent=2))
    print("median fitpool:", r["median_deg_fitpool_path"])
    print("median if clean-first:", r["median_deg_if_clean_filtered_first"])
    print("pooled methods:")
    for m, v in r["pooled_methods"].items():
        print(f"  {m}: {v}")
    for comp in ("SOFT", "HARD"):
        exs = r["examples"].get(comp) or []
        if not exs:
            continue
        ex = exs[0]
        print(
            f"\n  EXAMPLE {comp} {ex['driver']} stint{ex['stint']} "
            f"laps {ex['start_lap']}-{ex['end_lap']} (n={ex['n_laps_raw']})"
        )
        print(
            f"    fitpool={ex['n_fitpool']} clean={ex['n_clean']} "
            f"dirty_in_fitpool={ex['n_dirty_retained_in_fitpool']}"
        )
        print(f"    slopes: {ex['slopes']}")
        dirty = [
            L
            for L in ex["laps"]
            if (not L["green"]) or L["is_in_lap"] or L["is_out_lap"]
        ]
        late = [L for L in ex["laps"] if L["TyreLife"] and L["TyreLife"] >= 15]
        print(f"    dirty/out/in laps ({len(dirty)}):")
        for L in dirty[:10]:
            print(
                f"      L{L['LapNumber']} TL{L['TyreLife']} t={L['LapTimeS']} "
                f"TS={L['TrackStatus']} fit={L['kept_by_compute_stint_metrics']} "
                f"clean={L['kept_by_filter_clean_laps']}"
            )
        if late:
            n_show = min(6, len(late))
            print(f"    late TL>=15 sample ({n_show} of {len(late)}):")
            for L in late[:n_show]:
                print(
                    f"      L{L['LapNumber']} TL{L['TyreLife']} t={L['LapTimeS']} "
                    f"TS={L['TrackStatus']} fit={L['kept_by_compute_stint_metrics']} "
                    f"clean={L['kept_by_filter_clean_laps']}"
                )
