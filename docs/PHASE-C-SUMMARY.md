# Phase C summary — Close the predictor gap, then richer actions

Executed 2026-08-11. Scope was **only** Phase C (Blocks C.1a–C.1e, then C.2
after an honest C.1 conclusion). No Phase D+ work started.

---

## Verdict (read this first)

**The blended predictor does not beat the MA(2) baseline on clean held-out data.**

| Metric (held-out overall) | MAE (s) |
|---|---:|
| MA(2) baseline | **0.469** |
| Physics-only (unchanged from Phase B) | 15.211 |
| Physics+residual (Phase B / B3) | 0.971 |
| Physics+residual (Phase C.1c retuned) | **0.787** |
| Blended physics+residual ⊕ MA(2) (C.1d) | **0.549** |

Phase C closed a large fraction of the gap (0.971 → 0.549) via LORO-tuned
hyperparameters + inverse-variance blend with MA(2). The remaining ~0.08 s is
honest leftover: recent-pace features already dominated the residual, and pure
MA(2) remains a lower-variance mid/late-stint smoother than any blend that
still carries physics+residual noise.

**C.1 conclusion accepted as a documented limitation** → Block C.2 was reached.

---

## Block C.1a — Diagnosis (no code changes)

### Gain-based feature importances (`models/residual_xgb.json`, Phase B 123-race fit)

| Rank | Feature | Gain share |
|---:|---|---:|
| 1 | `lag1_pace` | 46.9% |
| 2 | `physics_pred` | 24.9% |
| 3 | `stint_roll3` | 22.3% |
| 4 | `compound_code` | 2.9% |
| 5 | `lag2_pace` | 1.6% |
| 6 | `fuel_kg` | 0.9% |
| 7 | `tyre_life` | 0.5% |

### Did a recent-pace feature exist?

**Yes.** `src/aris/models/features.py` already includes causal pace lags:

- `lag1_pace` — prior completed lap in-stint (`shift(1)`)
- `lag2_pace` — two laps back (`shift(2)`)
- `stint_roll3` — `shift(1).rolling(3, min_periods=1).mean()`

These are in the same spirit as MA(2). The “missing recent-pace” hypothesis is
**false**; pace features dominate gain (~71% for lag1 + roll3).

### Stint-position error breakdown (held-out)

| Bucket | MA(2) MAE | Physics+residual MAE |
|---|---:|---:|
| Early (first 2 scored in-stint) | n/a (MA needs 2 priors) | 1.15 s (n=415) |
| Later (pos ≥ 3) | 0.47 s | 0.98 s |
| Fine: stint pos 3 | **1.39 s** | **0.81 s** (residual wins cold-start) |
| Fine: stint pos 8+ | **0.44 s** | **1.04 s** (gap lives here) |

Residual error is **not** concentrated early. It is competitive at cold-start
and loses on mid/late stint where MA(2) is near-optimal.

**C.1c implication:** no new pace feature was added (item 6 gate); work focused
on hyperparameter tuning + blend.

---

## Block C.1b — Belgium `pit_loss_s` re-derivation

| | Value |
|---|---|
| Phase B (old) | **11.9 s** |
| Phase C (strict) | **14.6 s** |

**Method change** (`scripts/build_track_config.py` `derive_pit_loss_s(..., strict=True)` for Belgium):

- `TrackStatus == "1"` exactly (exclude mixed codes like `"12"`; Phase B used `startswith("1")`)
- Tyre-life window ±1 (was ±2)
- Same compound as the pit lap
- Fuel-state match via `LapNumber ± 5`
- Exclude traffic-affected clean refs (lap > driver-stint median + 1.0 s)
- Prefer same-driver free-air refs when ≥2 exist

Stored in `data/tracks/belgium.yaml` with `source.pit_loss_previous_s: 11.9`.
Corners unchanged. Note: clean-lap held-out MAE does not use pit_loss directly;
this corrects strategy sim / pit counterfactuals at Spa.

**Tests after C.1b:** green (115 passed at that checkpoint; suite grew later).

---

## Block C.1c — Targeted fixes

1. **No new pace feature** — already present (C.1a).
2. **LORO-CV hyperparameter search** (`scripts/tune_residual.py`):
   - Screen: 8 configs, LORO stride=5
   - Full LORO on top 2
   - **Selected by LORO-CV only:** `max_depth=6`, `eta=0.05`, `num_boost_round≤200`
   - Full LORO-CV MAE: **0.804 ± 0.994 s** (Phase B was 0.896 ± 1.107)
   - Held-out never used for selection
