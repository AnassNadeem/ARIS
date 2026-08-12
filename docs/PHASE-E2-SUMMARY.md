# Phase E.2 summary — Calendar-wide accuracy + pre-event rehearsal

Executed 2026-08-12. Scope: Blocks E2.1–E2.14 (calendar predictor accuracy,
then full pre-event rehearsal). No Phase F+ work started.

---

## Verdict (read this first)

**If the race started tonight, is this ready to demo?**

**Yes — for Zandvoort and for the calendar as a whole, with eyes open.**

The Phase D calendar-wide blended MAE of **1.605 s** is now **0.777 s**
(aimed: ≤ 1.5× overall MA(2) baseline = **0.823 s** — **PASS**). The root cause
was not “mysterious track geometry” alone: training frames still carried
Bahrain-era `physics_pred` (~113 s median) while eval used Phase D local YAML
geometry (shifts of −30 s to +15 s). Rebuilding every train-frame
`physics_pred` and re-fitting the residual closed most of the gap.

Zandvoort did not regress: 2024 blended **0.555 s** (E1b was 0.634; aimed ≤
1.5×0.427 = **0.640** — PASS). Sprint rehearsal, Strategy smoke, live-write
gating, SC caveat narration, and failure-mode drills all cleared.

Remaining honesty: most per-track tyre fits still fail SOFT>MEDIUM>HARD and
ship globals; track-evolution did not fix Zandvoort ordering; São Paulo
blended got worse; a handful of races miss the 1.5× baseline bar.

---

## Part 1 — Calendar-wide accuracy

### Block E2.1 — Regression diagnosis (read-only)

Target rule used throughout: classify error as **mostly_bias** if
`|mean|/MAE > 0.55`, else mostly variance / mixed.

| Race | Phase D blend | Bias vs var (blend) | Physics median vs actual | Ballpark vs real F1 | Train depth (2018–23) | Notes |
|---|---:|---|---:|---|---:|---|
| Japan | 3.681 | mostly_bias (+3.67) | 124.1 vs 97.4 | slow vs real; **+10.6 s vs train cache** | 4 | Systematic under-correction |
| Canada | 3.260 | mostly_bias (−2.57) | 95.6 vs 87.4 | closer physics; **−18.3 s vs train** | 4 | Residual overshoot; 2024 wet |
| Las Vegas | 3.441 | mostly_bias (+3.44) | 124.7 vs 98.4 | slow; **+11.0 vs train** | **1** (2023 only) | Low depth is real |
| Mexico City | 3.216 | mostly_bias (+3.20) | 103.7 vs 82.0 | slow; **−9.4 vs train** | 5 | Altitude unmodelled |
| Austria | 2.756 | mostly_bias (−2.75) | 83.1 vs 71.1 | closer; **−30.2 vs train** | 8 | Largest train/eval shift |
| Emilia Romagna | 2.871 | mostly_bias (+2.85) | 103.6 vs 82.0 | slow; **−10.0 vs train** | 3 | No 2023 race |
| United States | 2.283 | mostly_bias (+2.26) | 124.6 vs 100.1 | slow; **+11.1 vs train** | 5 (COTA) | |
| Azerbaijan | 2.115 | mostly_bias (+2.05) | 129.2 vs 108.9 | slow; **+15.3 vs train** | 5 | Street; low arc_frac 0.185 |
| Miami | 2.277 | mostly_bias (+2.27) | 119.0 vs 93.0 | slow; **+5.4 vs train** | **2** | Low depth |

Corner-radius audit: no mass `radius_m=70` default failures (Canada/Vegas 1
each). Street / high-speed geometries look imperfect but not “empty corners.”
**Main bug:** train/eval `physics_pred` distribution shift after Phase D YAMLs.

Monza (Italy) bonus: 11 corners, arc_frac 0.124 — expected high-speed shape;
not a top Phase D offender.

### Block E2.2 — Track-evolution hypothesis (Zandvoort)

Fuel-only (E1b restated): SOFT 0.0601 / MED 0.0563 / HARD 0.0765 — ordering
**FAIL**.

Fuel + track-evolution (fresh-flying LapNumber slope, between-stint): SOFT
−0.0444 / MED 0.0265 / HARD 0.0759 — ordering **FAIL**, worse.

Race-only evolution variants also failed. Evolution slopes often hit clip
bounds (±0.05 / −0.2) — estimator noisy.

