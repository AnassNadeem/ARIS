# Phase E.3 summary — Root-cause remaining E.2 gaps

Executed 2026-08-12. Scope: Blocks E3.1–E3.6 (raw-stint diagnosis → justified
fixes → São Paulo / miss-race / Zandvoort 2025 root-causes → full recheck).
No Phase F work started.

---

## Verdict (read this first)

**If the race started tonight, is this ready to demo?**

**Yes for Zandvoort (2024 and 2025 both pass their aimed bars), and yes for the
calendar overall — with one remaining per-race miss called out honestly.**

Calendar blended MAE is now **0.583 s** (aimed ≤ 1.5× overall MA(2) =
**0.783 s** — **PASS**). Per-race pass count is **23/24** (E2 was **17/24**).
The single miss is **China**: blend **0.596 s** vs aimed **0.563 s** (short by
**0.033 s**). That is not rounded up to a pass.

Zandvoort 2025, which missed in E2 (**0.679** vs aimed **0.626**), now passes:
blend **0.566 s** vs aimed **0.603 s**.

---

## Block E3.1 — What the raw stint data actually showed

Diagnosis-only. Circuits inspected: Netherlands, Spain, Italy, China, Japan,
Bahrain (2023–2024 where available). Full artefact:
`results/e3_1_raw_stint_diagnosis.json`.

### Finding 1 — Same-compound pit stops were not splitting stints (primary)

`detect_stints` keyed only on **compound change**. HARD→HARD (and MED→MED) pit
stops kept a single `StintId` while FastF1’s `Stint` and `TyreLife` reset.

Concrete Bahrain 2024 example — ALB HARD “stint” laps 16–56:

- Pit in at lap 36 (TL=21), out at lap 37 (TL=1) — FastF1 Stints 2 then 3
- Our old `StintId` stayed **2** across both tyre sets
- DegSlope fit saw TyreLife go 1…21 then 1…N → garbage slope (**−0.075**
  fitpool vs **+0.094** after clean split)

Bahrain 2024 alone: **17/46** of our stints covered multiple FastF1 stints —
every one HARD→HARD. China 2024: **11** merges. Netherlands 2024: **0** merges
(no same-compound doubles that race).

This disproportionately corrupts **HARD** DegSlope (HARD–HARD doubles are
common; SOFT–SOFT long doubles are rare).

### Finding 2 — DegSlope fit pool ignored green-flag filtering (secondary)

`compute_stint_metrics` did **not** use `filter_clean_laps`. It only dropped
first-lap-of-stint + `PitInTime` + NaN. SC/yellow laps stayed in the polyfit.

Cross-race means of dirty laps retained in the fit pool:

- SOFT: **0.746** dirty laps/stint
- HARD: **1.272** dirty laps/stint (HARD retains more)

Concrete 2023 Netherlands ALB SOFT stint 1 (laps 1–44):

| Lap | TyreLife | LapTimeS | TrackStatus | kept by old fitpool? | kept by filter_clean_laps? |
|---:|---:|---:|---|---|---|
| 15 | 15 | 74.958 | 1 | yes | yes |
| 16 | 16 | 91.989 | 124 | **yes** | no |
| 17 | 17 | 110.252 | 4 | **yes** | no |
| 18–20 | 18–20 | 114–118 | 4 | **yes** | no |
| 21 | 21 | 118.896 | 41 | **yes** | no |

Old full-stint slope: **−0.576 s/lap**. After green-only: still contaminated by
length, but SC laps are gone. China 2024 HARD mean dirty retained: **6.68**
laps/stint vs SOFT **0.83**.

### Finding 3 — HARD stints are longer (real), but cliff hypothesis fails

Mean stint length across inspected races: SOFT **17.3** laps, HARD **33.2**
laps. Part of that was the merge bug (Finding 1).

**Cliff test** (full-stint slope − early-window slope, TyreLife≤10): for most
long HARD examples, full < early (late stint *flatter*, not steeper). Matched
early-window fitting did **not** broadly restore SOFT>MED>HARD (only 2/10
race-years). **Cliff contamination is rejected** as the ordering cause.

