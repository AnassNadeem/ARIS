# Phase B summary — Prove the predictor is real

Executed 2026-08-10. Scope was **only** the Phase B checklist (Blocks 1–4;
Block 5 not reached). No Phase C+ work started.

---

## Verdict (read this first)

**Physics+residual does not beat the MA(2) baseline on clean held-out data.**

| Metric (held-out overall) | MAE (s) |
|---|---|
| MA(2) baseline | **0.469** |
| Physics-only (after track configs) | 15.211 |
| Physics+residual (after track configs + 2018–2023 refit) | **0.971** |

Residual training on the expanded corpus helped a lot versus Phase A (1.735 →
0.971), and residual is strongly net-positive versus physics-only after the
refit. It still loses to a per-stint moving average of recent pace by ~0.5 s.

**Best evidenced explanation:** the bicycle model (no downforce) is still a
large, track-dependent bias (~10–26 s physics-only MAE even with per-track
geometry). The XGBoost residual, given lag features + `physics_pred`, learns
to cancel most of that bias and track recent pace — but MA(2) *is* recent
pace, with less model risk. On held-out 2024 races the residual cannot beat
that floor. Undermodelled tyre/compound effects and remaining geometry error
(especially Belgium, where derived Spa corners made physics-only *worse*
than Bahrain fallback) are secondary contributors.

---

## Per-race MAE progression (Blocks 1 → 2 → 3)

Source: `results/heldout-laptime-mae.csv`. All on the same five 2024 held-out
races (China, Monaco, Spain, Belgium, Abu Dhabi), disjoint from training.

### Overall

| Stage | Baseline MA(2) | Physics-only | Physics+residual |
|---|---:|---:|---:|
| **B1** (as shipped / Bahrain physics everywhere) | 0.469 | 24.107 | **1.735** |
| **B2** (per-track YAML wired in; old 8-race residual) | 0.469 | **15.211** | 14.535 |
| **B3** (same tracks; residual refit on 2018–2023 corpus) | 0.469 | 15.211 | **0.971** |

### Per race

| Race | n | MA(2) | B1 phys | B1 p+r | B2 phys | B2 p+r | B3 phys | B3 p+r |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024 China | 716 | 0.400 | 12.124 | 1.567 | 10.031 | 4.166 | 10.031 | **1.213** |
| 2024 Monaco | 1148 | 0.634 | 34.509 | 3.148 | 13.578 | 18.001 | 13.578 | **0.814** |
| 2024 Spain | 1166 | 0.484 | 32.952 | 1.147 | 11.176 | 20.341 | 11.176 | **0.651** |
| 2024 Belgium | 711 | 0.444 | 4.820 | 1.792 | 26.065 | 20.901 | 26.065 | **1.550** |
| 2024 Abu Dhabi | 846 | 0.299 | 24.150 | 0.720 | 18.248 | 5.257 | 18.248 | **0.935** |
| **OVERALL** | **4587** | **0.469** | **24.107** | **1.735** | **15.211** | **14.535** | **15.211** | **0.971** |

Baseline `n` differs slightly (4379) because MA(2) needs two prior laps in-stint.

### Residual net effect after track fix (Block 2 vs Block 3)

- **Block 2 (old residual, new physics):** residual is **net-negative**
  (physics-only 15.211 → physics+residual 14.535 overall is a tiny gain, but
  Monaco/Spain/Belgium get *much* worse — the booster was trained against
  Bahrain `physics_pred` and misfires when geometry changes).
- **Block 3 (refit):** residual is **strongly net-positive**
  (15.211 → 0.971). Expanding + refitting was required for the track-config
  fix to help the full stack.

---

## Track configs (Block 2)

**Block 1 factual check:** all five held-out races lacked YAML under
`data/tracks/` and `load_track_config` fell back to Bahrain defaults
(57 laps, 21.0 s pit, `bahrain_2024` geometry). Also, `features.py` always
called `bahrain_2024()` for `physics_pred` — so MAE was Bahrain-geometry
everywhere regardless of strategy YAML.

**Built** (via `scripts/build_track_config.py`, same fields as `bahrain.yaml`
plus corners/`lap_length_m` so the bicycle model can use them):

| Track | File | total_laps | pit_loss_s | corners | lap_length_m | Corner source |
|---|---|---:|---:|---:|---:|---|
| China | `data/tracks/china.yaml` | 56 | 17.1 | 16 | 5367.3 | `get_circuit_info()` + fastest-lap telemetry circle fit |
| Monaco | `data/tracks/monaco.yaml` | 78 | 23.0 | 19 | 3282.4 | same |
| Spain | `data/tracks/spain.yaml` | 66 | 17.2 | 14 | 4618.9 | same |
| Belgium | `data/tracks/belgium.yaml` | 44 | 11.9 | 19 | 6944.1 | same |
| Abu Dhabi | `data/tracks/abu_dhabi.yaml` | 58 | 21.4 | 16 | 5250.7 | same |

