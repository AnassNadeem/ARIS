# Phase H.1 merge summary — grounded RAG onto main

Executed 2026-08-16 in the **main** tree `C:\Users\anass\OneDrive\Desktop\ARIS`, not the worktree. Scope: Blocks H1.1–H1.5. Rehearsal-grade: this is the tree used on 21–23 Aug.

---

## Verdict (read this first)

**Merge is clean and the Zandvoort demo path is unchanged.** `feature/grounded-rag` is on `main` at merge `55bf27d`. Ask ARIS retrieval is in this tree. G1.5 recommend identity still holds.

Phase H's work was **not committed** on `86db68f` (that hash is G.1). It lived as uncommitted files in the worktree. This phase committed it as `3fddb9b` then merged. No file-level conflicts.

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Pre-merge main HEAD | current `main`, clean tree | `10989f8` (`only this`), **dirty** G.2–G.6 uncommitted | **reported**, stashed then restored |
| Feature HEAD vs H.6 | `86db68f` with Phase H committed | `86db68f` = G.1; Phase H uncommitted in worktree; committed here as **`3fddb9b`** | **corrected** |
| G.6 overlap with Phase H files | report real overlap or absence | **none** on the five named G.6 files | **PASS** |
| Merge conflicts | resolve explicitly if any | **clean** (`ort`), 33 files, 0 conflicts | **PASS** |
| `faiss-cpu` | install in this tree | already present **1.15.0**; `uv.lock` gained `faiss-cpu>=1.8` | **PASS** (sync hit OneDrive lock) |
| Full pytest | 207 passed (Phase H isolated) | live corpus: **251 passed, 5 failed**; fixture-isolated Ask: **13 / 13**; non-Ask: **243 / 243** (G.6) | **see H1.2** |
| Zandvoort smoke | G1.5 identity | **SMOKE OK**; same recommend / clock / L25 | **PASS** |
| Live-corpus grounding | ≥ 5 questions, exact JSONL numbers | **6 / 6** selected triples exact; cited record always matched the answer | **PASS** |
| Push `main` | non-fast-forward ok, no force | pushed (see H1.5) | **PASS** |

---

## H1.1 — Pre-merge state check

### 1. Main HEAD and working tree

| Check | Aimed | Actual |
|---|---|---|
| Branch | `main`, tracking `origin/main` | `main`, up to date with `origin/main` before merge |
| HEAD | current main | **`10989f8`** `only this` (1 commit ahead of `86db68f`) |
| Working tree | clean, no G.6/other unstaged | **dirty**: 17 modified tracked files + G.2–G.6 untracked |

G.2–G.6 work was **not** discarded. It was stashed (`stash@{0}: H1.1: stash G.2-G.6 uncommitted work before grounded-rag merge`), merge ran on a clean-enough tree, then restored. OneDrive left `.env.example` with a CRLF phantom; the 17 tracked files were restored from the stash after pop failed on that file. Untracked G.6 files restored. `docs/PHASE-H-SUMMARY.md` and `docs/how-recommend-works.md` were identical in both trees (byte-identical, 11298 and 6178 bytes) so the merge copies were kept.

### 2. `feature/grounded-rag` vs H.6's `86db68f`

| Check | Aimed | Actual |
|---|---|---|
| Branch exists | reachable locally/remotely | **local yes**; `origin/feature/grounded-rag` **does not exist** |
| Worktree | `C:\Users\anass\OneDrive\Desktop\ARIS-grounded-rag` | present, was on `feature/grounded-rag` |
| HEAD vs `86db68f` | Phase H tested at `86db68f` | `86db68f` = `docs: add Phase G.1 diagnosis and fix summary` (2026-08-13). **No Phase H commit existed.** Worktree status was 7 modified + 25 untracked Ask files. |

`git merge-base main feature/grounded-rag` was `86db68f`. Merging that hash into main would have been a **no-op** (main already contained it plus `10989f8`). Phase H was committed in the worktree as:

**`3fddb9b`** `feat(ask): replace keyword matching with grounded FAISS retrieval`

`.gitignore` exception `data/ask/index/.gitkeep` did not work (`data/ask/index/` never descends). Changed to `data/ask/index/*` + `!data/ask/index/.gitkeep` so the keep-file is tracked. Built `meta.json` / `documents.jsonl` stay ignored.

### 3. Diff-stat and G.6 overlap

`git diff --stat main...feature/grounded-rag` after the Phase H commit (33 files, +14066 / −64):