3. Fit-all → `models/residual_xgb.json` (Phase B backup: `residual_xgb.phaseB.json`)
4. Held-out logged as `c1c_physics_residual_mae_s`

**Overall held-out physics+residual: 0.971 → 0.787 s**

### Per-race after C.1c

| Race | n | MA(2) | B3 p+r | C.1c p+r |
|---|---:|---:|---:|---:|
| 2024 China | 716 | 0.400 | 1.213 | **0.574** |
| 2024 Monaco | 1148 | 0.634 | 0.814 | 0.874 |
| 2024 Spain | 1166 | 0.484 | 0.651 | 0.757 |
| 2024 Belgium | 711 | 0.444 | 1.550 | **1.350** |
| 2024 Abu Dhabi | 846 | 0.299 | 0.935 | **0.418** |
| **OVERALL** | **4587** | **0.469** | **0.971** | **0.787** |

(Monaco/Spain slightly worse vs B3; China/Belgium/Abu Dhabi and overall better.)

**Tests after C.1c:** green.

---

## Block C.1d — Precision-weighted blend with MA(2)

Implemented inverse-variance forecast combination:

- `src/aris/models/blend.py` — `inverse_variance_blend`, `rolling_error_variance`
- Thin wrappers in `predict.py` (`blend_physics_residual_with_ma2`, `predict_blended_frame`)
- Causal per-driver rolling error window (8 laps, min 3 obs); MA(2) from `(lag1+lag2)/2`
- Scope stayed within blend + thin predict wrapper + eval mode (no large restructure)

Held-out logged as `c1d_blended_mae_s`.

| Race | n | MA(2) | C.1c p+r | **C.1d blended** |
|---|---:|---:|---:|---:|
| 2024 China | 716 | 0.400 | 0.574 | **0.485** |
| 2024 Monaco | 1148 | 0.634 | 0.874 | **0.673** |
| 2024 Spain | 1166 | 0.484 | 0.757 | **0.576** |
| 2024 Belgium | 711 | 0.444 | 1.350 | **0.633** |
| 2024 Abu Dhabi | 846 | 0.299 | 0.418 | **0.329** |
| **OVERALL** | **4587** | **0.469** | **0.787** | **0.549** |

**Does the blend beat baseline?** No (0.549 vs 0.469). Best evidenced reason:
residual already had MA-like features and still injects residual/physics noise
on steady-stint laps; inverse-variance blending moves toward MA(2) when MA
errors are smaller, but cannot fully discard the noisier source without
becoming MA(2) itself.

**Tests after C.1d:** green.

---

## Full per-race MAE progression (Phase B → C)

Source: `results/heldout-laptime-mae.csv`.

### Overall

| Stage | MA(2) | Physics-only | Physics+residual | Blended |
|---|---:|---:|---:|---:|
| B1 | 0.469 | 24.107 | 1.735 | — |
| B2 | 0.469 | 15.211 | 14.535 | — |
| B3 | 0.469 | 15.211 | 0.971 | — |
| **C.1c** | 0.469 | 15.211 | **0.787** | — |
| **C.1d** | 0.469 | 15.211 | 0.787 | **0.549** |

### Per race (continuity columns)

| Race | n | MA(2) | B3 p+r | C.1c p+r | C.1d blend |
|---|---:|---:|---:|---:|---:|
| 2024 China | 716 | 0.400 | 1.213 | 0.574 | **0.485** |
| 2024 Monaco | 1148 | 0.634 | 0.814 | 0.874 | **0.673** |
| 2024 Spain | 1166 | 0.484 | 0.651 | 0.757 | **0.576** |
| 2024 Belgium | 711 | 0.444 | 1.550 | 1.350 | **0.633** |
| 2024 Abu Dhabi | 846 | 0.299 | 0.935 | 0.418 | **0.329** |
| **OVERALL** | **4587** | **0.469** | **0.971** | **0.787** | **0.549** |

---

## Block C.1e — README honesty

Updated `README.md` with side-by-side MA(2) / physics-only / physics+residual /
blended numbers, explicit “blend does not beat baseline,” and a short paragraph
that raw next-lap MAE is not the only ARIS metric (MA(2) has no
action-conditional capability; Phase D backtest will measure decisions).