- **Lap count:** `session.total_laps` (not hardcoded).
- **Pit loss:** median of (pit in/out lap − clean lap at similar tyre life),
  clipped to (5, 45) s; Belgium’s 11.9 s looks low vs typical Spa figures —
  flagged under decisions.
- **Wiring:** `TrackConfig.load_physics()` prefers YAML corners;
  `build_from_fastf1` resolves track by GP/event/country and passes it into
  `physics_pred` / fuel total-laps.

`bahrain.yaml` left unchanged (still `physics_profile: bahrain_2024`).

---

## REFERENCE_RACES expansion (Block 3)

| | |
|---|---|
| Before | 8 races (mixed 2023/2024) |
| After | Full 2018–2023 schedule = **125** named races in `REFERENCE_RACES` |
| Loaded for fit | **123** races / **105 966** laps (`results/train_frames/*.parquet`) |
| Failed to load | **2018 Italian** (timing data incomplete in cache/API); **2021 Belgian** (empty clean-lap frame — rain-shortened Spa) |
| Procedure | Unchanged: leave-one-race-out CV, then fit-all → `models/residual_xgb.json` |
| LORO-CV | **0.896 ± 1.107 s** |

**Did expanding help?** Yes, substantially on held-out physics+residual:
**1.735 s (B1) → 0.971 s (B3)** after track configs + refit. That is evidence
the original 8-race set was undersized *for generalization once physics_pred
is track-correct*. (B2 alone made residual worse; data scale without refit
would not have been enough.)

---

## README

Updated with side-by-side held-out numbers (MA(2) / physics-only /
physics+residual), held-out race list, one-sentence methodology, and an
explicit statement that physics+residual does **not** beat baseline.

---

## Test suite

Docker Postgres up; `ARIS_DB_URL` set.

| Checkpoint | Result |
|---|---|
| After Block 1 | **115 passed**, 0 failed, 0 skipped |
| After Block 2 | **115 passed**, 0 failed, 0 skipped |
| After Block 3 | **115 passed**, 0 failed, 0 skipped |

---

## Block 5

**Not reached.** Time went into FastF1 rate-limit handling and the 123-race
refit. Precision-weighted tyre prior/FP2 blending in `tires.py` /
`weekend_form.py` is deferred — see decisions below.

---

## Files created / modified (high level)

### Created
| File | Reason |
|---|---|
| `data/tracks/{china,monaco,spain,belgium,abu_dhabi}.yaml` | Held-out track configs |
| `scripts/build_track_config.py` | Derive laps / pit loss / corners from FastF1 |
| `scripts/train_residual_corpus.py` | Checkpointed corpus build + LORO refit |
| `docs/PHASE-B-SUMMARY.md` | This summary |
| `results/train_frames/*.parquet` | Local training checkpoints (gitignored) |
| `models/residual_xgb.phaseA.json` | Backup of pre-Block-3 booster |

### Modified
| File | Reason |
|---|---|
| `src/aris/eval/laptime.py` | Multi-mode eval; extend CSV across B1/B2/B3 |
| `src/aris/tracks.py` | YAML corners; clearer matching |
| `src/aris/models/features.py` | Track-aware `physics_pred` + fuel laps |
| `src/aris/models/predict.py` | Prefer frame `physics_pred` when scoring |
| `src/aris/models/residual.py` | `REFERENCE_RACES` → 2018–2023; rate-limit-aware loader |
| `README.md` | Honest side-by-side MAE |
| `results/heldout-laptime-mae.csv` | Progression columns |
| `models/residual_xgb.json` | Refit artefact |

---

## Needs Anas's decision

1. **Belgium pit_loss_s = 11.9** — empirical under the stated method, but low
   versus typical Spa pit-loss intuition (~18–20 s). Re-derive with a stricter
   clean-lap matcher, or accept and document?

2. **Belgium physics-only regression** — derived Spa corners made physics-only
   MAE worse (4.8 → 26.1 s). Residual still recovers to 1.55 s. Revisit Spa
   corner fit (or survey-based radii) before trusting physics-only there?

3. **Two missing training races** — 2018 Italian (load failure) and 2021
   Belgian (empty after clean-lap filter). Worth a manual cache repair, or
   leave as known holes in the 125-race list?

4. **Block 5 tyre blending** — implement precision-weighted
   prior/observation slopes next, or park until predictor beats MA(2)?

5. **`docs/` gitignore** — same Phase A open question: whether
   `PHASE-B-SUMMARY.md` / track notes should be public on GitHub.

6. **Proposed tag (not cut)** — e.g. `v0.3-phase-b-predictor` representing:
   track YAMLs, corpus residual, honest 0.971 s held-out MAE (does not beat
   MA(2)). Confirm name / whether to cut.

---

## Stop

Phase B is complete pending review of this summary. No Phase C (or later)
work will start until you say so.