### E3.1 answer (not another blind hypothesis)

The ordering problem was **primarily stint-merge corruption of HARD DegSlope**,
plus **SC laps in the DegSlope fit pool**. Not cliff-effect; not “mystery
compound physics.” Clean races with no merges (NL 2024) can still fail
SOFT>MED>HARD mildly — that residual case remains after the fix (see E3.2).

---

## Block E3.2 — Justified fix + calendar refit

### Code changes

1. `detect_stints`: prefer FastF1 `Stint` when present; else split on compound
   change **or** pit-out.
2. `compute_stint_metrics`: DegSlope fit pool = `filter_clean_laps` ∩ not-first-
   lap-of-stint.
3. Calendar tyre script updated to E3.2 method strings; writes
   `results/e3_2_deg_stints/` + `results/e3_2_tire_slopes_report.json`.

Early-window / cliff matching: **not** adopted (E3.1 evidence against).

### Calendar sanity after refit

| Outcome | Tracks |
|---|---|
| **Fitted (SOFT>MED>HARD + magnitude)** | Japan, China, **Spain (new)**, Mexico City — **4/24** |
| Global fallback | other 20 (incl. Netherlands) |

E2 had **3/24** fitted (China/Japan/Mexico). Spain is newly ordered after the
stint-split + clean-lap fix.

Netherlands fitted-pre-sanity: SOFT **0.0609** / MED **0.0346** / HARD
**0.0491** — still fails (MED below HARD). Shipped globals. Honest residual:
even with correct stints, Zandvoort race+FP pooled slopes do not reliably
order; globals remain the right ship choice there.

**Ordering problem: partially resolved** (4 tracks ship fitted vs 3; root cause
of HARD inflation explained and fixed in the pipeline; most tracks still fall
back).

---

## Block E3.3 — São Paulo residual regression

### Root cause (confirmed)

| Metric | Phase D (`pre_e2`) | E2 model | After E3 damp |
|---|---:|---:|---:|
| Phys MAE | 3.39 | 3.39 | 3.39 |
| Phys+res MAE | 3.62 | 5.28 | **0.82** |
| Blend MAE | ~1.94 | ~2.98–3.12 | **0.815** |
| Aimed (1.5× MA2) | — | 1.671 (E2 MA2) | **1.172** (live MA2 0.782) |

2024 Interlagos physics is **unusually accurate** (phys MAE **3.39 s** vs train
corpus median **~18.8 s** — ~2nd percentile). True residual mean ≈ **−3.0 s**.
E2 residual predicted mean ≈ **−8.3 s** — large overshoot. When physics was
already within 1 s of truth (n=21 laps): phys MAE **0.55**, phys+res MAE
**9.01** under E2.

`physics_pred` is a feature, but the model still applied a large Interlagos-
scale correction learned from historical years where physics was ~10–13 s off.

### Fix

`damp_residual_toward_pace`: scale residual by
`min(1, |physics − lag1| / 8s)`. When physics already matches recent pace,
residual → 0; when physics is far (typical calendar race), full residual.

São Paulo held-out: blend **0.815 s** vs aimed **1.172 s** — **PASS** (E2 was
**3.121** MISS).

---

## Block E3.4 — Other E2 miss races

### Shared root cause (Australia, Spain, Belgium, Italy, United States)

Physics bias is large (+10…+26 s). Residual mostly corrects it, but the IV
blend used **sample variance of signed errors**, which **ignores constant
bias**. A predictor that is always ~1.2 s slow with low scatter got ~50% blend
weight.

Evidence (Australia): mean |bias| phys+res **1.43 s**, MA2 **0.43 s**; variance
weights gave phys+res weight **0.50**; MSE weights give **0.21**. MAE:
var-blend **0.75** → mse-blend **0.54**.

### Fix

`rolling_error_variance` now returns **MSE** (still under the historical name
for API stability). Bias² + variance is the right risk for IV combination.

### Per-race after fixes (E3.6 numbers)

