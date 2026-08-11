# ARIS action vocabulary

Counterfactual actions the simulator can score today. All deltas are relative
to **stay out** on the current compound (same remainder of the race).

## Pit actions

| Kind | Fields | Meaning |
|---|---|---|
| `stay_out` | optional `pit_laps` / `pit_compounds` for a multi-stop plan | Continue; optional scheduled future stops |
| `pit_now` | `pit_compound` | Pit this lap for the named compound |
| `pit_lap` | `pit_lap`, `pit_compound` | Pit on a future lap |

Pit loss comes from the track YAML (`pit_loss_s`). Lap times come from the
physics + residual predictor (with optional MC noise in `montecarlo.py`).

## Line actions (Phase C)

These extend the bicycle model’s corner-by-corner structure
(grip-limited corners + lumped inter-corner straights) — they do **not**
rebuild the physics engine.

| Kind | Fields | Meaning |
|---|---|---|
| `lift` | `corner_index` (1-based), `distance_m` | Lift / coast `distance_m` earlier into that corner |
| `brake` | `corner_index` (1-based), `distance_m` | Move the brake point `distance_m` earlier into that corner |

**Kinematic model.** For corner \(T_k\), the preceding straight segment length
is `straight_length_m / n_corners`. The final `distance_m` of that segment is
covered at corner speed instead of the grip-limited accel/cruise profile.
The resulting delta is ≥ 0 (earlier lift/brake ⇒ slower lap) and is applied
once to the current lap in `simulate()`.

**Not modelled yet (dropped until they can be simulated honestly):**

- Hardcoded DRS-attack (−0.15 s) and defend (+0.05 s) bonuses formerly in
  `recommend.py` — removed in Phase C because they were unsimulated constants.

## Example

```text
Lift 30 m into T7 (Bahrain geometry) → predicted delta ≈ +0.05–0.15 s
```

See `results/lift-t7-demo.txt` (regenerate with
`python scripts/demo_lift_t7.py`).
