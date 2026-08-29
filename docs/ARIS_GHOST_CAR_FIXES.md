# ARIS ghost car — lap-1 parallel strategy

## What changed

The map and timing-tower ghost is no longer created only when ARIS’s call diverges from the real driver. It is a **parallel run of ARIS’s lights-out plan from lap 1**, scored with the same `simulate(..., STAY_OUT)` model used for recommendations.

The Explain-tab ghost vs real chart uses that same plan and the same per-lap scoring, then ranks the ghost’s cumulative simulated time against the classified field. Live/replay ticks and the debrief therefore tell the same story (same plan, same sign of time delta).

## How the ghost is computed from lap 1

1. **Plan (once per driver/session, cached)**  
   `recommend()` runs at lap 1 (lap 2 if lap 1 returns `STRATEGY_RESET`) with the real driver’s **starting compound** and **grid position**. The top strategy card (not lift/brake) is converted to a pit schedule: stay-out, `pit_now`, `pit_lap`, or a multi-stop `pit_laps` list.

2. **Per-lap score**  
   For every lap:
   - Ghost `RaceState`: same circuit/lap/gaps as the real car; compound and tyre age follow the ARIS plan.
   - Real `RaceState`: classified compound and tyre age.
   - `simulate(..., STAY_OUT)` for both; **this lap’s** time is the first `lap_times_out` sample (not remaining-race mean).
   - Pit laps add circuit pit-loss to the car that stopped.
   - `lap_delta = real_lap_s − ghost_lap_s` (positive ⇒ ARIS ahead).
   - `cumulative_delta` sums those deltas.

3. **Replay/live frames**  
   Each frame gets the tick for the current lap (from lap 1 onward): compound, tyre age, cumulative delta, estimated position. `ghost_position_on_track` is the real car’s `path_frac` plus `cumulative_delta / typical_lap_s`.

4. **Map / tower**  
   Ghost is a separate dot (`A_` code, `[A]` label, translucent fill, dashed outline) offset along the lap. The tower inserts an ARIS row at the estimated position, shows the cumulative delta as gap, and uses `ARIS` / `—` instead of sector and last-lap times.

## How to verify

- **Map:** With ARIS on and a driver selected, a ghost dot is visible from lap 1. After the first ARIS or real pit it must not sit on top of the real car.
- **Timing tower:** An italic `[A]` row appears when ARIS is on. Gap updates each lap; last-lap/sectors show `ARIS` / `—`; tyre/age follow the ARIS plan.
- **Debrief (Explain → Ghost vs real):** Pit list matches the live ghost plan; position/gap series should agree in sign with the live cumulative delta (ARIS ahead ⇒ ghost closer to the leader / better rank).
- **Sanity log (Zandvoort 2025 VER fixture):** `pytest tests/test_ghost_vs_real.py -s` prints the plan and cumulative delta at lap 1 and the end.

## Known limitations

- **Position** is estimated (cumulative simulated time vs the classified field, or gap-based passing). It is not a full N-car race simulation.
- **Rivals** on live frames are often missing; passing uses the real driver’s gaps when present, otherwise rank vs field times from the explain bundle / DB.
- **Live sessions** that are not in the ARIS DB and have no FastF1 explain bundle cannot score a ghost yet (`session_not_ingested`).
- **Same start compound** as the real driver: until the first pit (ghost or real), the cars stay close on track — that is correct, not a bug. A tiny along-track offset is applied only so both dots remain visible.
- **Pit loss** is the circuit YAML value (SC/VSC-adjusted), applied as a one-shot on the in-lap. Out-laps are not modelled beyond `simulate()` warmup on fresh tyres.
- Divergence-gated `maybe_create_ghost()` remains for the older directional-accuracy tests; the map/tower/debrief path does not wait for a disagreement.
