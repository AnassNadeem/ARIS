---
id: undercut
source: ARIS model note (not an FIA sporting rule) — docs/how-recommend-works.md
url: docs/how-recommend-works.md
---
# Undercut mechanics

An undercut is a tactical pit: stop now so the out-lap on fresh tyres is faster than the car ahead still circulating on older rubber, then come out ahead after that car later boxes. It is a strategy mechanic, not an FIA article. Default ARIS applies a small ranking bonus of −0.3 s (capped at −0.8 s, T2-D) when a pit candidate is scored and the gap ahead is inside an undercut window of 22.0 s (`UNDERCUT_WINDOW_S` in recommend.py). With `ARIS_FIELD_UNDERCUT=1` and a field snapshot, the bonus can instead come from a physics-delta window vs the car ahead’s estimated pit lap (capped −1.2 s), falling back to T2-D when that estimate is missing. Those numbers are ARIS model choices, not a regulation.
