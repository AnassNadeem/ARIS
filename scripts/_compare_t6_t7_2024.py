"""Compare 2024 inflection results between T6 baseline and T7 per-inflection output."""
import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# Load T6 2024 results (per-race JSON list)
with open(_ROOT / "results/backtest/2024_full.json") as f:
    t6_races = json.load(f)

# Build T6 classification lookup: (gp, lap, driver) → class
t6_decisions = {}
for r in t6_races:
    gp = r.get("gp", "?")
    for d in r.get("decisions") or []:
        inf = d.get("inflection") or {}
        key = (gp, inf.get("lap", 0), d.get("driver_code", "?"))
        t6_decisions[key] = d.get("classification", "?")

# Parse T7 per-inflection output
t7_path = _ROOT / "results/backtest/t7_per_inflection_raw.txt"
t7_decisions = {}
pat = re.compile(
    r"INFLECTION year=2024 gp=([^ ]+) driver=(\S+) lap=(\d+) .*?class=(\S+)"
)
with open(t7_path, encoding="utf-8", errors="replace") as f:
    for line in f:
        m = pat.search(line.strip())
        if not m:
            continue
        gp, driver, lap_str, cls = m.group(1), m.group(2), m.group(3), m.group(4)
        key = (gp, int(lap_str), driver)
        t7_decisions[key] = cls

print(f"T6 2024 decisions: {len(t6_decisions)}")
print(f"T7 2024 decisions: {len(t7_decisions)}")
print()

# Find keys in both
common = set(t6_decisions) & set(t7_decisions)
print(f"Common keys: {len(common)}")
print()

# Regressions: T6 match → T7 non-match
regressions = [
    k for k in common
    if t6_decisions[k] == "match" and t7_decisions[k] != "match"
    and t7_decisions[k] != "divergence_insufficient_info"
]
print(f"REGRESSIONS (T6 match -> T7 non-match): {len(regressions)}")
for k in sorted(regressions):
    gp, lap, drv = k
    print(f"  {gp:<20} L{lap:<3} {drv} T6={t6_decisions[k]} → T7={t7_decisions[k]}")
print()

# New matches: T6 non-match → T7 match
new_matches = [
    k for k in common
    if t6_decisions[k] != "match" and t7_decisions[k] == "match"
    and t6_decisions[k] != "divergence_insufficient_info"
]
print(f"NEW MATCHES (T6 non-match -> T7 match): {len(new_matches)}")
for k in sorted(new_matches):
    gp, lap, drv = k
    print(f"  {gp:<20} L{lap:<3} {drv} T6={t6_decisions[k]} → T7={t7_decisions[k]}")