---

## Block C.2 — Richer counterfactual actions (reached)

Because C.1 reached a real conclusion (gap not closed; documented limitation
accepted), C.2 proceeded:

| Item | Result |
|---|---|
| Lift / brake actions | `ActionKind.LIFT` / `BRAKE` in `simulate.py`; `approach_delta_s` in `bicycle.py` (extends corner-segment straights; no rebuild) |
| `docs/actions.md` | Full action vocabulary documented |
| Demo | `scripts/demo_lift_t7.py` → `results/lift-t7-demo.txt`: **lift 30 m into T7 → +0.181 s physics / +0.222 s race delta vs stay-out** (Bahrain) |
| Hardcoded DRS/defend | Removed from `recommend.py` (±0.15 / +0.05); replaced with simulated lift/brake candidates |

---

## Test suite

Docker Postgres up; `ARIS_DB_URL` set.

| Checkpoint | Result |
|---|---|
| After C.1b | **115 passed** |
| After C.1c | **119 passed** (blend unit tests added mid-stream) |
| After C.1d | **119 passed** |
| **End of Phase C (after C.2)** | **123 passed**, 0 failed, 0 skipped |

---

## Files created / modified (high level)

### Created
| File | Reason |
|---|---|
| `src/aris/models/blend.py` | Inverse-variance forecast combination |
| `scripts/tune_residual.py` | LORO-CV hyperparam search + refit |
| `scripts/demo_lift_t7.py` | Lift-T7 demo artefact |
| `docs/actions.md` | Action vocabulary |
| `docs/PHASE-C-SUMMARY.md` | This summary |
| `results/residual-tune-c1c.json` | Tune log |
| `results/lift-t7-demo.txt` | Demo output |
| `models/residual_xgb.phaseB.json` | Pre-tune backup |
| `tests/test_blend.py` | Blend unit tests |

### Modified
| File | Reason |
|---|---|
| `data/tracks/belgium.yaml` | pit_loss 11.9 → 14.6 |
| `scripts/build_track_config.py` | Strict pit-loss matcher |
| `src/aris/models/residual.py` | Tunable params, early stopping, `tune_hyperparams` |
| `src/aris/models/predict.py` | Blend wrappers |
| `src/aris/eval/laptime.py` | `blended` mode; c1c/c1d columns |
| `src/aris/physics/bicycle.py` | `approach_delta_s` / line actions |
| `src/aris/simulate.py` | LIFT / BRAKE |
| `src/aris/recommend.py` | Drop hardcoded tactical; add line candidates |
| `src/aris/montecarlo.py` | Labels for line actions |
| `README.md` | Honest Phase C numbers + MAE context |
| `results/heldout-laptime-mae.csv` | Extended columns |
| `tests/test_bicycle.py`, `tests/test_strategy.py` | Line-action coverage |

---

## Needs Anas's decision

1. **Accept 0.549 s blended vs 0.469 s MA(2) as the published ceiling for now?**
   Recommended: yes — further chasing raw MAE has diminishing returns relative to
   action-conditional eval (Phase D). Confirm before Phase D starts.

2. **Should the shipped default predictor be blended or physics+residual-only?**
   Blend wins on held-out point MAE; residual-only stays simpler for
   counterfactuals that change the physics path. Recommend: use residual (or
   residual+physics) inside `simulate()`, keep blend as the published
   point-forecast metric — or wire blend into live next-lap display only.

3. **Belgium physics-only still poor (26 s)** — pit_loss fix does not repair
   Spa corner geometry. Revisit survey radii, or leave residual to carry Spa?

4. **`docs/` gitignore** — still open from Phase A/B: should Phase summaries and
   `actions.md` be public on GitHub?

5. **Proposed tag (not cut)** — e.g. `v0.4-phase-c` representing: tuned residual,
   blend, Belgium pit_loss 14.6, lift/brake actions, honest 0.549 s blended MAE.
   Confirm name / whether to cut.

6. **Ambiguity flagged (not guessed):** traffic filter for Belgium used
   “stint median + 1.0 s” as a free-air proxy because FastF1 laps lack
   `IntervalToPositionAhead` in this cache. If you want a different traffic
   definition, re-derive pit_loss.

---

## Stop

Phase C is complete pending review of this summary. No Phase D (backtest
harness, RAG, live mode) or later work will start until you say so.
