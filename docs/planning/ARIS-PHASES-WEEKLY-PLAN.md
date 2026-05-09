# ARIS — Phases & Weekly Plan (Week 0 → Ship)

**Status:** Master hub. Refer back here at the end of every week before writing the next week's elaborated plan.
**Source of truth:** `ARIS-FINAL-PLAN.md` (strategy) and `ARIS-EXECUTION-PLAN.md` (operational detail).
**Started:** 2026-05-04 (Week 1, Day 1) · **Ship:** 2026-08-31 · **Placement applications fire:** Sept 2026

---

## 0. Project at a glance

- **Name:** ARIS — *Always-on Race Intelligence System*
- **What it is:** A hybrid AI race-strategy software system that watches a live race (replay or live telemetry), predicts what's about to happen, and proposes the next driver/strategy decision with a quantified lap-time delta and a calibrated confidence interval. Built on real F1 telemetry (FastF1), validated end-to-end on held-out races.
- **Why we are building it:** To produce a presentable, shipped artefact that proves I can build and ship under deadline — the single strongest signal for an F1 / motorsport software placement (Williams VPS, Aston Martin Software, Mercedes AMG HPP Software & Controls, McLaren Engineering, Red Bull Race Strategy). Replaces the previous unbuilt NeuroSim / world-model fantasies with something that actually works.
- **What it improves over prior plans:**
  - Honest scope: hybrid physics + ML + LLM, not a "world model"
  - Validated end-to-end on held-out races with conformal prediction intervals (not just point MAE)
  - Tiered tick architecture (1–2s monitor, ~20–30s micro, per-lap macro, <400ms event-driven) — what real F1 strategy software actually looks like
  - Strategy-language backtest report (undercut risk, SC sensitivity, pit-window deltas) on top of MAE/RMSE
  - MATLAB/Simulink validation port closes the Mercedes HPP / Red Bull Powertrains "good to have" line
- **Who it's for (audience, in order):**
  1. F1 placement hiring managers (Williams, Mercedes HPP, McLaren, Red Bull, Aston Martin) — Nov 2026 application window
  2. Brunel Racing team (data partnership upside, severed as a hard dependency)
  3. Y3 final-year project examiners (the architecture extends naturally)
  4. The wider motorsport / sim-racing community (HF Space, Kaggle dataset, blog posts)
- **Skills it will develop:**
  - **Python (production-grade):** packaging with `uv`, typed code with `mypy`/`ruff`, idiomatic pandas/numpy, OO design behind a clean `DataSource` abstraction
  - **Vehicle dynamics first principles:** bicycle model, Pacejka-style tire curves, fuel-burn linearisation, pit-loss modelling
  - **Machine learning fundamentals:** supervised regression, residual learning, race-by-race CV, leakage prevention, conformal prediction, calibration evaluation
  - **Data engineering:** Postgres schema design, idempotent ingestion, FastF1 telemetry pipeline
  - **LLM application engineering:** local Ollama deployment, retrieval-augmented generation, prompt templating, structured-to-natural-language pipelines
  - **MATLAB/Simulink:** porting the bicycle module for cross-tool validation
  - **Software engineering hygiene:** Docker, CI, automated tests, clean Git history with daily commits
  - **Communication:** 90-second demo video, technical + motivation blog posts, strategy-language backtest write-up, mapping CV bullets to role-listing language
  - **Interview craft:** vehicle dynamics first-principles, defending technical choices, the five canonical strategy interview questions

### Tech stack

