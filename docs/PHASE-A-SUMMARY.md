# Phase A summary — Stabilize & de-risk

Executed 2026-08-10. Scope was **only** the Phase A checklist. No Phase B+ work started.

---

## Files created / renamed / deleted

### Created
| File | Reason |
|---|---|
| `docs/data-sources.md` | Document every field ARIS uses from FastF1 vs model-derived (`ingest.py` + `features.py`) |
| `docs/decision-schema.md` | Document `DecisionRecord` as implemented today (no audit-trail redesign) |
| `docs/PHASE-A-SUMMARY.md` | This review summary |
| `results/heldout-laptime-mae.csv` | Recorded disjoint held-out MAE from Block 3 |

### Renamed
| From | To | Reason |
|---|---|---|
| `src/aris/ask/rag.py` | `src/aris/ask/keyword_qa.py` | Keyword/rule Q&A, not retrieval RAG |
| `src/aris/eval/conformal.py` | `src/aris/eval/mc_intervals.py` | MC p10/p90 bands, not split-conformal; real mapie conformal deferred |

Functions renamed with the conformal module: `conformal_interval` → `mc_percentile_interval`, `calibrated_delta_interval` → `mc_delta_interval`. Import sites updated (`apps/components/aris_chat.py`, `apps/pages/01_Strategy.py`).

### Deleted
| Path | Reason |
|---|---|
| `dashboard/` (entire tree) | Parallel FastF1 UI; `apps/` is canonical; nothing outside imported it |
| `.today-backup/` | Untracked duplicate of package/UI code; unused |
| `scripts/nb_dump_cell.py` | Orphan notebook helper; unused by notebooks/CI |
| `scripts/nb_dump_outputs.py` | Same |
| `scripts/nb_show_errors.py` | Same |
| `scripts/nb_show_mojibake.py` | Same |
| `scripts/fix_wk2_notebooks.py` | Same |
| `scripts/refactor_wk2_notebooks.py` | Same |
| `scripts/wk2_day3_block2.py` | Same |
| `scripts/wk2_day3_block5.py` | Same |

### Modified (logic / docs / infra)
| File | Reason |
|---|---|
| `README.md` | F1 unofficial disclaimer; status/roadmap reconciled with repo; honest MAE + MC wording |
| `BUILD-LOG.md` | Backfilled Jun–Aug gap from git history; explicit backfill note |
| `src/aris/io/ingest.py` | Weather/results upsert counts = newly inserted rows (idempotency) |
| `tests/test_ingest.py` | Assert weather/results insert counts stay zero on re-ingest |
| `src/aris/eval/laptime.py` | Disjoint `HELD_OUT_RACES`; overlap guard; write MAE CSV |
| `src/aris/field/standings.py` | Mid-lap hide later sectors / unfinished lap time / premature `pit_in` |
| `src/aris/models/sector_split.py` | Documented as **post-session-only** (not wired into replay) |
| `src/aris/models/residual.py` | Documented training-time vs replay-time leakage distinction |
| `tests/test_no_leakage.py` | Extended: holdout disjoint, mid-lap standings, causal feature lags |
| `tests/test_field.py` | Mid-lap standings assertion |
| `scripts/deploy_to_neon.py` | Also applies `db/migrations/002_weekend_data.sql` |
| `scripts/inspect_cache.py` | Repo-relative / `--cache-db` path (no hardcoded Windows absolute) |
| `.gitignore` | Allow-list `results/heldout-laptime-mae.csv` (like other locked MAE artefacts) |

---

## Test suite results

| Checkpoint | Result |
|---|---|
| **Before Block 1** (Docker/Postgres up, first full run) | **1 failed**, rest passed — `test_ingest_is_idempotent` expected only `{sessions,drivers,laps}=0` but weather/results `DO UPDATE` reported non-zero write counts when migration 002 tables exist |
| After idempotency count fix (required to continue) | **110 passed** |
| After Block 2 | **110 passed** |
| After Block 3 | **115 passed** (+ leakage/field coverage) |
| After Block 4 | **115 passed** |
| After Block 5 | **115 passed**; Streamlit `apps/streamlit_app.py` reached “You can now view…” on `:8502` |
| **After Block 6 (end of Phase A)** | **115 passed**, **0 failed**, **0 skipped** with `ARIS_DB_URL` set and Docker Postgres up (integration tests included) |

