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
- **2026-05-16 (Sat):** *missed.* Day 6 (tag `v0.1-foundation`, Wk 2 retro, Wk 3 plan, LinkedIn decision) did not happen on the calendar day. Repulled into Mon May 18 as backlog — see Wk 3 row.
- **2026-05-17 (Sun):** *off* (kept the rule from last week — no "just one quick fix" Sunday; Mon takes the Sat backlog instead).

**Weekly retro (Wk 2):**

- **Shipped:**
  - Pandas fluency on real F1 data — `03-pandas-deep-dive.ipynb` Q1/Q2/Q3 + merge drills (`672ebab`); kaggle-pandas speedrun scaffolded (`069aa61`); James Powell ≈75 min covered Day 1.
  - Stint detection + degradation pipeline — `04-stint-analysis.ipynb` matched FastF1's native `Stint` column on Bahrain 2024 VER (SOFT 1–17 / HARD 18–37 / SOFT 38–57), DegSlope box-plot for Saudi validation (`0e24344`).
  - Statistical baseline locked in code, not vibes — `moving_average_baseline(window)` in `src/aris/eval/baseline.py`; scoring primitives in `src/aris/eval/scoring.py` (`18d1abe`, `952bc6e`). Per-race CSV in `results/wk2-baseline-mae.csv`, window-sweep CSV in `results/wk2-window-sweep.csv`.
  - Repo crossed from notebook-dump to **package** — `pip install -e .` works, `from aris.physics.stint import detect_stints` resolves; `Stint` dataclass with `(driver, stint_id, compound, start_lap, end_lap, num_laps, median_pace_s, deg_slope_s_per_lap | None)` (`7755730`, `1c31708`).
  - CI gate live — `.github/workflows/ci.yml` runs ruff + pytest on push/PR to main; green badge in README (`7644cfc`, `6bee716`); 30/30 tests pass cold-clone on Mon Day 6 Block 1.
  - Root-caused the `requests 2.34.2` × `requests-cache`/`cattrs` forward-ref bug — `src/aris/_compat.py` monkey-patches `RequestsCookieJar` + `HTTPAdapter` into `requests.models` before `typing.get_type_hints` is called, fixing the misleading "Failed to load any schedule data" surface error (`5361b53`).
  - `v0.1-foundation` tag pushed (`5bb8a03`/Block 2 above), Phase 1 closed.
- **Slipped:**
  - **Sat May 16 missed entirely** — Day 6 backlog moved to Mon May 18 (this row + the Mon row in Wk 3 below).
  - GitHub Release page (UI form on github.com/AnassNadeem/ARIS/releases/new) — flagged to user.
  - `docs/planning/ARIS-Tracker.xlsx` Wk 2 row not updated — binary file, manual edit.
  - LinkedIn post #1 — deferred (see Block 6 below; criterion-4 failed: posting on a backlog day is not "in flow").
  - Plan called `scripts/run_baseline_all_races.py`; actual file is `scripts/wk2_day3_block4.py` — flagged for rename in Wk 3.
- **Numbers on the board:**
  - **Baseline MAE = 1.088 s** at `window=2`, 6734 laps across 8 races (`window=2` is the floor Phase 3 must beat; `window=3` was within 0.002 s at 6391 laps and `window=1` was 1.129 s).
  - Per-race spread: best 0.367 s (Abu Dhabi '23), worst 2.511 s (Miami '24 — red-flag/SC laps not yet `TrackStatus`-filtered).
  - **Tests: 30/30 green** in 21.71 s cold-clone, 0.85 s warm (test_baseline 5, test_scoring 15, test_stint 10).
  - **CI:** first push green in 13 s, no iteration; runs on `ubuntu-latest` / py3.11 / `uv sync --extra dev → ruff → pytest`.
  - **35 commits this week** (Wk 1 carried 4-day cold start; Wk 2 is the cadence the rest of the project needs).
- **Changes for Wk 3:**
  - Calendar-day discipline — Sat slipping is allowed; Sat being completely silent is not. If a day looks dead by 18:00, the BUILD-LOG entry that day says "didn't ship" with one sentence on why, not nothing.
  - Promote `wk2_day3_block4.py` into the package as `aris.eval.run_baseline_all_races` (or similar) and add a `python -m aris.eval.baseline_all` entry point — the plan named a script that doesn't exist by that name, that's a real fingerprint of "exploratory script never got promoted."
  - Add `TrackStatus` filtering in Wk 3 ingest before the baseline gets recomputed against the Postgres-backed corpus — Miami and Australia together cost ~0.4 s of overall MAE.
  - Cloud deploy (Streamlit Community Cloud) is hard-blocked for Wk 3 Day 5 (Fri May 22). Do not let it slide into Sat.

**Phase 1 retrospective:**

