# Phase H.2 summary — commit G.2–G.6, isolate Ask tests, fix retrieval identity

Executed 2026-08-17 in the **main** tree `C:\Users\anass\OneDrive\Desktop\ARIS`.
Scope: Blocks H2.1–H2.4. Rehearsal-grade. G1.5 stays shipped.

---

## Verdict (read this first)

**G.2–G.6 was already committed and pushed** before this phase started.
HEAD is `a908e79`, matching `origin/main`. No G.2–G.6 files were sitting
uncommitted; nothing was lost in the H.1 stash/restore.

Ask unit tests no longer depend on an unset `ARIS_ASK_DECISION_DIRS`.
They pin the 14-event fixture in `tests/conftest.py`. Confirmed with that
env var **explicitly set to the live corpus**.

Live `results/decisions/*.jsonl` mixes G1.5-shipped proposes with G2/G3/G4
overlay-experiment walks in the **same files**, untagged. Records are now
tagged at write time. Ask retrieval **defaults to G1.5-shipped only**.
Zandvoort smoke still matches the locked identity.

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| G.2–G.6 committed + pushed | yes, real history | already on `origin/main`; see hashes below | **PASS** (pre-existing) |
| Working tree vs G.2–G.6 summaries | same files, nothing missing | all named files present in those commits | **PASS** (one split note) |
| Ask tests ignore live corpus / shell env | deterministic fixture | 14 fixture docs with live env set | **PASS** |
| Overlay vs shipped mixed in JSONL | measure, don't guess | **yes**; 0 records tagged; 9530 overlay-window / 7100 g1-window | **confirmed** |
| Ask default surfaces G1.5, not overlay duplicate | yes | load-time filter + retrieval prefer; test proves it | **PASS** |
| Full pytest | green | **261 passed**, 0 failed | **PASS** |
| Zandvoort smoke vs G1.5 lock | Pit lap 33 HARD / Pit lap 30 HARD / Stay out | **same**; **SMOKE OK** | **PASS** |

---

## H2.1 — G.2–G.6 commit safety (done first, not touched)

`git status` / `git diff --stat` at start: **no modified tracked files**.
Untracked only `.cursor/` and `docs/PHASE-R1-CORNERING-LOAD-SUMMARY.md`
(R.1 worktree artefact; **not** committed here — R.1 was not merged).

`main` == `origin/main` at **`a908e79`**. The G.2–G.6 work H.1 left
uncommitted was committed after H.1 (and before R.1) as eight commits:

| Commit | Message | Phase |
|---|---|---|
| `ba8f4db` | feat(physics): map Pirelli C-code nominations onto event-relative compounds | G.2 |
| `8177f6f` | feat(tracks): opt-in C-code slope overlay without changing the shipped default | G.3.1 overlay wiring (G.2 call sites) |
| `03fd7ff` | feat(physics): add traffic-gap construction and isotonic C-code slope constraint | G.3 |
| `126482a` | feat(models): add pooled context-aware tyre degradation behind an opt-in flag | G.4 |
| `0e857a0` | docs: lock G1.5 as the shipped tyre model and close the degradation thread | G.5 |
| `429a284` | chore(scripts): let G1 diagnosis and walk-forward backtests write to a chosen directory | G.2 `--out-dir` |
| `82c8192` | fix(decisions): fail loudly when the JSONL decision log cannot be written | G.6 persist |
| `a908e79` | docs: add Phase G.6 pre-event rehearsal and day-of overlay/log checklist | G.6 docs |

Cross-check vs `docs/PHASE-G2-SUMMARY.md` … `PHASE-G6-SUMMARY.md`: every
file those docs name as shipped is in `HEAD` (`nominations.json`, slope
tables, `compounds.py`, `tracks.py`, `traffic.py`, `pooled_deg.py`,
`persist.py`, live-write tests, day-of checklist, `.env.example`, G.2–G.6
summaries, `_g2_`/`_g3_`/`_g4_`/`_g6_` scripts).

