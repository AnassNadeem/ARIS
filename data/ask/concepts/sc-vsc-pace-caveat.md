---
id: sc-vsc-pace-caveat
source: ARIS live caveat string — docs/how-recommend-works.md and Phase E SC/VSC work
url: docs/how-recommend-works.md
---
# Safety Car / VSC pace caveat in ARIS

When recent lag pace used by recommend() includes Safety Car or VSC-affected laps, ARIS attaches the confidence caveat: “based on Safety Car-affected recent pace — lower confidence”. That string is a model warning because lag features inherit dirty pace; it is not an FIA procedure. Track status still comes from FastF1 TrackStatus on the snapshot. SC/VSC also trigger a decision prompt in the live engine.
