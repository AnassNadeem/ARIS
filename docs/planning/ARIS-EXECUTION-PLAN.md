# ARIS — Execution Plan (Week-by-Week, May 4 → August 31, 2026)

**Companion to `ARIS-FINAL-PLAN.md`. This is the operational doc — what to learn, where to learn it, what to build, what to commit, and what proves each phase is done.**

**Revised 2026-04-29:** Tier A + Tier B grafts from `ARIS-IMPROVEMENT-SYNTHESIS.md` are baked in. The big four schedule changes:
1. **Brunel Racing hard kill moves Wk6 → Wk3 Day 5.**
2. **Phase 1 cloud deploy moves Wk4 → Wk3** (recovers a week for Phase 2 leakage debugging).
3. **Day 1 of Phase 2 = leakage tripwire commit**, before any model code.
4. **MATLAB/Simulink port of bicycle module = parallel evening work in Wks 11–12** (separate repo `aris-matlab-validation`).
5. **Conformal calibration baked into Phase 6** (~2 days).

---

## Pre-Day-1 setup (T-5 → T-0, April 29 → May 3)

This is the "show up to Day 1 already loaded" checklist. Every minute spent here is a minute not lost on Day 1 to a failed install or a missing account. Aim to finish all of this **by Sunday May 3 evening**. The build starts Monday May 4.

### A. Software to download and install

