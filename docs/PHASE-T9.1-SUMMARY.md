# T9.1 phase summary — Fresh-Compound Pace Offsets + Warmup Wiring

Date: 2026-08-26
Commit: e404a59 (working tree; T9.1 not committed)
Status: **PARTIAL**

T9 left the simulator unable to prefer MEDIUM/SOFT: all slicks shared the same fresh lap, so HARD’s shallower slope always won 15–30 lap remainders. T9.1 puts a fresh-compound pace offset in the bicycle and wires `tyre_warmup` into `simulate()`. Identity still holds. 2025 dry is still not above stay-out. Confirmation walk on the shipped offsets **regressed 2024 dry 19→15/40**, so combined dry 87 is **28/87** (T9 32/87; back to the true T8 floor).

## Changes

- Added `COMPOUND_PACE_OFFSET` (HARD=0.0, MEDIUM=−0.30, SOFT=−0.40) in `src/aris/physics/tires.py`, applied inside `tire_pace_loss()` so the bicycle base lap is compound-specific. INTER/WET offset = 0.
- Wired `apply_warmup()` from `tyre_warmup.py` into `_simulate_remainder()` for stint laps 1–2 (added to the lap *total*, not chained `pred`, so warmup does not accumulate).
- Calibrated from 2024–2025 dry stints (`scripts/analyze_fresh_compound_pace.py`): within-circuit later-stint paired medians were MEDIUM −0.19 s, SOFT −0.62 s. Naive global medians are unusable (circuit lap-length mix).
- SOFT capped at −0.40 so the Zandvoort two-stop `L31 SOFT → L46 HARD` does not displace Pit 30 HARD in the top-3.
- MEDIUM −0.40 (equal to SOFT) was tried on 2025 and **regressed** 13→12/47; reverted to −0.30.
- No changes to match logic, gates, scoring bonuses, or fuel correction.

## Gate results (before vs after)

| Gate | Threshold | T9 | T9.1 | Pass? |
|---|---|---|---|---|
| Dry 87 | ≥ 30/87 (0.345) | 32/87 (0.368) | **28/87 (0.322)** | **NO** |
| 2025 dry slice | > stay-out (14/47) | 13/47 | **13/47** (stay-out 14/47) | **NO** |
| 2024 dry slice | ≥ 14/40 | 19/40 (0.475) | **15/40 (0.375)** (stay-out 10/40) | **YES** (above 14; **−4 vs T9**) |
| Combined wet | ≥ 0.340 | 41/110 (0.373) | **37/110 (0.336)** — 2024 19/49, 2025 18/61 | **NO** (−4 vs T9; same 2024 dry HARD drop) |
| Lights-out all-48 | ≤ −1.70 | −1.3125 | **−1.229** (n=48; less negative than T9) | **YES** |
| Zandvoort identity | Pit 33 HARD / Pit 30 HARD / Stay | PASS | **PASS** | **YES** |
| Compound accuracy | ≥ 70% on 2025 aris-hindsight | 15.2% (5/33) | **10.0% (3/30)** | **NO** |
| All tests | ≥ 505 | 505 | **511 passed** | **YES** |

Zandvoort window times at the shipped offsets (HARD still clearly best):

- Pit lap 33: HARD = 3694.6 s, MEDIUM = 3709.9 s (+15.3), SOFT = 3746.6 s (+52.0).
- Pit lap 30: HARD = 3699.9 s, MEDIUM = 3718.8 s (+18.9), SOFT = 3761.9 s (+61.9).
- recommend top-3: Pit lap 33 for HARD / Pit lap 30 for HARD / Stay out.

Offset ablation on 2025 dry (same code, only the table changed):

| Offsets (H / M / S) | 2025 dry | PIT_M | PIT_S | PIT_H | STAY | Identity |
|---|---|---|---|---|---|---|
| T9 (no offset) | 13/47 | 0/11 | 0/6 | 12/16 | 1/14 | PASS |
| 0 / −0.30 / −0.40 | **13/47** | **3/11** | **1/6** | 8/16 | 1/14 | PASS |
| 0 / −0.40 / −0.40 | 12/47 | 3/11 | 0/6 | 7/16 | 2/14 | PASS |

Shipped table is the middle row. Larger MEDIUM offset did not beat stay-out; it traded HARD matches away.

## What improved

- 2025 MEDIUM team stops: **0/11 → 3/11**. Converted: Emilia Romagna L29 MEDIUM, Monaco L56 MEDIUM, Sao Paulo L51 MEDIUM.
- 2025 SOFT: **0/6 → 1/6** (Spain L56 Pit now for SOFT).
- Simulator can now prefer MEDIUM (and occasionally SOFT) on short final stints. Monaco L56 (HARD life 39, ~22 laps remaining) is the canonical example.
- Zandvoort identity still PASS with a 15 s HARD margin at pit 33 (T9 was ~27 s).

## What didn’t move

- **2025 dry 13/47**, still 1 below stay-out (14/47). Headline did not change: +3 MEDIUM and +1 SOFT were offset by −4 HARD.
- **2024 dry 19→15/40.** Combined dry 87 **32→28/87**, below the ≥30/87 gate and back to the true T8 floor. Combined wet **41→37/110** (0.336, below 0.340); 2025 wet held 18/61, the −4 is the same 2024 HARD drop showing up in the include-wet denominator.
- Compound accuracy on 2025 aris-hindsight **15% → 10%**. Generating MEDIUM matches is not the same as winning the 70% gate; lost HARD-label events hurt this metric.
- Remaining MEDIUM misses are long remainders (Bahrain L17/L32, Spain L9, Austria L18, Qatar L7, Mexico City L24) where HARD’s slope still wins a 25–50 lap stint. Raising the offset enough to convert those would flip Zandvoort (or already did, via the two-stop SOFT plan, when SOFT went past −0.40).
- Las Vegas / Japan Cause-A from T9 are unchanged (no FP2 HARD long-run at Vegas; Japan still wants a later HARD stop).
- Fuel-load deg correction is still a comment placeholder in `_simulate_remainder`.

## Readiness for T10

- [ ] Dry 87 ≥ 30/87 (now 28/87)
- [ ] 2025 dry > stay-out
- [ ] Compound accuracy ≥ ~50%
- [x] Zandvoort identity PASS
- [x] No lights-out regression (−1.229 vs T9 −1.3125)
- [ ] Combined wet ≥ 0.340 (now 37/110 = 0.336)

T10 (SC risk, conformal, wet classifier, per-lap MC) will not fix “HARD still wins a 40-lap remainder.” The remaining 2025 gap is fuel-corrected race deg vs FP2-light slopes, and/or per-circuit pace offsets — not another global −0.1 s on MEDIUM.

## Files

- `src/aris/physics/tires.py` — `COMPOUND_PACE_OFFSET`, `compound_pace_offset()`, `tire_pace_loss()`
- `src/aris/physics/tyre_warmup.py` — `apply_warmup()`, `tyre_warmup_for_lap()`
- `src/aris/simulate.py` — warmup on remainder totals
- `scripts/analyze_fresh_compound_pace.py` — 2024–2025 fresh-stint calibration
- `scripts/check_zandvoort_pace.py` — identity + window times
- `tests/test_tyre_warmup.py`, `tests/test_tires.py`, `tests/test_strategy.py`
