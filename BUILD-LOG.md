# ARIS — Build Log

A daily journal of what got built, what broke, and what I learned. One bullet per day, Mon–Sat. Sundays off (non-negotiable).

**Companion docs:** `[ARIS-FINAL-PLAN.md](./ARIS-FINAL-PLAN.md)` · `[ARIS-EXECUTION-PLAN.md](./ARIS-EXECUTION-PLAN.md)` · `[ARIS-PHASES-WEEKLY-PLAN.md](./ARIS-PHASES-WEEKLY-PLAN.md)`

**Started:** 2026-05-04 · **Ship target:** 2026-08-31 · **Cadence:** 6 hrs/day × 6 days/week

---

## How to read this log

- **One line per day.** What was actually done — not what was planned.
- **Friction logged.** Bugs, dead-ends, and "this took 3 hours longer than expected" entries are *more* valuable than smooth days. Hiring managers read this.
- **Commits referenced.** Each entry should be tied to a real commit hash or PR where possible.
- **No backfilling.** If a day was missed, the entry says so. The log is honest or it's worthless.
- **Weekly retro at the end of each week** — what shipped, what slipped, what changes for next week.

---

## Phase 0 — Pre-Day-1 setup (Week 0, Apr 29 – May 3)

### Week 0 — loadout

- **2026-04-29 (Wed):** Locked the plan. Read `ARIS-FINAL-PLAN.md` end-to-end, confirmed CS+AI direction (no more revisiting), reframed target role to "Software Engineer — Vehicle Performance / Strategy Tools." Drafted GitHub profile rewrite (NeuroSim out, ARIS framing in) — staged, not yet pushed. Reserved Rajamani *Vehicle Dynamics and Control* via Brunel library (Wk5 read).
- **2026-04-30 (Thu):** Python 3.11.9 installed via `uv 0.11.11` (kept system Python 3.14.4 untouched as fallback). NVIDIA Studio driver + CUDA 12.x toolkit verified — `nvidia-smi` shows RTX 5070 (8GB), `nvcc --version` confirms toolkit. Git for Windows + GitHub CLI authed.
- **2026-05-01 (Fri):** Docker Desktop installed, `docker run hello-world` clean. VS Code + Python/Pylance/Ruff/Jupyter/Docker/GitLens extensions installed. Free-tier accounts created or verified: GitHub, Streamlit Community Cloud (GitHub login), Neon.tech (Postgres connection string saved to password manager), Hugging Face.
- **2026-05-02 (Sat):** Ollama installed, `llama3.1:8b-instruct-q5_K_M` pulled (~5.5 GB). Local inference smoke test: *"Explain F1 tire degradation in one sentence"* — answered coherently in ~6s on RTX 5070, VRAM headroom confirmed. Decision logged: Llama 3.1 8B local is the default LLM throughout the build; Claude API stays out of budget until Phase 7 demo polish.
- **2026-05-03 (Sun, prep day):** Repo skeleton committed (`src/aris/`, `scripts/`, `notebooks/`, `tests/`, `data/`, `models/`, `results/`, `configs/`, `learning/`). Planning docs landed in `docs/planning/`. `BUILD-LOG.md` and `ARIS-EXECUTION-PLAN.md` templates dropped at repo root. Day 1 (May 4) schedule set; Rajamani not yet collected from library (queue).

**Weekly retro (Wk 0):**

- Shipped: full toolchain (Python 3.11.9, uv, Docker, NVIDIA stack, Ollama + Llama 3.1 8B, VS Code, Git, gh), all free-tier accounts, repo skeleton with planning docs.
- Slipped: GitHub profile rewrite staged but not pushed (deferred to Day 1). FastF1 cache pre-warm (per execution plan §E) not run — pushed to Wk 1.
- Changes for Wk 1: hit the ground running on Day 1 — first commit, send Brunel WhatsApp, push profile rewrite, install FastF1 + start cache pre-warm.

---

## Phase 1 — Python foundations + first FastF1 plot (Weeks 1–2, May 4 – May 17)

### Week 1 (May 4 – May 10) — Day 1 ignition (delayed start, recovered Fri)

