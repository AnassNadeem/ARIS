# T9.2 phase summary — Fuel-Load Correction + Smarter MEDIUM/HARD Offsets

Date: 2026-08-26
Commit: e404a59 (working tree; T9.2 not committed)
Status: **PARTIAL**

T9.1 left long-remainder MEDIUM stops (Bahrain, Austria, Spain, Qatar, Mexico) on HARD because a global −0.30 s offset cannot beat HARD’s shallower slope over 25–50 laps, and because fuel-lightening in the chained remainder made stay-out look cheap. T9.2 puts a linear fuel deg-trend correction in `simulate()` and per-circuit MEDIUM offsets in the bicycle. Identity still holds. 2025 dry is unchanged at 13/47.

## Changes

- Added simple linear fuel correction to `simulate()` (`k_fuel` ≈ 0.03 s/kg, `fuel_start` ≈ 110 kg). Bicycle already adds `k_fuel * fuel_kg` to the absolute lap. FP2 slopes are fuel-corrected (practice starts light), so the chained remainder now subtracts that term from physics before differencing: `lap_time_fuel_adjusted = lap_time_raw - k_fuel * fuel_load`. Tyre drop is no longer masked by ~0.05 s/lap of fuel burn. First residual-corrected lap is unchanged. INTER/WET use the same term.
- Added per-circuit MEDIUM offsets vs HARD in `CIRCUIT_MEDIUM_OFFSET` (`tires.py`), looked up via `_normalize_circuit_key`. Fallback is the global −0.30 s. SOFT stays −0.40 globally (capped so Zandvoort two-stop SOFT does not displace Pit 30 HARD).
- No changes to match logic, gates, or scoring bonuses.

Shipped `CIRCUIT_MEDIUM_OFFSET`:

| Circuit | Offset | Why |
|---|---:|---|
| bahrain | −0.35 | T9.1 long-MEDIUM miss; must stay weaker than SOFT (−0.40) |
| austria | −0.35 | same |
| qatar | −0.35 | same |
| mexico | −0.35 | same |
| spain | *(fallback −0.30)* | −0.40 tied SOFT and stole T9.1 Spain L56 SOFT match |
| netherlands | *(fallback −0.30)* | Zandvoort identity |

Later-stint race medians (2024–2025 dry, first 3 green laps) do **not** support a more-negative MEDIUM offset at the miss circuits (Bahrain +0.55 s, Qatar +2.30 s, Mexico +0.27 s, Austria +0.02 s). Those medians are a confounded mix of stint position and allocation. The table above is a strategy prior in the allowed −0.50…−0.20 band, not a copy of the raw table.

## Gate results (before vs after)

| Gate | Threshold | T9.1 | T9.2 | Pass? |
|---|---|---|---|---|
| 2025 dry slice | > stay-out (14/47) | **13/47** | **13/47** (stay-out 14/47) | **NO** |
| Compound accuracy | ≥ 70% on 2025 aris-hindsight | 10.0% (3/30) documented; remeasured 6/30 (20%) | **6/30 (20%)** same rule | **NO** |
| Zandvoort identity | Pit 33 HARD / Pit 30 HARD / Stay | PASS | **PASS** | **YES** |
| 2024 dry slice | ≥ 14/40 | confirmation walk **15/40** | not re-walked (2025 labels identical) | pending |
| Dry 87 | ≥ 30/87 | confirmation 28/87 (15+13) | not re-walked | pending |

Zandvoort window times (HARD still clearly best; compound gaps unchanged vs T9.1 because fuel strip is common across compounds):

- Pit lap 33: HARD = 3750.9 s, MEDIUM = 3766.3 s (+15.3), SOFT = 3803.0 s (+52.0).
- Pit lap 30: HARD = 3756.3 s, MEDIUM = 3775.1 s (+18.9), SOFT = 3818.2 s (+61.9).
- recommend top-3: Pit lap 33 for HARD / Pit lap 30 for HARD / Stay out.
- Absolute remaining times rose ~56 s vs T9.1 (cumulative fuel-lightening removed over ~47 laps). Rankings did not.

2025 per-action breakdown (identical to T9.1):

| Class | T9.1 / T9.2 |
|---|---|
| PIT_M | 3/11 |
| PIT_S | 1/6 |
| PIT_H | 8/16 |
| STAY | 1/14 |