**Hypothesis did NOT hold.** Cause of HARD>SOFT after fuel correction remains
**unknown**. No third speculative correction added. E2.3 uses **fuel-only**.

### Block E2.3 — Calendar-wide tyre fits

Method: fuel-corrected Race DegSlope + FP long runs; IV session pool; sanity =
SOFT>MEDIUM>HARD **and** each dry slope in (0, 0.25] (Bahrain first pass
SOFT=0.70 was ordered but absurd — magnitude gate added).

| Track | Fitted SOFT/MED/HARD | Sanity | Shipped |
|---|---|---|---|
| China | 0.1207 / 0.0827 / 0.016 | PASS | **fitted** |
| Japan | 0.0811 / 0.0361 / 0.0118 | PASS | **fitted** |
| Mexico | 0.0952 / 0.0509 / 0.0376 | PASS | **fitted** |
| All others (21) | (see YAML `compound_slopes_fitted_pre_sanity`) | FAIL | **global 0.08/0.05/0.03** |

Netherlands remains global fallback (same as E1b). Full audit JSON under
`results/e2_3_tire_slopes_*.json` and per-track CSVs in
`results/e2_3_deg_stints/`.

### Block E2.4 — Root causes fixed

1. **Train/eval physics mismatch** — fixed in E2.5 (rebuild all frames).
2. **Australia `pit_loss_s=9.0`** — multi-year strict median → **14.3 s**
   (years: 17.1 / 16.7 / 13.8 / 14.8 / 13.1 / 9.0; 2025 alone was soft).
3. **Las Vegas / Miami low training depth** — documented limitation, not
   fabricated data.
4. Corner fits: no concrete “wrong circuit” alias bug found beyond the known
   Phase D Sakhir-outer / Madrid items (unchanged).

### Block E2.5 — Residual retrain

`scripts/rebuild_train_physics.py`: recomputed `physics_pred`/`residual` on
all 123 cached train frames (no FastF1 refetch), then existing LORO-CV +
fit-all. Prior artefact backed up to `models/residual_xgb.pre_e2.json`.

LORO-CV MAE: **1.242 ± 2.269 s** (aimed: improve held-out calendar blend vs
Phase D — judged by E2.7, not CV alone).

### Block E2.6 — `weekend_form` deg_slope

Was Pearson correlation; now `np.polyfit` slope (s/lap of tyre life). Tests in
`tests/test_weekend_form_deg_slope.py`.

### Block E2.7 — Full 2024 held-out (aimed = 1.5× that race’s MA(2))

| Race | MA(2) | Phys | P+R | Blend | Aimed (1.5× MA2) | vs aimed | Phase D blend |
|---|---:|---:|---:|---:|---:|---|---:|
| Bahrain | 0.328 | 16.645 | 0.578 | **0.420** | 0.492 | PASS | 0.371 |
| Saudi Arabia | 0.489 | 20.555 | 0.560 | **0.521** | 0.734 | PASS | 0.478 |
| Australia | 0.486 | 24.734 | 1.305 | **0.909** | 0.729 | MISS | 1.657 |
| Japan | 0.685 | 26.534 | 0.855 | **0.723** | 1.028 | PASS | 3.681 |
| China | 0.400 | 10.005 | 1.548 | **0.933** | 0.600 | MISS | 0.485 |
| Miami | 0.413 | 26.205 | 0.682 | **0.524** | 0.620 | PASS | 2.277 |
| Emilia Romagna | 0.453 | 21.729 | 0.768 | **0.547** | 0.680 | PASS | 2.871 |
| Monaco | 0.634 | 13.578 | 1.009 | **0.732** | 0.951 | PASS | 0.673 |
| Canada | 1.271 | 8.801 | 2.416 | **1.291** | 1.907 | PASS | 3.260 |
| Spain | 0.484 | 11.176 | 1.472 | **0.913** | 0.726 | MISS | 0.576 |
| Austria | 0.379 | 12.061 | 0.769 | **0.531** | 0.569 | PASS | 2.756 |
| Britain | 1.347 | 18.505 | 1.213 | **1.269** | 2.020 | PASS | 1.248 |
| Hungary | 0.511 | 11.984 | 0.668 | **0.526** | 0.767 | PASS | 1.411 |
| Belgium | 0.444 | 26.065 | 1.353 | **0.780** | 0.666 | MISS | 0.633 |
| Netherlands | 0.427 | 18.363 | 0.687 | **0.555** | 0.640 | PASS | 0.634 |
| Italy | 0.469 | 16.868 | 1.620 | **1.009** | 0.704 | MISS | 0.816 |
| Azerbaijan | 0.528 | 20.245 | 0.602 | **0.487** | 0.792 | PASS | 2.115 |
| Singapore | 0.526 | 8.112 | 1.102 | **0.739** | 0.789 | PASS | 0.800 |
| United States | 0.394 | 24.662 | 1.112 | **0.729** | 0.591 | MISS | 2.283 |
| Mexico City | 0.386 | 22.008 | 0.467 | **0.400** | 0.578 | PASS | 3.216 |
| Sao Paulo | 1.114 | 3.555 | 5.531 | **3.121** | 1.671 | MISS | 2.092 |
| Las Vegas | 0.632 | 26.156 | 1.176 | **0.906** | 0.948 | PASS | 3.441 |
| Qatar | 0.352 | 18.672 | 0.535 | **0.389** | 0.528 | PASS | 0.610 |
| Abu Dhabi | 0.299 | 18.248 | 0.424 | **0.335** | 0.448 | PASS | 0.329 |
| **OVERALL** | **0.549** | **17.347** | **1.140** | **0.777** | **0.823** | **PASS** | **1.605** |

