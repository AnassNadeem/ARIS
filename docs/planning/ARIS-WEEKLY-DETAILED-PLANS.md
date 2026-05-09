# ARIS — Weekly Detailed Plans

**Purpose:** Day-by-day, hour-blocked execution doc. Written one week ahead at the end of each previous week. Refers back to [`ARIS-PHASES-WEEKLY-PLAN.md`](./ARIS-PHASES-WEEKLY-PLAN.md) (the hub) for context and reasoning.

**Companion docs:** [`ARIS-FINAL-PLAN.md`](./ARIS-FINAL-PLAN.md) · [`ARIS-EXECUTION-PLAN.md`](./ARIS-EXECUTION-PLAN.md) · [`BUILD-LOG.md`](./BUILD-LOG.md)

**Format:** Each week → each day → time-blocked tasks with exact commands, links, and acceptance criteria. Tick boxes as you go. Anything not ticked at end of day rolls into the next day's first block.

**Cadence:** 6 hrs/day × Mon–Sat = 36 hrs/week. Sunday off (non-negotiable).

---

## Week 1 (May 4 – May 10, 2026) — Day 1 ignition: scaffold, foundations, first signal

**Phase:** 1 — Python foundations + first FastF1 plot
**Hub reference:** `ARIS-PHASES-WEEKLY-PLAN.md` → Phase 1, Week 1
**Theme of the week:** Get the repo public, the toolchain working, daily commit muscle live, and Python/NumPy fluent enough that Week 2 can spend its energy on FastF1 instead of syntax.

**End-of-week deliverables:**
- [ ] `aris` repo public on GitHub, README v0 live, MIT license, `.gitignore`, `pyproject.toml` via `uv init`
- [ ] LOG.md with 6 daily bullets (Mon–Sat) — first row of `BUILD-LOG.md` filled
- [ ] `learning/` folder with committed exercises from CS50P / Boot.dev (≥6 small commits)
- [ ] One Python class hand-written from memory (no doc lookup) — committed under `learning/oop/`
- [ ] One NumPy notebook with broadcasting, slicing, and a small vectorised computation — committed
- [ ] LinkedIn post #1 ("starting ARIS" announcement, no claims of progress) — published end of Sat
- [ ] Daily commit streak: ≥1 commit on each of Mon–Sat (6/6)
- [ ] FastF1 cache pre-warmed (running in background from Week 0; verified working)