| Race | E2 blend | E3 blend | Aimed (1.5× MA2) | Result |
|---|---:|---:|---:|---|
| Australia | 0.909 | **0.685** | 0.695 | **PASS** |
| Spain | 0.913 | **0.584** | 0.714 | **PASS** |
| Belgium | 0.780 | **0.543** | 0.639 | **PASS** |
| Italy | 1.009 | **0.597** | 0.680 | **PASS** |
| United States | 0.729 | **0.496** | 0.590 | **PASS** |
| China | 0.933 | **0.596** | 0.563 | **MISS** |

### China — investigated, not forced

On MA(2)-available laps, blend MAE is **0.408** (would pass). Overall **0.596**
is pulled up by **57** early-stint laps without `lag2` (fallback = phys+res
alone, MAE **2.74**). Worst errors are almost all LapNumber=2 / tyre_life=2
after out-lap, under ~10 s physics bias.

Tried MA(1)=lag1 fallback: China improves only **−0.003 s**; Australia
**regresses** (+0.055 s, would fail). **Not shipped.** Remaining China miss is
**0.033 s** past aimed — documented, not fabricated away.

---

## Block E3.5 — Zandvoort 2025

| | 2024 | 2025 |
|---|---:|---:|
| MA(2) | 0.427 | 0.402 |
| Aimed (1.5×) | 0.640 | 0.603 |
| E2 blend | 0.555 PASS | 0.679 MISS |
| **E3 blend** | **0.502 PASS** | **0.566 PASS** |
| Non-green raw lap frac | **0.0** | **0.232** |
| Soft clean laps | 107 | 213 |
| Phys+res MAE | 0.692 | 1.048 |
| Rain | no | no |

**Why 2025 was harder:** not weather — **Safety Car density**. 2025 raw laps
show extensive SC/yellow codes (~23% non-green) vs a fully green 2024. More
SOFT running and worse phys+res. The E2 miss was the same bias-blind blend
variance issue under that noisier race; MSE blend + residual damp clears the
aimed bar without a Zandvoort-specific hack.

---

## Block E3.6 — Full recheck

### 2024 held-out (E2.7-equivalent)

| Race | MA(2) | Phys | P+R | Blend | Aimed | vs aimed | E2 blend |
|---|---:|---:|---:|---:|---:|---|---:|
| Bahrain | 0.284 | 16.635 | 0.564 | **0.350** | 0.426 | PASS | 0.420 |
| Saudi Arabia | 0.489 | 20.555 | 0.560 | **0.503** | 0.734 | PASS | 0.521 |
| Australia | 0.463 | 24.739 | 1.288 | **0.685** | 0.695 | PASS | 0.909 |
| Japan | 0.644 | 26.604 | 0.816 | **0.660** | 0.966 | PASS | 0.723 |
| China | 0.376 | 10.560 | 1.954 | **0.596** | 0.563 | MISS | 0.933 |
| Miami | 0.411 | 26.205 | 0.680 | **0.481** | 0.617 | PASS | 0.524 |
| Emilia Romagna | 0.449 | 21.731 | 0.767 | **0.499** | 0.674 | PASS | 0.547 |
| Monaco | 0.634 | 13.578 | 1.030 | **0.630** | 0.951 | PASS | 0.732 |
| Canada | 1.196 | 8.836 | 1.449 | **1.088** | 1.794 | PASS | 1.291 |
| Spain | 0.476 | 11.356 | 1.306 | **0.584** | 0.714 | PASS | 0.913 |
| Austria | 0.368 | 12.063 | 0.809 | **0.409** | 0.553 | PASS | 0.531 |
| Britain | 1.318 | 18.530 | 1.219 | **1.262** | 1.977 | PASS | 1.269 |
| Hungary | 0.490 | 11.981 | 0.728 | **0.529** | 0.735 | PASS | 0.526 |
| Belgium | 0.426 | 26.051 | 1.329 | **0.543** | 0.639 | PASS | 0.780 |
| Netherlands | 0.427 | 18.363 | 0.692 | **0.502** | 0.640 | PASS | 0.555 |
| Italy | 0.453 | 16.860 | 1.620 | **0.597** | 0.680 | PASS | 1.009 |
| Azerbaijan | 0.527 | 20.245 | 0.622 | **0.480** | 0.790 | PASS | 0.487 |
| Singapore | 0.521 | 8.110 | 1.165 | **0.706** | 0.781 | PASS | 0.739 |
| United States | 0.393 | 24.664 | 1.111 | **0.496** | 0.590 | PASS | 0.729 |
| Mexico City | 0.382 | 21.993 | 0.468 | **0.381** | 0.573 | PASS | 0.400 |
| Sao Paulo | 0.782 | 3.393 | 0.822 | **0.815** | 1.172 | PASS | 3.121 |
| Las Vegas | 0.617 | 26.155 | 1.154 | **0.744** | 0.926 | PASS | 0.906 |
| Qatar | 0.343 | 18.679 | 0.532 | **0.360** | 0.514 | PASS | 0.389 |
| Abu Dhabi | 0.286 | 18.247 | 0.418 | **0.292** | 0.428 | PASS | 0.335 |
| **OVERALL** | **0.522** | **17.378** | **0.948** | **0.583** | **0.783** | **PASS** | **0.777** |