Calendar-wide: **1.605 → 0.777 s** blended. 17/24 races meet 1.5× baseline;
overall meets it.

---

## Part 2 — Pre-event rehearsal

### Block E2.8 — Zandvoort re-check (post Part 1)

| Race | Mode | E1b | E2 final | Aimed |
|---|---|---:|---:|---|
| 2024 NL | Blended | 0.634 | **0.555** | ≤ 0.640 (1.5×0.427) — PASS |
| 2025 NL | Blended | 0.673 | **0.679** | ≤ 0.626 (1.5×0.417) — slight MISS vs 1.5×; still sub-second |
| 2024 NL | Phys+res | 0.975 | **0.687** | — |
| 2025 NL | Phys+res | 0.996 | **1.055** | — |

No demo-breaking regression.

### Block E2.9 — Sprint rehearsal (2024 Austria)

Commands: `scripts/ingest_session.py 2024 Austria {FP1,SQ,S,Q,R}` then
`ingest_weekend.py 2024 Austria --sprint` (runbook pattern).

Aimed timing: comfortably inside a real inter-session gap (~30–90+ min). Using
**≤ 120 s session-end→ingest→UI-ready** as the rehearsal target for cached /
already-known data.

| Session | Ingest (s) | UI-ready probe (s) | Total (s) | Aimed | Result |
|---|---:|---:|---:|---|---|
| FP1 | 3.0 | 0.0 | 3.0 | ≤ 120 | PASS |
| SQ | 1.9 | 1.4 | 3.3 | ≤ 120 | PASS |
| Sprint | 4.3 | 1.3 | 5.6 | ≤ 120 | PASS |
| Q | 4.5 | 1.3 | 5.8 | ≤ 120 | PASS |
| Race | 2.2 | 1.3 | 3.5 | ≤ 120 | PASS |
| Full `--sprint` weekend | 4.0 | — | 4.0 | ≤ 300 | PASS |

**Runbook notes:** Austria 2024 works with the documented sprint session IDs
(`FP1/SQ/S/Q/R`). No instruction mismatch found for that path. Cold FastF1
(first-ever weekend) will be slower than these cached timings — expect
minutes, not seconds, on first load.

### Block E2.10 — 2025 Zandvoort Strategy smoke

`scripts/_e1_smoke_strategy_zandvoort.py`: **SMOKE OK**

- Windows A/B/C = 18 / 29 / 18+40; pit_loss 18.5; slopes globals
- Weekend form n=20; clock 287 ticks → lap 72
- Recommend: Pit now HARD / Pit lap 26 HARD / Stay out
- Postrace export written

### Block E2.11 — Live-write gating (actual behavior)

| Condition | Flags | Actual behavior |
|---|---|---|
| Outside event window (today 2026-08-12) | `--write` alone | **Writes** `netherlands.yaml` (verified this run) |
| Outside window | no `--write` | Log only |
| Inside window (2026-08-21…23) | `--write` alone | **REFUSED** (exit 2) — requires `--allow-live-write` |
| Inside window | `--write --allow-live-write` | Allowed (gate bypass) |

