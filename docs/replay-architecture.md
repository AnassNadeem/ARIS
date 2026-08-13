# Replay architecture

`engine/clock.py` (`SectorClock`) plus `engine/session.py` (`RaceEngineSession`)
**is the permanent, intentional replacement** for the originally-planned
`src/aris/replay.py`. The live Strategy path already advances a race
sector-by-sector through `SectorClock.tick()`, builds a temporally cut-off
`FieldState` / `RaceState` at that index, and fires `check_triggers` →
`DecisionQueue.propose` (`recommend()`). A second replay module would duplicate
that cutoff and drift from the demo.

Walk-forward backtest does **not** add `replay.py` either. Unattended calendar
walks cannot use the wall-clock 25 s cadence or Watch-mode pending-blocking
(one unresolved prompt would hide every later trigger). `scripts/backtest.py`
is a distinct **driver** around the same clock, session, triggers, and
`recommend()`: it ticks as fast as the CPU allows, logs every propose/resolve
to JSONL, and clears pending without committing ARIS pits so the replay keeps
observing the real race rather than a closed-loop ARIS-driven one. Temporal
cutoff stays in `FieldState.from_laps` / `compute_standings` / `build_race_state`
lag features — the walker does not reimplement it.