Ask modules, tests, fixtures, concepts, `scripts/build_ask_index.py`, `docs/PHASE-H-SUMMARY.md`, `docs/how-recommend-works.md`, `faiss-cpu>=1.8` in `pyproject.toml` / `requirements.txt` / `apps/requirements.txt`, `.gitignore`, `apps/components/aris_chat.py`.

**Named G.6 files vs Phase H changed-file list:**

| G.6 file | In Phase H diff? |
|---|---|
| `src/aris/decisions/persist.py` | **no** |
| `tests/test_live_write_gating.py` | **no** |
| `tests/test_decision_queue.py` | **no** |
| `docs/zandvoort-day-of-checklist.md` | **no** |
| `.env.example` | **no** |

**Absence of overlap on those five files is measured, not assumed.**

Untracked-name overlap with main's dirty tree: `docs/PHASE-H-SUMMARY.md`, `docs/how-recommend-works.md` only. `fc /b`: **no differences**.

`simulate.py` / `recommend.py` / `tires.py` / `tracks.py` / `physics/` were not in the Phase H commit. Main's uncommitted G.6 edits to `simulate.py` / `tracks.py` remain local and unmerged-with-H because H did not touch them.

---

## H1.2 — Merge

### 4. Merge

```
git merge feature/grounded-rag
```

**Clean.** Strategy `ort`. No conflict markers, no ours/theirs choice. 33 files, 14066 insertions, 64 deletions. Merge commit **`55bf27d`**.

Parents: `10989f8` (main) + `3fddb9b` (Phase H).

### 5. `faiss-cpu`

| Check | Aimed | Actual |
|---|---|---|
| Import in this tree's `.venv` | `faiss-cpu>=1.8` | **`faiss-cpu==1.15.0`** (already installed; same as Phase H) |
| `IndexFlatIP(4096)` | smoke OK | **OK**, `idx.d=4096` |
| `uv lock` | add package | **Added faiss-cpu v1.15.0** (+23 lines in `uv.lock`) |
| `uv sync --extra dev` | install into `.venv` | **FAIL** OneDrive: `Access is denied` removing `jupyter_console-6.6.3.dist-info\licenses`. Import still works because 1.15.0 was already in the venv. |

`.venv` has no `pip` module; install path is `uv`.

### CHECKPOINT — full pytest

Docker `aris-postgres` healthy (Up 5 days). `ARIS_DB_URL` set from `.env`. `ARIS_ASK_DECISION_DIRS` unset. `ARIS_FAST_CLOCK` / `ARIS_TRUE_COMPOUND_SLOPES` unset.

**Run A — merged tree, live `results/decisions/*.jsonl` present (48 files, 16630 proposes):**

| Suite | Aimed | Actual | Result |
|---|---|---|---|
| Full pytest | **207 passed** (Phase H isolated worktree) | **251 passed, 5 failed**, 227.00 s | **not 207** |

The 5 failures are all Ask tests, all because `_decision_dirs()` **always** appends `results/decisions/` then the 14-event fixture. Phase H's note that “unset `ARIS_ASK_DECISION_DIRS` uses the fixture” is true **only when the live JSONL directory is missing** (worktree / CI). On this main tree the live corpus exists, so tests index 16630 proposes:

| Test | Why it failed on live corpus |
|---|---|
| `test_decision_source_is_real_jsonl` | first SAI lap-21 is not 2024 NL; aimed delta **−72.72805747985858**, actual **−2.251042938232149** |
| `test_grounding_ten_plus_logged_decisions` | builds one question per **all** proposes, not 14 |
| `test_grounding_does_not_guess_when_nothing_retrieved` | FIFA question retrieved 2025 Mexico PIA L60 instead of `ABSTAIN` (MIN_COSINE 0.08 on a large hashing index) |
| `test_grounding_does_not_mix_another_lap_delta` | 2024 NL SAI L21 not top-ranked among 8 SAI L21 copies |
| `test_follow_up_uses_session_memory_not_a_new_guess` | same L21 miss |

These 5 did not fail on the worktree (no live JSONL) and did not exist on main before the merge (no Ask tests). They are **environment isolation**, not a conflicted merge of `persist.py` / recommend / simulate.

**Run B — same merged tree, live JSONL temporarily renamed** (`results/decisions` is a OneDrive reparse point; restored after):

| Suite | Aimed | Actual | Result |
|---|---|---|---|
| `tests/test_ask_*.py` | **13 passed** (Phase H) | **13 passed**, 2.68 s | **PASS** |

Non-Ask tests in Run A: **243 passed**. That matches G.6's **243 passed**. Combined isolation equivalent: **256 passed** (243 G.6 uncommitted tests + 13 Ask). Aimed 207 vs that 256 is the G.2–G.6 tests that were never on `86db68f`, plus 13 Ask.

