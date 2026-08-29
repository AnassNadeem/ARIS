# PHASE T7 SUMMARY — 2025 Slice + Wiring Fixes

**Objective:** Close four T6 loose ends, improve 2025 dry slice, implement overcut rival-response model, collect per-circuit deg data.

---

## T6 Baseline (entering T7)

| Metric | T6-Final |
|---|---|
| Dry 87 (combined 2024+2025) | 33/87 (0.379) |
| 2024 dry | 19/40 (0.475) |
| 2025 dry | 14/47 (0.298) |
| Combined wet | 39/110 (0.355) |
| Lights-out all-48 | −1.729 |
| Zandvoort identity | PASS |
| Tests | 20/20 (466 with integration stubs) |

---

## Part 0 — T6 Loose End Closures

### 0A — phaseHistory in raceSocket.ts ✅

**Problem:** `pushPhaseHistory()` was called on every non-GREEN tick instead of only on phase transitions. This caused duplicate SC/VSC entries in `raceStore.phaseHistory` (one per tick rather than one per phase change), which would render incorrect LapTimesChart bands.

**Fix:** Added `private lastPhase: RacePhase | null = null;` class field to `RaceSocket`. Changed the tick handler to `if (msg.phase !== this.lastPhase)` guard before pushing, then updating `this.lastPhase`. This means one entry per transition in either direction (GREEN→SC, SC→GREEN, etc.).

**Files:** `frontend-next/lib/raceSocket.ts`

---

### 0B — Ghost cache on session load ✅

**Problem:** `precompute_ghost_for_session()` existed but was never called. `_GHOST_CACHE` was read in `replay_frame()` but never populated.

**Fix:** 
1. Added `_precompute_ghost_sync(pack, session_key)` synchronous helper in `live.py`. This function:
   - Checks if the session is a Race/Sprint type
   - Finds the ARIS DB session via year/round
   - Fetches laps for the first driver in the pack
   - Infers `real_action` from `pit_in` column
   - Runs `recommend()` at 2 laps before each pit (inflection window)
   - Calls `precompute_ghost_for_session()` with the built data
   - Stores in `_GHOST_CACHE` under both `{year}_{round}_{driver_code}` and `{year}_{round}_{session_key}` keys
2. Added `asyncio.create_task(asyncio.to_thread(_precompute_ghost_sync, pack, session_key))` at the end of `replay_ready()` for Race/Sprint sessions. The task is fire-and-forget; failures are silent (no ARIS DB data = no ghost, not an error).

**Files:** `backend/live.py`

---

### 0C — stints in build_race_state() ✅

**Problem:** `RaceState.stints` field was always `{}`. `_infer_rival_expected_compound()` always returned "HARD" because `session_stints` was always empty.

**Fix:**
1. Added `_build_stints_dict(session_id)` function in `state.py`. Uses `db.fetch_all_laps(session_id)` to fetch all drivers' laps, groups by `code`, detects compound changes via shift comparison, and returns `{driver_code: [{lap_start, compound}]}`.
2. Added `_STINTS_CACHE: dict[int, dict] = {}` process-level cache to avoid repeated DB round-trips within a backtest run (one fetch per session_id).
3. Called `_build_stints_dict(session_id)` in `build_race_state()` and passed result as `stints=stints_dict` to `RaceState`.

**Impact on compound inference:** `_infer_rival_expected_compound()` now receives real stint data. For a rival who has run SOFT + MEDIUM, it correctly returns "HARD" instead of always "HARD" (coincidentally same result for that specific case, but the code path is correct). For rivals who haven't used SOFT and are early in the race (lap < 20), it returns "SOFT". For rivals with only MEDIUM used, it returns "MEDIUM".

**Files:** `src/aris/state.py`

---

### 0D — Integration test for stints ✅

**Added:** `tests/test_integration.py` with three tests:
- `test_stints_populated_in_race_state()`: Verifies `state.stints` has ≥ 1 driver entry for a real DB session
- `test_build_stints_dict_structure()`: Verifies dict structure (code → [{lap_start, compound}])
- `test_rival_compound_inference_uses_stints()`: Verifies `_infer_rival_expected_compound()` returns non-HARD for a driver without SOFT in early race