**Expected split, not a loss:** G.5's `load_track_config` lock docstring
landed in `8177f6f` (overlay commit) rather than `0e857a0` (G.5 docs
commit), because the previously-uncommitted tree was committed later as
logical slices. The docstring is in `src/aris/tracks.py` at HEAD.
`docs/how-recommend-works.md` was already committed in Phase H
(`3fddb9b`); H.1 measured it byte-identical across trees.

`git log` shows these as real history on `origin/main`, not working-tree
orphans. `stash@{0}` (`H1.1: stash G.2-G.6…`) is still a backup; do not
`stash pop` it.

No new G.2–G.6 commit was created. Push was already done.

---

## H2.2 — Ask test isolation

H.1.4: `_decision_dirs()` always appended `results/decisions/` then the
fixture. Unset `ARIS_ASK_DECISION_DIRS` used the fixture **only when the
live directory was missing**. On this tree the live corpus exists
(16630 proposes), so Ask tests indexed it and failed.

**Fix:**

1. `ARIS_ASK_DECISION_DIRS` is now an **exclusive** override (no silent
   append of the live dir).
2. `tests/conftest.py` pins `data/ask/fixtures/decisions.jsonl` via
   `pytest_configure` **and** an autouse `monkeypatch.setenv`, so a
   shell-set live path cannot leak in.

**Confirmation:** `ARIS_ASK_DECISION_DIRS=C:\Users\anass\OneDrive\Desktop\ARIS\results\decisions`
(the live corpus) during Ask tests. `test_decision_source_is_real_jsonl`
asserts **exactly 14** fixture docs and SAI L21 delta
**−72.72805747985858**. Suite green.

Three fixture rows were overlay-window copies of laps that also have
G1.5-window records (VER 2024 Azerbaijan L23, PER 2024 Australia L46,
HAM 2024 Italy L34). Replaced with the shipped-window copy of the same
lap so the 14-event fixture is itself G1.5-only.

---

## H2.3 — Multi-model-version retrieval

### What the corpus actually contains

`results/decisions/*.jsonl`: **48** files, **16630** propose events.
**0** records had a `true_compound_slopes` field. Overlay experiments
were **not** in a separate directory — G2 appended onto G1's files
(G3.2 already documented this).

Unique `(year, round, country, driver, lap)`: **0 of 2713** keys unique;
max **174** copies. **2290** keys have conflicting deltas, and **all
2290** span both the G1.5 walk window and the overlay window.

G3.2 cutoff `2026-08-13 20:00 UTC`:

| Window | n propose | What it is |
|---|---:|---|
| before cutoff (g1-window) | **7100** | Phase G + G1.5 re-runs (shipped globals) |
| 2026-08-13 21–22 UTC | **4765** | G2 unconstrained walk (count matches G3.2) |
| 2026-08-14 12–14 UTC | **1931** | later overlay walk cluster (G3/G4; not tagged on the record) |
| 2026-08-14 18–20 UTC | **2834** | later overlay walk cluster (G3/G4; 1931+2834=**4765**) |

Aug 14 total **4765** = one more full 2024+2025-sized walk, split across
two hour clusters. The record itself cannot say isotonic vs pooled.
Timestamp + G3.2's G2 count is recoverable; C-code mode is not, because
it was never written.

**R1.1 / H.1 lead — SAI 2024 Netherlands L21, 8 copies, all in
`2024_r15_SAI_15.jsonl`:**

| ts (UTC) | Window | Label | `delta_vs_stay_out_s` | event_id prefix |
|---|---|---|---|---|
| 2026-08-13 14:36:46 / 14:36:49 | g1 | Pit now for HARD | **−72.72805747985858** | `d64077b8` / `e482debb` |
| 2026-08-13 16:14:50 / 16:14:51 | g1 | Pit lap 26 for HARD | **−60.8** | `237bb1e9` / `dac9f241` |
| 2026-08-13 21:39:16 (×2) | overlay (G2) | Pit lap 29 for HARD | **−24.1643** | `c22ab051` / `4a9ee742` |
| 2026-08-14 12:59:53 (×2) | overlay (later walk) | Plan: L31→SOFT, L46→HARD | **−254.674** | `9ab37209` / `14d6c8a2` |

