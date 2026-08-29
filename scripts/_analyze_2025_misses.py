"""Analyze 2025 dry misses from existing T6 backtest results."""
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

DRY = {"SOFT", "MEDIUM", "HARD", "C1", "C2", "C3", "C4", "C5"}

with open(_ROOT / "results/backtest/2025_full.json") as f:
    races = json.load(f)

misses = []
matches = []
for r in races:
    gp = r.get("gp", "?")
    for d in r.get("decisions") or []:
        inf = d.get("inflection") or {}
        cls = d.get("classification", "")
        sc = str(d.get("state_compound") or "").upper()
        if sc not in DRY:
            continue
        if cls == "divergence_insufficient_info":
            continue
        entry = {
            "gp": gp,
            "lap": inf.get("lap", 0),
            "kind": inf.get("kind", ""),
            "team_compound": str(inf.get("compound") or "").upper(),
            "state_compound": sc,
            "tyre_life": d.get("state_tyre_life", 0),
            "aris": d.get("aris_label", ""),
            "class": cls,
            "rainfall": d.get("state_rainfall"),
        }
        if cls == "match":
            matches.append(entry)
        else:
            misses.append(entry)

print(f"2025 dry matches: {len(matches)}")
print(f"2025 dry misses: {len(misses)}")
print()

# Group misses by compound
from collections import Counter
by_compound = Counter(m["state_compound"] for m in misses)
print("Misses by state_compound:", dict(by_compound))

by_class = Counter(m["class"] for m in misses)
print("Misses by classification:", dict(by_class))
print()

# ARIS-hindsight misses (ARIS wrong)
aris_wrong = [m for m in misses if m["class"] == "divergence_aris_hindsight"]
print(f"ARIS-hindsight misses: {len(aris_wrong)}")
for m in sorted(aris_wrong, key=lambda x: x["state_compound"]):
    print(
        f"  {m['gp']:<20} L{m['lap']:<3} {m['state_compound']:<8} "
        f"age={m['tyre_life']:<3} team->{m['team_compound']:<8} "
        f"aris={repr(m['aris'])[:35]}"
    )
print()

# Group aris-wrong by compound
print("ARIS-hindsight by compound:", Counter(m["state_compound"] for m in aris_wrong))
print("ARIS-hindsight by GP:", Counter(m["gp"] for m in aris_wrong))
print()

# Team-hindsight misses (team wrong)
team_wrong = [m for m in misses if m["class"] == "divergence_team_hindsight"]
print(f"Team-hindsight misses: {len(team_wrong)}")
for m in sorted(team_wrong, key=lambda x: x["gp"]):
    print(
        f"  {m['gp']:<20} L{m['lap']:<3} {m['state_compound']:<8} "
        f"age={m['tyre_life']:<3} team->{m['team_compound']:<8} "
        f"aris={repr(m['aris'])[:35]}"
    )
print()

# Late-race HARD urgency candidates (potential urgency penalty targets)
urgency_candidates = [
    m for m in aris_wrong
    if m["state_compound"] == "HARD"
    and m["class"] == "divergence_aris_hindsight"
    and m["tyre_life"] >= 18
]
print(f"Urgency penalty candidates (HARD age>=18 ARIS-hindsight): {len(urgency_candidates)}")
for m in urgency_candidates:
    print(
        f"  {m['gp']:<20} L{m['lap']:<3} HARD age={m['tyre_life']:<3} "
        f"team->{m['team_compound']}"
    )