**What we are NOT doing this week:**
- Sending the Brunel Racing WhatsApp (moved to Week 5 — needs a working artefact behind it)
- Touching FastF1 plotting (that's Week 2 — Week 1 is foundations)
- Ingesting into Postgres (Phase 2)
- ANY model code (Phase 3)
- Tweeting MAE numbers, accuracy claims, or anything quantitative (no numbers exist yet)

---

### Day 1 — Monday, May 4 (Ignition: 6 hrs)

**Goal of the day:** Repo live, first commit pushed, profile cleaned, LOG.md alive, LinkedIn post #1 drafted (not yet published — publish Saturday once the week has actual movement behind it). End the day with a green commit dot on the GitHub graph.

#### Block 1 — Profile + repo bootstrap (90 min, 09:00 – 10:30)

- [ ] Open `ARIS-PHASES-WEEKLY-PLAN.md`, this file, and `ARIS-Tracker.xlsx`. Close everything else (no Discord, no YouTube tab).
- [ ] Verify Week 0 environment is live (run all four in PowerShell — should all succeed):
  ```powershell
  python --version          # 3.11.9
  uv --version
  git --version
  gh auth status
  ```
  If anything fails → fix that first before continuing. Day 1 does not move until the toolchain works.
- [ ] Open `github.com/AnassNadeem` in browser. Confirm Week 0 profile cleanup landed:
  - NeuroSim references purged
  - ARIS-aligned profile README live (use `PROFILE-README.md` from this repo as source)
  - Photo + London location + one-sentence bio set
  - 2 strongest hackathon repos pinned
- [ ] Create the `aris` repo from terminal:
  ```powershell
  cd "C:\Users\anass\OneDrive\Desktop"
  mkdir aris; cd aris
  gh repo create aris --public --license=mit --description "Always-on race-strategy AI: hybrid physics + ML + LLM, validated on FastF1." --source=. --remote=origin
  uv init --python 3.11
  git add .
  git commit -m "chore: scaffold repo with uv + MIT license"
  git push -u origin main
  ```
- [ ] Confirm the repo is public and renders the (empty) README on GitHub.

#### Block 2 — README v0 + LOG.md + project skeleton (60 min, 10:30 – 11:30)

- [ ] Replace the auto-generated `README.md` with a v0 containing:
  - Project name + one-line pitch (copy from `ARIS-FINAL-PLAN.md` line 6)
  - "Status: Week 1 of 17 — foundations" badge (plain markdown)
  - Roadmap section (4 phases, copied from `PROFILE-README.md`)
  - Stack section
  - Links to `ARIS-EXECUTION-PLAN.md` and `BUILD-LOG.md` (these will 404 until you push them — fine)
- [ ] Create `BUILD-LOG.md` in the repo root by copying `BUILD-LOG.md` from `Planning NeuroSim\` into the `aris` repo. Fill in today's entry: *"Day 1: scaffolded repo, configured uv, pushed initial commit. Toolchain verified."*
- [ ] Create directory skeleton:
  ```powershell
  mkdir src\aris, scripts, tests, notebooks, learning, docs, docs\screenshots
  New-Item -ItemType File src\aris\__init__.py
  New-Item -ItemType File tests\__init__.py
  ```
- [ ] Add `.gitignore` (Python + Jupyter + VS Code + FastF1 cache):
  - `__pycache__/`, `.venv/`, `*.pyc`, `.ipynb_checkpoints/`, `.vscode/`, `fastf1_cache/`, `.env`, `*.parquet`
- [ ] Commit:
  ```powershell
  git add .
  git commit -m "docs: add README v0, BUILD-LOG, project skeleton"
  git push
  ```

#### Block 3 — Python foundations: pick the track (30 min, 11:30 – 12:00)

- [ ] Decide between **Boot.dev Learn Python** (paid trial, gamified, faster) and **CS50P** (free, deeper). Default: **CS50P** unless you've already paid for Boot.dev.
- [ ] Open the chosen track. Bookmark it. Write the URL into `learning/README.md` along with a target completion date (end of Week 1 = OOP + functions covered).
- [ ] Commit `learning/README.md`.

**Lunch — 12:00 – 13:00 (off the laptop, walk)**

#### Block 4 — Python core: control flow + functions (90 min, 13:00 – 14:30)

- [ ] CS50P Week 0 (Functions, Variables) — watch lecture, do shorts.
- [ ] CS50P Week 1 (Conditionals) — watch lecture.
- [ ] As you go, write each problem-set solution into `learning/cs50p/week0/` and `learning/cs50p/week1/`.
- [ ] Commit at end of block:
  ```powershell
  git add learning/
  git commit -m "feat(learning): cs50p week 0-1 problem sets"
  git push
  ```

#### Block 5 — Python core: loops + iteration (90 min, 14:30 – 16:00)

- [ ] CS50P Week 2 (Loops) — lecture + problem set.
- [ ] CS50P Week 3 (Exceptions) — lecture only (problem set goes to Day 2).
- [ ] Hand-write (no IDE autocomplete, no AI) a function `tire_pace_loss(compound, lap_in_stint)` that returns a fake number based on a simple if/elif chain. This is throwaway practice — purpose is to stop fearing function syntax. Save under `learning/handwritten/day1.py`.
- [ ] Commit.

#### Block 6 — LinkedIn draft + LOG.md close (60 min, 16:00 – 17:00)

- [ ] Draft LinkedIn post #1 in `docs/social/linkedin-post-01-draft.md`:
  > Today I'm starting ARIS — an always-on race-strategy system that watches live F1 telemetry, predicts the next decision, and proposes it with a quantified lap-time delta. Built on real FastF1 data, validated on held-out races. Shipping by Aug 31, 2026. Will share the build openly along the way.
  >
  > Repo: github.com/AnassNadeem/aris
- [ ] **Do NOT publish yet.** Publish on Saturday so the post links to a repo that already has a week of commits behind it.
- [ ] Update today's BUILD-LOG entry with: tools verified, repo live (link), CS50P weeks 0–2 done, post #1 drafted.
- [ ] Final commit of the day:
  ```powershell
  git add .
  git commit -m "docs: draft linkedin announcement, log day 1"
  git push
  ```
- [ ] Open GitHub graph — verify ≥3 commits today, all green.

**End-of-day reflection (5 min, written into BUILD-LOG):** What broke? What was slower than expected? Anything to push from today into tomorrow?

---

### Day 2 — Tuesday, May 5 (Python core: data structures + OOP intro)

**Goal:** Finish CS50P weeks 3–5; start OOP. End the day able to write a `class` with `__init__`, methods, and one property without looking it up.

#### Block 1 — Warmup + finish exceptions (60 min, 09:00 – 10:00)
- [ ] CS50P Week 3 problem set — try/except, custom exceptions.
- [ ] Commit `learning/cs50p/week3/`.

#### Block 2 — Libraries + unit tests (90 min, 10:00 – 11:30)
- [ ] CS50P Week 4 (Libraries) — lecture + problem set.
- [ ] CS50P Week 5 (Unit Tests) — lecture + problem set. **This week is high-leverage** — testing discipline carries through every later phase.
- [ ] Commit.

#### Block 3 — File I/O (60 min, 11:30 – 12:30)
- [ ] CS50P Week 6 (File I/O) — lecture + half of problem set.
- [ ] Read CSV / write CSV in pure Python (no pandas yet).

**Lunch — 12:30 – 13:30**

#### Block 4 — OOP first half (90 min, 13:30 – 15:00)
- [ ] CS50P Week 8 (OOP) — lecture only, slowly. Take notes in `learning/notes/oop.md`.
- [ ] Concepts to nail down: `__init__`, `self`, instance vs class methods, `@property`, `@classmethod`, dunder methods (`__str__`, `__repr__`, `__eq__`).
- [ ] Hand-write a `Lap` class: `driver`, `lap_number`, `lap_time_s`, with `__repr__` and a `is_outlap` property. Save under `learning/oop/lap.py`.

#### Block 5 — OOP second half + small project (90 min, 15:00 – 16:30)
- [ ] CS50P Week 8 problem set — implement the class assignments.
- [ ] Extend your `Lap` class: build a `Stint` class that holds a list of `Lap`s, exposes `mean_pace`, `degradation_per_lap` (linear fit slope), and `__len__`.
- [ ] Write `tests/test_stint.py` with pytest — at least 3 tests covering empty stint, single-lap stint, multi-lap deg slope.
- [ ] Run `uv run pytest`. Green? Commit.

#### Block 6 — Log + tomorrow prep (30 min, 16:30 – 17:00)
- [ ] BUILD-LOG entry. Note any concept that felt fragile.
- [ ] Glance at tomorrow's block 1 — make sure NumPy notebook environment is ready (`uv add numpy jupyter`).

---

### Day 3 — Wednesday, May 6 (NumPy: arrays, broadcasting, vectorisation)

**Goal:** End the day able to vectorise a small lap-time computation using NumPy without falling back to Python loops.

#### Block 1 — Install + first arrays (60 min, 09:00 – 10:00)
- [ ] `uv add numpy pandas matplotlib jupyter` in the `aris` repo.
- [ ] Launch `jupyter lab`. Create `notebooks/00-numpy-basics.ipynb`.
- [ ] Read [NumPy quickstart](https://numpy.org/doc/stable/user/quickstart.html) sections "The Basics" + "Shape Manipulation".

#### Block 2 — Indexing, slicing, broadcasting (120 min, 10:00 – 12:00)
- [ ] Work through Sentdex NumPy playlist (first 4 videos, ~90 min).
- [ ] Drill in the notebook: 1D / 2D / 3D arrays, fancy indexing, boolean masking, broadcasting rules.
- [ ] Write 5 micro-exercises directly into the notebook with markdown explanations of what each does:
  1. Generate 100 random lap times centred on 90 s; flag laps >+1.5 σ as outliers.
  2. Compute a moving average of window 3 using slicing (no loop).
  3. Stack two driver stints into a 2D array and compute per-driver mean.
  4. Broadcast a tire-deg correction `+0.05 * lap_in_stint` across a stint.
  5. Use `np.where` to apply different deg multipliers to soft / medium / hard compounds.

**Lunch — 12:00 – 13:00**

#### Block 3 — Random + statistics (60 min, 13:00 – 14:00)
- [ ] `np.random` API, distributions you'll actually use: `normal`, `uniform`, `choice`.
- [ ] Compute mean / std / percentile of a synthetic lap-time array.

#### Block 4 — Vectorisation drill (90 min, 14:00 – 15:30)
- [ ] Write the *naive Python loop* version of "compute predicted lap time = base + fuel_burn × lap + deg × stint_age" for 10 000 laps. Time it with `%timeit`.
- [ ] Re-write as pure NumPy. Time it. Aim for ≥50× speedup. Document the speedup in the notebook.
- [ ] This drill matters — Phase 3 lives or dies on vectorisation discipline.

#### Block 5 — Commit + log (30 min, 15:30 – 16:00)
- [ ] Convert notebook to a clean commit. Commit message: `feat(learning): numpy fundamentals + vectorisation drill`.
- [ ] BUILD-LOG entry: include the Python-vs-NumPy timing numbers.

---

### Day 4 — Thursday, May 7 (Git fluency + project hygiene + first src module)

**Goal:** Stop being scared of `git rebase`, `git restore`, and merge conflicts. Move some learning code into `src/aris/` so the repo starts to look like a real project, not a tutorial dump.

#### Block 1 — Git deep practice (90 min, 09:00 – 10:30)
- [ ] Walk through [Atlassian Git tutorials](https://www.atlassian.com/git/tutorials): branches, merge, rebase, reset, restore.
- [ ] Practice in a throwaway directory: create a branch, commit twice, rebase onto main, force-push to a sandbox repo.
- [ ] Practice on `aris`: create branch `phase-1/numpy-warmup`, move yesterday's notebook to that branch, open a self-PR via `gh pr create`, merge it.
- [ ] Outcome: PR muscle is live. Every future feature lands via PR — even though you're solo.

#### Block 2 — Project structure + first `src/aris/` module (90 min, 10:30 – 12:00)
- [ ] Create `src/aris/timing.py` with a single function: `format_lap_time(seconds: float) -> str` that returns `"1:23.456"` style.
- [ ] Add proper type hints. Add docstring (one line, not three paragraphs).
- [ ] Write `tests/test_timing.py` with 4 cases: zero, sub-minute, multi-minute, edge-case 59.999.
- [ ] Configure `pyproject.toml` so `uv run pytest` finds tests.
- [ ] Add `ruff` config to `pyproject.toml` (`[tool.ruff] line-length = 100`); run `uv run ruff check .` and clean any warnings.

**Lunch — 12:00 – 13:00**

#### Block 3 — Commit conventions + branch protection (60 min, 13:00 – 14:00)
- [ ] Read [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) summary.
- [ ] Write `docs/contributing.md` (3 short sections: branches, commit prefixes, PR-only into main).
- [ ] On GitHub, set branch protection on `main`: require PR, allow force-pushes off, allow direct admin push (you're solo).

#### Block 4 — GitHub Actions: minimal CI (90 min, 14:00 – 15:30)
- [ ] Create `.github/workflows/ci.yml`. On push + PR to main: setup Python 3.11, install `uv`, `uv sync`, run `ruff check .`, run `pytest`.
- [ ] Push, watch the run go green on the Actions tab.
- [ ] If red — fix today, do not move on. Phase 2 will lean on this.

#### Block 5 — pandas first contact (60 min, 15:30 – 16:30)
- [ ] Skim [James Powell's "Pandas From The Ground Up"](https://www.youtube.com/watch?v=dPwLlJkSHLo) first 30 minutes.
- [ ] Make `notebooks/01-pandas-warmup.ipynb`. Load a small CSV (synthetic lap times you generate). Try `groupby`, `agg`, `merge`.
- [ ] Don't push deep — the deep pandas day is Friday.

#### Block 6 — Log + commit (30 min, 16:30 – 17:00)
- [ ] BUILD-LOG entry: today the repo crossed from "tutorial dump" to "project". CI green. PR muscle live.

---

### Day 5 — Friday, May 8 (Pandas in depth + first taste of FastF1)

**Goal:** Pandas fluency to the level you can do `groupby + agg + merge` on driver/lap data without reaching for docs. End the day with FastF1 installed and one race loaded from cache (cache was pre-warmed Week 0).

#### Block 1 — James Powell pandas video, in full (150 min, 09:00 – 11:30)
- [ ] Watch the full 2.5-hour video. Pause to type along.
- [ ] Write notes into `learning/notes/pandas.md` — only the things you didn't already know.
- [ ] Save the working notebook as `notebooks/02-pandas-deepdive.ipynb`.

**Lunch — 11:30 – 12:30**

#### Block 2 — Kaggle pandas micro-course (90 min, 12:30 – 14:00)
- [ ] [Kaggle Pandas course](https://www.kaggle.com/learn/pandas) — speed through the exercises. Don't watch slides; jump to coding.
- [ ] Commit completed exercises into `learning/kaggle-pandas/`.

#### Block 3 — Pandas drill: synthetic lap data (60 min, 14:00 – 15:00)
- [ ] In `notebooks/03-lap-data-pandas.ipynb`, generate a synthetic DataFrame: 5 drivers × 50 laps × 3 sectors. Compute:
  - Mean lap time per driver
  - Best sector per driver
  - Lap-time deltas vs the field median per lap
  - Tire-stint identification using a `compound_change` boolean
- [ ] Plot one driver's lap-time trace with matplotlib (one line, no decoration).
- [ ] Commit.

#### Block 4 — FastF1 install + cache verify (60 min, 15:00 – 16:00)
- [ ] `uv add fastf1`
- [ ] Verify the Week 0 pre-warmed cache exists at `./fastf1_cache/`. If not, point FastF1 at the existing one.
- [ ] In `notebooks/04-fastf1-hello.ipynb`:
  ```python
  import fastf1
  fastf1.Cache.enable_cache('./fastf1_cache')
  s = fastf1.get_session(2024, 'Bahrain', 'R')
  s.load()
  print(s.laps.head())
  ```
- [ ] Confirm laps DataFrame loads. **Do not plot yet** — that's tomorrow's first deliverable, save it for the morning.
- [ ] Commit the notebook with a one-line `print(s.laps.head())` cell only.

#### Block 5 — Log + tee up Saturday (30 min, 16:00 – 16:30)
- [ ] BUILD-LOG: pandas now fluent, FastF1 hello-world running, ready for first real plot tomorrow.

---

### Day 6 — Saturday, May 9 (First FastF1 plot + LinkedIn post #1 publish)

**Goal:** Commit one matplotlib chart of a real driver's real lap times. Publish LinkedIn post #1. Close out Week 1.

#### Block 1 — First real chart (90 min, 09:00 – 10:30)
- [ ] In `notebooks/04-fastf1-hello.ipynb`, plot Verstappen's lap times vs lap number for 2024 Bahrain GP race.
- [ ] Mark in-laps and out-laps differently (use `Lap['PitInTime'] / PitOutTime'] not null`).
- [ ] Title, axis labels, light grid. Black-on-white, no chartjunk.
- [ ] Save the figure to `docs/screenshots/wk1-bahrain-ver-laptimes.png` via `plt.savefig`.
- [ ] Commit notebook + PNG: `feat(notebooks): first fastf1 plot — VER 2024 Bahrain laps`.

#### Block 2 — Second chart: tire stints (90 min, 10:30 – 12:00)
- [ ] Same notebook, new cell: plot tire compound stints for the top 5 drivers as horizontal bars colored by compound.
- [ ] Save as `docs/screenshots/wk1-bahrain-stints.png`.
- [ ] Commit.

**Lunch — 12:00 – 13:00**

#### Block 3 — README update with screenshots (60 min, 13:00 – 14:00)
- [ ] Embed both screenshots in `README.md` under a new section `### Week 1 — first signal`.
- [ ] One-paragraph caption for each: what it shows, what FastF1 endpoint produced it.
- [ ] Commit. **The repo now passes the cold-open test:** anyone landing on it sees an actual chart, not a wall of TODOs.

#### Block 4 — Publish LinkedIn post #1 (30 min, 14:00 – 14:30)
- [ ] Open `docs/social/linkedin-post-01-draft.md`. Copy the text.
- [ ] Attach the Verstappen lap-times PNG.
- [ ] Publish on LinkedIn.
- [ ] Paste the post URL into the BUILD-LOG entry under "LinkedIn post #1 link".
- [ ] **Do not check engagement for the rest of the day.** Phone away.

#### Block 5 — Weekly retro (60 min, 14:30 – 15:30)
- [ ] In `BUILD-LOG.md`, fill in the **Weekly retro (Wk 1)** section:
  - **Shipped:** all checkboxes from this week's deliverables
  - **Slipped:** anything that didn't get ticked
  - **Changes for Wk 2:** what'll move differently next week
- [ ] In `ARIS-PHASES-WEEKLY-PLAN.md`, tick every Week 1 box that landed.
- [ ] Update `ARIS-Tracker.xlsx` with the week's metrics (commit count, hours, blockers).

#### Block 6 — Write Week 2's detailed plan (90 min, 15:30 – 17:00)
- [ ] In **this file** (below the Week 1 section), write the Week 2 detailed plan using the same structure: theme, end-of-week deliverables, Day 1–6 hour-blocked tasks.
- [ ] Reference Phase 1 Week 2 in `ARIS-PHASES-WEEKLY-PLAN.md` as the source of truth.
- [ ] Commit: `docs: add week 2 detailed plan`.

#### Block 7 — Close the week (30 min, 17:00 – 17:30)
- [ ] Final BUILD-LOG entry for Saturday. Tag the repo: `git tag week-1-foundations && git push --tags`.
- [ ] Phone away. Laptop closed. Sunday is genuinely off.

---

### Day 7 — Sunday, May 10 — *OFF*

**Non-negotiable.** No code, no tutorials, no LinkedIn checking. Walk, sleep, see people. Burnout in Week 1 ends the project before Week 5.

---

## Week 1 self-check (run Saturday evening before closing)

If any of these is "no", note it in the retro and adjust Week 2 — don't paper over it.

- [ ] Can I write a Python class with `__init__`, a method, and a `@property` from a blank file without Googling?
- [ ] Can I do `df.groupby('driver').agg({'lap_time': 'mean'}).merge(other_df, on='driver')` without Googling?
- [ ] Can I explain why broadcasting `(N,) + (N, 3)` works but `(N,) + (3, N)` does not?
- [ ] Did I commit on every weekday (Mon–Sat)?
- [ ] Is CI green on `main`?
- [ ] Does the repo have at least one screenshot in the README?
- [ ] Was the LinkedIn post published with a real chart attached, not vapourware?

---

## Week 2 (May 11 – May 17, 2026) — *write at end of Week 1, Day 6 Block 6*

*This section gets filled in on Saturday May 9 during the planning block. Do not pre-write it now — the shape of Week 2 depends on what slipped in Week 1.*