The last row is G2's inverted-SOFT identity (G2.7.14 smoke). It is **not**
the shipped model. H.1 live Ask retrieved a −60.8 / Pit lap 26 copy —
a g1-window re-run, not the fixture −72.73 row.

g1-window still has **two** 2024 walks (Phase G + G1.5). Those are not
overlay experiments. This phase does **not** pick a winner among them
by delta. It only excludes overlay-window / overlay-tagged records.

### What was done (tag, don't guess)

Option (a): tag at write, filter Ask to shipped by default.

- `JsonlDecisionLog.append` writes `true_compound_slopes` =
  `parse_true_compound_mode()` (`off` / `unconstrained` / `isotonic` /
  `pooled`) from `ARIS_TRUE_COMPOUND_SLOPES` at persist time.
- Historical untagged records: **not** labelled by recommend identity.
  G3.2's timestamp split is the only recoverable signal. Before cutoff
  → treat as `off`. After → `unknown-overlay`, excluded from Ask
  unless `ARIS_ASK_INCLUDE_OVERLAY_DECISIONS=1`.
- Overlay JSONL stays in `results/decisions/` (cannot split by file;
  G1 and G2 share paths). They are **not indexed** for Ask by default.
- Retrieval: if a mixed in-memory index still has both, `_prefer_shipped_model`
  keeps `off` and drops overlay hits.

**Test:** two conflicting SAI NL L21 records (`off` delta −72.73 vs
`unconstrained` delta −24.16). Overlay is first in the index.
`answer_question` returns the shipped delta and label, not the overlay
duplicate (`tests/test_ask_model_version.py`).

---

## H2.4 — Re-verification

Docker `aris-postgres` healthy (Up 6 days). Overlay / fast-clock unset.
Ask tests ran with live `ARIS_ASK_DECISION_DIRS` set; conftest pinned
the fixture anyway.

| Suite | Aimed | Actual | Result |
|---|---|---|---|
| Full pytest | green | **261 passed**, 0 failed, 261 collected | **PASS** |
| vs G.6 / H.1 | 243 G.6 + 13 Ask | 243 + 13 Ask + **5** H2.3 tests = **261** | **PASS** |

Log: `results/h2/pytest.log`.

### Zandvoort smoke vs G1.5 lock

`python scripts/_e1_smoke_strategy_zandvoort.py`. Session 123, VER,
driver_id 2448.

| Check | Aimed (G1.5 / E4.1 identity) | Actual | Result |
|---|---|---|---|
| Track laps / pit | 72 / 18.5 | 72 / 18.5 | **PASS** |
| Slopes H/M/S | **0.08 / 0.05 / 0.03** | **0.08 / 0.05 / 0.03** | **PASS** |
| Prewrite windows | A:[18] B:[29] C:[18, 40] | **same** | **PASS** |
| Weekend form | n=20 | **20** | **PASS** |
| Clock | 287 ticks → lap 72 complete | **287 / 72 / True** | **PASS** |
| L25 state | MEDIUM, tyre_life=2 | **MEDIUM / 2** | **PASS** |
| Recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **Pit lap 33 for HARD; Pit lap 30 for HARD; Stay out on current tyres** | **PASS** |
| Smoke exit | SMOKE OK | **SMOKE OK** | **PASS** |
| What-if / MC | G1.4 **−11.92 s**, P10/P90 **−147.55 / +29.33** (not E4.1 −13.00; not G2 −2.34) | **−11.92 / −147.55 / +29.33** | **PASS** |

Log: `results/h2/zandvoort-smoke.log`.

---

## What this does and does not claim

Does: confirm G.2–G.6 is on `origin/main` with real commit hashes; make
Ask unit tests fixture-only regardless of env; tag new decision-log
writes with the active tyre-model mode; keep G2/G3/G4 overlay proposes
out of default Ask retrieval; prove a conflicting overlay duplicate
loses to the shipped record; re-confirm G1.5 Zandvoort identity.

Does not: rewrite historical JSONL; split overlay walks into another
directory (they share files with G1.5); pick among g1-window re-runs
of the same lap (Phase G vs G1.5 still both indexable); enable any
overlay as default; restore E4.1 What-if −13.00 s.

**STOP.**