| Layer | Tool |
|---|---|
| Language | Python 3.11 (pinned via `pyenv-win`) |
| Package manager | `uv` (Astral) |
| Editor | VS Code + Pylance + Ruff + Jupyter + Docker + GitLens |
| Notes | Obsidian (personal vault, outside repo) |
| Data source | FastF1 (primary); sim-racing UDP/shared-memory adapter (Y2 extension); Brunel Racing CSV (upside, optional) |
| Storage | PostgreSQL 16 (Docker locally; Neon.tech free tier in cloud) |
| Numerics | NumPy, pandas, SciPy |
| Physics | Hand-coded bicycle model + tire-deg curve + fuel-burn linear term + pit-loss constant |
| ML | scikit-learn, XGBoost, small MLP (PyTorch optional) |
| Calibration | Custom split-conformal harness on top of sklearn |
| Counterfactuals | In-house perturbation engine + Monte Carlo (numpy) |
| LLM | Ollama running Llama 3.1 8B q5 locally (RTX 5070, 8 GB VRAM); Llama 3.2 3B fallback; Claude API only for final demo polish |
| UI | Streamlit (CLI + Jupyter through Phase 6, Streamlit only in Phase 7) |
| Deployment | Streamlit Community Cloud + Hugging Face Space (Tier C) |
| Cross-tool validation | MATLAB R2024b / MATLAB Online + Simulink (separate `aris-matlab-validation` repo) |
| Containerisation | Docker Desktop (Windows) |
| Demo recording | OBS Studio + DaVinci Resolve / CapCut |
| VCS / collaboration | Git, GitHub, GitHub CLI (`gh`), GitHub Actions for CI |
| GPU | RTX 5070 (mobile, 8 GB VRAM) + CUDA Toolkit 12.x + latest NVIDIA driver |
| Project tracking | `ARIS-Tracker.xlsx` + this file + weekly elaborated docs |

---

## Phases & Weekly Plan

> Cadence: 6 hrs/day × 6 days/week = 36 hrs/week. Sunday off.
> Tick the boxes as you go. At the end of each week, write `WEEK-NN-PLAN.md` referring back to this hub.

---

### Phase 0 — Pre-Day-1 setup (Week 0, April 29 → May 3)

**Goal:** Show up to Day 1 already loaded — every tool installed, every account live, GitHub profile cleaned, ARIS repo standing empty and ready.
**Tools/tech this phase:** pyenv-win, uv, Git, GitHub CLI, VS Code, Docker Desktop, NVIDIA driver + CUDA 12.x, Ollama + Llama 3.1 8B q5 (and 3.2 3B fallback), DBeaver, OBS, DaVinci/CapCut, MATLAB Online, Obsidian, Excel, Streamlit Cloud, Neon.tech, Hugging Face, Coursera, LinkedIn, Bright Network.

#### Week 0 (Apr 29 – May 3) — Pre-Day-1 loadout

- [ ] Install Python 3.11.9 via pyenv-win; verify `python --version`
- [ ] Install `uv`; verify `uv --version`
- [ ] Install Git for Windows; install GitHub CLI; run `gh auth login`
- [ ] Install VS Code + extensions (Python, Pylance, Ruff, Jupyter, Docker, GitLens, Mermaid Preview, Markdown All-in-One)
- [ ] Install Docker Desktop; `docker run hello-world` works
- [ ] Install latest NVIDIA Game Ready / Studio driver; `nvidia-smi` shows RTX 5070
- [ ] Install CUDA Toolkit 12.x; `nvcc --version` works
- [ ] Install Ollama; `ollama --version`
- [ ] `ollama pull llama3.1:8b-instruct-q5_K_M`; verify it answers a prompt on GPU
- [ ] `ollama pull llama3.2:3b` (fallback if 8 GB VRAM is tight)
- [ ] Install DBeaver Community (optional Postgres GUI)
- [ ] Install OBS Studio + DaVinci Resolve free (or CapCut)
- [ ] Set up MATLAB Online (or Brunel R2024b student license)
- [ ] Install & set up Obsidian vault for personal notes (outside the repo)
- [ ] Create / verify accounts: Streamlit Cloud, Neon.tech, Hugging Face, MathWorks, Coursera, DeepLearning.AI, LinkedIn refresh, Bright Network, YouTube, Medium
- [ ] Clean GitHub profile: purge NeuroSim, write ARIS-aligned README, pin strongest hackathon repos, set photo + London location + one-line bio
- [ ] Create empty `aris` repo (public, MIT, `.gitignore` ready)
- [ ] Reserve Rajamani *Vehicle Dynamics and Control* + Milliken *Race Car Vehicle Dynamics* from Brunel library
- [ ] Identify Brunel Racing contact (name + role) for the Day 1 WhatsApp
- [ ] Book Brunel Careers Service 1:1 for May (CV pre-review)
- [ ] Flag a friend now for mock interviews in Week 16
- [ ] Open `ARIS-Tracker.xlsx`; confirm columns; ready to log daily

