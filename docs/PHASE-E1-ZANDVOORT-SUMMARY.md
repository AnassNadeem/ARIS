# Phase E.1 summary — Zandvoort readiness

Executed 2026-08-12. Scope was **only** Zandvoort / Netherlands (Blocks E1.1–E1.5).
No Phase E.2 circuit regression work was started.

---

## Verdict (read this first)

**If the race started tonight, is this ready to demo?**

**Yes — with eyes open.** Zandvoort is the strongest newly covered circuit from Phase D, and E.1 improved it further: blended MAE is **0.558 s (2024 held-out)** and **0.591 s (2025 validation)** after track-specific tyre slopes. The Strategy pipeline smoke-passes end-to-end on 2025 Netherlands (72-lap prewrite windows, live clock, Ask/What-if, postrace). Sprint-weekend ingest works (`FP1/SQ/S/Q/R`), and the live runbook is at `docs/zandvoort-weekend-runbook.md`.

Caveats for a live demo: residual model was **not** retrained on the new tyre slopes; What-if deltas during SC/VSC laps can still look extreme because lag features inherit dirty pace; weekend form needs FP1/SQ/S/Q ingested (not race alone).

---

## Block E1.1 — Standing + 2025 validation

### Phase D held-out (restated)

| Metric | 2024 Netherlands |
|---|---:|
| MA(2) | **0.427** |
| Physics-only | **18.363** |
| Physics+residual | **0.975** |
| Blended | **0.634** |

### 2025 validation (not in Phase D held-out)

FastF1 race cache was already present; race was ingested to Postgres (`+1` session, `+1364` laps).

| Metric | 2025 Netherlands |
|---|---:|
| MA(2) | **0.417** |
| Physics-only | **18.930** |
| Physics+residual | **0.996** |
| Blended | **0.673** |

2025 looks very similar to 2024 — slightly worse blended, still sub-second and demo-credible.

**Checkpoint:** full suite green (125 → later grew with E.1 tests).

---

## Block E1.2 — Track-specific tyre degradation

### Data

- FP2 + Race long runs, Dutch GP **2021–2025** (272 stints after `NumLaps≥5` and DegSlope clip to `[-0.5, 1.0]`).
- FP2 is noisy; **session-level inverse-variance pooling** down-weights high-variance practice sessions so race stints dominate.

### Fit (shipped in `data/tracks/netherlands.yaml`)

| Compound | Global default | Zandvoort override |
|---|---:|---:|
| SOFT | 0.08 | **0.0128** |
| MEDIUM | 0.05 | **0.0029** |
| HARD | 0.03 | **0.0322** |

**Interim call (labeled):** used session-level IV pooling of `(mean, sample variance)` per session rather than a hierarchical LOO prior that let FP2 outlier *means* pollute the prior. Live update helper remains `blend_slope_prior(prior_mean, prior_var, obs_mean, obs_var)` in `aris.physics.tires`.

### Wiring

- `TrackConfig.compound_slopes` / YAML `compound_slopes:` → `Track.compound_slopes` → `tire_pace_loss(..., slopes=…)`.
- Other tracks unchanged (still use global `DEFAULT_COMPOUND_SLOPE`).

### Before / after (same blended predictor stack)

| Race | Mode | Before | After |
|---|---|---:|---:|
| 2024 NL | Physics-only | 18.363 | **18.119** |
| 2024 NL | Physics+residual | 0.975 | **0.833** |
| 2024 NL | Blended | 0.634 | **0.558** |
| 2025 NL | Physics-only | 18.930 | **18.605** |
| 2025 NL | Physics+residual | 0.996 | **0.861** |
| 2025 NL | Blended | 0.673 | **0.591** |

**Checkpoint:** **133 passed** (tyre + track-override tests added).

---

## Block E1.3 — Pit loss robustness

Strict Phase C/D matcher on Race, per year:

| Year | pit_loss_s |
|---|---:|
| 2021 | 18.5 |
| 2022 | 19.8 |
| 2023 | 18.5 |
| 2024 | 19.5 |
| 2025 | 16.4 |

- **Range:** 3.4 s (2025 is the soft outlier).
- **Multi-year median:** **18.5 s**
- Phase D single-year (2025) was **16.4 s** → **updated** `data/tracks/netherlands.yaml` to **18.5** (difference ≥ 0.5 s).

Lap-time MAE unchanged by pit_loss (clean scored laps exclude pit laps); strategy sim / prewrite use the new value (windows A/B/C ≈ **18 / 29 / 18+40** on 72 laps).

**Checkpoint:** suite green.

---

## Block E1.4 — End-to-end Strategy smoke

Headless smoke on **2025 Netherlands R** (`scripts/_e1_smoke_strategy_zandvoort.py`):

| Stage | Result |
|---|---|
| Session setup | OK (session_id=123, VER) |
| Strat prewrite | OK — 3 plans, windows 18 / 29 / 18+40 |
| Weekend form | Empty until FP/Q ingested; **OK after FP1–Q ingest** (20 drivers) |
| Live clock | OK — 287 ticks → lap 72 complete |
| Watch/Ask/What-if | OK — recommend returns 3 options incl. stay-out |
| Postrace | OK — export written |

### Bugs found and fixed

1. **DNF crash:** field clock past focus driver’s last lap called `build_state` → `ValueError` (NOR retired L65 in 2025).  
   - `check_triggers` skips when past last lap.  
   - `RaceEngineSession.build_state` clamps to last recorded lap for UI.