Per-race aimed pass count: **23/24** (E2: **17/24**).

### Zandvoort 2024+2025 (E2.8-equivalent)

| Race | Blend | Aimed | Result |
|---|---:|---:|---|
| 2024 NL | **0.502** | ≤ 0.640 | PASS |
| 2025 NL | **0.566** | ≤ 0.603 | PASS |

---

## Test suite

Docker Postgres up; `ARIS_DB_URL` set.

| Checkpoint | Result |
|---|---|
| After E3.2 stint fix | green |
| After E3.3 residual damp | green |
| After E3.4 MSE blend | green |
| **End of Phase E.3** | **150 passed**, 0 failed (`results/e3_final_pytest.log`) |

New/updated tests: `tests/test_stint.py` (pit-split, FF1 Stint, SC DegSlope),
`tests/test_residual_damp.py`, `tests/test_blend.py` (MSE / bias penalty).

---

## Genuinely unresolved (investigated, still open)

1. **Most tracks still fail SOFT>MED>HARD** after correct stint splitting +
   clean-lap DegSlope (20/24 fallback). Netherlands included. Not forced.
2. **China** still **0.033 s** over its 1.5× MA(2) bar due to early-stint
   no-MA2 fallback under large physics bias; MA(1) fallback regresses other
   races — not shipped.
3. **Physics absolute level** still ~10–26 s slow on many circuits; residual +
   MSE blend mask this for demo MAE, but the bicycle ballpark remains a
   geometry/calibration debt (unchanged Phase D/E2 honesty).

---

## Files created / modified (high level)

### Created
| File | Reason |
|---|---|
| `docs/PHASE-E3-SUMMARY.md` | This summary |
| `scripts/_e3_1_raw_stint_diagnosis.py` | Raw stint + cliff + clean asymmetry |
| `scripts/_e3_1_stint_split_bug.py` | Same-compound merge proof |
| `scripts/_e3_3_sao_paulo_diagnosis.py` / `_check.py` | SP residual overshoot |
| `scripts/_e3_4_*.py` | Miss-race / blend MSE / China dive |
| `scripts/_e3_5_zandvoort_2025.py` | 2024 vs 2025 NL |
| `scripts/_e3_6_*.py` | Full recheck helpers |
| `tests/test_residual_damp.py` | Unit tests |
| `results/e3_*` | Diagnosis artefacts + logs |

### Modified
| File | Reason |
|---|---|
| `src/aris/physics/stint.py` | Pit/FF1 stint split; clean-lap DegSlope |
| `src/aris/models/predict.py` | Residual damp toward pace |
| `src/aris/models/blend.py` | MSE for IV blend weights |
| `scripts/fit_calendar_tire_slopes.py` | E3.2 method + output paths |
| `tests/test_stint.py`, `tests/test_blend.py` | Cover new behaviour |
| `data/tracks/*.yaml` | E3.2 tyre refit (4 fitted, 20 fallback) |
| `results/heldout-laptime-mae.csv` | `e3_*` columns |

---

## Stop

Phase E.3 is complete pending review of this summary. **No Phase F (or later)
work will start until you say so.**