---

### Phase 1 — Python foundations + first FastF1 plot (Weeks 1–2, May 4 – May 17)

**Goal:** Fluent enough Python and pandas to read FastF1 data; one matplotlib chart of a real driver's lap times committed and pushed; WhatsApp sent to Brunel Racing on Day 1.
**Tools/tech:** Python 3.11, uv, FastF1, pandas, NumPy, matplotlib, Jupyter, Boot.dev (or equivalent), James Powell pandas tutorials, GitHub.
**Deliverable:** `aris` repo with README, FastF1 install, one committed chart of a real driver's lap times, daily commits.

#### Week 1 (May 4 – May 10) — Day 1 ignition

- [ ] Initial commit to `aris` (README, `pyproject.toml` via `uv init`, `.gitignore`, MIT)
- [ ] Boot.dev Python track through OOP basics (or equivalent)
- [ ] NumPy basics — arrays, slicing, broadcasting
- [ ] First daily commit streak — at least one commit every weekday
- [ ] LOG.md created; daily two-line journal entries start today
- [ ] **LinkedIn post #1 — "starting ARIS"** (announcement only): one short post stating the project name, the one-line pitch, the ship date. No code, no claims of progress. Anchor for the followers, not a status update.

#### Week 2 (May 11 – May 17) — pandas + first FastF1 plot

- [ ] Finish Boot.dev OOP / numpy module
- [ ] James Powell pandas tutorials (2 hrs, YouTube)
- [ ] `uv add fastf1 matplotlib pandas jupyterlab`
- [ ] Pull one race via FastF1 (e.g. 2023 Bahrain GP)
- [ ] Plot one driver's lap times in matplotlib; commit chart PNG + notebook
- [ ] **Statistical baseline (Tier B graft):** moving-average-of-sector-times baseline, scoring stub — runs end-to-end on dummy data so the rest of the pipeline can be debugged before any ML lands
- [ ] Push to `main`; tag `v0.1-foundation`

---

### Phase 2 — Postgres ingest + Streamlit dashboard + cloud deploy (Weeks 3–4, May 18 – May 31)

**Goal:** A live public Streamlit URL that ingests FastF1 data into Postgres and lets a viewer pick driver+race and see lap times with sector breakdown. Brunel Racing dependency severed if no engagement by Wk3 Day 5.
**Tools/tech:** Postgres 16 (Docker locally; Neon.tech for cloud), SQLAlchemy, FastF1 ingest scripts, Streamlit, Streamlit Community Cloud, Docker, GitHub Actions for basic CI.
**Deliverable:** Public Streamlit URL pasteable into a message; idempotent ingest script; first dashboard screen.

#### Week 3 (May 18 – May 24) — Postgres + ingest + cloud deploy moves up