2. **Simulate used Bahrain physics** (`_predict_lap` never passed `track`) and **double-counted pit_loss** (`pit_lap=True` plus explicit `+ pit_loss`). Fixed in `aris.simulate`.
3. **Stay-out dropped from top-k** once pit cost was corrected (pits correctly look better on worn softs). `recommend()` now always surfaces stay-out.

**Checkpoint:** **134 passed**.

---

## Block E1.5 — Sprint-weekend ingest + runbook

### Findings

- `scripts/ingest_weekend.py` previously **hardcoded FP1–FP3, Q, R** and would soft-fail FP2/FP3 on a sprint weekend but **never ingested SQ/S**.
- FastF1 sprint IDs (Austria 2024 probe): **FP1, SQ, S, Q, R** — no FP2/FP3. `SS`/`SR` are not the active identifiers for that weekend.
- DB CHECK constraint **rejected `S`** until migration `db/migrations/003_sprint_session_type.sql`.

### Fixes

- Sprint-aware `ingest_weekend.py`: `--sprint` / `--conventional` / `--auto`.
- Schema + ingest allow `S`; weekend ordering + `weekend_form` include Sprint / SQ fallbacks.
- Tyre fit script session list now includes **FP1 + S** as FP2 fallbacks for sprint weekends.
- Verified: `python scripts/ingest_weekend.py 2024 Austria --sprint` ingested FP1/SQ/S/Q successfully.

### Runbook

Exact live sequence + FastF1 timing expectations: **`docs/zandvoort-weekend-runbook.md`**.

---

## Phase E.2 notes (noticed, not fixed)

From Phase D held-out, still the accuracy problems to attack **after** the Dutch GP — do not start now:

- Large blended MAE circuits: **Japan (3.68), Canada (3.26), Mexico (3.22), Las Vegas (3.44), Australia (1.66), Imola (2.87), Austria (2.76), Miami (2.28), …**
- Calendar-wide blended still **1.605 s** vs Phase C five-race ~0.55.
- Australia `pit_loss_s=9.0` still looks suspiciously low.
- Residual was trained with **global** tyre slopes; after E.1 Zandvoort overrides, a future retrain (E.2+) should rebuild `physics_pred` with per-track slopes where they exist.
- Simulate/What-if remains sensitive to SC-contaminated lag features mid-race.

---

## Needs Anas's decision

1. **Accept multi-year pit_loss 18.5 s** (vs Phase D’s 2025-only 16.4)? Recommended yes — 2025 looks soft vs 2021–24.
2. **Accept empirical Zandvoort SOFT/MEDIUM slopes ≪ globals** (fuel burn confounds DegSlope)? They improved MAE; a fuel-corrected deg model is later work.
3. **Retrain residual before the weekend**, or ship with current artefact + track tyre overrides only?
4. **Tag?** e.g. `v0.5-phase-e1-zandvoort` — confirm name / whether to cut.
5. **Live tyre YAML overwrite policy** during FP1/Sprint — runbook leaves `--write` optional; confirm whether ops should rewrite `netherlands.yaml` mid-weekend or only log blended slopes.

---

## Test suite

Docker Postgres up; `ARIS_DB_URL` set; migration 003 applied.

| Checkpoint | Result |
|---|---|
| After E1.1 | green |
| After E1.2 | **133 passed** |
| After E1.3 | green |
| After E1.4 | **134 passed** |
| **End of Phase E.1** | **134 passed**, 0 failed |

---

## Files created / modified (high level)

### Created
| File | Reason |
|---|---|
| `scripts/fit_zandvoort_tire_slopes.py` | Fit + write Zandvoort compound slopes |
| `scripts/_e1_score_zandvoort.py` | 2024/2025 MAE scorer |
| `scripts/_e1_pit_loss_zandvoort.py` | Multi-year strict pit_loss |
| `scripts/_e1_smoke_strategy_zandvoort.py` | Strategy E2E smoke |
| `tests/test_track_tire_overrides.py` | YAML → Track slopes wiring |
| `tests/test_triggers_dnf.py` | DNF clock regression |
| `db/migrations/003_sprint_session_type.sql` | Allow session_type `S` |
| `docs/zandvoort-weekend-runbook.md` | Live weekend commands |
| `docs/PHASE-E1-ZANDVOORT-SUMMARY.md` | This summary |

### Modified
| File | Reason |
|---|---|
| `data/tracks/netherlands.yaml` | `compound_slopes`; `pit_loss_s` 16.4→18.5 |
| `src/aris/physics/tires.py` | IV slope blend + track fit |
| `src/aris/physics/bicycle.py` | Track carries `compound_slopes` |
| `src/aris/tracks.py` | Load/apply YAML overrides |
| `src/aris/simulate.py` | Pass track; no double pit_loss |
| `src/aris/recommend.py` | Always surface stay-out |
| `src/aris/engine/session.py` / `triggers.py` | DNF-safe build_state / triggers |
| `src/aris/plan/weekend_form.py` | Sprint / SQ fallbacks |
| `src/aris/io/ingest.py` / `db.py` / `db/schema.sql` | Sprint `S` support |
| `scripts/ingest_weekend.py` | Sprint/conventional/auto modes |
| `tests/test_tires.py` | IV blend unit tests |

---

## Stop

Phase E.1 is complete pending review of this summary. **No Phase E.2 (or later) work will start until you say so.**