Label diff T9.1 confirmation JSON vs T9.2 JSON: **0 / 74** scored decisions.

Fuel sanity (`scripts/check_fuel_effect.py`, 30-lap HARD Bahrain):

- Fuel-adjusted physics lap 1 is **−3.30 s** vs raw (110 kg × 0.03). Early laps faster after detrend.
- Remainder with deg-trend correction is **+22.2 s** vs without (tyre drop unmasked). Totals plausible (~3475 s).

## What improved

- Fuel effect is now explicit in the remainder chain and checkable. Absolute stint times no longer get a free ~0.05 s/lap as fuel burns.
- MEDIUM can be faster than the global −0.30 s at four high-deg circuits without touching Zandvoort.
- Spain L56 SOFT match **held** after dropping Spain from the circuit table (a −0.40 Spain offset had flipped it to MEDIUM on the first probe).

## What didn’t move

- **2025 dry 13/47**, still 1 below stay-out. Fuel strip is a common additive across strategies (same race laps), so it does not change pit vs stay-out ranking. Per-circuit −0.35 is too small against weekend FP2 slope gaps.
- Long MEDIUM misses unchanged: Bahrain L17/L32, Spain L9, Austria L18, Qatar L7, Mexico City L24.
  - **Candidate suppression:** Bahrain L17/L32 and Austria L18 are already on MEDIUM, remaining ≥ 25, track temp > 25 °C → `_get_available_compounds` drops MEDIUM (SOFT+HARD only). Offsets never get scored. Not changed in T9.2 (not a bicycle term).
  - **FP2 slope gap:** Bahrain MEDIUM 0.125 vs HARD 0.075 (Δ 0.050 s/lap). A 40-lap remainder needs ~−0.98 s of fresh offset for MEDIUM to win; the allowed band stops at −0.50. Austria Δ 0.043; Spain L9 is 57 laps (Δ 0.020, needs ~−0.55). Diagnosed windows: Bahrain L17 pit-now M−H = **+22.6 s**; Austria L18 **+35.9 s**; Spain L9 **+8.3 s** (MEDIUM available, still HARD).
- Compound accuracy **6/30 (20%)** on 2025 aris-hindsight (label contains team compound). T9.1 summary’s 3/30 used a stricter count; both JSONs agree at 6/30 under the same rule.
- Las Vegas / Japan Cause-A unchanged (no FP2 HARD long-run at Vegas; Japan still wants a later HARD stop).
- Raising miss-circuit MEDIUM to −0.40 (equal to SOFT) steals short-final SOFT matches (Spain L56). Do not go there.

## Readiness for T10

- [ ] 2025 dry > stay-out
- [ ] Compound accuracy ≥ ~40–50%
- [x] Zandvoort identity PASS
- [ ] No major 2024 regression (2024 not re-walked on T9.2; T9.1 confirmation was 15/40)

T10 (SC risk, conformal, wet classifier, per-lap MC) will not make HARD’s 0.075 s/lap Bahrain slope lose a 40-lap remainder to MEDIUM at −0.35 s. The remaining 2025 gap is (1) weekend FP2 slope gaps on long stints, and (2) hot-track repeat-MEDIUM suppression in `_get_available_compounds` — not another −0.05 s on the global MEDIUM offset.

## Files

- `src/aris/simulate.py` — `fuel_correction_s()`, chained physics fuel strip, `fuel_deg_correction` flag
- `src/aris/physics/tires.py` — `CIRCUIT_MEDIUM_OFFSET`, `compound_pace_offset(circuit_id=...)`, `tire_pace_loss(circuit_id=...)`
- `src/aris/physics/bicycle.py` — `track.name` into `tire_pace_loss`
- `src/aris/recommend.py` — undercut `tire_pace_loss` passes `state.country`
- `scripts/analyze_circuit_compound_offsets.py` — 2024–2025 per-circuit fresh MEDIUM vs HARD table
- `scripts/check_fuel_effect.py` — 30-lap HARD with/without fuel correction
- `scripts/check_zandvoort_pace.py` — identity + circuit offset print
- `scripts/_t92_probe_rounds.py`, `scripts/_t92_diagnose_medium.py` — iteration probes
- `tests/test_strategy.py`, `tests/test_tires.py` — fuel-strip physics-delta + circuit offset tests