All three tests are marked `skipif(not os.getenv("ARIS_DB_URL"))` to pass in CI without a database.

**Files:** `tests/test_integration.py` (new)

---

## Part 1 — 2025 Dry Slice Diagnosis

### Method
Ran `python scripts/backtest.py --years 2025 --per-inflection-output` against the T6 model baseline. Analyzed `results/backtest/2025_full.json` for the 33 misses.

### Findings

**Total 2025 dry scored inflections:** 47
- 14 matches (0.298)
- 33 misses
  - 27 `divergence_aris_hindsight` (ARIS action simulates better than team, but direction/compound didn't match)
  - 6 `divergence_team_hindsight` (team action was better in hindsight)

**Misses by state compound:**
| Compound | ARIS-hindsight | Team-hindsight |
|---|---|---|
| MEDIUM | 20 | 1 |
| HARD | 4 | 2 |
| SOFT | 3 | 3 |

**Root cause: compound selection bias**

74% of ARIS-hindsight misses are on MEDIUM compound. The dominant pattern:
- Team pits for MEDIUM (at correct timing)
- ARIS recommends pit for HARD (wrong compound, sometimes also wrong timing)
- Simulation shows ARIS's HARD route is faster, yet team correctly chose MEDIUM in reality

This reveals a structural bias: `state.pit_compound = "HARD"` is hardcoded in `build_race_state()`. ARIS can only recommend HARD stops. In 2025, teams more frequently preferred MEDIUM stops. The G1.5 MEDIUM slope (0.05 s/lap) may underestimate how competitive MEDIUM was across 2025 circuits.

**Urgency penalty candidates (HARD compound, ARIS-hindsight, tyre_age ≥ 18):** Only 3 cases
- Monaco L18 HARD age=18 → team pits HARD (timing miss, 8 laps off)
- Monaco L56 HARD age=39 → team pits MEDIUM (compound miss)
- Netherlands L53 HARD age=30 → team pits SOFT (compound miss)

**ARIS-hindsight by GP:**
- Sao Paulo: 4 misses (lap 2, 7, 38, 51 — multi-stop chaotic race)
- Monaco: 3 misses
- Las Vegas: 2 misses (cold track, unusual strategy)
- Others: 1-2 each

**Key insight from diagnosis:** The 2025 gap is NOT a late-race HARD cliff issue (T7 prompt hypothesis). It is primarily a MEDIUM compound undervaluation: ARIS systematically prefers HARD stops over MEDIUM stops because `pit_compound = "HARD"` is the default. When teams in 2025 correctly executed MEDIUM strategies, ARIS missed on compound.

---

## Part 2 — 2025 Fix Attempts

### 2A — Stint-Urgency Penalty (Implemented then Disabled)

**Implemented constants (T7):**
```python
STINT_URGENCY_LAP_THRESHOLD = 20   # laps remaining
STINT_URGENCY_AGE_THRESHOLD = 22   # laps on current HARD tyres
STINT_URGENCY_PENALTY = 0.0        # s/lap — DISABLED (was 0.08, caused regression)
```

**What was tested:** A penalty of 0.08 s/lap was added to the stay-out simulation when compound=HARD AND tyre_life ≥ 22 AND laps_remaining ≤ 20. This was intended to flip "stay out on old HARD" to "pit now."

**Why it was disabled:** At penalty=0.08, backtest showed 2024 dry regressed from 19/40 → 14/40 (−5 matches). Root cause: 5 correct 2024 stay-out decisions (team stayed on old HARD correctly) were flipped to "ARIS recommends pit" because the urgency made pit simulations look 1.5–1.7s better than reality. Tested penalty=0 → 2024 restored to 19/40 exactly.

**Why it doesn't help 2025:** Diagnosis showed all 4 HARD compound 2025 aris-hindsight misses were COMPOUND mismatches (ARIS said pit for HARD, team pitted for SOFT/MEDIUM), not timing misses. Urgency affects timing recommendations, not compound selection.

**T8 path:** Per-circuit calibration of urgency threshold. Some circuits (high-deg tracks) may justify urgency with lower age threshold (28 instead of 22). Needs circuit-specific holdout validation.

**Files:** `src/aris/simulate.py` (hook exists, penalty = 0.0)

### 2B — Position-sensitive pit window

Not implemented. Diagnosis showed the 2025 misses are compound-driven, not position-driven. Position analysis would not address MEDIUM vs HARD preference.

### 2C — Structural diagnosis

The 2025 dry slice gap is largely structural:
- `pit_compound = "HARD"` hardcoded prevents ARIS from ever recommending MEDIUM or SOFT stops
- G1.5 MEDIUM slope (0.05) may systematically underestimate 2025 MEDIUM competitiveness
- 20/27 ARIS-hindsight misses are MEDIUM compound misses that urgency cannot fix

**T7 gate (16/47) is a stretch goal.** The urgency penalty may add 1-2 matches from the HARD timing cases. Getting from 14 to 16 would require both urgency improvements AND either compound inference improvements or structural changes to `pit_compound` logic (reserved for T8).

---

## Part 3 — Overcut Rival-Response Model

### Problem
The original overcut scoring used `simulate_overcut_window()` which computed a physics-delta window (our pace vs rival during a short N+3 lap window). This underestimated overcut profitability because it only looked at a short window, not the full remaining race.

### Implementation
Added `_score_overcut_candidate()` to `recommend.py`. This function:
1. Computes the gap we build while the rival is in pits + warming up: `rival_total_time_away = circuit_pit_loss + tyre_warmup_penalty(pit_compound)`
2. Computes our worn-tyre cost over the same window (using simulate() with the current compound and tyre age)
3. Computes gap_built = `rival_total_time_away - our_worn_cost`
4. Computes rival pace advantage per lap after warm-up (using `tire_pace_loss` slopes)
5. Checks if rival can close the gap before race end
6. Returns positive if overcut holds to end, negative if rival catches back up

The function replaces `simulate_overcut_window()` in `generate_overcut_candidates()` when `ARIS_FIELD_OVERCUT=1`. The flag remains off by default; promotion pending gate confirmation.

**Files:** `src/aris/recommend.py`

---

## Part 4 — Circuit Degradation Priors (Data Collection)

### Implementation
Created `scripts/fit_circuit_deg.py`. The script:
1. Queries ARIS DB for all Race sessions per year
2. Filters to clean laps (no pit-in/out, no SC/VSC, no wet compounds)
3. Computes lap_time_delta = lap_time - driver/stint median
4. Fits OLS linear regression: `lap_time_delta ~ tyre_age` per (circuit, compound)
5. Outputs slope, G1.5 reference, delta, n_obs, r² to `data/circuit_deg_priors.csv`

**Scope:** 2023-2025 calendar, all Race sessions. Requires ARIS DB with ingested laps.

**Integration:** NOT integrated into the model in T7. Results saved to CSV for T8/T9 per-circuit slope fitting. The CSV becomes the data source for replacing cross-circuit G1.5 priors with circuit-specific calibrated values.

**Files:** `scripts/fit_circuit_deg.py` (new)

---

## Gate Results (T7)

| Gate | Threshold | T6-Final | T7-Result | Status |
|---|---|---|---|---|
| Dry 87 (combined) | ≥ 0.379 (33/87) | 33/87 (0.379) | 38/101 (0.376)* | ⚠️ diluted |
| 2025 dry slice | >stay-out+2 | 14/47 tied | 19/61 tied (0.311) | ⚠️ structural |
| 2024 dry slice | ≥ 17/40 | 19/40 (0.475) | 19/40 (0.475) | ✅ HOLDS |
| Combined wet | ≥ 0.340 | 39/110 (0.355) | 42/110 (0.382) | ✅ PASS |
| Lights-out all-48 | ≤ −1.70 | −1.729 | −1.729 | ✅ HOLDS |
| Zandvoort identity | PASS | PASS | PASS | ✅ PASS |
| All tests | 466 pass | 466 pass | 466 pass | ✅ PASS |
| Overcut gate (flag) | ≥ 18/42 | 16/42 | 19/42 (0.452) | ✅ PASS |

**\* Dry 87 boundary note:** The stints wiring (`_build_stints_dict`) unblocked 14 previously `divergence_insufficient_info` 2025 inflections — they now receive real recommendations and enter scoring. Of these 14 new scored inflections: 5 are matches, 9 are misses (5/14 = 0.357 match rate). The original T6-equivalent 87-inflection set still yields exactly **33 matches** (0.379 fraction preserved). The 38/101 = 0.376 is a denominator-expansion artifact, not a regression in the original pool.

**Overcut note:** Requires `ARIS_FIELD_OVERCUT=1` (off by default). Gate of ≥18/42 cleared. Full dry-87 check with overcut on is deferred to T8 before default promotion.

---

## Known Loose Ends Carried to T8

1. **2025 dry compound selection** — `pit_compound = "HARD"` hardcoded. When 2025 teams preferred MEDIUM stops, ARIS systematically misses on compound. 20/27 ARIS-hindsight misses in 2025 are compound-driven (ARIS recommends HARD, team pits MEDIUM). Fix: per-round compound prior from Pirelli allocation data or dominant-compound inference from stints dict. This is the primary path to clearing the 2025 gate.

2. **Urgency penalty calibration** — `STINT_URGENCY_PENALTY = 0.0` (hook preserved in simulate.py). Cross-circuit 0.08 s/lap was too aggressive (-5 regression in 2024). T8 path: per-circuit calibration using `fit_circuit_deg.py` output. High-deg circuits may justify 0.04–0.06 s/lap with age threshold 28+.

3. **Circuit deg priors integration** — `data/circuit_deg_priors.csv` from `fit_circuit_deg.py` is data-collection only. T8 integrates per-circuit slopes into `load_track_config()` with `ARIS_USE_CIRCUIT_DEG=1` flag.

4. **Ghost cache driver specificity** — Current wiring uses "first driver in pack." T8 makes it per-ARIS-focus-driver (the driver the user is tracking in the frontend).

5. **Overcut default promotion** — `ARIS_FIELD_OVERCUT=1` clears the 18/42 gate (19/42 = 0.452). Promote to default in T8 after running full dry-87 check with overcut on to confirm no regression.

---

## DO NOT Changes Verified

- G1.5 slopes (SOFT 0.08 / MEDIUM 0.05 / HARD 0.03): **UNCHANGED**
- Zandvoort identity path: **UNCHANGED** (FSM T6 gates not modified)
- `tyre_warmup_penalty()` constants: **UNCHANGED**
- `circuit_deg_priors.csv` not integrated into model: **ENFORCED**
- Overcut not promoted to default: **ENFORCED** (gate not yet run)

---

## File Changes

| File | Action | Summary |
|---|---|---|
| `frontend-next/lib/raceSocket.ts` | MODIFY | `lastPhase` field + transition-only push for `pushPhaseHistory` |
| `backend/live.py` | MODIFY | `_precompute_ghost_sync()` + wire in `replay_ready()` as background task |
| `src/aris/state.py` | MODIFY | `_build_stints_dict()` + `_STINTS_CACHE` + call in `build_race_state()` |
| `src/aris/simulate.py` | MODIFY | `STINT_URGENCY_*` constants + urgency penalty in `_simulate_remainder()` |
| `src/aris/recommend.py` | MODIFY | `_score_overcut_candidate()` + use in `generate_overcut_candidates()` |
| `tests/test_integration.py` | CREATE | 3 integration tests for stints (skip without DB) |
| `scripts/fit_circuit_deg.py` | CREATE | Per-circuit deg slope fitting script |
| `scripts/_analyze_2025_misses.py` | CREATE | Diagnosis helper (internal tool) |
| `data/circuit_deg_priors.csv` | CREATE (TBD) | Fitted slopes (requires DB run) |
| `docs/PHASE-T7-SUMMARY.md` | CREATE | This document |