- [ ] Postgres 16 in Docker, schema for `sessions / drivers / laps / telemetry`
- [ ] FastF1 ingest script — idempotent (re-running doesn't duplicate rows)
- [ ] Ingest 1 full season as the test corpus
- [ ] Streamlit skeleton: pick driver/race, list lap times
- [ ] **Cloud deploy moves to this week (Wk3, not Wk4):** push to Streamlit Community Cloud, get public URL
- [ ] **Brunel Racing hard kill checkpoint — Day 5 of this week:** if no clean CSV path, commit publicly in `LOG.md`: *"validated on held-out FastF1 races"*. Stop chasing.

#### Week 4 (May 25 – May 31) — dashboard polish + week-buffer for Phase 3 leakage debugging

- [ ] Sector breakdown chart on the Streamlit page
- [ ] Race selector with proper season/round dropdowns
- [ ] First README pass: live URL, screenshots, one-paragraph project pitch
- [ ] Tag `v0.2-pipeline`
- [ ] **LinkedIn post #2 — "first 3 weeks shipped"** (end of Wk4): public Streamlit URL + one screenshot of the dashboard + one paragraph on what it ingests. This is the first post with a working artefact behind it.
- [ ] **Reclaimed week (cloud deploy moved to Wk3):** absorb any Phase 3 leakage debugging early; if not needed, lightly polish ingest + add basic schema migrations

---

**Brunel Racing outreach moves to Phase 3.** Rationale: contacting them on Day 1 with nothing to show looks like a student fishing for data; contacting them when there is a working physics + residual model + a public dashboard URL signals seriousness and gives them something to react to. The Wk3 Day 5 kill date in `ARIS-FINAL-PLAN.md` is *deferred*, not removed — it shifts to Phase 3.

### Phase 3 — Lap-time predictor: physics + residual ML + conformal intervals (Weeks 5–7, June 1 – June 21)

**Goal:** Predict a held-out stint's lap times to floor < 1.0 s / target < 0.7 s / stretch < 0.5 s MAE, with conformal 90% prediction intervals plotted, on 5 held-out races. Train/test split by race, never by lap.
**Tools/tech:** Rajamani Ch. 2, NumPy, SciPy, scikit-learn, XGBoost, optional small PyTorch MLP, custom split-conformal harness, pytest, race-by-race CV harness.
**Deliverable:** Notebook + script that hits the MAE target on held-out races, residual contribution visualised, conformal intervals plotted, leakage tripwire test passing in CI.

#### Week 5 (Jun 1 – Jun 7) — leakage tripwire FIRST, then bicycle model, send Brunel WhatsApp

- [ ] **Day 1 of Phase 3:** commit `tests/test_no_leakage.py` — race-by-race CV harness + a unit test that fails if any held-out race appears in the training fold (Tier B graft, single most important commit of Phase 3)
- [ ] Read Rajamani Ch. 2 (single-track bicycle model)
- [ ] Hand-code bicycle model in Python; plot predicted vs actual on one stint (it will be wrong — fine)
- [ ] Add **fuel-burn linear term** + **pit-loss constant** so the physics layer covers what a strategy reviewer expects
- [ ] Commit physics module with tests for invariants (mass conservation, monotonic fuel burn, etc.)
- [ ] **Send the Brunel Racing WhatsApp (final version in `ARIS-FINAL-PLAN.md` §4)** — now that the public Streamlit URL + ingest pipeline + first physics layer exist, the message can lead with a working artefact, not an idea. Attach the live URL and one chart.

#### Week 6 (Jun 8 – Jun 14) — tire degradation curve

- [ ] Tire degradation curve: linear-with-fuel + exponential wear (Pacejka-style, simplified)
- [ ] Plug into the physics model; re-plot stint
- [ ] Notebook: per-compound deg curves visualised on real FastF1 stints
- [ ] Document assumptions in `docs/physics-model.md`

#### Week 7 (Jun 15 – Jun 21) — residual ML + conformal calibration

- [ ] Residual layer: XGBoost (or tiny sklearn MLP) — target = (actual lap time − physics prediction)
- [ ] Train/test split **by race**, never by lap (leakage tripwire still green)
- [ ] Compute MAE per fold; report against floor / target / stretch
- [ ] **Split-conformal calibration harness** — empirical coverage on held-out fold, per-stint interval width plotted
- [ ] Strategy backtest stub: undercut / SC-sensitivity scaffolding (full report comes in Phase 7)
- [ ] **Phase 3 kill criterion:** if MAE > 1.5 s on held-out, drop residual ML, ship physics-only with honest conformal intervals
- [ ] **Brunel Racing kill checkpoint (deferred from Wk3 Day 5):** if no reply / data path by end of Wk7, commit publicly in `LOG.md`: *"validated on held-out FastF1 races"*. Stop chasing.
- [ ] Tag `v0.3-predictor`
- [ ] **LinkedIn post #3 — "first real result"**: predictor MAE on held-out races + conformal coverage plot + one chart of physics vs residual contribution. First post that contains a hard, verifiable number.

---

### Phase 4 — Counterfactual simulator (Weeks 8–9, June 22 – July 5)

**Goal:** A clean perturbation API — `simulate(state, action_change) → predicted_delta` — and a Streamlit page where you pick a real lap, perturb one action, and see the new predicted lap time + delta chart. This produces the screenshot that goes into the demo video.
**Tools/tech:** Python OO design, NumPy, the Phase 3 model, Streamlit, hypothesis-based property tests.
**Deliverable:** "Lift 30 m earlier in T7 → +0.18 s" screenshot.

#### Week 8 (Jun 22 – Jun 28) — perturbation API

- [ ] Action vocabulary: lift point, brake point, line offset, pit lap, compound choice
- [ ] `simulate(state, action_change)` returns delta + new predicted stint
- [ ] Property tests: monotonicity (later pit ≠ earlier pit unless tire deg dominates), idempotence on null action
- [ ] Hook into the Phase 3 predictor

#### Week 9 (Jun 29 – Jul 5) — what-if Streamlit page

- [ ] What-if mode in Streamlit: real lap selector + action sliders
- [ ] Predicted delta + chart + before/after comparison
- [ ] Capture the screenshot for the demo video
- [ ] Tag `v0.4-counterfactual`
- [ ] **LinkedIn post #4 — "what-if simulator"**: the "lift 30 m earlier T7 → +0.18 s" screenshot + one paragraph on counterfactual reasoning. First post that's hard for anyone to replicate in 5 minutes.

---

### Phase 5 — Always-on loop + tiered tick architecture (Weeks 10–11, July 6 – July 19)

**Goal:** The "always-on" claim is true — feed updates without you asking. Replay a real race lap-by-lap; every 5 s take current state, run top-K action perturbations, surface top 3 with predicted deltas. Tier 1 monitor + Tier 3 macro recompute hooks in place. **Slim 3-day Monte Carlo layer (Phase 4.5)** lives inside this phase as Wk11 days.
**Tools/tech:** asyncio / threading, Streamlit auto-refresh, the Phase 4 simulator, NumPy MC sampler, MATLAB/Simulink (parallel evening work — separate `aris-matlab-validation` repo).
**Deliverable:** Streamlit "Watch" mode showing a streaming feed of recommendations during a race replay.

#### Week 10 (Jul 6 – Jul 12) — replay-as-live + Tier 1 + Tier 3

- [ ] Replay engine: feed FastF1 historical lap-by-lap as if live
- [ ] Tier 1 monitor (every 1–2 s): anomaly detection on telemetry
- [ ] Tier 3 macro (per lap): action search across pit / compound / defend / attack
- [ ] Streamlit "Watch" feed: scrolling cards, top-3 recommendations
- [ ] **Phase 5 kill criterion:** if 5 s cadence is missed, loosen to 15 s and document in `docs/latency-budget.md`

#### Week 11 (Jul 13 – Jul 19) — Phase 4.5 MC slim layer + start MATLAB port

- [ ] **3-day Monte Carlo slim layer:** sample N continuations of remaining race; aggregate to win-prob delta on each top-3 recommendation
- [ ] Event-driven recompute hook (<400 ms): SC/VSC, competitor pit, weather threshold, pace residual
- [ ] **MATLAB/Simulink port (evenings, parallel):** start `aris-matlab-validation` repo — bicycle module ported, cross-checked against Python on the same stint
- [ ] Tag `v0.5-always-on`
- [ ] **LinkedIn post #5 — "always-on loop"**: short clip / GIF of the recommendation feed updating during a race replay + one paragraph on the tiered tick architecture (the part that signals systems-engineering thinking).

---

### Phase 6 — LLM narration + MATLAB validation finish (Weeks 12–13, July 20 – August 2)

**Goal:** Structured recommendations narrated into clean sentences by a local LLM; MATLAB validation repo finished and linked from main README; `Ask` mode (RAG over ARIS state) live.
**Tools/tech:** Ollama + Llama 3.1 8B q5 (3.2 3B fallback), prompt templates, simple RAG over ARIS structured state, Claude API (final week of August only, demo polish), MATLAB / Simulink.
**Deliverable:** Narrated recommendation feed + RAG-grounded `Ask` mode + finished `aris-matlab-validation` repo.

#### Week 12 (Jul 20 – Jul 26) — Llama narrator + RAG

- [ ] Prompt template: structured JSON recommendation → human sentence
- [ ] Local Llama 3.1 8B narrating in real time during replay
- [ ] `Ask` mode: natural-language Q&A grounded in ARIS state (RAG over model fits, residuals, MC runs)
- [ ] Citation in every answer: which model fit / residual / MC run was drawn from

#### Week 13 (Jul 27 – Aug 2) — MATLAB port finish + LLM polish

- [ ] Finish `aris-matlab-validation` — Simulink block diagram, comparison plot vs Python, README with placement-relevant framing
- [ ] Pin the MATLAB repo on GitHub profile
- [ ] LLM prompt regression tests (sample inputs → expected sentence shapes)
- [ ] Tag `v0.6-narrated`
- [ ] **LinkedIn post #6 — "narrated strategy + MATLAB validation"**: a short narrated example + the MATLAB-vs-Python cross-validation plot. Two pieces of unique signal in one post.

---

### Phase 7 — Eval harness + conformal report + strategy backtest + 90-second demo (Weeks 14–15, August 3 – August 16)

**Goal:** A defensible eval pack: backtest on 5 held-out races, MAE with conformal 90% intervals, % of recommendations that "would have been right", strategy-language backtest report, 90-second demo video.
**Tools/tech:** custom eval harness, matplotlib reports, `docs/strategy-backtest.md`, OBS Studio, DaVinci Resolve / CapCut, Claude API (narration polish for the video only), YouTube unlisted, Hugging Face Spaces (Tier C).
**Deliverable:** YouTube unlisted demo + GitHub repo with eval numbers + strategy-language report + MATLAB repo linked + HF Space (optional) + 2 blog posts queued.

#### Week 14 (Aug 3 – Aug 9) — eval pack + strategy report + conformal calibration deep-dive

- [ ] Backtest on 5 held-out races; full eval table
- [ ] Conformal calibration empirical coverage check; coverage curve plot
- [ ] **`docs/strategy-backtest.md` (~1 day):** undercut risk, SC sensitivity, pit-window deltas, recommendation hit-rate — written for a strategy hiring manager, not a metrics dashboard
- [ ] **Phase 7 kill criterion:** if demo video is taking > 5 days, ship a 60-second cut. Done > perfect.

#### Week 15 (Aug 10 – Aug 16) — demo video + Replay mode + HF Space

- [ ] `Replay` mode: scrub past laps, see what ARIS *would have* recommended at any moment vs what actually happened (recording surface for the video)
- [ ] OBS screen recording — three beats: (1) "real lap from [race], ARIS watching live"; (2) "lap 23, ARIS recommends X +0.2 s ± 0.15 s; driver did Y, lost 0.3 s"; (3) "trained on 5 seasons, validated on held-out, conformal intervals, runs locally"
- [ ] Edit in DaVinci/CapCut; final cut ≤ 90 s; voiceover (Claude API allowed for polish)
- [ ] Upload to YouTube unlisted; embed in main README
- [ ] Hugging Face Space (Tier C, free CV signal) — deploy ARIS Watch mode publicly
- [ ] Tag `v1.0-shipped`
- [ ] **LinkedIn post #7 — "ARIS shipped"**: pin the demo video, link the repo, link the HF Space, link the strategy backtest report. The flagship post the placement applications point back to.

---

### Phase 8 — Placement applications prep (Weeks 16–17, August 17 – August 31)

**Goal:** Application pack ready to fire on Day 1 of Year 2 — CV mapped to role-listing language, 2 blog posts live, cover-letter templates per team, alumni cold-message pipeline running, mock interviews booked.
**Tools/tech:** LinkedIn, Medium, the role-language mapping table from `ARIS-FINAL-PLAN.md` §2, Brunel Careers Service, mock-interview friend.
**Deliverable:** Application pack ready for November 2026 placement window.

#### Week 16 (Aug 17 – Aug 23) — CV + blog posts + cover letters

- [ ] CV rewrite: ARIS at top, mapped to role-language table
- [ ] Brunel Careers Service review on the new CV
- [ ] **LinkedIn post #8 — technical deep-dive (long-form)**: how ARIS works under the hood; cross-post to Medium
- [ ] **LinkedIn post #9 — motivation/story (long-form)**: why I built it, what I learned; cross-post to Medium
- [ ] Cover-letter templates per team (McLaren, Williams, Red Bull, Mercedes HPP, M-Sport, Alpine, Williams Advanced Engineering, Red Bull Advanced Technologies, AP Racing, Stray Systems, Bentley Motors)

#### Week 17 (Aug 24 – Aug 31) — alumni outreach + mock interviews + canonical questions

- [ ] 3 cold messages/week to Brunel alumni at target firms (LinkedIn search: Brunel + company)
- [ ] Mock interview #1 with the friend flagged in Week 0
- [ ] Drill the five canonical strategy interview questions (undercut/overcut, gap-to-leader vs gap-ahead, 1-stop vs 2-stop in mixed weather, pit-stop walkthrough, "defend a decision under time pressure")
- [ ] Walk-through dry-run: open any line of ARIS code and answer the 5-question test (what / why / breaks / would change / show me the line)
- [ ] Final tag `v1.0-placement-ready`; freeze main; only doc-level commits afterwards

---

### Phase 9 — Year 2 sustain + sim-racing extension hook (Sept 2026 → placement decision)

**Goal:** Keep the GitHub graph green, ship the placement applications in November, build the sim-racing adapter as a clean extension if/when time allows.
**Tools/tech:** ongoing — plus iRacing / ACC / Le Mans Ultimate / rFactor 2 telemetry adapters (Y2), behind ARIS's existing `DataSource` abstraction.
**Deliverable:** Placement offer.

#### Ongoing (Sept 2026 onward)

- [ ] 1 commit/week minimum (keep the streak)
- [ ] LinkedIn post cadence shifts to **monthly**, only when there's a genuinely new artefact (a new feature, a new validation result, a sim-racing adapter demo). No filler posts.
- [ ] Friday 2-hour interview prep block (vehicle dynamics + LeetCode-easy + behavioural)
- [ ] **November 2026:** fire applications (Williams VPS, Mercedes AMG HPP, McLaren, Red Bull, Aston Martin)
- [ ] Sim-racing adapter (if time): `DataSource` impl for iRacing/ACC; cover-letter line *"currently extending ARIS to read sim-racing telemetry, enabling live narration during human driving sessions"*
- [ ] Brunel Racing in-person test-day visit (Wk8/9 or whenever offered, regardless of summer engagement)

---

## Hard kill / pivot criteria (refer back here at every weekly retro)

- **Wk7 (end of Phase 3)** — Brunel Racing was contacted in Wk5 with a working artefact; if no reply / data path by end of Wk7, publicly pivot in `LOG.md` to *"validated on held-out FastF1 races"*. Do not chase. (This is the deferred Wk3 Day 5 kill — moved because outreach itself moved.)
- **Wk7** — predictor MAE > 1.5 s on held-out → drop residual ML, ship physics-only with conformal intervals.
- **Wk11** — always-on loop won't hit 5 s cadence → loosen to 15 s, document the tradeoff.
- **Wk14** — demo video taking > 5 days → ship 60-second cut.

## What we explicitly do NOT do this summer

QDIE / quant plugin · FS-AI · reinforcement learning · a research paper · world-model anything · calling it UDX · asking to sit in Brunel Racing meetings · spending money before Wk12.

---

*This document is the hub. Every Sunday evening, write `WEEK-NN-PLAN.md` (next week elaborated) referring to this file as the source of context and reasoning. Tick boxes here as deliverables land — don't let it rot.*