No failure appeared that was absent from both (a) fixture-isolated Ask tests and (b) G.6's 243. The merge did not break simulate/recommend/strategy tests.

Logs: `results/h1/pytest.log`, `results/h1/pytest-ask-isolated.log`.

---

## H1.3 — Zandvoort smoke, merged tree

`python scripts/_e1_smoke_strategy_zandvoort.py` against local Postgres. Compared to G1.5 (`docs/PHASE-G1-SUMMARY.md`), same lock every phase since E4.1.

| Check | Aimed (G1.5) | Actual (merged main) | Result |
|---|---|---|---|
| Setup | 2025 Netherlands session_id 123, VER | **123**, VER, driver_id **2448** | **PASS** |
| Track | 72 laps, pit_loss **18.5**, slopes **0.08 / 0.05 / 0.03** | **72 / 18.5 / 0.08, 0.05, 0.03** | **PASS** |
| Prewrite windows | A:[18] B:[29] C:[18, 40] | **same** | **PASS** |
| Weekend form | n=20 | **20** | **PASS** |
| Clock | 287 ticks → lap 72 complete | **287** ticks, lap **72**, complete | **PASS** |
| Live state L25 | MEDIUM, tyre_life=2 | **MEDIUM / 2** | **PASS** |
| Recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **Pit lap 33 for HARD; Pit lap 30 for HARD; Stay out on current tyres** | **PASS** |
| Smoke exit | SMOKE OK | **SMOKE OK** | **PASS** |

What-if MC is unseeded and not a locked identity. This run: delta **−11.92 s**, MC P10/P90 **−147.55 / +29.33** (same printed delta as Phase H). Log: `results/h1/zandvoort-smoke.log`.

---

## H1.4 — Ask ARIS against the real corpus

`python scripts/build_ask_index.py` on this tree's `results/decisions/` (not the 14-event fixture).

| Check | Aimed | Actual |
|---|---|---|
| Sources | live JSONL + races + concepts | decisions=**16630** races=**959** concepts=**12** |
| IndexFlatIP | n_features=4096, n_docs=17601 (Phase H) | **n_docs=17601** `by_source={decision: 16630, race: 959, concept: 12}` |
| Elapsed | Phase H 7.096 s | **3.101 s** |
| JSONL files now | report | **48** files; 33260 events; proposes 2024=9340, 2025=7290 |
| Unique (year, round, country, driver, lap) | hoped some | **0 of 2713** keys unique; max **174** duplicate proposes per key (backtest re-runs, distinct `event_id`s) |

Corpus size matches Phase H's 16630 — it did not grow past that count since H.6. What *is* different from the fixture tests is that all 16630 are searchable at once.

Grounding contract checked two ways:

1. **Intended-record match** (answer numbers = the specific JSONL row we asked about). Works when every copy of that key shares the same delta/mean/label, or retrieval ranks that row first.
2. **Cited-record match** (answer numbers = the JSONL row named in `Cited:`). **27 / 27** of the probe set — compose still copies facts; it does not invent.

### Six live-corpus triples (question / answer / source record)

Numbers below are `json.dumps` of the cited JSONL fields (same contract as `narrate.py`).

**1. ALB 2025 Netherlands L14 (Zandvoort session 123)**

- Question: `What did ARIS recommend for ALB at the 2025 Netherlands round 15 race on lap 14?`
- Aimed: `delta_vs_stay_out_s=-43.504999999999924`, `mean_race_time_s=4485.409974090734`, label `Pit lap 22 for HARD`, `event_id=dce9286c-eeb2-4b4e-a98c-19ec2aa7ce5c`, file `2025_r15_ALB_123.jsonl`
- Actual answer: those exact numbers, label, and `event_id` in `Cited:`
- Result: **PASS** (intended record and cited record)

**2. LEC 2025 Canada L8**

- Question: `What did ARIS recommend for LEC at the 2025 Canada round 10 race on lap 8?`
- Cited source: `event_id=5333a20e-8a23-40ad-839c-aee0dfa42a75` file `2025_r10_LEC_235.jsonl`
- Aimed from that record: `delta_vs_stay_out_s=-161.9170204081628`, `mean_race_time_s=4471.846338970696`, label `Pit lap 9 for MEDIUM`
- Actual answer: those exact numbers
- Result: **PASS** (cited-record exact). Same key has other re-runs with different deltas; retrieval picked this row.

**3. ALB 2025 Australia L56**