### Block E2.12 — SC/VSC caveat (real output)

HIT: **2024 Austria, RIC, lap 66, TrackStatus=71**

```
confidence_caveat=based on Safety Car-affected recent pace — lower confidence
recommend_evidence=lift 30m into T1 (+0.648s physics) | caveat: based on Safety Car-affected recent pace — lower confidence
narrate=RIC, recommend lift 30m into t1 at lap 66 — expected -0.8s vs staying out. Note: based on Safety Car-affected recent pace — lower confidence.
```

### Block E2.13 — Failure-mode drill

1. FastF1 `RateLimitExceededError` → raised immediately (0.00 s), no hang.
2. Nonsense session type CLI → `ValueError: session_type 'NOTASESSION' not one of [...]` in 1.1 s.
3. Empty/missing laps → ingest now **refuses** with a clear `RuntimeError`
   before writing DB state (`session.laps is None` / `0 laps`).

### Block E2.14 — Day-of checklist

Created: **`docs/zandvoort-day-of-checklist.md`**.

---

## Genuinely unresolved (investigated, still open)

1. **Zandvoort / most tracks: fuel-corrected DegSlope still fails
   SOFT>MEDIUM>HARD** even after track-evolution. Shipped globals; fitted
   values kept for audit only.
2. **Why HARD often looks steeper than SOFT** in pooled long-run fits —
   unknown after two confound corrections; not forced.
3. **São Paulo blended regression** (2.09 → 3.12) after physics rebuild —
   residual overshoots where physics is already close (phys MAE ~3.6 s).
4. **China / Spain / Belgium / Italy / US** miss 1.5× baseline despite overall
   PASS — residual/geometry still imperfect on those layouts.
5. **2020 Sakhir outer / Madrid 2026** — still held off (Phase D decisions).

---

## Test suite

Docker Postgres up; `ARIS_DB_URL` set.

| Checkpoint | Result |
|---|---|
| After E2.2 | green |
| After E2.3–E2.6 code | green |
| **End of Phase E.2** | **142 passed**, 0 failed (`results/e2_final_pytest.log`) |

New tests: `tests/test_deg_corrections.py`, `tests/test_weekend_form_deg_slope.py`;
track-override test updated for explicit global slopes on Bahrain.

---

## Files created / modified (high level)

### Created
| File | Reason |
|---|---|
| `docs/PHASE-E2-SUMMARY.md` | This summary |
| `docs/zandvoort-day-of-checklist.md` | Day-of printable checklist |
| `src/aris/physics/deg_corrections.py` | Fuel + track-evolution helpers |
| `scripts/fit_calendar_tire_slopes.py` | Calendar tyre fit + sanity |
| `scripts/rebuild_train_physics.py` | Offline physics_pred rebuild + retrain |
| `scripts/_e2_diagnose_regression.py` | E2.1 diagnosis |
| `scripts/_e2_australia_pit_loss.py` | Multi-year Australia pit_loss |
| `scripts/_e2_sc_caveat_demo.py` | SC caveat visual check |
| `scripts/_e2_failure_mode_drill.py` | Ingest failure drill |
| `tests/test_deg_corrections.py` | Unit tests |
| `tests/test_weekend_form_deg_slope.py` | Unit tests |

### Modified
| File | Reason |
|---|---|
| `data/tracks/*.yaml` | compound_slopes + Australia pit_loss 14.3 |
| `models/residual_xgb.json` | Retrained on rebuilt physics |
| `results/train_frames/*.parquet` | Rebuilt physics_pred |
| `results/heldout-laptime-mae.csv` | E2 columns |
| `scripts/fit_zandvoort_tire_slopes.py` | Evolution optional; fuel via shared helper |
| `scripts/train_residual_corpus.py` | `--rebuild-all` |
| `src/aris/physics/stint.py` | Harden polyfit against LinAlgError |
| `src/aris/plan/weekend_form.py` | Real DegSlope |
| `src/aris/io/ingest.py` | Loud fail on empty/missing laps |
| `tests/test_track_tire_overrides.py` | Allow explicit global slopes |

---

## Stop

Phase E.2 is complete pending review of this summary. **No Phase F (or later)
work will start until you say so.**