- Tag shipped: **`v0.1-foundation`** on commit `99833f5` (Mon 2026-05-18, Sat May 16 backlog).
- MAE / metric snapshot: **baseline MAE = 1.088 s** at `window=2` across 8 races / 6734 laps; **scoring functions live in `src/aris/eval/scoring.py`** so Phase 3 residual models are scored on the identical `mae(y_true, y_pred)` call — no moved goalpost.
- What I'd change: stop letting the BUILD-LOG carry a one-week lag in honest "didn't do it" entries — the Sat blank cell only got marked "missed" two days late, on Mon.

**Block 4 (Phase doc tick):** opened `docs/planning/ARIS-PHASES-WEEKLY-PLAN.md` and ticked the boxes that actually shipped — leaving un-ticked everything that slipped, with a one-line annotation explaining why. Phase 1 Wk 1: 3/6 ticked (initial commit, NumPy basics, LOG); 3/6 un-ticked (Boot.dev OOP — substituted by direct pandas/FastF1 work; daily commit streak — four-day cold start at week open broke it; LinkedIn post #1 — deferred to Wk 3 Sat, see Block 6 below). Phase 1 Wk 2: 5/7 ticked (uv add, FastF1 pull, lap-time plot, statistical baseline + scoring stub, `v0.1-foundation` tag); 2/7 un-ticked (Boot.dev/numpy carry-over, James Powell pandas tutorials — partial at ~75 min of 120). Tracker spreadsheet (`ARIS-Tracker.xlsx`) is a binary file — **flagged to user** to update the Wk 2 row (hours, commits, deliverables, blockers) by hand. Note: `docs/` is repo-wide gitignored (since Wk 1 Sat — same reason screenshots live in `assets/`), so the phases-doc tick edit is **local-only** on this machine; the git commit for Block 4 carries only the BUILD-LOG entry, not the ticked phases-doc itself. Decision deferred to user: either keep `docs/` private (planning material stays off-repo) or unignore `docs/planning/` selectively so the ticked source-of-truth is in version control going forward.

**Block 5 (Wk 3 detailed plan):** appended Wk 3 (May 18–24) to `docs/planning/ARIS-WEEKLY-DETAILED-PLANS.md` — same shape as Wk 1/2 (theme + hub reference + carry-overs + deliverables + what we're NOT doing + why-this-shape + cadence note + Days 1–6 hour blocks + self-check). Theme: **Postgres 16 in Docker + idempotent FastF1 ingest + Streamlit skeleton + first public URL on Streamlit Community Cloud.** Cadence-honest move: Mon May 18 is recorded as Day 1 but the day is openly absorbed by the Wk 2 backlog (this entry) with only a 60-min Block 8 reserved for `docker-compose.yml` scaffolding tonight; the real ingest work starts Tue. Cloud deploy is hard-blocked Fri May 22 (Day 5) — anything that slips on Tue–Thu eats into Sat's hardening window, never into Fri. Key decision branches written into the plan: (1) raw SQL vs SQLAlchemy ORM — recommendation raw, one paragraph rationale; (2) managed Postgres (Neon free tier) vs static parquet snapshot for the cloud deploy — recommendation Neon, parquet only as a >2 hr eviction fallback. Cross-check designed in: Thu Day 4 Block 3 re-implements the MA(2) baseline as a SQL window query and compares per-race MAE against `results/wk2-baseline-mae.csv` — must match within float precision or the ingest dropped/duplicated a lap and the deploy is blocked. Same `docs/` gitignore constraint as Block 4 — Wk 3 plan is **local-only**; commit carries the BUILD-LOG note describing what was written, not the planning markdown itself.

**Block 6 (LinkedIn post #1 — judgement call): deferred to Wk 3 Sat (May 23).** Ran the four-criterion gate from the plan: (1) `v0.1-foundation` tag pushed ✓ (commit `99833f5`, pushed in Block 2 above); (2) CI green on `main` ✓ (last green run was on `c7b314a`; today's changes are doc-only — Wk 3 first push will re-prove it); (3) README hero "proud-to-send" ✓ for the Bahrain VER plot but **there's no live URL yet** — Phase 2 owns that and the strongest possible v1 post is one with a clickable demo; (4) **in flow, not catching up — fails.** Today is by definition a Sat backlog day; posting an announcement on the day you're closing out a slipped Saturday is exactly the "mid-recovery" failure mode the plan calls out. The penalty for waiting one week is zero; the penalty for posting now and then needing to follow up with "and here's the actual public URL" five days later is real. Defer to Wk 3 Sat (May 23) when the Streamlit Cloud URL is live — that's a strictly stronger first post (announcement + working public artifact in the same message). No `docs/social/linkedin-post-01-final.md` draft today.

**Block 7 (close the week):** Wk 2 closed. Saturday's full backlog landed across 7 commits today — `8e346f4` (backlog header), `99833f5` (cold-clone check + script fix), `5bb8a03` (`v0.1-foundation` tag), `5b7b1e5` (Wk 2 + Phase 1 retro), `999f457` (phase doc tick, local), `46aa789` (Wk 3 plan, local), `53dce89` (LinkedIn deferred), plus this Block 7 commit. Each block its own commit so the graph reads as the actual close-out sequence, not a single "wk2 done" smash commit. Open obligations carried to the user (cannot be done from the CLI): (a) GitHub Release page for `v0.1-foundation` on github.com/AnassNadeem/ARIS/releases/new with `wk2-bahrain-stints.png` attached; (b) `docs/planning/ARIS-Tracker.xlsx` Wk 2 row update; (c) decision on whether to unignore `docs/planning/` so the ticked phases doc + Wk 3 detailed plan land in version control. Wk 3 starts tomorrow (Tue May 19) per the cadence-compressed plan written in Block 5; today's Block 8 (`docker-compose.yml` scaffold) is **deferred** because the backlog itself took the day — the honest call is to start Wk 3 Day 2 work tomorrow on a clean morning rather than rush the Postgres container into a tired evening. Sun May 17 was kept off (per rule); Sun May 24 will be kept off (same rule). Phone away.

---

## Phase 2 — Postgres ingest + Streamlit + cloud deploy (Weeks 3–4, May 18 – May 31)

### Week 3 (May 18 – May 24)

- **2026-05-18 (Mon):** *Wk 2 Day 6 backlog day.* Saturday's close-out (fresh-clone sanity check → `v0.1-foundation` tag → Wk 2 retro → Phase 1 retro → Phase doc tick → Wk 3 detailed plan → LinkedIn judgement call) is being executed today, before any Wk 3 Day 1 ingest/Postgres work starts. Each Day 6 block ships as its own commit so the log stays honest about *when* each piece landed vs the original plan. **Block 1 (fresh-clone sanity check):** cloned the repo into `C:\Users\anass\OneDrive\Desktop\aris-cleancheck`, `uv venv` + `uv pip install -e .[dev]` resolved 70+ packages clean, `uv run pytest -v` → **30/30 green in 21.71 s** on Windows/py3.11 (test_baseline 5, test_scoring 15, test_stint 10 — same shape as on the dev box). Then ran the multi-race baseline script: it crashed immediately with `NotADirectoryError: Cache directory does not exist!` because `fastf1.Cache.enable_cache(...)` doesn't auto-create the directory and the cold clone has no `fastf1_cache/`. Plan-as-written said "the script should fall back to triggering a FastF1 download" — actually it died before reaching the network at all. Fixed in main repo: added `CACHE.mkdir(parents=True, exist_ok=True)` immediately before `enable_cache(...)`. After `mkdir -p fastf1_cache` in the clean clone, the script ran end-to-end: pulled all 8 race sessions from FastF1/livetiming over the network (~90s), wrote `results/wk2-baseline-mae.csv`, reproduced per-race numbers identical to Wed's run (Bahrain 0.369, Saudi 1.117, Australia 1.756, Japan 0.618, Miami 2.511, '23 Bahrain 1.116, Belgium 0.744, Abu Dhabi 0.367) and **overall MAE 1.090 s across 6391 laps in 8 races** — same float as the cached run, so the cache isn't masking a number. Second honest finding: the plan referenced `scripts/run_baseline_all_races.py` but the actual file is `scripts/wk2_day3_block4.py` (a Day 3 working name that never got renamed); flagging for Wk 3 — should rename or add a thin alias when the script gets promoted into the package. Clean clone deleted after verification. **Block 2 (tag):** `git tag -a v0.1-foundation` on commit `99833f5`; pushed clean (`* [new tag] v0.1-foundation -> v0.1-foundation`). Tag message records that it was tagged 2026-05-18 as Sat May 16 backlog, not back-dated to the calendar Saturday — the commit graph stays truthful. The GitHub Release page (title + `wk2-bahrain-stints.png` attachment) is a manual UI step on github.com — **flagged to user**, not done from here. **Wk 3 Day 1 proper (Block 8 — `docker-compose.yml` scaffold): missed.** The Wk 2 backlog took the whole day; per Block 7's call the Postgres scaffold was deliberately *not* rushed into a tired evening. Day 1's only net-new Wk 3 deliverable did not ship today — picked up Wed May 20 (see below).
- **2026-05-19 (Tue):** *missed.* Wk 3 Day 2 (schema design, `db/schema.sql`, SQLAlchemy wiring) did not happen — no commits, no schema, no DB connection. Logging honestly per the no-backfill rule. This stacks on Mon's deferred Block 8: as of Wed morning Wk 3 has shipped none of its own deliverables and is two days into a five-day compressed week with nothing on the board.
- **2026-05-20 (Wed):** *Catchup day — executed Wk 3 Day 1 two days late.* Picked up the deferred Day 1 scaffold (Block 8) rather than skipping ahead to Day 3's ingest pipeline — the Postgres container has to exist before anything can be ingested into it, so honouring plan order beat chasing the calendar. Wrote `docker-compose.yml` at repo root: one `postgres:16-alpine` service, host port bound to `127.0.0.1:5432` only (never exposed on the LAN), named volume `aris_pg_data` so data survives `down`/`up`, `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` all read from a gitignored `.env`, and a `pg_isready` healthcheck so `docker compose ps` reports `(healthy)` rather than a bare `up`. Added `.env.example` as the committed template plus a real local-dev `.env` (gitignored). Caught a `.gitignore` bug while wiring this: the existing `.env.*` secrets rule was *also* matching `.env.example`, so the template would never have reached the repo — added `!.env.example` to un-ignore it; `git status` then correctly showed `.env.example` tracked and `.env` ignored. Friction: Docker Desktop was not running and did not come up within ~4 min of the first launch attempt (Windows first-launch of a session often needs a manual click-through). Once Docker Desktop was started, retried: `docker compose up -d` pulled `postgres:16-alpine` (~105 MB) and started the container; the `pg_isready` healthcheck went `starting → healthy` in ~15 s, and `docker compose ps` confirms `Up (healthy)` on `127.0.0.1:5432->5432/tcp`. `docker compose config` had already validated the YAML + `.env` substitution cleanly. Block 8's "container starts" bar is met — verified at runtime, not just as config. Container left running for Day 2; `docker compose down` not separately exercised, but the `aris_pg_data` named volume makes a restart a no-op. Honest status: Wk 3 is now ~2 days behind — Day 2 (`db/schema.sql` + SQLAlchemy wiring) and Day 3 (idempotent FastF1 → Postgres ingest) both still owe, so the five-day compressed week must now fit four days of work into Thu–Sat; the Fri May 22 cloud-deploy hard-block is at real risk and is the next thing that cannot slip. Commits today: `9550dd8` (compose scaffold + `.env.example` + `.gitignore` fix), `ba35ac2` (Mon/Tue logged missed), and this BUILD-LOG entry. — **Continued same day — Wk 3 Day 2 (schema design + SQLAlchemy wiring) also executed as catchup.** Five blocks, each its own commit. *Block 1:* `db/SCHEMA-NOTES.md` — one paragraph per table written *before* any SQL; the live design call was `drivers` versioning — chose per-season (`year` column, natural key `(code, year)`) over per-session duplication, because a 3-letter code is reused across seasons by different people and per-session rows would ~20×-inflate the table. That adds a `year` column the Day 1 plan's literal `drivers(driver_id, code, full_name, team)` list didn't carry — a deliberate, documented forward-fix, since Day 3's upsert keys on `(code, year)` regardless. *Block 2:* `db/schema.sql` — `BIGSERIAL` PKs, `TIMESTAMPTZ` dates, `NUMERIC(8,3)` lap/sector times, `session_type` `CHECK`, FKs into `sessions`/`drivers`, three indexes on the laps query path; applied to the container with `docker compose exec -T postgres psql` (no local `psql` install needed — psql runs *inside* the container), `\dt` shows all four tables and `\d laps` confirms columns + indexes + FKs. Natural-key `UNIQUE` constraints deliberately deferred to Day 3 per plan. *Block 3:* `src/aris/io/db.py` — `engine()` (pooled, `pool_pre_ping`, built from `ARIS_DB_URL` loaded from `.env` via `python-dotenv`) and `get_session()`; added `sqlalchemy` / `psycopg[binary]` / `python-dotenv` to project deps and refreshed `uv.lock`; `tests/test_db.py` asserts `SELECT 1` round-trips, `skipif` on `ARIS_DB_URL` so CI (no DB) stays green. *Block 4:* `fetch_laps(session_id, driver_id)` — raw parameterized SQL → DataFrame; the raw-SQL-over-ORM decision is logged in the module docstring (Phase 2 reads are a flat `SELECT … WHERE`, and keeping the executed query identical to what you read matters for Day 4's SQL-vs-pandas baseline cross-check). *Block 5:* throwaway smoke ingest of Bahrain 2024 R — `import aris` activated the Wk2 `_compat` shim, FastF1 loaded the race entirely from the warm cache (no network), and a hand-written script inserted 1 `sessions` row + 20 `drivers` + 57 VER `laps`; `fetch_laps` returned all 57, round-trip clean, VER lap 1 = 97.284 s SOFT stint 1 (matches Wk2's stint analysis). **No schema mistakes surfaced** — the good outcome Block 5 exists to either find or rule out — so the Day 2 schema holds; the scratch script was discarded as planned. Bahrain VER smoke data left in the DB (harmless — Day 3 drops + recreates the schema anyway). Verification: `ruff check src tests` clean, **31/31 pytest green** (30 prior + new `test_db`). Net status: Wednesday May 20 absorbed both Day 1 and Day 2 — Wk 3 is now ~1 day behind, not two; Day 3 (idempotent FastF1 → Postgres ingest) is the only backlog item left before Thu's Streamlit + telemetry day. Day 2 commits: `f287c31` (schema notes), `a277ac4` (`schema.sql`), `40ef29b` (sqlalchemy engine + round-trip test), `8888e9a` (`fetch_laps`), plus this entry.
- **2026-05-21 (Thu):** *Catchup day — executed Wk 3 Day 3 (idempotent ingest) and Day 4 (Streamlit + telemetry + SQL cross-check) back-to-back on the calendar Thursday.* Wednesday May 20 had already absorbed Days 1–2, so Day 3's ingest pipeline still owed; rather than split it across two short sessions it was run end-to-end today ahead of Day 4. Each block its own commit. **Day 3 — Block 1 (natural-key constraints):** added the three natural-key `UNIQUE` constraints to `db/schema.sql` that the idempotent upsert keys on — `uq_sessions_natural (year, round_no, session_type)`, `uq_drivers_natural (code, year)`, `uq_laps_natural (session_id, driver_id, lap_number)`; `telemetry` needs none, its composite PK already *is* its natural key. Dropped the standalone composite laps index from Day 2 — `uq_laps_natural` creates an equivalent index and covers the dashboard's hot query path, so keeping both was redundant. Re-applied the schema to the container (drop-and-recreate, no production data yet); `pg_constraint` confirms all three `u`-type constraints, and `db/SCHEMA-NOTES.md` was updated to match. Commit `18a399f`. **Block 2 (`src/aris/io/ingest.py`):** `ingest_session(year, event, session_type)` loads one FastF1 session and upserts `sessions`/`drivers`/`laps` inside a single `engine().begin()` transaction — any table's failure rolls the whole race back, never a half-ingest. Every `INSERT` is `ON CONFLICT (<natural key>) DO NOTHING`; `DO NOTHING` not `DO UPDATE` because a finished race is immutable. Live decision: `stint` is stored as the compound-change-cumsum `StintId` from `aris.physics.stint.detect_stints`, **not** FastF1's native `Stint` column — Day 4's SQL baseline cross-check partitions on `stint` and must reproduce Wk 2's pandas baseline exactly, so the DB column has to carry the same definition Wk 2 used. NaN/NaT → SQL NULL and numpy scalars → native Python are coerced at the boundary. Smoke test on Bahrain 2024 R: run 1 → +1 session / +20 drivers / +1129 laps, run 2 → +0/+0/+0 — idempotent. Commit `db63b85`; thin CLI `scripts/ingest_session.py` (accepts a round number *or* an event name) commit `78b95e2`. **Block 3 (`tests/test_ingest.py`):** three integration tests — `test_ingest_is_idempotent` (a second ingest is +0/+0/+0), `test_ingest_row_counts` (Bahrain 2024 R = **1129** laps), `test_no_orphan_laps` (every laps row resolves to a real session + driver). Honest row-count note: the test pins to **1129 — the raw, unfiltered FastF1 lap count** — *not* the `908` in `results/wk2-baseline-mae.csv`, which is the post-filter, post-stint-shift count the baseline scored on; the ingest stores every lap, filtering is a read-time concern. Tests marked `integration` and `skipif` on `ARIS_DB_URL` so CI (no Postgres) skips them; marker registered in `pyproject.toml`. Suite **34 passed**. Commit `8a182ef`. **Block 4 (`scripts/ingest_season.py`):** full-season runner — iterates the FastF1 event schedule, ingests each round's race, per-race failures logged and skipped so one network hiccup can't abort the season. Commit `059cae9`. Ran `ingest_season.py 2024` end-to-end: **24 races, 0 failed, +25,475 laps** — 5 from the warm cache, 19 fetched live from FastF1, no failures. Then ingested the 3 cached 2023 races directly (`2023 Bahrain` 1056, `Belgium` 816, `Abu Dhabi` 1157 laps) so all 8 of Wk 2's baseline races are in for Day 4's cross-check. DB now holds **27 sessions, 45 drivers, 29,633 laps**. Day 3: fully shipped, same day. — **Continued same day — Wk 3 Day 4 (Streamlit skeleton + telemetry + SQL baseline cross-check).** Each block its own commit. **Block 1 (Streamlit skeleton):** `apps/streamlit_app.py` — season → race → driver selectboxes feeding an `st.line_chart` of lap time vs lap number, all sourced from Postgres. The three dropdown queries (`fetch_seasons` / `fetch_races` / `fetch_drivers`) went into `aris.io.db` alongside `fetch_laps`, keeping every query the app issues as raw parameterized SQL in one module rather than scattered through the UI; `streamlit` added to project deps. Verified at runtime: server boots headless, `/_stcore/health` returns `ok`, `GET /` → 200. Commits `7e709cc` (db helpers), `96f7565` (app). **Block 2 (telemetry):** the `telemetry` table already existed from the Day 2/3 schema, so this was purely the ingest path — `ingest_session` gained an `include_telemetry` flag and `ingest_session.py` a `--telemetry` flag; `_upsert_telemetry` upserts per-sample rows in 20k-row batches, idempotent on the composite PK. Ran it for Bahrain 2024 R: **+840,934 telemetry samples** (20 drivers, 57 laps) — the plan's ~500k estimate was low. Spot-check: speeds 0–335 km/h and throttle/rpm sane, but **~20 of 840k samples carry garbage gear values** (47, 17, 75 — an F1 car has 8 gears). These are glitched raw FastF1 samples, not an ingest fault, so they were left as faithfully-captured source data and flagged for a Wk 4 telemetry-cleaning pass rather than silently mutated. Commit `812dcac`. **Block 3 (SQL baseline cross-check — the Phase 2 canary):** `db/queries/baseline_ma2.sql` recomputes the MA(2) baseline as a Postgres window query (`ROWS BETWEEN 2 PRECEDING AND 1 PRECEDING`, partitioned by session/driver/`stint`); `scripts/baseline_crosscheck.py` diffs its per-race MAE against `results/wk2-baseline-mae.csv`. **The canary fired on the first run — all 8 races mismatched.** Investigated rather than papered over: `SQL n` was uniformly ~40 laps *higher* than the csv's `n`, ≈1 lap per (driver, stint) group — the signature of a window-size difference, not a dropped lap. Re-running the same SQL at window=3 reproduced the csv **exactly — every race, every MAE to 6 d.p.** — which *proves the ingest is lossless* (no dropped or duplicated lap) and pins the fault elsewhere. Root cause: `results/wk2-baseline-mae.csv` was generated at window=3 (the `wk2_day3_block4.py` dry-run default, 6391 laps) despite its own footer declaring `window=2`, and despite `wk2-window-sweep.csv` recording window=2 as 6734 laps — the Wk 2 artifact was internally inconsistent. Fix: `scripts/recompute_wk2_baseline.py` regenerates the csv at window=2 through the package API (`aris.physics.stint` / `aris.eval.baseline` / `aris.eval.scoring`) — 6734 laps, overall MAE **1.088 s**, now self-consistent with its footer and the sweep. With the corrected csv the cross-check **passes: max abs diff 4.4e-15 s** (machine epsilon) across all 8 races — the SQL-from-Postgres baseline and the pandas-from-FastF1 baseline are the same number. Phase 2's data pipeline is verified end-to-end. Commits `56bf5d6` (csv fix), `3221752` (SQL query), `ee65e41` (cross-check). **Block 4 (Streamlit polish):** subtitle, an About-ARIS sidebar with a README link, and a caption under the chart showing the selected driver/race's MA(2) baseline MAE via a new `db.fetch_driver_ma2_mae` helper (the same window-2 computation scoped to one driver). Commit `290fe93`. **CI fix:** CI runs `ruff check .` repo-wide, which flagged that the notebook helper scripts committed earlier today — `fix_wk2_notebooks.py`, `inspect_cache.py` — carried two long-line and one import-sort violation that had turned `main`'s CI red; fixed by splitting the over-long string literals (notebook content byte-identical) and re-sorting imports, commit `88f3433`. Verification: `ruff check .` clean repo-wide, **34/34 pytest green**. Net status: Wk 3 Days 3 and 4 both shipped today — the idempotent ingest pipeline, the full 2024 season in Postgres, the telemetry schema validated on one race, the Streamlit dashboard running locally, and the Phase 2 canary green. Wk 3 is back on plan order; Friday's hard-blocked cloud deploy is next.
- **2026-05-22 (Fri):** *missed as the cloud-deploy day.* No commits on the calendar Friday; Day 5's hard-blocked deploy window did not get used. The deferred work absorbed Sat morning instead — see the Sat row.
- **2026-05-23 (Sat):** *Day 5 prep + Day 6 close-out, both today.* Day 5's cloud deploy split into local-prep (what I can do) and browser-UI steps (only the user can do); the runbook is now `DEPLOY.md`. **Day 5 prep:** `apps/requirements.txt` mirrors the runtime deps Streamlit Cloud needs (it reads `requirements.txt`, not `pyproject.toml`'s `[project] dependencies` — pyproject extras are silently ignored on Streamlit Cloud and that's the #1 first-deploy bug); `.streamlit/config.toml` for headless server + dark theme; `.streamlit/secrets.toml.example` documents the shape of the secrets blob without committing real values; `apps/streamlit_app.py` gained a six-line `try: if "ARIS_DB_URL" in st.secrets: os.environ.setdefault(...) except (FileNotFoundError, KeyError): pass` shim that runs *before* `from aris.io import db`, so the cloud path reads the URL from Streamlit's secrets pane while local dev unchanged falls through to the gitignored `.env`. First config draft had `enableCORS = false` which Streamlit warned about because XSRF protection is on by default and the two settings are mutually exclusive — dropped the line, kept XSRF (the safer default for a public deploy). `DEPLOY.md` documents every step end-to-end: Neon project creation, the `postgresql://` → `postgresql+psycopg://` + `?sslmode=require` URL rewrite SQLAlchemy needs, a PowerShell one-liner that applies `db/schema.sql` against the remote without needing a local `psql`, the season-ingest command against the remote URL, the Streamlit Cloud secrets pane wiring, the build-log failure modes I expect, and a static-parquet fallback path if Neon eats more than two hours. Commit `66ec25a`. **Day 6 — hardening:** ruff repo-wide clean; **34/34 unit tests + 3/3 integration tests green** (the integration tests skip on CI but ran today with the real Postgres container — idempotency, row-count pin, FK integrity all pass); SQL baseline cross-check **re-run today against the live DB, max abs diff 4.44e-15 s** across all 8 races vs `results/wk2-baseline-mae.csv` (the Phase 2 canary is still green, the ingest hasn't drifted); DB row counts unchanged from Day 4 — **27 sessions / 45 drivers / 29 633 laps / 840 934 telemetry samples**; Streamlit app boots headless on `:8765`, `/_stcore/health → ok`, `GET / → 200` with the new secrets shim falling through cleanly when no secrets file exists. README: bumped "Current phase" from Phase 1 to Phase 2 and added a `Last tag: v0.1-foundation` row with the baseline MAE number — commit `5b91585`. **Day 6 — retro + Wk 4 plan + LinkedIn:** Wk 3 weekly retro written below; Wk 4 detailed plan appended to `docs/planning/ARIS-WEEKLY-DETAILED-PLANS.md` (still local-only — `docs/` is repo-wide gitignored); LinkedIn post #1 deferred again (criterion 1 — public URL — fails because the cloud deploy is prep-only until the user runs the manual UI steps in `DEPLOY.md`); a candidate draft lives at `docs/social/linkedin-post-01-final.md` (local-only) ready to publish the moment the URL goes live. **Open obligation to the user:** the four manual steps in `DEPLOY.md` (Neon project, paste URL into Streamlit Cloud Secrets, click Deploy, verify in incognito). Everything else is scripted.
- **2026-05-24 (Sun):** *off* — same non-negotiable rule. Phase 2 Wk 4 starts Monday rested.

**Weekly retro (Wk 3):**

- **Shipped:**
  - Postgres 16 in Docker locally — `docker-compose.yml` at repo root, `127.0.0.1:5432` bind, healthcheck, named `aris_pg_data` volume (`9550dd8`, Wed catchup).
  - Four-table schema landed and tested — `sessions / drivers / laps / telemetry` in `db/schema.sql` with `BIGSERIAL` PKs, `TIMESTAMPTZ`, `NUMERIC(8,3)` for lap times, FKs into sessions/drivers, three indexes on the laps query path, and the three natural-key `UNIQUE` constraints (`a277ac4`, `18a399f`).
  - SQLAlchemy wiring + raw-SQL read path — `src/aris/io/db.py` with `engine()` + `get_session()` + `fetch_laps` + dashboard dropdown queries; `test_db.py` round-trips `SELECT 1` (`40ef29b`, `8888e9a`, `7e709cc`).
  - **Idempotent FastF1 → Postgres ingest** — `src/aris/io/ingest.py` does `INSERT ... ON CONFLICT (natural_key) DO NOTHING` for every table, all-or-nothing transaction per session, optional `include_telemetry` flag (`db63b85`, `812dcac`). `scripts/ingest_session.py` + `scripts/ingest_season.py` CLI runners (`78b95e2`, `059cae9`). Re-runnable, no duplicates.
  - 2024 season fully ingested + 3 cached 2023 races — **27 sessions, 45 drivers, 29 633 laps, 840 934 telemetry samples** in the local DB (telemetry only for Bahrain 2024 R, validating the schema).
  - **Three integration tests guard the ingest** — `test_ingest_is_idempotent`, `test_ingest_row_counts` (pinned to 1129 raw laps for Bahrain 2024 R), `test_no_orphan_laps` (`8a182ef`). Marked `integration`, skipped on CI (no DB), green when `ARIS_DB_URL` is set.
  - **The Phase 2 canary** — `db/queries/baseline_ma2.sql` re-implements the MA(2) baseline as a Postgres `LAG/OVER` window query; `scripts/baseline_crosscheck.py` diffs the per-race SQL MAE against `results/wk2-baseline-mae.csv` (`3221752`, `ee65e41`). Caught a real Wk 2 artifact bug on first run: the csv had been generated at `window=3` despite its own footer declaring `window=2` — `scripts/recompute_wk2_baseline.py` regenerated it through the package API and the cross-check now passes at **4.44e-15 s max abs diff** across all 8 races (`56bf5d6`).
  - Streamlit dashboard skeleton — `apps/streamlit_app.py` with season → race → driver dropdowns + lap-time chart sourced from Postgres + an MA(2) MAE caption (`96f7565`, `290fe93`). Boots local on `localhost:8501`.
  - **Streamlit Cloud deploy prep, runbook landed** — `apps/requirements.txt`, `.streamlit/config.toml`, `.streamlit/secrets.toml.example`, `st.secrets` shim in `apps/streamlit_app.py`, `DEPLOY.md` with end-to-end PowerShell + browser steps (`66ec25a`).
- **Slipped:**
  - **Cloud deploy itself — the URL is not live.** Fri May 22 (Day 5) was the hard-blocked deploy day and it did not get used — the plan called for that day to be entirely about pushing the smallest possible thing through Neon + Streamlit Cloud, and instead the prep landed on Sat. The runbook (`DEPLOY.md`) reduces the remaining work to ~30 min of browser clicks + one PowerShell session, but until the user executes those steps, the "URL someone outside the laptop can open" deliverable is unmet. **This is the headline miss of Wk 3.**
  - LinkedIn post #1 deferred again. Same four-criterion gate: criterion 1 (live URL) fails by definition while the deploy is still prep-only. Wk 4 Sat is the next eligible window.
  - `wk2_day3_block4.py` → `aris.eval.run_baseline_all_races` rename — flagged in Wk 2 retro, not done. Pushed to Wk 4 polish.
  - `TrackStatus` filter on the baseline — same as above, Wk 4. Miami + Australia still cost ~0.4 s of overall MAE because of SC/red-flag laps.
  - GitHub Release page for `v0.1-foundation` — still a UI step that needs the user.
- **Numbers on the board:**
  - **DB:** 27 sessions / 45 drivers / 29 633 laps / 840 934 telemetry samples (telemetry for one race; full population is Wk 4).
  - **Pipeline cross-check:** SQL MA(2) baseline matches the pandas one at **4.44e-15 s max abs diff** across 8 races — the ingest is lossless.
  - **Tests:** 34/34 unit + 3/3 integration green; **CI green** on `main` (last 5 pushes — `5b91585`, `66ec25a`, `f71c2f1`, `88f3433`, `290fe93`).
  - **Commits this week:** 22 on `main` Mon May 18 → Sat May 23 (vs Wk 2's 35; week was honestly 4 work days after the calendar Wk 2 backlog ate Mon and Tue went missed).
  - **Telemetry data quality finding:** ~20 of 840 934 samples carry impossible gear values (47, 17, 75 — the car has 8 gears); flagged as a Wk 4 cleaning pass rather than silently mutated. Faithful to source.
- **Changes for Wk 4:**
  - **Drive the deploy to completion in the first hour of Mon May 25.** The runbook exists; the URL doesn't. Anything that blocks it gets escalated, not deferred again.
  - Add `TrackStatus` filter to the baseline path — re-recompute `results/wk2-baseline-mae.csv` and the SQL canary against it; expect overall MAE to drop ~0.4 s from removing SC/red-flag laps.
  - Promote `scripts/wk2_day3_block4.py` to `aris.eval.run_baseline_all_races` with a `python -m aris.eval.baseline_all` entry point. The Wk 2 retro flagged it, Wk 3 didn't do it, Wk 4 owns it.
  - Sector-breakdown chart on the Streamlit page — the existing `sector_1_s` / `sector_2_s` / `sector_3_s` columns ingest already; the chart is the deliverable for Phase 2 close.
  - `v0.2-pipeline` tag at Wk 4 close, on a commit that includes the live URL in the README, the sector chart deployed, and the SQL canary still green.
  - Telemetry cleaning pass — drop the ~20 garbage-gear samples (or null the gear column on rows where `gear > 8`); the rest of the telemetry surface is intact.

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

