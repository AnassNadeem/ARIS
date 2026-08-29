"""List T6 2024 matches."""
import json, sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
DRY = {"SOFT", "MEDIUM", "HARD", "C1", "C2", "C3", "C4", "C5"}
with open(_ROOT / "results/backtest/2024_full.json") as f:
    races = json.load(f)
print("T6 2024 matches:")
count = 0
for r in races:
    gp = r.get("gp", "?")
    for d in (r.get("decisions") or []):
        inf = d.get("inflection") or {}
        sc = str(d.get("state_compound") or "").upper()
        if sc not in DRY:
            continue
        if d.get("classification") == "match":
            count += 1
            print(f"  {gp:<25} L{inf.get('lap', 0):<4} {d.get('driver_code','?')}")
print(f"Total: {count}")
print()
print("T6 2024 non-matches (scored):")
count2 = 0
for r in races:
    gp = r.get("gp", "?")
    for d in (r.get("decisions") or []):
        inf = d.get("inflection") or {}
        sc = str(d.get("state_compound") or "").upper()
        if sc not in DRY:
            continue
        cls = d.get("classification", "")
        if cls in ("match", "divergence_insufficient_info"):
            continue
        count2 += 1
        print(f"  {gp:<25} L{inf.get('lap', 0):<4} {d.get('driver_code','?')} {cls}")
print(f"Total non-matches: {count2}")
