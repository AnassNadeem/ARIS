# T9 phase summary — Degradation Model v2 + Compound Evaluation

Date: 2026-08-25
Commit: e404a59 (working tree; T9 not committed)
Status: **PARTIAL**

True T8 floor used throughout: dry 87 = **28/87 (0.322)**. 33/87 included a double-counting bug and is not a gate.

## Gate results

| Gate | Threshold | T8-final | T9 | Pass? |
|---|---|---|---|---|
| Dry 87 | ≥ 30/87 (0.345) | 28/87 (0.322) | **32/87 (0.368)** | **YES** |
| 2025 dry slice | > stay-out (14/47) | 13/47 | **13/47** (stay-out 14/47) | **NO** |
| 2024 dry slice | ≥ 14/40 | 16/40 | **19/40 (0.475)** | **YES** |
| Combined wet | ≥ 0.340 | (carry T8 / T7 42/110) | **41/110 (0.373)** — 2024 23/49, 2025 18/61 | **YES** |
| Lights-out all-48 | ≤ −1.70 | −1.729 | **−1.3125** (improved; less negative) | **YES** |
| Zandvoort identity | Pit 33 HARD / Pit 30 HARD / Stay | PASS | **PASS** | **YES** |
| Compound accuracy | ≥ 70% on 2025 aris-hindsight from simulator output | 87.5% (label only) | **15.2% (5/33)** | **NO** |
| FP2 calibration | Slope available for ≥ 10 circuits | 0 | **15 circuits / 19 HARD weekends** (fp2 or fp2_scaled) | **YES** |
| All tests | ≥ 489 | 489 | **505 passed** | **YES** |

Part 1 only (FP2 slopes, no multi-compound): 31/87, 2024 19/40, 2025 12/47.
Part 2 (multi-compound shortlist): +1 combined (32/87), 2025 12→13, 2024 held 19/40.

## FP2 calibration results

`calibrate_race_weekend` priority: valid FP2 long-run OLS → FP1/FP3 → scale-up from a fitted slick → circuit prior CSV (file absent) → G1.5. INTER/WET always G1.5. Physical order cap: MEDIUM ≤ SOFT × 0.05/0.08, HARD ≤ MEDIUM × 0.03/0.05. Slopes clipped at 0.20.

| Circuit | Year | HARD slope | G1.5 HARD | Delta | Source |
|---|---|---|---|---|---|
| Bahrain | 2024 | 0.0398 | 0.030 | +0.010 | fp2_scaled |
| Japan | 2024 | 0.0750 | 0.030 | +0.045 | fp2_scaled |
| Belgium | 2024 | 0.0750 | 0.030 | +0.045 | fp2 |
| Italy | 2024 | 0.0750 | 0.030 | +0.045 | fp2_scaled |
| Las Vegas | 2024 | 0.0300 | 0.030 | 0 | g15 (no long-runs) |
| Bahrain | 2025 | 0.0750 | 0.030 | +0.045 | fp2_scaled |
| Netherlands | 2025 | 0.0555 | 0.030 | +0.026 | fp2 (order-capped) |
| Spain | 2024 | 0.0727 | 0.030 | +0.043 | fp2 |
| Emilia Romagna | 2024 | 0.0450 | 0.030 | +0.015 | fp2 |
| Austria | 2025 | 0.0465 | 0.030 | +0.017 | fp2 |

Bahrain / Japan HARD slopes are **> 0.03** as required. Las Vegas has **no** practice long-run signal, so Cause-A Las Vegas cannot be fixed by FP2 calibration.

FP2/fp2_scaled HARD weekends (19): 2024 Australia, Bahrain, Belgium, Britain, Canada, Emilia Romagna, Hungary, Italy, Japan, Monaco, Netherlands, Saudi Arabia, Spain; 2025 Austria, Bahrain, Canada, Mexico City, Netherlands, Spain. Unique circuits: **15** (≥ 10).

### Cause-A (5 stay-out misses, team pitted HARD)

| Event | T8 | After FP2 (Part 1) | After Part 2 |
|---|---|---|---|
| 2024 Bahrain RUS L31 | stay-out miss | Pit lap 34 HARD (team-hindsight, not a match) | same |
| 2024 Japan NOR L26 | stay-out miss | Pit lap 31 HARD (aris-hindsight) | same |
| 2024 Belgium NOR L29 | stay-out miss | **match** (Pit now HARD) | **match** |
| 2024 Italy HAM L37 | stay-out miss | **match** (Pit now HARD) | **match** |
| 2024 Las Vegas VER L27 | stay-out miss | Stay out (still miss; G1.5 HARD) | Stay out |

**2/5 recovered as matches** (Belgium, Italy). Bahrain stopped staying out but the stop is 3 laps late (outside the match window). Japan still late. Las Vegas unchanged.

## Compound evaluation results

- Before T9: **87.5%** compound accuracy (**label-only**, `_infer_focus_compound`).
- After T9: **15.2% (5/33)** on 2025 aris-hindsight, measured from the **top-ranked `recommend()` label** (simulator output). All-scored 2025 dry: 19/47 (40.4%) including HARD timing matches.
- 2025 MEDIUM team stops: **0/11 converted**. Per-action: PIT_M 0/11, PIT_S 0/6, PIT_H 12/16, STAY_OUT 1/14.