- **2026-05-04 (Mon, Day 1):** *missed.* Real-life slippage. No commits, no WhatsApp sent, no Day 1 ignition. Logging honestly per the no-backfill rule.
- **2026-05-05 (Tue):** *missed.*
- **2026-05-06 (Wed):** *missed.*
- **2026-05-07 (Thu):** *missed.* Four-day cold start now baked in; Fri/Sat/Sun reframed as a 3-day catchup sprint to land on Wk 2 cadence.
- **2026-05-08 (Fri):** Catchup ignition. Verified `uv 0.11.11` + Python 3.11.9 toolchain; created `.python-version` pinning the repo to 3.11.9 so anyone (or future-me) cloning gets the right interpreter. Confirmed `.venv` already targets 3.11.9. Wrote `scripts/prewarm_cache.py` — idempotent FastF1 pre-warm over 8 sessions (2024 Bahrain/Saudi/Australia/Japan/Miami + 2023 Bahrain/Belgium/Abu Dhabi), with per-session try/except, timing, and progress logging. Started the pre-warm — Japan 2024 hung on a stalled HTTP request (Ctrl+C wouldn't fire because the block was inside a C extension); killed the terminal, rerun, cached races skipped in <1s each as designed. Drafted `docs/planning/TO-DO.md` (the 5-notebook cap for Phases 0–2, hygiene rules, mid-plan check) and `docs/learning/SKILLS-MASTERY.md` (13-part self-test rubric: Python OOP through F1 strategy through MATLAB/Simulink) — the standard is "rebuild ARIS on a blank machine with no AI."
- **2026-05-09 (Sat):** Catchup sprint Day 2. FastF1 prewarm completed cleanly on retry — Japan 2024 succeeded second attempt; cached races skipped <1s as designed. Discovered `.gitignore` was syntactically broken (wrapped in a PowerShell here-string with leading whitespace on every rule, so no patterns were matching) — rewrote it from scratch, added `fastf1_cache/` and `.claude/` ignores. Wrote and pushed `README.md` with the locked one-line pitch, six-layer L0–L6 architecture, status table, "what ARIS is NOT" section, and a roadmap mapping each phase to a release tag — recruiter-readable at the repo root. Over-pushed `docs/planning/` and `docs/learning/` initially (NeuroSim docs, deep-research AI feedback, internal trackers all went public for ~30 minutes); corrected by untracking `docs/` wholesale and adding it to `.gitignore` — local files preserved, public repo cleaned. Drafted `notebooks/00-numpy-basics.ipynb` covering arrays, slicing-as-view, boolean indexing, broadcasting, vectorised math, axis-aware aggregations, seeded random, and a closed-form OLS via `np.linalg.solve`. Filled out the project skeleton: `src/aris/{physics,models,eval}/__init__.py` subpackages, `configs/.gitkeep`, and a `pyproject.toml` stub (hatchling build, ruff/mypy/pytest config, optional dev extras). Six commits pushed to `origin/main` across the day.
- **2026-05-10 (Sun):** Catchup sprint Day 3 — broke the "Sunday off" rule once to close out Wk 1. Scaffolded `notebooks/01-fastf1-first-pull.ipynb` (cache-wiring cell + section headers, TODO stubs for the load/inspect/pick/plot cells) and pushed as its own commit so the diff history shows scaffold → fill. Filled the stubs: loaded Bahrain 2024 Race from the pre-warmed cache (no network, 1129 laps × 31 cols, 20 drivers), picked VER's fastest race lap (lap 39, 1:32.608 on softs, tyre life 7) via `pick_drivers('VER').pick_fastest()`, pulled car telemetry with `get_car_data().add_distance()` (349 samples over 5.41 km, max 301 km/h), and plotted speed-vs-distance with matplotlib — the first real ARIS plot. Wrote `notebooks/02-pandas-basics.ipynb` covering Series/DataFrame, `.loc` vs `.iloc`, boolean filtering, groupby (single + multi-key + multi-agg), SQL-style merge, NaN triage, datetime-indexed `resample`, and a closing fuel-corrected pace ranking pipeline — same teaching shape as the NumPy notebook. Installed `nbconvert`/`nbclient`/`ipykernel` via `uv pip` to run notebooks headless from CI/scripts; both notebooks executed top-to-bottom from a fresh kernel before outputs were cleared for commit. Three commits pushed (`1ab7c7e` scaffold, `41feee0` Bahrain fill, `1d8775d` pandas).

**Weekly retro (Wk 1):**

- Shipped: `.python-version` pinning Python 3.11.9; idempotent FastF1 prewarm script with 8 cached race sessions; functional `.gitignore`; public-facing `README.md` with pitch + architecture + roadmap; project skeleton (`src/aris/{physics,models,eval}/`, `pyproject.toml`, configs); NumPy-fluency notebook committed; BUILD-LOG backfilled honestly; locally-archived planning + skills-mastery docs (gitignored).
- Slipped: WhatsApp to Brunel Racing **still not sent** (was Day 1 task). Pandas refresh and FastF1 first-pull notebook (originally Sat/Sun work) pushed to Wk 2 Mon/Tue. Lost ~1 hr to the docs/ over-push reversal.
- Changes for Wk 2: send WhatsApp Mon morning before any code. Pandas tutorial + `01-fastf1-first-pull.ipynb` Mon–Tue. Then Wk 2 original plan (stint-analysis notebook, README screenshot) Wed–Sat. Sunday properly off.

### Week 2 (May 11 – May 17) — pandas + first FastF1 plot

- **2026-05-11 (Mon):** Wk 2 ignition. Block 1 sanity check: re-ran `02-pandas-basics.ipynb` on a fresh kernel — green, no env drift (`ecd916e`). Scaffolded `03-pandas-deep-dive.ipynb` with three James Powell translation cells (`dtypes`, `groupby + named-tuple agg`, `.dt.total_seconds()`) on real Bahrain 2024 R lap data — no synthetic frames anywhere in the notebook. Block 2 Q1/Q2/Q3 implemented end-to-end: per-driver median race pace (VER 95.41s / SAI 96.10s / PER 96.21s top three after filtering pit-in/pit-out/non-green laps); compound pace deltas via `groupby + median + unstack` pivot (only SOFT and HARD pivot columns appeared — confirms Bahrain stints were SOFT-HARD-SOFT for most front-runners); VER lap-time progression chart with per-stint compound colours, median-pace reference line, and pit-stop markers, saved to `docs/screenshots/wk2-ver-pace-progression.png`. Block 3 merge mechanics: `pd.merge_asof` lap → weather joined cleanly (1129 rows preserved); standard merge lap → results required renaming `Position` → `FinishPosition` because `laps` already carries its own running-position `Position` column (`Position_x`/`Position_y` collision otherwise — that bug ate 15 min, the kind of footgun that won't bite twice now); Pearson r(TrackTemp, LapTime) for VER green laps as the toy correlation. Block 4: drafted `learning/kaggle-pandas-speedrun.ipynb` scaffold — six lesson sections, TODOs for the actual exercises (`069aa61`). Side fix: `00-numpy-basics.ipynb` cell 20 had `fuel = 100 - 1.5*lap` exactly collinear with the intercept + lap columns, so `np.linalg.solve(X.T @ X, X.T @ y)` was raising `LinAlgError: Singular matrix` on every fresh run — added small per-lap consumption noise so the design matrix is full rank (`1d53fff`). Four commits pushed (`1d53fff`, `672ebab`, `ecd916e`, `069aa61`). Day 2 prep verified against the real frame: FastF1 exposes a `Stint` column natively (VER = SOFT 1–17 → HARD 18–37 → SOFT 38–57), so Day 2's job is to rebuild that from `Compound` transitions + `PitInTime`/`PitOutTime` and check against the built-in.
- **2026-05-12 (Tue):** Stint analysis day. Wrote `notebooks/04-stint-analysis.ipynb` end-to-end (`0e24344`). `detect_stints` segments laps via `df.groupby('Driver')['Compound'].transform(lambda s: s != s.shift(1)).cumsum()` — the boolean `shift(1)` gives NaN on the first row which `!=` everywhere treats as True, so StintId starts at 1 with no extra logic. Verified identical to FastF1's native `Stint` column on Bahrain 2024 R VER (SOFT 1–17, HARD 18–37, SOFT 38–57). `compute_stint_metrics` fits `LapTimeS ~ TyreLife` per stint with `np.polyfit(deg=1)` after dropping the first lap of each stint (out-lap) and pit-in laps; guards `len(fit) >= 3` and returns NaN for the lap-1-pit edge case. Two surprises: (1) HARD median DegSlope is *negative* in Bahrain (-0.10 s/lap) because fuel burn (≈1.5 kg/lap → ≈0.04 s/lap gain) exceeds hard tyre deg — sanity check is SOFT minus HARD positive, not SOFT positive on its own. (2) Plot titles rendered as `â€"` mojibake on first run — em-dashes in the notebook source were UTF-8 bytes that got mis-decoded as cp1252 (â + € + " sequence) during the initial Write; replaced the 3-char sequence with ASCII hyphens and re-executed. Block 4 charts saved to `assets/screenshots/wk2-bahrain-stints.png` (top-5 horizontal timeline, broadcast-style) and `assets/screenshots/wk2-deg-curves.png` (DegSlope box-plot per compound) — not `docs/screenshots/` per the plan because `docs/` is gitignored repo-wide since Wk 1 Sat. Block 5 validation: Saudi 2024 R runs clean with no `StintNumber==0` bugs and no `|DegSlope|>5` fit failures; only one NaN slope per race from a driver pitting on lap 1, which the `min_laps=3` guard handles silently. Day 2 deliverable code is the prototype for Thursday's `src/aris/physics/stint.py` — lift verbatim, add type hints + a `Stint` dataclass, pytest with the VER three-stint case as the golden truth.
- **2026-05-13 (Wed):** Baseline day — the floor Phase 3 must beat is now on the books. Block 1 was a *markdown-only* problem statement in `notebooks/05-sector-baseline.ipynb`, committed before any code (`f1f88d0`) — forces the inputs / not-inputs / metric / split to be written out instead of assumed. Block 2: `moving_average_baseline(laps_df, window=3)` predicts lap N's `LapTimeS` from a per-stint `.shift(1).rolling(window).mean()` after sorting on `[Driver, StintId, LapNumber]` and grouping on `[Driver, StintId]` — three guards (sort, groupby, shift-before-rolling) together kill the lap-N-into-its-own-prediction leak. Sanity check: `n_stints * window` = `45 * 3 = 135` expected NaN preds on Bahrain 2024 R; got exactly 135. Bahrain MAE = **0.369 s** on 908 laps (`c70abf2`). Block 3 lifted the scoring math out of the notebook into `src/aris/eval/scoring.py` — `mae`, `rmse`, `per_race_mae`, pure NumPy, all three raise `ValueError` on shape mismatch and on any NaN slipping through; the notebook now re-computes through the module and asserts the float-precision match (`18d1abe`). Added `pythonpath = ["src"]` to `[tool.pytest.ini_options]` so tests find `aris.*` without an editable install (Day 4 still does `pip install -e .`). Block 4: looped over the 8 cached races, concatenated `(y_true, y_pred, race_id)`, scored per-race and overall. Numbers: Bahrain 0.369, Saudi 1.117, Australia 1.756, Japan 0.618, Miami 2.511, '23 Bahrain 1.116, Belgium 0.744, Abu Dhabi 0.367 — overall **1.090 s** across 6391 laps (`8c2378e`). Australia + Miami pull the average up because both had red-flag / SC laps that we aren't yet filtering on `TrackStatus` (Day 5 picks that up). Had to whitelist `results/wk2-baseline-mae.csv` + `results/wk2-window-sweep.csv` in `.gitignore` — `results/*` was globally ignored and the plan explicitly says commit this CSV. Block 5: swept `window ∈ {1, 2, 3, 5, 7}`. MAEs were 1.129 / 1.088 / 1.090 / 1.134 / 1.150 — w=2 is the empirical minimum, w=3 within 0.002 s. Picked **w=2** (smaller window = fewer leading NaN per stint, identical predictive power) and wrote the floor line into the CSV: `# BASELINE: window=2, MAE=1.088 s, 8 races (6734 laps), leakage-free per-stint shift.` Plot saved to `assets/screenshots/wk2-baseline-window-sweep.png` (the plan's path `docs/screenshots/` is gitignored, same as Wk 2 Tue's deg-curves chart) (`e374f31`). Block 6: 15 pytest cases in `tests/test_scoring.py` covering identical/shifted/mixed residuals, list-accepting inputs, shape mismatch, NaN in either side, empty arrays, RMSE > MAE on a single-outlier vector, `per_race_mae` returning a dict, single-race edge case — all green in 0.22 s. Friction: `.venv` had no `pip` (uv-managed) so `python -m pip install pytest` died — `uv pip install pytest jupyter nbconvert ipykernel --python .venv/Scripts/python.exe` is the right shape. Ran `nbconvert --execute --inplace` on `05-sector-baseline.ipynb` so cell outputs (table, plot, MAE prints) are pinned in the committed file. The 1.088 s number is what Phase 3's residual models have to beat, on the same 8 races, with the same scoring function — anything else is a moved goalpost.
- **2026-05-14 (Thu):** Notebook-dump → package day. Repo now installs as `aris` and CI gates every push. Block 1: added `numpy`, `pandas`, `matplotlib`, `fastf1` to `[project] dependencies` (was empty — pyproject existed since Wk 1 with build backend + packaging config already correct) and `jupyterlab`, `nbconvert` to the dev extra; `uv pip install -e .` succeeded, `python -c "import aris; print(aris.__file__)"` resolves to `src/aris/__init__.py` from any cwd (`7755730`). Block 2: created `src/aris/physics/stint.py` — lifted `detect_stints` + `summarise_stints` + `compute_stint_metrics` verbatim from `notebooks/04-stint-analysis.ipynb`, added a frozen `Stint` dataclass with `(driver, stint_id, compound, start_lap, end_lap, num_laps, median_pace_s, deg_slope_s_per_lap | None)` and a `stints_from_metrics(metrics_df) -> list[Stint]` materialiser; NaN slope → `None` is handled at the boundary so consumers never see NaN (`1c31708`). Block 3: `src/aris/eval/baseline.py` for `moving_average_baseline`; `tests/test_stint.py` (10 cases: detect_stints column shape, two stints per driver, first-lap-is-compound-change, six rows out of compute_stint_metrics, median pace within ±0.01s of analytic answer, slope recovers the synthetic 0.05 s/lap gradient exactly, <3-lap stint → NaN slope, `Stint.length == num_laps`, NaN slope materialises to `None`, filter_clean_laps drops pit-in + pit-out laps) and `tests/test_baseline.py` (5 cases: first `window` laps NaN per stint, constant stint predicts the constant, `window=1` reduces to previous lap, window > stint length yields all-NaN, no leakage across stints). 30/30 green in 0.85s. Wired up `[tool.ruff] extend-exclude = ["notebooks", "learning", ".venv", "fastf1_cache"]` because ruff was lighting up E501s on cell outputs and existing notebook markdown — exploratory notebooks aren't a CI gate. Cleaned `scripts/wk2_day3_block4.py` + `wk2_day3_block5.py` (import order, unused `rid` → `_rid`, long line broken into a label var) so `ruff check .` is clean (`952bc6e`). Block 4: refactor pass replaced inline `detect_stints` + `compute_stint_metrics` cells in `04-stint-analysis.ipynb` and the inline `detect_stints` + `filter_clean_laps` + `moving_average_baseline` cells in `05-sector-baseline.ipynb` with one-line imports from `aris.physics.stint` and `aris.eval.baseline` — used `scripts/refactor_wk2_notebooks.py` (json surgery, in-place) so the edit is reproducible (`ad85691`). Re-execution was blocked: FastF1's `get_event_schedule(...)` raised `ValueError: Failed to load any schedule data.` — the FastF1 backends + Ergast fallback were both unreachable from this machine. The moved functions are byte-identical to the previous inline cells, so notebook outputs can't drift; flagged for re-execution on a network-clean run. Block 5: `.github/workflows/ci.yml` runs `uv sync --extra dev → ruff check . → pytest -v` on push/PR to main, ubuntu-latest, Python 3.11; first push went green in 13s with no iteration (had the lockfile + pyproject pinned correctly the first time). Generated `uv.lock` (131 packages resolved) and committed alongside the workflow (`7644cfc`). Added the CI status badge to README directly under the `# ARIS` heading (`6bee716`). Friction: (1) `uv pip install -e .[dev]` originally timed out fetching `matplotlib` from pypi — fell back to `uv pip install -e .` and the deps that were already in `.venv` from Wk 1 carried the import surface; the dev extras still aren't reinstalled but `nbconvert`/`jupyterlab` were already there from earlier weeks. (2) The earlier failed sync left `requests/`, `idna-3.13.dist-info`, `urllib3/`, `certifi/`, `charset_normalizer/` in a half-uninstalled state (empty `requests/` directory with only `__pycache__` inside) — `requests_cache.backends.base` then failed with `ImportError: cannot import name 'Request' from 'requests' (unknown location)` and bricked any FastF1 call. Fixed by deleting the corrupt site-packages dirs by hand and running `uv pip install --reinstall requests urllib3 idna certifi charset-normalizer` with `UV_LINK_MODE=copy` to dodge the OneDrive hardlink lock. Lesson: on Windows-under-OneDrive, `UV_LINK_MODE=copy` should be the default — hardlink mode hits `os error 5` whenever OneDrive has a handle open on a `.dist-info/licenses` dir. Block 6: BUILD-LOG entry (this one). Branch protection on `main` requires the GitHub UI — flagged to user, not done from here.
- **2026-05-15 (Fri):** Root-caused yesterday's `Failed to load any schedule data` blocker and got the moved-to-package notebooks re-executing clean. Walked it from `fastf1.get_event_schedule(...)` down through `requests_cache.serializers.cattrs.CattrStage.dumps` → `attrs.resolve_types` → `typing.get_type_hints(Response)` and watched the last call die with `NameError: name 'RequestsCookieJar' is not defined`. `requests 2.34.2` annotates `Response.cookies: 'RequestsCookieJar'` and `Response.connection: 'HTTPAdapter'` as forward-ref strings but never imports those names into `requests.models`, so `get_type_hints` can't resolve them and fastf1 surfaces the failure as a generic "no schedule" — wrong-layer error message, ate ~90 min before I stopped trusting the top of the traceback. Wrote `src/aris/_compat.py` with an `apply()` that monkey-patches `requests.models.RequestsCookieJar` and `requests.models.HTTPAdapter` from their real homes (`requests.cookies`, `requests.adapters`); deliberately no `requests`/`requests-cache`/`cattrs` behaviour changes, just makes the forward refs evaluable. Wired `apply()` into `src/aris/__init__.py` so any notebook or script that does `import aris` is safe before touching fastf1 (`5361b53`). Same commit also fixed nb03 drill 2: cell 22 was *still* hitting the `Position_x`/`Position_y` collision because the earlier fix lived only in the merge mechanics block — re-issued the `Position → FinishPosition` rename on the results frame before the merge and trimmed the column selection to match (Tuesday's "won't bite twice" comment didn't age well: same footgun, different cell). Added `import aris` to the imports cell in `04-stint-analysis.ipynb` (`63c4683`) and `05-sector-baseline.ipynb` (`5ad549e`) — that single line is what activates the shim — and re-executed both notebooks top-to-bottom from a fresh kernel. Stored stale error outputs from yesterday's failed runs cleared in the same diffs. nb05 dropped from 1790 lines of stored output to 427 (heavy reduction because the previous output was mostly traceback noise from the half-broken re-execution attempts). Six diagnostic scripts (`scripts/inspect_cache.py`, `scripts/nb_dump_cell.py`, `scripts/nb_dump_outputs.py`, `scripts/nb_show_errors.py`, `scripts/nb_show_mojibake.py`, `scripts/fix_wk2_notebooks.py`) written along the way — left untracked since they were single-use debugging aids, not pipeline code. The mojibake script caught a second bug while I was there: nb04 markdown cells had `â†'`, `â€"`, `â‰ˆ` triples (the same cp1252-on-UTF-8 mis-decode that hit nb04's plot titles on Tuesday) — replaced with `→`, `–`, `≈`. Lesson: when a top-level error message names the wrong layer (fastf1 reporting "no schedule" for a downstream cattrs/typing failure), the only honest way out is `pdb` at the lowest call site, not pattern-matching against past blockers. Wk 2 retro deferred to tomorrow.
- **2026-05-16 (Sat):**
- **2026-05-17 (Sun):** *off*

**Weekly retro (Wk 2):**

**Phase 1 retrospective:**

- Tag shipped:
- MAE / metric snapshot:
- What I'd change:

---

## Phase 2 — Postgres ingest + Streamlit + cloud deploy (Weeks 3–4, May 18 – May 31)

### Week 3 (May 18 – May 24)

- **2026-05-18 (Mon):**
- **2026-05-19 (Tue):**
- **2026-05-20 (Wed):**
- **2026-05-21 (Thu):**
- **2026-05-22 (Fri):**
- **2026-05-23 (Sat):**
- **2026-05-24 (Sun):** *off*

**Weekly retro (Wk 3):**

### Week 4 (May 25 – May 31)

- **2026-05-25 (Mon):**
- **2026-05-26 (Tue):**
- **2026-05-27 (Wed):**
- **2026-05-28 (Thu):**
- **2026-05-29 (Fri):**
- **2026-05-30 (Sat):**
- **2026-05-31 (Sun):** *off*

**Weekly retro (Wk 4):**

**Phase 2 retrospective:**

- Tag shipped: `v0.2-pipeline`
- Live URL:
- LinkedIn post #2 link:
- What I'd change:

---

## Phase 3 — Lap-time predictor (Weeks 5–7, Jun 1 – Jun 21)

### Week 5 (Jun 1 – Jun 7) — leakage tripwire + bicycle model + Brunel WhatsApp

- **2026-06-01 (Mon):**
- **2026-06-02 (Tue):**
- **2026-06-03 (Wed):**
- **2026-06-04 (Thu):**
- **2026-06-05 (Fri):**
- **2026-06-06 (Sat):**
- **2026-06-07 (Sun):** *off*

**Weekly retro (Wk 5):**

### Week 6 (Jun 8 – Jun 14) — tire degradation curve

- **2026-06-08 (Mon):**
- **2026-06-09 (Tue):**
- **2026-06-10 (Wed):**
- **2026-06-11 (Thu):**
- **2026-06-12 (Fri):**
- **2026-06-13 (Sat):**
- **2026-06-14 (Sun):** *off*

**Weekly retro (Wk 6):**

### Week 7 (Jun 15 – Jun 21) — residual ML + conformal calibration

- **2026-06-15 (Mon):**
- **2026-06-16 (Tue):**
- **2026-06-17 (Wed):**
- **2026-06-18 (Thu):**
- **2026-06-19 (Fri):**
- **2026-06-20 (Sat):**
- **2026-06-21 (Sun):** *off*

**Weekly retro (Wk 7):**

**Phase 3 retrospective:**

- Tag shipped: `v0.3-predictor`
- MAE on held-out (5 races): floor < 1.0 s / target < 0.7 s / stretch < 0.5 s →
- Conformal 90% empirical coverage:
- Brunel Racing reply status:
- LinkedIn post #3 link:
- What I'd change:

---

## Phase 4 — Counterfactual simulator (Weeks 8–9, Jun 22 – Jul 5)

### Week 8 (Jun 22 – Jun 28) — perturbation API

- **2026-06-22 (Mon):**
- **2026-06-23 (Tue):**
- **2026-06-24 (Wed):**
- **2026-06-25 (Thu):**
- **2026-06-26 (Fri):**
- **2026-06-27 (Sat):**
- **2026-06-28 (Sun):** *off*

**Weekly retro (Wk 8):**

### Week 9 (Jun 29 – Jul 5) — what-if Streamlit page

- **2026-06-29 (Mon):**
- **2026-06-30 (Tue):**
- **2026-07-01 (Wed):**
- **2026-07-02 (Thu):**
- **2026-07-03 (Fri):**
- **2026-07-04 (Sat):**
- **2026-07-05 (Sun):** *off*

**Weekly retro (Wk 9):**

**Phase 4 retrospective:**

- Tag shipped: `v0.4-counterfactual`
- Demo screenshot ("lift 30 m T7 → +0.18 s"):
- LinkedIn post #4 link:

---

## Phase 5 — Always-on loop + tiered ticks + MC + MATLAB start (Weeks 10–11, Jul 6 – Jul 19)

### Week 10 (Jul 6 – Jul 12)

- **2026-07-06 (Mon):**
- **2026-07-07 (Tue):**
- **2026-07-08 (Wed):**
- **2026-07-09 (Thu):**
- **2026-07-10 (Fri):**
- **2026-07-11 (Sat):**
- **2026-07-12 (Sun):** *off*

**Weekly retro (Wk 10):**

### Week 11 (Jul 13 – Jul 19) — MC slim layer + MATLAB port begins

- **2026-07-13 (Mon):**
- **2026-07-14 (Tue):**
- **2026-07-15 (Wed):**
- **2026-07-16 (Thu):**
- **2026-07-17 (Fri):**
- **2026-07-18 (Sat):**
- **2026-07-19 (Sun):** *off*

**Weekly retro (Wk 11):**

**Phase 5 retrospective:**

- Tag shipped: `v0.5-always-on`
- Loop cadence achieved: 5 s / 15 s fallback?
- Event-driven recompute latency:
- LinkedIn post #5 link:

---

## Phase 6 — LLM narration + MATLAB validation finish (Weeks 12–13, Jul 20 – Aug 2)

### Week 12 (Jul 20 – Jul 26)

- **2026-07-20 (Mon):**
- **2026-07-21 (Tue):**
- **2026-07-22 (Wed):**
- **2026-07-23 (Thu):**
- **2026-07-24 (Fri):**
- **2026-07-25 (Sat):**
- **2026-07-26 (Sun):** *off*

**Weekly retro (Wk 12):**

### Week 13 (Jul 27 – Aug 2)

- **2026-07-27 (Mon):**
- **2026-07-28 (Tue):**
- **2026-07-29 (Wed):**
- **2026-07-30 (Thu):**
- **2026-07-31 (Fri):**
- **2026-08-01 (Sat):**
- **2026-08-02 (Sun):** *off*

**Weekly retro (Wk 13):**

**Phase 6 retrospective:**

- Tag shipped: `v0.6-narrated`
- `aris-matlab-validation` repo link:
- LinkedIn post #6 link:

---

## Phase 7 — Eval + conformal report + strategy backtest + demo (Weeks 14–15, Aug 3 – Aug 16)

### Week 14 (Aug 3 – Aug 9)

- **2026-08-03 (Mon):**
- **2026-08-04 (Tue):**
- **2026-08-05 (Wed):**
- **2026-08-06 (Thu):**
- **2026-08-07 (Fri):**
- **2026-08-08 (Sat):**
- **2026-08-09 (Sun):** *off*

**Weekly retro (Wk 14):**

### Week 15 (Aug 10 – Aug 16) — demo video + Replay mode + HF Space

- **2026-08-10 (Mon):**
- **2026-08-11 (Tue):**
- **2026-08-12 (Wed):**
- **2026-08-13 (Thu):**
- **2026-08-14 (Fri):**
- **2026-08-15 (Sat):**
- **2026-08-16 (Sun):** *off*

**Weekly retro (Wk 15):**

**Phase 7 retrospective:**

- Tag shipped: `v1.0-shipped`
- Demo video (YouTube unlisted):
- HF Space link:
- Strategy backtest report link:
- LinkedIn post #7 link:
- Final eval numbers (MAE / coverage / hit-rate):

---

## Phase 8 — Placement applications prep (Weeks 16–17, Aug 17 – Aug 31)

### Week 16 (Aug 17 – Aug 23)

- **2026-08-17 (Mon):**
- **2026-08-18 (Tue):**
- **2026-08-19 (Wed):**
- **2026-08-20 (Thu):**
- **2026-08-21 (Fri):**
- **2026-08-22 (Sat):**
- **2026-08-23 (Sun):** *off*

**Weekly retro (Wk 16):**

### Week 17 (Aug 24 – Aug 31) — alumni outreach + mock interviews

- **2026-08-24 (Mon):**
- **2026-08-25 (Tue):**
- **2026-08-26 (Wed):**
- **2026-08-27 (Thu):**
- **2026-08-28 (Fri):**
- **2026-08-29 (Sat):**
- **2026-08-30 (Sun):** *off*
- **2026-08-31 (Mon):**

**Weekly retro (Wk 17):**

**Phase 8 retrospective:**

- Tag shipped: `v1.0-placement-ready`
- CV final link:
- Cover-letter templates count:
- Alumni messages sent:
- Mock interviews completed:
- Long-form posts (LinkedIn #8, #9):

---

## Year 2 — Sustain (Sept 2026 onward)

Monthly entries only. New artefact = new entry. No filler.

- **2026-09:**
- **2026-10:**
- **2026-11:** *placement applications fired*
- **2026-12:**
- **2027-01:**
- **2027-02:**
- **2027-03:**
- **2027-04:**
- **2027-05:**

---

## Final retrospective (Sept 2026 — written when ARIS v1.0 ships)

*Filled out the week after v1.0-placement-ready is tagged. Honest answers only — this is the document I'll re-read before every interview.*

- **What I shipped:**
- **What I cut:**
- **What broke that I didn't expect:**
- **Single best technical decision:**
- **Single worst technical decision:**
- **What I'd build differently if I started Day 1 again:**
- **The 30-second pitch I now lead with:**

