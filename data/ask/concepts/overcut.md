---
id: overcut
source: ARIS strategy concept (not an FIA sporting rule) — docs/how-recommend-works.md
url: docs/how-recommend-works.md
---
# Overcut mechanics

An overcut is the opposite tactic: stay out while a rival boxes, hoping clean air and a lighter fuel load on the current stint offset their fresh-tyre out-lap. ARIS may emit an `OVERCUT_{code}_{N}L` candidate when a field snapshot is present, a rival is estimated to pit within 8 laps (confidence not LOW), the gap ahead is at least 2 s, and at least 15 laps remain. The window vs that rival is physics-delta only; the card is still ranked by `simulate()` vs stay-out. Stay-out remains on the scored shortlist. This is an ARIS model choice, not an FIA sporting rule.