| Tool | Why | Install command / link | Verify with |
|---|---|---|---|
| **Python 3.11** via pyenv-win | Project runtime; pinned version avoids "works on my machine" later | `winget install pyenv-win` then `pyenv install 3.11.9` | `python --version` → 3.11.9 |
| **uv** (Astral) | Fast modern package manager | `winget install --id=astral-sh.uv` | `uv --version` |
| **Git for Windows** | VCS | [git-scm.com](https://git-scm.com/) | `git --version` |
| **GitHub CLI (`gh`)** | Creates repos, opens PRs from terminal | `winget install GitHub.cli` | `gh auth login` succeeds |
| **VS Code** | Editor | [code.visualstudio.com](https://code.visualstudio.com/) | Opens |
| **VS Code extensions** | Python tooling | Install: Python, Pylance, Ruff, Jupyter, Docker, GitLens, Mermaid Preview, Markdown All-in-One | Listed in Extensions tab |
| **Docker Desktop** | Postgres + reproducible env | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) | `docker run hello-world` works |
| **NVIDIA Game Ready / Studio driver** | RTX 5070 GPU acceleration | nvidia.com — latest for laptop GPU | `nvidia-smi` shows driver + GPU |
| **CUDA Toolkit 12.x** | PyTorch + Ollama GPU | [developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads) | `nvcc --version` |
| **Ollama** | Local LLM runtime | [ollama.com](https://ollama.com/) | `ollama --version` |
| **Llama 3.1 8B q5** | Default LLM throughout | `ollama pull llama3.1:8b-instruct-q5_K_M` (~5.5 GB) | `ollama run llama3.1:8b` answers a prompt |
| **Llama 3.2 3B (fallback)** | If 8B is tight on VRAM | `ollama pull llama3.2:3b` | Same |
| **DBeaver Community** (optional) | GUI for Postgres exploration | [dbeaver.io](https://dbeaver.io/) | Opens, can connect to a local Postgres |
| **OBS Studio** | Phase 7 demo video recording | [obsproject.com](https://obsproject.com/) | Records a screen test |
| **DaVinci Resolve free** OR **CapCut** | Phase 7 video editing | [blackmagicdesign.com/products/davinciresolve](https://www.blackmagicdesign.com/products/davinciresolve) | Opens |
| **MATLAB Online** OR **MATLAB R2024b student license** | Tier B graft — bicycle module port | [matlab.mathworks.com](https://matlab.mathworks.com/) (free Online) or Brunel student license | Logs in / launches |
| **Microsoft Excel** OR **LibreOffice Calc** | `ARIS-Tracker.xlsx` (already provided) | Already installed on Windows / [libreoffice.org](https://libreoffice.org) | Opens the tracker |
| **Notion** OR **Obsidian** (optional) | Personal notes outside repo | Either app | Pick one, don't fiddle |

### B. Accounts to create / verify (free tiers)

- [ ] **GitHub** — `AnassNadeem` profile cleaned (NeuroSim purged, ARIS-aligned README staged for Day 1, hackathon repos pinned)
- [ ] **Streamlit Community Cloud** — sign in with GitHub
- [ ] **Neon.tech** — free Postgres tier (3 GB), get a connection string ready
- [ ] **Hugging Face** — username, will host a Space in Tier C
- [ ] **MathWorks** — for MATLAB Online + Onramp courses
- [ ] **Coursera** — audit Andrew Ng ML Specialization + Michigan Vehicle Dynamics (free audit)
- [ ] **DeepLearning.AI** account (rolls into Coursera)
- [ ] **LinkedIn** — profile updated to mirror new GitHub framing (CS+AI, building ARIS)
- [ ] **Bright Network** — newsletter signup for F1 placement event alerts
- [ ] **Anthropic Console** (defer — only needed if you swap Llama for Claude in Phase 6 polish; free tier exists)
- [ ] **Groq** (Tier C fallback) — free tier for cloud LLM if local Ollama struggles
- [ ] **YouTube** — channel ready for the unlisted demo video
- [ ] **Medium** — for blog posts in Phases 6 and 7

### C. Physical / library / contact prep

- [ ] **Borrow Rajamani — *Vehicle Dynamics and Control* from Brunel library** (Wk5 Day 1 read; reserve early, popular book)
- [ ] **Borrow Milliken — *Race Car Vehicle Dynamics* from Brunel library** (reference for Phase 7 interview prep)
- [ ] **Brunel Racing contact's name + role identified** (so the Day 1 WhatsApp uses the right framing)
- [ ] **Brunel Careers Service** — first 1:1 booked for sometime in May (CV review pre-write)
- [ ] **A friend who'll do mock interviews** — flag them now, don't wait until Wk16

### D. Repo + GitHub profile (DONE BEFORE FIRST COMMIT, ideally May 3)

- [ ] **Profile README rewritten** (NeuroSim removed, ARIS-aligned) — see template below
- [ ] **`aris` repo created**, public, MIT license, empty but with `.gitignore` ready
- [ ] **Pinned repos reordered:** ARIS placeholder #1, 2 strongest hackathon repos #2 and #3, room for `aris-matlab-validation` to land later
- [ ] **Profile photo + location (London, UK) + one-sentence bio** ("CS+AI undergrad building race-strategy AI")

Profile README template (paste into `github.com/AnassNadeem/AnassNadeem/README.md`):

```markdown
### Hi, I'm Anass.
CS with AI @ Brunel University of London. Building **ARIS** —
an always-on race-strategy software system that watches live telemetry,
predicts the next decision, and proposes it with a quantified delta
and a calibrated confidence interval.

Currently targeting 2027 industrial placements in F1 / motorsport
software (Vehicle Performance Software, Strategy Tools).

→ Active project: ARIS · github.com/AnassNadeem/aris (link Day 1)
→ Stack: Python · NumPy/Pandas · scikit-learn · XGBoost · PyTorch ·
   FastF1 · Postgres · Streamlit · Ollama (Llama 3.1) · MATLAB/Simulink
→ Interests: motorsport software, applied ML, race strategy
```

### E. Pre-pull FastF1 cache (overnight, May 3)

FastF1's first-pull from cold cache can take an evening per race. Pre-warm it now so Wk2 doesn't burn a day to "FastF1 told me to slow down":

```bash
uv venv && source .venv/Scripts/activate
uv pip install fastf1
python -c "import fastf1; fastf1.Cache.enable_cache('./fastf1_cache'); \
  s = fastf1.get_session(2024, 'Bahrain', 'R'); s.load()"
```

Repeat for 5–10 race sessions of 2023 + 2024 while you sleep. Day 1 Phase 0 then runs against a warm cache.

### F. The five things on the desk Day 1

1. Rajamani Ch.2 photocopied or library copy beside the laptop.
2. `ARIS-Tracker.xlsx` open in one window.
3. WhatsApp message to Brunel Racing drafted in a text file (send Day 1 morning, not Day 1 evening).
4. The leakage-test pytest scaffold drafted (it's 30 lines — write it Wk4 night, commit it Phase 2 Day 1).
5. This document open as the only plan you read on Day 1.

**Stop rereading the plan. Day 1 is May 4.**

---

## Ground rules

- **GitHub cadence:** ≥4 commits/week, ≥1 commit on Sunday rest day off-limit (Mon–Sat only counts). Empty/whitespace commits don't count. Use real, scoped commits with conventional-commit prefixes (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- **Branch model:** `main` always works. Feature branches `phase-N-thing`. Merge via PR even though you're solo — it builds the muscle and the PR descriptions become your blog material.
- **README discipline:** end of every phase, README gets a new section showing what's now possible, with a screenshot or GIF.
- **Daily log:** `LOG.md` in the repo, one bullet per day. Future-you and any interviewer browsing the repo will love this.
- **Definition of done per phase:** all "Done means" boxes ticked. No skipping forward with "I'll come back to it."

### Tooling baseline (install Week 1, Day 1)
- Python 3.11 via `pyenv` (Windows: `pyenv-win`)
- `uv` for package management (faster than pip, modern)
- VS Code + Python + Pylance + Ruff + Jupyter extensions
- Git + GitHub CLI (`gh`)
- Docker Desktop (for Postgres later)
- A FastF1 cache directory committed to `.gitignore`

### Hardware setup (Day 1, ~2 hours)
Lenovo Legion 5 (AMD Ryzen AI 7, RTX 5070 8GB VRAM, 32GB RAM):
- **NVIDIA drivers** — latest Game Ready / Studio driver from nvidia.com, plus CUDA 12.x toolkit
- **Verify GPU:** `nvidia-smi` should show RTX 5070 + driver version
- **Ollama** — install from [ollama.com](https://ollama.com), pull `llama3.1:8b-instruct-q5_K_M` (~5.5GB on disk, fits 8GB VRAM with headroom)
- **Test Llama locally:** `ollama run llama3.1:8b` → ask "Explain F1 tire degradation in one sentence" → confirms GPU inference works
- **PyTorch with CUDA:** when needed in Phase 2, install via `uv pip install torch --index-url https://download.pytorch.org/whl/cu121` so CUDA is wired up
- **Decision logged in repo:** Llama 3.1 local on GPU is the default LLM throughout the build. Claude API stays out of the build budget.

### GitHub profile cleanup (Day 1, ~1 hour) — DO BEFORE FIRST COMMIT
Current profile at [github.com/AnassNadeem](https://github.com/AnassNadeem) mentions NeuroSim and needs to be ARIS-aligned before any new work goes public.

- Replace profile README. Suggested structure:
  ```markdown
  ### Hi, I'm Anass.
  CS with AI @ Brunel University of London. Building **ARIS** —
  an always-on race strategist that watches live telemetry, predicts
  the next decision, and proposes it with a quantified delta.
  
  → Active project: ARIS (link)
  → Interests: motorsport software, applied ML, race strategy
  → Stack: Python · NumPy/Pandas · scikit-learn · PyTorch · FastF1 · Postgres · Streamlit
  ```
- Do NOT delete hackathon repos — those are real signal. Pin the 2 strongest as the first two pinned repos. ARIS will become pinned #1 once it has a hero GIF.
- Profile photo, location (London / United Kingdom), bio (one sentence: "CS+AI undergrad building race-strategy AI"), public email if comfortable
- Add a link to your LinkedIn from the profile

---

## Phase 0 — Python foundations + first FastF1 plot
**Weeks 1–2 (May 4 – May 17, 2026)**

### What you're learning
- Python syntax, control flow, functions, classes, modules
- `numpy` arrays, broadcasting, indexing
- `pandas` DataFrames, groupby, merge, time-series basics
- `matplotlib` — line plots, subplots, labels
- Git fundamentals: clone, branch, commit, push, pull, merge, rebase basics
- FastF1 API surface

### Where to learn it (named, free where possible)
- **Python core:** [Boot.dev — Learn Python](https://www.boot.dev/courses/learn-python) (free trial covers basics; paid $25 if you want certs — skip the cert)
- **Free alternative:** [CS50P — Harvard's Python course on YouTube](https://cs50.harvard.edu/python/) (full free, 10 hours, very high quality)
- **NumPy:** [NumPy official quickstart](https://numpy.org/doc/stable/user/quickstart.html) + [Sentdex NumPy YouTube playlist](https://www.youtube.com/playlist?list=PLQVvvaa0QuDfKTOs3Keq_kaG2P55YRn5v) (2 hours)
- **Pandas:** [James Powell — "Pandas From The Ground Up"](https://www.youtube.com/watch?v=dPwLlJkSHLo) (2.5 hours, this is *the* tutorial)
- **Pandas exercises:** [Kaggle Pandas micro-course](https://www.kaggle.com/learn/pandas) (free, 4 hours)
- **Git:** [Atlassian Git tutorials](https://www.atlassian.com/git/tutorials) — branches, merge, rebase pages
- **FastF1:** [Official FastF1 docs](https://docs.fastf1.dev/) — read the "Getting started" + "Examples" pages end-to-end

### What to build
1. **Day 1:** Repo `aris` on GitHub, public, MIT license, README with the one-liner pitch from the master plan, `.gitignore` for Python, a Python virtualenv, one commit `chore: scaffold repo`. **Send WhatsApp message today.**
2. **Days 2–4:** Work through CS50P Weeks 0–4 OR Boot.dev through OOP. Each day commit a `learning/` folder with the exercises. Yes, commit your homework — it's evidence of consistent practice.
3. **Days 5–7:** NumPy + pandas tutorials. Notebook `notebooks/00-pandas-basics.ipynb`, committed.
4. **Week 2 Days 1–3:** Install FastF1, pull 2024 Bahrain GP race session, dump it to a parquet file. Notebook `notebooks/01-fastf1-first-pull.ipynb`. Plot Verstappen's lap times vs lap number with matplotlib. Commit the plot as PNG to `docs/screenshots/`.
5. **Week 2 Days 4–6:** Pull 5 races, compute and plot per-driver tire compound stints. This is the real exercise — joining sessions, telemetry, and lap data. Notebook `02-stint-analysis.ipynb`.

### Deliverables (Done means)
- [ ] Public GitHub repo with ≥8 commits, README with pitch + screenshot
- [ ] `LOG.md` with daily bullets
- [ ] Two notebooks committed showing FastF1 working end-to-end
- [ ] WhatsApp sent (Day 1)
- [ ] You can write a Python class with `__init__`, methods, and properties without looking it up
- [ ] You can do a pandas groupby + agg + merge without looking it up

### Interviewer-test sanity check
Open the repo cold, can you in 60 seconds: explain the pitch, run `python -m scripts.pull_race --year 2024 --round 1`, show me the resulting plot? If no, Phase 0 isn't done.

---

## Phase 1 — Postgres ingest + Streamlit dashboard
**Weeks 3–4 (May 18 – May 31, 2026)**

### What you're learning
- SQL: SELECT, JOIN, GROUP BY, indexes, EXPLAIN
- Postgres specifically: psql, schemas, types, primary/foreign keys
- Docker basics — `docker run`, `docker compose`, volumes
- `psycopg` / `SQLAlchemy` (use SQLAlchemy 2.0 ORM-lite style)
- Streamlit fundamentals — pages, widgets, caching, deployment
- Project layout: `src/aris/`, `scripts/`, `tests/`, `notebooks/`

### Where to learn it
- **SQL:** [SQLBolt](https://sqlbolt.com/) (free, 2 hours, perfect for what you need)
- **Postgres:** [Postgres Tutorial — Practical Postgres](https://www.postgresqltutorial.com/) — first 5 sections only
- **Docker:** [Docker — Get Started Part 1–3](https://docs.docker.com/get-started/) only. Don't go deep.
- **SQLAlchemy 2.0:** [Official tutorial — Unified Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/index.html) — sections 1–6
- **Streamlit:** [Streamlit 30 Days](https://30days.streamlit.app/) — free, hands-on, ship daily
- **Streamlit deployment:** [Streamlit Community Cloud docs](https://docs.streamlit.io/deploy/streamlit-community-cloud)

### What to build
1. **Week 3 Day 1:** `docker-compose.yml` with Postgres 16, persistent volume. README updated with `docker compose up -d` instructions.
2. **Week 3 Days 2–3:** Schema design. Tables: `seasons`, `events`, `sessions`, `drivers`, `laps`, `telemetry_samples`, `weather`. Migration file `migrations/001_init.sql`. Document the ERD in `docs/schema.md` with a Mermaid diagram (GitHub renders it natively).
3. **Week 3 Days 4–6:** Ingest script `scripts/ingest_session.py` — idempotent (rerunnable, no duplicates), takes `--year --round --session`, fills all tables. Pull 10 races from 2023 + 2024.
4. **Week 3 Days 4–5 (compressed from Wk4 — Tier B graft):** Streamlit app skeleton `app/Home.py`, `app/pages/01_Lap_Explorer.py`. Connect to Postgres. Page lets user pick year → race → session → driver, shows lap-time chart + sector chart + tire stint timeline. **Add a moving-average-of-sector-times statistical baseline as the first "predictor" so the dashboard has dummy numbers to render** (Gemini's recommendation — lets Phase 1 ship before Phase 2 ML lands).
5. **Week 3 Day 5 = Brunel Racing hard-kill checkpoint** (revised from Wk6). If no clean CSV telemetry path in hand by today, commit `LOG.md` entry: *"Pivoting validation story to held-out FastF1 + sim-racing. Brunel Racing remains upside, not dependency."* Stop chasing.
6. **Week 3 Day 6:** Deploy to Streamlit Community Cloud. Use Neon.tech free tier (already set up pre-Day-1). Add a 5-min keepalive ping via GitHub Actions — Neon free tier cold-starts in 2–5s and that will make the demo feel broken. Public URL works on phone.
7. **Week 4 Days 1–3:** Polish the dashboard — error states, mobile-responsive layout, tire-stint timeline component, race-replay scrubber skeleton (will be filled by Phase 4).
8. **Week 4 Days 4–5:** Write the **leakage-test scaffold** (`tests/test_no_leakage.py`, 30 lines pytest) so it's ready to commit Day 1 of Phase 2. Don't run it yet — there's no model to test. Just have it staged.
9. **Week 4 Day 6:** LinkedIn post #1 with the live URL. "4 weeks in, here's the data layer." Quiet but real.

### Deliverables (Done means)
- [ ] Local Postgres running via `docker compose up`
- [ ] 10+ races ingested, ≥500k telemetry rows
- [ ] Streamlit app deployed to a public URL
- [ ] First public post (LinkedIn) with the URL
- [ ] You can write a JOIN across 4 tables without looking it up
- [ ] You can explain why you used SQLAlchemy ORM vs raw SQL (or vice versa)

---

## Phase 2 — Lap-time predictor (physics + residual ML)
**Weeks 5–7 (June 1 – June 21, 2026) ← extended to 3 weeks**

### What you're learning
- **Vehicle dynamics fundamentals:** longitudinal/lateral force, slip ratio, slip angle, tire load sensitivity, weight transfer, basic bicycle model
- **Tire degradation:** linear-with-fuel + exponential thermal/wear, compound differences (soft/medium/hard)
- **scikit-learn:** train/test split, cross-validation, pipelines, metrics (MAE, RMSE)
- **XGBoost:** when to use it, hyperparameters that matter (max_depth, eta, n_estimators)
- **Tiny PyTorch:** an MLP with 2 hidden layers, training loop, no GPU needed

### Where to learn it
- **Vehicle dynamics — pick ONE, not both:**
  - [Rajamani — *Vehicle Dynamics and Control*, Chapter 2](https://link.springer.com/book/10.1007/978-1-4614-1433-9) (Brunel library has this — go borrow it Week 5 Day 1)
  - Lighter alt: [The Racing Line YouTube — vehicle dynamics primer](https://www.youtube.com/@TheRacingLine) — pick the bicycle-model + tire-load videos
- **Pacejka tire model intuition:** [Wikipedia — Hans B. Pacejka](https://en.wikipedia.org/wiki/Hans_B._Pacejka) → Pacejka Magic Formula — read the "simplified" form, ignore the full 14-coefficient version
- **F1 tire deg context:** [The Race — How Pirelli's tire compounds work](https://www.the-race.com/) (search "tire degradation explained")
- **scikit-learn:** [scikit-learn user guide — Sections 1.1, 3.1, 3.3](https://scikit-learn.org/stable/user_guide.html)
- **XGBoost:** [XGBoost Python tutorial](https://xgboost.readthedocs.io/en/stable/python/python_intro.html)
- **PyTorch quickstart:** [PyTorch — Learn the Basics](https://pytorch.org/tutorials/beginner/basics/intro.html) (8 short pages)
- **Reference paper:** [Frontiers 2025 — Deep learning for F1 pit-stop decisions](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1673148/full) — read the methods section twice
- **Reference repo:** [TUM race-simulation](https://github.com/TUMFTM/race-simulation) — clone and read their tire model. Don't copy. Understand.

### What to build

**Week 5 — Leakage tripwire + Bicycle model from first principles**
- **Day 1 (BEFORE ANY MODEL CODE):** commit `tests/test_no_leakage.py` from the staged Wk4 scaffold. Race-by-race CV harness with a unit test that fails if any held-out race appears in the training fold. Commit message: `test: add race-by-race CV harness + leakage tripwire (the most important test in the project)`. This is the single most important commit in Phase 2 — Claude flagged train/test leakage as the #1 risk that "produces a great-looking MAE that collapses under interview scrutiny."
- Day 1 evening: Read Rajamani Ch.2 (already borrowed pre-Day-1).
- Days 2–3: Implement `src/aris/physics/bicycle.py`. Inputs: speed, steering, throttle, brake, mass, wheelbase, friction. Outputs: longitudinal accel, lateral accel, predicted segment time. Hand-coded, every line owned. Add a simple **fuel-burn linear term** (`fuel_kg_to_pace_loss`) and **pit-loss constant** (`PIT_LOSS_BASE = 22.0`) so the physics layer covers what an F1 strategy reviewer expects.
- Days 4–5: Validate against one stint of FastF1 telemetry. Plot predicted lap time vs actual. It will be off by 3–10s. That's expected.
- Day 6: Notebook `notebooks/03-bicycle-validation.ipynb`. README updated with what you've built.

**Week 6 — Tire degradation curve**
- Days 1–2: Implement `src/aris/physics/tires.py`. Function: `tire_pace_loss(compound, lap_in_stint, fuel_load) → seconds_lost_per_lap`. Coefficients fit from FastF1 historical stints (linear regression by compound).
- Days 3–4: Add tire model to predictor. Re-validate. Should now be off by 1–3s.
- Day 5: ~~Brunel Racing checkpoint~~ (moved earlier — was Wk3 Day 5 in revised Phase 1). Use today as a clean buffer day for tire-coefficient debugging — unphysical fits are common.
- Day 6: LinkedIn post #2 — "Hand-coded a bicycle model and a tire deg curve this week. Here's the predicted-vs-actual chart." Include the chart.

**Week 7 — Residual ML correction**
- Days 1–2: Build feature set: weather, track temp, lap number, fuel estimate, compound, stint age, sector grip. Save as parquet.
- Day 3: Baseline — XGBoost on residual = (actual − physics prediction). Cross-validate by *race*, not by lap (preventing leakage is critical — write a comment about why).
- Day 4: Compare to a tiny PyTorch MLP (2 hidden layers, 64 units). Probably XGBoost wins on this dataset; ship XGBoost, keep MLP code in `experiments/`.
- Day 5: Eval harness `src/aris/eval/laptime.py` — held-out 5 races, MAE per stint, **using the leakage-tripwire CV harness from Day 1**.
- Day 6: README results table. **Recalibrated targets (Tier A):** floor < 1.0s, target < 0.7s, stretch < 0.5s. Residual contribution visualised. Conformal prediction intervals are added in Phase 6 — for now, report MAE alone honestly.

### Deliverables (Done means)
- [ ] `aris.physics.bicycle` module with tests (`pytest`, even basic ones)
- [ ] `aris.physics.tires` module with fit coefficients per compound
- [ ] `aris.models.residual` predictor with eval results in README
- [ ] `tests/test_no_leakage.py` committed Day 1, passing, in CI
- [ ] Held-out MAE: floor < 1.0s achieved, target < 0.7s ideally, OR documented honestly if not (no over-claim)
- [ ] LinkedIn posts #2 done
- [ ] You can derive the bicycle model from Newton's 2nd law on a whiteboard
- [ ] You can explain why a residual on physics is more sample-efficient than end-to-end ML

---

## Phase 3 — Counterfactual simulator
**Weeks 8–9 (June 22 – July 5, 2026)**

### What you're learning
- API design — clean function signatures, type hints, docstrings
- State representation — what makes a "race state" snapshot
- Perturbation patterns — how to express "lift 30m earlier in T7" as a structured action

### Where to learn it
- [Python type hints — RealPython guide](https://realpython.com/python-type-checking/)
- [Pydantic v2 docs — basic models](https://docs.pydantic.dev/latest/concepts/models/) — your action vocabulary will be Pydantic models
- [Streamlit — Plotly charts](https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart) — for interactive counterfactual viz

### What to build
1. **Week 8 Days 1–2:** `src/aris/state.py` — `RaceState` Pydantic model: lap, sector, position, gap_ahead, gap_behind, tire_age, compound, fuel, weather, drs_available, etc.
2. **Week 8 Days 3–4:** `src/aris/actions.py` — action vocabulary as a discriminated union: `LiftPoint`, `BrakePoint`, `LineOffset`, `PitNow`, `CompoundChange`. Each has parameters with bounds.
3. **Week 8 Day 5–6:** `src/aris/simulate.py` — `simulate(state, action) → PredictedOutcome`. Outcome contains: predicted lap time delta, sector deltas, tire wear delta, fuel delta, confidence band.
4. **Week 9 Days 1–3:** Streamlit page `pages/02_Counterfactual.py` — pick a real lap, choose action type, scrub a parameter, see overlaid predicted-vs-actual chart.
5. **Week 9 Days 4–5:** Capture the demo screenshot — *"Lift 30m earlier in T7 → predicted +0.18s gain."* This image goes everywhere from now on.
6. **Week 9 Day 6:** LinkedIn post #3 with the screenshot. Short caption — let the image work.

### Deliverables (Done means)
- [ ] Action vocabulary documented in `docs/actions.md`
- [ ] Counterfactual page deployed live
- [ ] At least one screenshot worthy of the demo video
- [ ] All public functions have type hints + docstrings
- [ ] You can demo the counterfactual page on your phone in 30 seconds

---

## Phase 4 — Always-on loop + recommendation feed
**Weeks 10–11 (July 6 – July 19, 2026)**

### What you're learning
- Async Python — `asyncio`, `await`, event loops, basics only
- Streaming/replay patterns — turn historical data into a live feed
- Action search — top-K perturbations, scoring, ranking

### Where to learn it
- [RealPython — async IO walkthrough](https://realpython.com/async-io-python/) — first half only
- [Streamlit — `st.empty` + `st.rerun` patterns for live UIs](https://docs.streamlit.io/) (search "live updates")

### What to build
1. **Week 10 Days 1–2:** `src/aris/replay.py` — replay a finished race lap-by-lap, emitting RaceState every N seconds of wall time (configurable; default 5s).
2. **Week 10 Days 3–5:** `src/aris/recommend.py` — every state tick, enumerate top-K candidate actions (start with 20–50 actions in the vocabulary), score each by `simulate()`, return top 3 with predicted delta + confidence.
3. **Week 10 Day 6:** Recommendation feed component in Streamlit — scrolling list, newest at top, color-coded by delta sign.
4. **Week 11 Days 1–3:** Performance: ensure tick + scoring + render cycle stays under your target (start with 10s, aim for 5s). Profile with `cProfile`. Document tradeoffs in `docs/performance.md`.
5. **Week 11 Days 4–6:** End-to-end demo: hit play, watch a 2024 race, see live recommendations updating against the actual race. Record a 30-second screen capture for the README hero GIF.

### Deliverables (Done means)
- [ ] Always-on loop runs without manual prodding
- [ ] Recommendation feed visible and updating
- [ ] Tick latency documented honestly
- [ ] Hero GIF in README
- [ ] You can explain the action search algorithm in 90 seconds

---

## Phase 4.7 — MATLAB / Simulink port of bicycle module (Tier B graft, parallel evening work)
**Wks 11–12 evenings (~1 week of total effort, no daytime cost)**

### Why
Mercedes AMG HPP, Red Bull Powertrains, Williams Vehicle Dynamics, and Aston Martin Performance all list MATLAB/Simulink as "good to have" — which means *should have*. Porting the bicycle module is cheap (it's already debugged in Python) and produces a separate pinned repo on GitHub that doubles your perceived stack.

### What you're learning
- MATLAB syntax basics (matrix-first thinking, 1-indexed arrays, function files)
- Simulink block-diagram modelling — bicycle as a state-space block
- Cross-language validation (Python output vs MATLAB output to within 5%)

### Where to learn it
- [MathWorks MATLAB Onramp](https://matlabacademy.mathworks.com/) (free, ~2 hrs) — DO BEFORE this phase
- [Simulink Onramp](https://matlabacademy.mathworks.com/) (free, ~2 hrs) — DO BEFORE this phase
- [MATLAB for Data Processing and Visualization](https://matlabacademy.mathworks.com/) (free, ~5 hrs)

### What to build
1. **New repo `aris-matlab-validation`** on GitHub, MIT-licensed, README links back to ARIS main repo and vice versa.
2. Port `src/aris/physics/bicycle.py` → `bicycle.m` + supporting function files. Same inputs, same outputs, ±5% agreement on 10 sample stints.
3. Simulink block diagram of the same model — screenshot for the README.
4. `validate_against_python.m` script that loads a Python-generated CSV of inputs/outputs and asserts agreement.
5. README with: motivation, install, run, validation results, link to main ARIS repo. Pin this repo on your GitHub profile (slot #2 after ARIS).

### Deliverables (Done means)
- [ ] Separate `aris-matlab-validation` repo, public, README ≥ 1 screenshot
- [ ] Bicycle outputs agree with Python to within 5% on 10 stints
- [ ] Simulink block diagram present
- [ ] Repo pinned on GitHub profile
- [ ] CV self-study line updated: *"MATLAB Onramp + Simulink Onramp completed (2026)"*

---

## Phase 4.5 — Monte Carlo strategy layer (NEW — added back)
**Week 12 first half (July 20 – July 23, 2026, ~3 days)**

### Why it's back
F1 strategy teams run Monte Carlo race simulations as standard practice — sampling thousands of race trajectories with stochastic safety cars, weather, traffic, and pit-stop variance. The TUM open-source simulator and the Frontiers 2025 paper both build on this. **Cutting it would weaken the F1 story.** The reason it was cut originally was scope (a full pit-window optimiser is 2 weeks); a slim layer on top of your existing `simulate()` is 3 days.

### What you're learning
- Monte Carlo sampling basics — sampling from distributions, law of large numbers intuition
- `numpy.random` — generators, seeds, reproducibility
- Conditional distributions — safety car probability per lap, weather change probability

### Where to learn it
- [Statistics 101 — Monte Carlo simulation explained (YouTube)](https://www.youtube.com/results?search_query=monte+carlo+simulation+intuition) — pick the 15-min Brandon Foltz video
- [Frontiers 2025 paper](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1673148/full) — Monte Carlo section
- [TUM race-simulation README](https://github.com/TUMFTM/race-simulation) — their assumptions doc

### What to build
- Day 1: `src/aris/montecarlo.py` — given a state and a candidate strategy (e.g. "pit lap 22, mediums to hards"), sample N=1000 race continuations with stochastic safety car, weather, pit-loss variance. Return distribution of final position + finish time.
- Day 2: Plug into Phase 4 recommender — top-3 actions now include Monte Carlo confidence: "Pit lap 22 → expected +0.4 positions, P10 = -1, P90 = +2."
- Day 3: New Streamlit panel — pit-lap histogram of finish position. Screenshot-ready for demo.

### Deliverables (Done means)
- [ ] Monte Carlo module with seeded reproducibility
- [ ] Recommendations now include confidence intervals
- [ ] Histogram screenshot in README
- [ ] You can explain sampling vs optimisation in one sentence

---

## Phase 5 — LLM narration + grounded Q&A
**Week 12 second half + Week 13 (July 24 – August 2, 2026)**

### What you're learning
- Prompt engineering basics — system prompts, few-shot, structured output
- Local LLM inference via Ollama on RTX 5070 GPU
- Retrieval-augmented generation (RAG) basics — answering questions grounded in structured state, not from LLM training data
- Anthropic Claude API SDK (optional, last week, polish only — not required)

### Where to learn it
- [Ollama install + Llama 3.1 quickstart](https://ollama.com/) — already installed in Phase 0; `ollama serve` exposes a local API
- [Anthropic — prompt engineering overview](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview) (technique-agnostic, applies to Llama too)
- RAG primer — search "retrieval augmented generation tutorial" — short Pinecone or LangChain blog post is sufficient

### What to build
1. **Week 12 Days 4–6:** `src/aris/narrate.py` — takes a structured recommendation JSON, returns a one-sentence narration. Backend interface so any LLM (Llama local or Claude API) can be plugged in. Llama 3.1 8B on GPU is the default backend throughout.
2. **Week 13 Days 1–2:** Llama few-shot prompt with 6 examples covering: pit, lift, brake earlier, defend, attack, *strategy pivot*. Measure latency on RTX 5070 — target <2s per narration.
3. **Week 13 Days 3–4:** **Ask ARIS pane** — Q&A with grounded answers. The LLM receives the user question + a structured snapshot of current race state (positions, gaps, deg curves, recent recommendations, MC outputs) and answers using only that data. Cite the data source in every answer. This is RAG, scoped tight.
4. **Week 13 Day 5:** Plug both into Streamlit — narration on each rec card, Ask pane in the right column.
5. **Week 13 Day 6:** Optional — Claude API as a swap-in backend (gated by env var `ARIS_LLM=claude`), used only if you want polish in the demo recording. Skip if budget tight; Llama is good enough.

### Deliverables (Done means)
- [ ] Llama 3.1 narration working locally on GPU, free, <2s/call
- [ ] Ask ARIS pane answers grounded questions correctly with cited evidence
- [ ] Spot-check 20 narrations: ≤2 hallucinated numbers (per success criteria)
- [ ] LinkedIn post #4 with a narrated recommendation example

---

## Phase 6 — Eval harness + dashboard polish + 90-second demo video
**Weeks 14–15 (August 3 – August 16, 2026)**

### Dashboard 4-mode finalisation (parallel to eval, Week 14)
The dashboard exposes four interaction modes from one Streamlit app. Build this in the order below — Watch mode already exists from Phase 4, the rest layer on top:

1. **Watch mode** (default) — recommendation feed scrolls, each card has expandable `[Why?]` showing evidence, alternatives considered, risks, confidence breakdown
2. **Ask mode** — full-height chat pane (Phase 5 Q&A reused)
3. **What-if mode** — counterfactual sliders for pit lap + compound + lift point + driver style. Live-updating predicted-outcome chart and Monte Carlo distribution. **This is the killer demo screen — invest 2 days here.**
4. **Replay mode** — timeline scrubber. Drag to any past lap, see what ARIS would have recommended at that moment vs what actually happened. **This is the recording surface for the demo video.**

All four share one data layer. Single browser tab. Mobile-responsive (test on your own phone, mobile network not WiFi — per success criteria).

### What you're learning
- Backtesting methodology — train/test split by time, leakage avoidance
- **Conformal prediction (now mandatory — Tier B graft, ~2 days):** split-conformal, empirical coverage, interval width
- Screen recording + voice-over basics

### Where to learn it
- **Conformal prediction:** [Anastasios Angelopoulos — A Gentle Introduction to Conformal Prediction](https://people.eecs.berkeley.edu/~angelopoulos/blog/posts/gentle-intro/) — read the first 6 pages, that's enough for split-conformal on regression
- [`mapie` Python library docs](https://mapie.readthedocs.io/) — does split-conformal in 5 lines
- **Recording:** OBS Studio (already installed pre-Day-1)
- **Voiceover:** record on your phone in a quiet room; edit in DaVinci Resolve free or CapCut (already installed pre-Day-1)

### What to build

**Week 14 — Eval + conformal calibration + strategy backtest report**
- Days 1–2: `scripts/backtest.py` — pick 5 held-out races (different tracks, different conditions). Run ARIS through them in replay mode. Log every recommendation.
- Day 3: **Conformal calibration (Tier B graft).** Split-conformal on a calibration fold using `mapie`. Output 90% prediction intervals on every lap-time prediction. Plot empirical coverage on held-out — should be 85–95%. Plot per-stint interval width. This is the answer to *"how did you handle uncertainty?"*
- Day 4: Compute strategy metrics: lap-time MAE *with conformal interval coverage*, recommendation hit rate (% where ARIS recommendation matched what driver/team actually did, OR predicted delta direction was correct on the laps where you can validate). Add **undercut risk reduction vs naive baseline** and **safety-car sensitivity** numbers — strategy-language metrics, not just ML metrics.
- Day 5: Results table → README. Be honest. Numbers that look modest but are real beat numbers that look great but are leaked. Write `docs/strategy-backtest.md` — one page minimum, written for a strategy hiring manager.
- Day 6: Blog post #1 (technical) — "How I built a race-strategy simulator in 14 weeks (with conformal-calibrated intervals)." Cross-post LinkedIn + Medium.

**Week 15 — Demo video**
- Days 1–2: Script the 90 seconds. Three beats: (1) what it is + live race watching [25s], (2) one specific counterfactual with predicted delta vs actual outcome [40s], (3) how it works + repo link [25s].
- Days 3–4: Record. Re-record. Re-record. First 3 takes will be bad — that's normal.
- Day 5: Edit. Captions burned in (people watch muted).
- Day 6: Upload YouTube unlisted + embed in README + LinkedIn post #5 with the video.

### Deliverables (Done means)
- [ ] Backtest results table in README with held-out race numbers + conformal interval coverage
- [ ] `docs/strategy-backtest.md` written in strategy language (undercut risk, SC sensitivity, pit-window deltas)
- [ ] 90-second demo video on YouTube unlisted, linked from README
- [ ] Blog post published
- [ ] You can give the same demo live, no video, in 90 seconds, on a phone
- [ ] You can answer "how did you handle uncertainty?" with the conformal-prediction story in 60 seconds

---

## Phase 7 — Placement applications prep
**Weeks 16–17 (August 17 – August 31, 2026)**

### What you're learning
- CV writing for engineering roles — STAR bullets, mapping skills to listings
- Cover letter patterns — research the team, lead with the artifact
- Interview prep — vehicle dynamics first principles, code walkthrough fluency, behavioural (STAR)
- LinkedIn outreach etiquette

### Where to learn it
- **CV:** [Brunel Careers Service CV templates + 1:1 review booking](https://www.brunel.ac.uk/life/careers) — use the free 1:1
- **Interview prep — vehicle dynamics:** revisit Rajamani Ch.2, Milliken's *Race Car Vehicle Dynamics* (library)
- **LeetCode-easy in Python:** [NeetCode 150 — easy section only](https://neetcode.io/) — 30 minutes/day
- **Behavioural:** [Amazon's STAR method guide (universal)](https://www.amazon.jobs/) — applies to all interviews

### What to build
1. **Week 16 Days 1–2:** CV rewrite — ARIS at top, mapped to role-listing language using the table from `ARIS-FINAL-PLAN.md` §2.
2. **Week 16 Day 3:** Cover-letter template, then 11 customised versions (McLaren, Williams, Red Bull Racing, Red Bull Advanced Technologies, Mercedes AMG HPP, Mercedes Petronas F1, Alpine, M-Sport, Williams Advanced Engineering, AP Racing, Stray Systems).
3. **Week 16 Days 4–6:** LinkedIn outreach pack — search Brunel alumni at each of the 11 firms. Aim for 30 names. Personalised first-message template per firm.
4. **Week 17 Days 1–3:** Mock interviews — record yourself answering 10 common questions on camera. Watch back. Cringe. Re-record.
5. **Week 17 Days 4–5:** Code walkthrough rehearsal — open the repo cold, narrate the architecture in 5 minutes. Have a friend timer it.
6. **Week 17 Day 6:** Blog post #2 (motivation/story) — "Why I'm building a race strategist as a CS first-year." More personal, fewer code blocks.

### Deliverables (Done means)
- [ ] CV (1 page) + cover-letter template + 11 customised versions
- [ ] 30 LinkedIn alumni identified, message template ready
- [ ] 10 recorded mock-interview answers reviewed
- [ ] 5-minute code walkthrough you can do without notes
- [ ] Blog post #2 published
- [ ] **You can describe ARIS in 30 seconds, 90 seconds, and 5 minutes**

---

## Supporting courses (parallel to the build)

Courses are a **multiplier**, not a substitute. Recruiters discount certificates heavily; the repo is the artifact. The right courses fill specific gaps ARIS doesn't naturally demonstrate (MATLAB/Simulink, formal ML grounding, vehicle dynamics theory). Wrong ones eat build time.

### Tier 1 — high signal, do these
- **MathWorks MATLAB Onramp** (free, ~2 hrs) + **Simulink Onramp** (free, ~2 hrs) + **MATLAB for Data Processing and Visualization** (free, ~5 hrs). Maps directly to Mercedes HPP and Red Bull Powertrains "good to have" lines. → [matlabacademy.mathworks.com](https://matlabacademy.mathworks.com/)
- **Coursera — DeepLearning.AI Machine Learning Specialization (Andrew Ng)** (audit free; $49/month if you want the cert, finish in 1 month = $49 total). The single most-recognised ML course in industry. → [coursera.org/specializations/machine-learning-introduction](https://www.coursera.org/specializations/machine-learning-introduction)

### Tier 2 — domain-targeted, high signal but narrow
- **Coursera — University of Michigan Vehicle Dynamics specialisation** (audit free). Maps 1:1 to Williams Vehicle Performance and Red Bull Vehicle Dynamics roles. Single most F1-targeted course available.
- **MIT OpenCourseWare — 18.06 Linear Algebra** (free, no cert). Foundation for Phase 2. List under "self-study," no logos.
- **edX — MIT 6.86x Machine Learning with Python** (audit free; ~$150 cert). Pick this *or* Andrew Ng, not both — they overlap.

### Tier 3 — career-adjacent
- **Brunel Careers Service workshops** (free, on-campus). Highest ROI per hour because Brunel has direct relationships with McLaren / M-Sport / Williams. Book ≥3 sessions: CV review, mock interview, employer event.
- **Bright Network** newsletter — F1-specific employer events. Free. Sign up Week 1.

### Tier 4 — skip (vanity)
- Udemy bootcamps, "AI mastery in 30 days," generic AWS certs, LinkedIn Learning certs. Low signal.

### Phasing (so courses don't break the build)

| Phase / Weeks | Course | Time cost | Why now |
|---|---|---|---|
| Phase 0–1 (Wks 1–4) | MATLAB + Simulink Onramps | 4–6 hrs total, evenings | Cheap win; finishes before ML phase |
| Phase 2–3 (Wks 5–9) | Andrew Ng ML Specialization (audit) | ~5 hrs/wk, parallel | Theory backs what you're building |
| Phase 4–6 (Wks 10–15) | Michigan Vehicle Dynamics (audit) | ~3 hrs/wk, parallel | Defends the bicycle/tire model in interviews |
| Year 2 (Sept–Nov) | MIT 6.86x OR finish Vehicle Dynamics | Spare hours | Keeps learning visible while applying |

### CV framing
One line under Education:
> *Self-study: Andrew Ng ML Specialization (2026), MathWorks MATLAB & Simulink Onramps (2026), Michigan Vehicle Dynamics (2026)*

No logos, no cert numbers. The project keeps the real estate.

### Failure mode
Course-collecting becomes procrastination dressed as productivity. If a course is eating into Phase deliverables, **drop the course**, not the build. The repo is the artifact; courses just frame it.

---

## Year 2 (September 2026 onward)

### November application sprint
- Submit applications during opening week of each company's portal (most open Sept–Nov)
- Track in a single spreadsheet: company, role, date submitted, status, follow-up date
- 3 cold messages/week to alumni (Mon/Wed/Fri, 20 minutes each)
- Friday 2-hour interview prep block — vehicle dynamics, code walkthrough, behavioural
- Bi-weekly LinkedIn post — small ARIS refinement, paper read-through, or Brunel Racing update

### Maintain ARIS lightly
- ≥1 commit/week minimum (keep the GitHub graph alive)
- One small feature per month — driver-style fingerprinting, rain-tire model, sector-level confidence intervals, etc.
- If Brunel Racing engaged: real-data adapter as priority

### Phase 9 — Sim-racing live telemetry adapter (Y2 stretch)
The natural Year-2 extension. Do NOT start before applications go in (Nov 30, 2026). Architect for it now (Phase 1 keeps the data layer behind `DataSource` interface) but ship later.

**What it adds:**
- iRacing / ACC / Le Mans Ultimate / rFactor 2 telemetry adapters via UDP / shared memory
- ARIS narrates *live* during your own sim sessions
- Solves the Brunel Racing data dependency entirely (sim data is yours, generated on demand)

**Cover-letter language (already valid in November even though unbuilt):**
> *"Currently extending ARIS to read sim-racing telemetry, enabling live narration during human driving sessions."*

**Hardware fit:** RTX 5070 + 32GB RAM runs sim + ARIS + Llama 3.1 inference simultaneously without thermal throttle.

**Time budget:** ~3 weeks of evening work in Y2, after applications submitted. Or full-time across spring break 2027 if placement secured.

### When you can revisit cut scope
- **QDIE (quant plugin):** summer 2027 if Y2 placement secured. Now you can earn the UDX umbrella name.
- **FS-AI:** Y3 final-year project candidate, especially if CS(AI) degree.
- **World model:** post-graduation research direction, only if you go that path.

---

## Honest tradeoffs you're accepting

- **No deep RL.** The "agent" framing is shallower than a real RL system. You're shipping a *predictor + search + recommender*, not a learned policy. This is honest, defensible, and matches what F1 teams actually deploy.
- **No real-time hardware.** Replay-as-live is enough for a demo. Real low-latency telemetry pipelines are an Year-2-onward problem.
- **Single-driver, single-car.** Multi-car interaction modeling is a research project of its own; you parameterise gap_ahead/gap_behind as inputs and stop there.
- **MAE on a hold-out set, not a podium.** You will not "beat the pit wall" — you will demonstrate competence, taste, and shipping ability. That is the actual currency for placements.

---

## Tier C — add-ons (only after Tier A + Tier B is locked and shipped)

These are **bonus** — do not start any of them until the core plan + all Tier A + Tier B grafts are green. If you can't tick every Tier B deliverable, these don't exist.

| Add-on | Effort | When | Why |
|---|---|---|---|
| **Hugging Face Spaces deployment** | 1 day | Wk16 once Streamlit is locked | Free CV signal, listable URL, "deployed to two clouds" line |
| **Llama 3.2 3B as fallback backend** | 4 hrs | Wk13 if 8B is tight | Mitigates 8GB VRAM OOM risk per Gemini |
| **Groq free tier as cloud LLM fallback** | 2 hrs | Wk13 | Removes Ollama as single-point-of-failure for demo |
| **pybind11 C++ Monte Carlo inner loop** | 3–4 days | Y2, only if NumPy version misses budget | Don't pre-optimise — Claude/Perplexity flagged this as Gemini-only suggestion |
| **One LeetCode-easy block per week** (≤2 hrs, replacing buffer) | 2 hrs/wk | Throughout | Software placement screens are auto-graded; ARIS doesn't help you pass them |
| **Five canonical strategy interview questions drilled** | 5 × 30 min | Wk16–17 | Undercut/overcut, gap-to-leader vs gap-ahead, 1-stop vs 2-stop in mixed weather, pit-stop walkthrough, "defend a decision under time pressure" |
| **Public Kaggle / HF dataset of FastF1 backtest task** | 1 day | Y2 | Own the benchmark; recruiters can run your eval themselves |
| **Brunel Racing in-person test-day visit (Wk8 or Wk9)** | 1 day | Wk8 or Wk9 | Public viewing area attendance — they don't have to invite you |
| **Toastmasters / mock-interview reps** (English fluency under pressure) | 2 hrs/wk | Y2 | Interview cadence not vocabulary — Andrea Stella, Riccardo Adami all non-native; this is solvable |
| **Submit ARIS to AIcrowd / Kaggle motorsport competitions** | varies | Y2 if any open | Free CV signal, public benchmark to point at |
| **Blog post #3 on conformal prediction in strategy** | 1 day | Y2 | Niche-defining — almost no one writes about uncertainty quantification in F1 strategy publicly |

**Discipline rule:** if a Tier C item starts eating into Tier A+B deliverables, drop it the same day. Tier A+B is the score-lift to 9. Tier C is the polish to 10. You cannot get to 10 without first being at 9.

---

## When to ask for help

- **Stuck >2 hours on a bug:** ask Claude/ChatGPT, but write up the problem first (rubber-duck effect alone solves half).
- **Stuck >1 day on a concept:** post in the FastF1 Discord, the r/F1Technical subreddit, or the Brunel CS course Teams. Free help, real people.
- **Brunel Racing silent for 7 days after first message:** send one polite follow-up. After that, drop it for 2 weeks and try a different contact (your MEng friend's introduction).
- **Falling behind by >3 days on a phase:** message me — we cut, we don't extend. The deadline is fixed; scope flexes.
