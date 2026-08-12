"""Print E3.6 held-out table with aimed vs actual."""
from __future__ import annotations

import pandas as pd

df = pd.read_csv("results/heldout-laptime-mae.csv")
df = df[df["race_id"].astype(str).str.match(r"^(20\d{2}-|OVERALL$)")].copy()
cols = [
    "race_id",
    "baseline_mae_s",
    "e3_physics_only_mae_s",
    "e3_physics_residual_mae_s",
    "e3_blended_mae_s",
    "e2_blended_mae_s",
]
print(df[cols].to_string(index=False))
print()
sub = df[df["race_id"] != "OVERALL"].copy()
sub["aimed"] = 1.5 * sub["baseline_mae_s"]
sub["pass"] = sub["e3_blended_mae_s"] <= sub["aimed"]
print(f"pass {int(sub['pass'].sum())}/{len(sub)}")
print("MISS:")
miss = sub.loc[
    ~sub["pass"],
    ["race_id", "baseline_mae_s", "e3_blended_mae_s", "aimed", "e2_blended_mae_s"],
]
print(miss.to_string(index=False) if len(miss) else "(none)")
ov = df[df["race_id"] == "OVERALL"].iloc[0]
aimed_ov = 1.5 * float(ov["baseline_mae_s"])
print(
    f"OVERALL blend e3={float(ov['e3_blended_mae_s']):.4f} "
    f"e2={float(ov['e2_blended_mae_s']):.4f} "
    f"aimed={aimed_ov:.4f} "
    f"{'PASS' if float(ov['e3_blended_mae_s']) <= aimed_ov else 'MISS'}"
)
# Markdown table for summary
print("\n| Race | MA(2) | Phys | P+R | Blend | Aimed | vs aimed | E2 blend |")
print("|---|---:|---:|---:|---:|---:|---|---:|")
for _, r in sub.iterrows():
    name = str(r["race_id"]).replace("2024-", "").replace("_", " ")
    flag = "PASS" if r["pass"] else "MISS"
    print(
        f"| {name} | {r['baseline_mae_s']:.3f} | {r['e3_physics_only_mae_s']:.3f} | "
        f"{r['e3_physics_residual_mae_s']:.3f} | **{r['e3_blended_mae_s']:.3f}** | "
        f"{r['aimed']:.3f} | {flag} | {r['e2_blended_mae_s']:.3f} |"
    )
print(
    f"| **OVERALL** | **{ov['baseline_mae_s']:.3f}** | **{ov['e3_physics_only_mae_s']:.3f}** | "
    f"**{ov['e3_physics_residual_mae_s']:.3f}** | **{ov['e3_blended_mae_s']:.3f}** | "
    f"**{aimed_ov:.3f}** | "
    f"{'PASS' if float(ov['e3_blended_mae_s']) <= aimed_ov else 'MISS'} | "
    f"**{ov['e2_blended_mae_s']:.3f}** |"
)