**Explicit confirmation:** `pytest` is fully green, including integration tests, as of the end of this phase.

---

## Held-out MAE (Block 3)

**Overall held-out MAE = 1.735 s** (4587 scored laps). Baseline floor = 0.460 s. Does **not** beat MA(2).

Saved to `results/heldout-laptime-mae.csv`.

### Train (`REFERENCE_RACES` in `src/aris/models/residual.py`)
- 2024 Bahrain
- 2024 Saudi Arabia
- 2024 Australia
- 2024 Japan
- 2024 Miami
- 2023 Bahrain
- 2023 Belgium
- 2023 Abu Dhabi

### Held-out (`HELD_OUT_RACES` in `src/aris/eval/laptime.py`) — disjoint
| Race | n | MAE (s) |
|---|---|---|
| 2024 China | 716 | 1.567 |
| 2024 Monaco | 1148 | 3.148 |
| 2024 Spain | 1166 | 1.147 |
| 2024 Belgium | 711 | 1.792 |
| 2024 Abu Dhabi | 846 | 0.720 |
| **OVERALL** | **4587** | **1.735** |

---

## Needs Anas's decision

1. **`src/aris/models/sector_split.py` fate** — Unused (orphan) and non-causal (full-session medians). Scoped in docstring as post-session-only. Needs a decision: **wire in properly** (with temporal cutoff) **or delete**.

2. **Residual training on whole races** — Confirmed intentional offline supervised learning (`REFERENCE_RACES` → fit after leave-one-race-out CV). Features within a race are causal (`shift`), but the shipped booster sees all reference races. This is **not** the same class of bug as mid-replay leakage. Left documented in `residual.py` rather than “fixed.” Please confirm that framing is acceptable.

3. **`docs/` gitignore split (proposed, not applied)** — Today `.gitignore` has `docs/` entirely. Proposal: make **`docs/*.md` public** (data-sources, decision-schema, Phase A summary, future schema notes) while keeping **`docs/planning/`** and **`docs/learning/`** (and any personal audit notes like `REPO-STATUS-*.md` if you want them private) local-only via more specific ignore rules. **Not changed** — your call what becomes visible on GitHub.

4. **Proposed git tag (not cut)** — Name: **`v0.2.1-stabilize`** (or `v0.3-phase-a` if you prefer folding into predictor narrative). Represents: Phase A honesty pass — disclaimer, data-sources/decision-schema docs, RAG→keyword and conformal→MC renames, disjoint held-out MAE published (1.735 s), mid-lap standing cutoff, Neon migration 002 in deploy script, `dashboard/` removed, BUILD-LOG/README reconciled. Does **not** claim predictor beats baseline or that conformal/RAG/backtest exist.

5. **Disclaimer wording** — Added a standard unofficial / not-affiliated-with-F1-FIA-teams block near the top of `README.md`. If you want softer/stronger legal language, say so; I did not invent a lawyer-reviewed text.

---

## Checklist items not completed / caveats

| Item | Status |
|---|---|
| Real mapie split-conformal | **Deferred** (non-trivial redesign) — renamed instead per instructions |
| `docs/` gitignore change | **Not applied** — proposed only |
| Git tag | **Not cut** — proposed only |
| `sector_split.py` delete/wire | **Left in place** per item 13 |
| Residual training “fix” | **Documented, not changed** — judgment call for you |
| Fresh `uv sync` environment | Local `.venv` had broken `streamlit`/`toml` dist-info mid-run (OneDrive/access issues); repaired enough to smoke-test Streamlit. Worth a clean `uv sync --extra dev` on your machine before demos. |

---

## Stop

Phase A is complete pending your review of this summary. No Phase B (or later) work will start until you say so.