- Question: `What did ARIS recommend for ALB at the 2025 Australia round 1 race on lap 56?`
- Source: file `2025_r1_ALB_225.jsonl`; copies share delta/mean/label; `event_id=afddc42b-2d17-4c06-9b7e-1392af491a42` is among citations
- Aimed: `delta_vs_stay_out_s=-0.09369411200937633`, `mean_race_time_s=181.1724911966377`, label `Brake 20m earlier into T7`
- Actual: exact
- Result: **PASS**

**4. ALB 2025 Australia L57**

- Question: `What did ARIS recommend for ALB at the 2025 Australia round 1 race on lap 57?`
- Aimed: `delta_vs_stay_out_s=-0.19684705600468816`, `mean_race_time_s=90.58074559831886`, label `Brake 20m earlier into T7`
- Actual: exact (`Cited:` includes `event_id=0e4f93bd-54ca-43be-b863-bd76acca111f` among same-key copies)
- Result: **PASS** (lap 57 mean **90.58074559831886** ≠ L56's **181.1724911966377**)

**5. VER 2025 United Kingdom L12**

- Question: `What did ARIS recommend for VER at the 2025 United Kingdom round 12 race on lap 12?`
- Aimed: `delta_vs_stay_out_s=-0.3`, `mean_race_time_s=4400.710704332644`, label `Lift 30m into T10`, file `2025_r12_VER_237.jsonl`
- Actual: exact
- Result: **PASS**

**6. VER 2025 United Kingdom L18**

- Question: `What did ARIS recommend for VER at the 2025 United Kingdom round 12 race on lap 18?`
- Aimed: `delta_vs_stay_out_s=-0.3`, `mean_race_time_s=3996.272143555908`, label `Lift 30m into T10`
- Actual: exact (`Cited:` leads with `event_id=f44079fc-913d-4b55-bfdc-e48942bb9553`)
- Result: **PASS** (same label as L12, different `mean_race_time_s` — lap constraint held)

### Live-corpus misses worth logging (not invented numbers)

| Question | Aimed (fixture / one re-run) | Actual retrieved | Cited-grounded? |
|---|---|---|---|
| SAI 2024 Netherlands round 15 lap 21 | delta **−72.72805747985858**, `Pit now for HARD` | delta **−60.8**, `Pit lap 26 for HARD`, `event_id=dac9f241-…` in `2024_r15_SAI_15.jsonl` | **yes** — a later backtest copy of the same lap |
| NOR 2024 Belgium round 14 lap 11 | delta **−11.188644561767251**, `Pit now for HARD` | delta **−14.159999999999673**, `Pit lap 16 for HARD` | **yes** — different copy, same file |
| VER 2025 Netherlands L25 / PIA L33 / HAM 2025 Spain L20 | some propose in those files | **ABSTAIN** (nothing ≥ MIN_COSINE 0.08 after constraints) | n/a |

Headline for this block: **6 / 6** chosen live questions returned exact JSONL numbers for the record they cited. The fixture's SAI NL L21 delta is **in** the index (8 SAI L21 rows; two still hold **−72.72805747985858**) but is not always the top hit on the full corpus.

---

## H1.5 — Push and worktree cleanup

Pushed `main` (no force). Commits on origin after this phase: `3fddb9b` (Phase H), `55bf27d` (merge), plus the lockfile + this summary commit.

G.2–G.6 files remain **uncommitted** on this working tree, as they were before H.1. `stash@{0}` still holds a backup of that work; do not `stash pop` it again (it would collide with the restored files). Drop it only after you are sure the working tree still has G.6: `git stash drop stash@{0}`.

Worktree **not** removed. When you are confident:

```
git worktree remove "C:\Users\anass\OneDrive\Desktop\ARIS-grounded-rag"
```

If git refuses because of gitignored index files under `data/ask/index/`, the force form is:

```
git worktree remove --force "C:\Users\anass\OneDrive\Desktop\ARIS-grounded-rag"
```

Do not run that until you have used this merged main tree. After remove, `git branch -d feature/grounded-rag` is optional (`origin/feature/grounded-rag` was never pushed).

---

## What this does and does not claim

Does: land grounded Ask ARIS on the event tree; confirm no merge conflicts with G.6; confirm G1.5 Zandvoort smoke; confirm fixture Ask tests still pass when live JSONL is hidden; confirm live-index answers copy JSONL numbers for the cited row.

Does not: commit G.2–G.6; make Ask unit tests green while `results/decisions/` exists (needs an explicit fixture-only path); make every natural-language lap question retrieve one canonical re-run among 174 copies; enable pgvector; change G1.5 slopes.

**STOP.**