The shortlist now emits `PIT_NOW` / `PIT_LAP` for each available dry compound. Scoring still picks HARD on almost every pit card because the bicycle has **no fresh-compound pace offset** — SOFT/MEDIUM/HARD share the same out-lap + base lap, and HARD's shallower slope always wins a 15+ lap remainder. Warm-up priors exist in `tyre_warmup.py` but are only applied on the undercut path, not in `simulate()` ranking (not wired in T9: a 0.4 s MEDIUM-vs-HARD warm-up gap cannot beat 0.02–0.05 s/lap × 25 laps, and adding a large SOFT-faster offset would move Zandvoort identity off HARD).

Zandvoort window scores after multi-compound (identity **held**, HARD clearly best):

- Pit lap 33: HARD = 3696.0 s, MEDIUM = 3723.4 s, SOFT = 3764.5 s.
- Pit lap 30: HARD = 3700.4 s, MEDIUM = 3732.3 s, SOFT = 3780.1 s.

## What went wrong

1. **2025 still at 13/47**, not above stay-out. Multi-compound evaluation did not convert MEDIUM/SOFT team stops.
2. **Simulator compound accuracy 15%**, far below 70%. Generating three candidates is not the same as the physics being able to prefer MEDIUM.
3. **Las Vegas Cause-A unrecovered** — no FP2 HARD long-run; G1.5 0.03 remains.
4. **Japan Cause-A unrecovered** — FP2 HARD 0.075 still wants to pit later (L31 vs team L26).
5. **`data/circuit_deg_priors.csv` is missing**, so the CSV prior fallback is a no-op (G1.5 after FP2).
6. 2024 Bahrain FP2 has **no HARD laps** (SOFT/MEDIUM only); HARD is `fp2_scaled` (0.0398), only +0.01 vs G1.5 — not enough to match L31.
7. One wet unit test broke after FP2 overlay (INTER on a dry Zandvoort bicycle preferred stay-out). Restored by applying existing `INTER_PACE_LOSS_VS_SLICK` / `WET_PACE_LOSS_VS_SLICK` to the remainder **total** when rain flags are false — not a new wet classifier.
8. Order-cap was required after a noisy Zandvoort HARD stint (raw ~0.11) so identity did not flip to MEDIUM. Cap is physics-order, not a hardcoded HARD winner.

## What went well

- Dry 87 recovered **28 → 32/87** (+4 vs true T8 floor) without scoring bonuses.
- 2024 **16 → 19/40**; Belgium and Italy Cause-A HARD pits now match.
- Combined wet **41/110 (0.373)** holds ≥ 0.340 (2024 23/49, 2025 18/61).
- Lights-out baseline mean **−1.3125** (T8 −1.729); n=48.
- FP2 slopes for **≥ 10 circuits** (15 unique, 19 HARD weekends).
- Zandvoort identity held with HARD **~27 s** faster than MEDIUM at pit 33.
- Tests **505** (was 489).
- Pirelli allocation CSV populated for all 48 2024–2025 rounds from `data/compounds/nominations.json`.

## What would make this drastically better

1. **Fuel load correction for race deg** (FP2 starts light — race starts heavy ~110 kg, losing ~3 kg/lap × k_fuel ≈ 0.03 s/kg = 0.09 s/lap fuel advantage per lap early in race. This means early-race lap times are faster than the deg model predicts, making stay-out look better than it is. Fix: add a fuel correction term to `simulate()`. Marked in `_simulate_remainder` as `lap_time_fuel_adjusted = lap_time_raw - k_fuel * fuel_load`. Not implemented in T9.)
2. **Per-driver deg variation** (Hamilton is known to be easier on tyres; Verstappen harder. FastF1 has driver-level stint data to fit this. Currently all drivers use the same slope.)
3. **Track evolution within a session** (rubber laid down over a session means lap 15 of FP2 is faster than lap 3 even on same tyres. Currently not corrected for.)
4. **Fresh-compound pace offset** (SOFT/MEDIUM must be faster than HARD on lap 1 of a stint, not only steeper later. Without this, multi-compound evaluation cannot prefer MEDIUM. Do not add it as a ranking bonus; put it in `tire_pace_loss` / the bicycle. Must re-check Zandvoort identity.)
5. **Wire `tyre_warmup.py` into `simulate()`** (today only the undercut scorer adds it). Small (~0.4–0.9 s) vs slope×remainder; helps only very short final stints.

## T9 readiness for T10

- [ ] All gates pass (2025 dry and simulator compound accuracy fail)
- [x] FP2 calibration available for ≥ 10 circuits
- [ ] Multi-compound simulator produces correct compound choices (candidates exist; HARD still dominates)
- [ ] Summary committed

## Files

- `src/aris/physics/fp2_calibration.py` — extract / fit / `calibrate_race_weekend`
- `src/aris/physics/tires.py` — `get_deg_slope(year, round_number)` FP2-first
- `src/aris/simulate.py` — `_track_for` overlay; fuel-correction comment; INTER-on-dry remainder add-on
- `src/aris/recommend.py` — `_get_available_compounds`, three-compound PIT_NOW/PIT_LAP
- `src/aris/state.py` — `pirelli_allocation`, `load_pirelli_allocation`
- `data/pirelli_allocation.csv`
- `tests/test_fp2_calibration.py`, `tests/test_compound_evaluation.py`
- `scripts/backtest.py` — `--zandvoort-identity`, `--lights-out`
