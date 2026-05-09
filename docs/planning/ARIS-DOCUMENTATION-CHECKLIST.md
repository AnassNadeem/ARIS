# ARIS — Documentation Checklist

**Purpose:** Treat ARIS as a real software project, not a student capstone. Every artefact below is what a senior engineer at Williams VPS / Mercedes HPP / McLaren expects to see when they open a public repo. Missing pieces are *more* visible than missing features — a sparse repo with great code looks half-finished; a fully-documented repo with average code looks shipped.

**How to use:** Each item has a Tier and a Window. Build them in tier order during the phases listed. Don't try to write everything in Wk 17 — most of these only get good if they grow alongside the code.

---

## Tier S — The repo's "first 60 seconds" (must be perfect)

These are the artefacts an engineer sees in the first minute of opening the GitHub URL. If these aren't right, nothing below matters.

### 1. `README.md` (root)

**Window:** First pass Wk 4. Heavy revision Wk 15–17.

The README is the demo. Structure (in this order):

1. **Hero block** (above the fold — visible without scrolling):
   - Project name + one-line pitch (≤ 20 words)
   - Status badge row: build status, license, Python version, commits, last-update
   - Hero GIF or screenshot (3–5 seconds of ARIS doing something visually obvious)
   - Live demo URL + 90-second video URL (both clickable)
2. **What it is** (2 short paragraphs):
   - Problem statement in plain English
   - One paragraph on the approach (hybrid physics + ML + LLM, conformal calibrated)
3. **Headline numbers** (table):
   - Held-out MAE point estimate + 90% prediction interval coverage
   - Number of validated races
   - Always-on tick latency
   - Recommendation hit-rate
4. **Quick start** (the 1-command install):
   ```bash
   docker compose up && streamlit run app/Home.py
   ```
   Must work on a fresh clone. If it doesn't, the README is wrong.
5. **Architecture diagram** (one image, mermaid or PNG)
6. **What's in this repo** (project structure tree, ≤ 15 lines)
7. **Documentation index** (links to ARCHITECTURE.md, EVAL.md, etc.)
8. **Acknowledgements** (FastF1, TUMFTM if you read their code, libraries you used)
9. **License**

**Cold-open test:** Open it on your phone, on mobile data, in front of a friend who has never seen it. Time them: do they understand what it is in 60 seconds? Would they click the demo? If no, fix it.

### 2. Hero GIF / screenshot

**Window:** Wk 9 (after counterfactual mode ships) for v1; Wk 15 for final.

A 3–5 second loop showing ARIS doing the most visually compelling thing it does. The "lift 30m earlier in T7 → +0.18s" frame is the canonical asset. Recorded in OBS, exported to GIF (ffmpeg or ScreenToGif). Must be under 5MB to render inline.

### 3. 90-second demo video

**Window:** Wk 15.

Three beats:
- (0:00–0:25) "Real lap from [race], ARIS watching live."
- (0:25–0:55) "Lap 23: ARIS recommends X, +0.2s ± 0.15s. Driver did Y, lost 0.3s."
- (0:55–1:30) "Trained on 5 seasons, validated on held-out, conformal intervals, runs locally."

YouTube unlisted. Embedded in README via thumbnail-with-link. Hard kill: if it takes >5 days to make, ship the 60-second cut.

---

## Tier A — Engineering documentation (must exist, must be defensible)

These prove the project isn't a toy. Reviewers who pass the 60-second test go here next.

### 4. `docs/architecture.md`

**Window:** First pass Wk 1 (yes, day one — even before code). Living document, edit as decisions change.

**Sections:**

1. **System overview** — block diagram showing: data sources → ingest → DB → physics layer → ML residual → counterfactual engine → LLM narrator → UI
2. **Module-by-module breakdown** — for each module: responsibility, inputs, outputs, dependencies, key file paths. ≤ 1 paragraph each.
3. **Data flow diagram** — how a single FastF1 race becomes a recommendation
4. **Tiered tick architecture** — explicit explanation of Tier 1 (1–2s monitor), Tier 3 (per-lap macro), event-driven (<400ms). Why each tier exists; what triggers each.
5. **Tech stack table** — language, framework, DB, ML libraries (already exists in `ARIS-PHASES-WEEKLY-PLAN.md` §0; copy here)
6. **What this isn't** — *explicit* disclaimers: not a world model, not RL, not real-time at sub-second (that's a real F1 stack), not productionized.
7. **Mapping to placement role-listings** — table mapping ARIS modules to specific job-listing language at Williams VPS, Mercedes HPP, etc. (Already exists in your plan — copy here so reviewers see it.)

This is the single most important doc after README. Hiring managers read this to check "do you actually understand what you built."

### 5. `docs/decisions/` (Architecture Decision Records — ADRs)

**Window:** Add one ADR per major design decision, throughout. Aim for 8–12 by ship.

Format: short markdown files numbered `001-use-fastf1.md`, `002-postgres-not-sqlite.md`, etc.

Each ADR is ≤ 1 page with sections: Context, Decision, Consequences, Alternatives Considered.

**Required ADRs (the ones an interviewer will probe):**
- 001 — Why FastF1 (vs scraping / official API / sim-racing UDP)
- 002 — Why Postgres (vs SQLite / Parquet / TimescaleDB)
- 003 — Why physics + residual ML (vs pure ML / pure physics / neural ODE)
- 004 — Why XGBoost (vs MLP / RF / linear)
- 005 — Why split-conformal (vs Bayesian / quantile regression / bootstrap)
- 006 — Why race-by-race CV (vs k-fold / per-lap / time-series CV)
- 007 — Why local Llama (vs Claude API only / OpenAI / no LLM)
- 008 — Why Streamlit (vs FastAPI + React / Dash / Gradio)
- 009 — Why MATLAB validation port (vs unit tests only)
- 010 — Tiered tick architecture rationale

**This is the single highest-leverage documentation addition for interview defensibility.** When asked "why did you choose X?" you point to the ADR.

### 6. `docs/physics-model.md`

**Window:** Wk 6 (during Phase 3).

Explicit assumptions and equations of the bicycle model + tire degradation curve + fuel-burn term + pit-loss constant. Plots showing predicted vs actual on real stints. **Reviewer test:** can a vehicle dynamics engineer read this and replicate it? If no, it's not done.

### 7. `docs/eval.md`

**Window:** Wk 14.

The technical eval pack. Different from `strategy-backtest.md` — this is for ML reviewers.

Sections:
- Splitting protocol (race-by-race, leakage tests)
- Headline table: per-fold MAE point estimate + conformal interval width + coverage
- Coverage curve plot (empirical vs nominal)
- Per-stint width plot
- Ablation: physics-only vs physics+residual vs naive baseline
- Failure mode analysis: where does ARIS predict worst? Why?

### 8. `docs/strategy-backtest.md`

**Window:** Wk 14.

The same numbers, written for a strategy hiring manager (not an ML engineer). Different audience, different vocabulary.

Sections:
- Executive summary (≤ 5 sentences, recruiter-friendly)
- Undercut risk reduction vs naive baseline
- Safety car sensitivity analysis
- Pit-window delta analysis
- Recommendation hit-rate (direction-correct on validatable laps)
- Per-race summaries with one chart each

### 9. `docs/latency-budget.md`

**Window:** Wk 11.

The tiered tick architecture explained operationally. Per-tier latency target, measured actual, what dominates the cost. Honest framing: ARIS is *not* sub-second; it's tiered for human-readable cadence. Document the trade.

### 10. `CHANGELOG.md`

**Window:** Maintain throughout.

Keep-a-Changelog format. Tag-by-tag what changed. Every git tag (v0.1, v0.2, ..., v1.0) gets an entry.

---

## Tier B — Operational documentation (looks professional, costs little)

### 11. `docs/setup.md`

**Window:** Wk 4 first pass; Wk 17 final pass.

Step-by-step "from a clean machine to running ARIS." Covers: Python version, OS gotchas (Windows-specific notes since you're on Windows + RTX 5070), Docker setup, NVIDIA driver + CUDA, Ollama setup, FastF1 cache directory, Postgres init.

Test it on a Windows VM or by asking a friend with no context to follow it. If they hit any error, add a troubleshooting section for that error.

### 12. `docs/runbook.md`

**Window:** Wk 11.

How to *run* ARIS day-to-day:
- How to start a replay
- How to switch between Watch / Ask / What-if / Replay modes
- How to clear caches
- How to ingest a new race
- Known issues and workarounds

This signals "I built something that runs, not just demos."

### 13. `docs/observability.md`

**Window:** Wk 11.

What metrics ARIS exposes (at minimum: tick latency per tier, ingest throughput, model inference time, LLM token throughput, MC sampler runtime). How to view them. **Even a basic version of this signals "operational thinking."**

### 14. `LICENSE`

**Window:** Wk 0 (with initial commit).

MIT or Apache 2.0. Don't overthink. MIT is fine.

### 15. `.github/CONTRIBUTING.md`

**Window:** Wk 16.

Even if you're the only contributor, a CONTRIBUTING.md signals "this is a real project." Cover: how to set up dev env, code style (ruff config), how to run tests, commit message conventions.

### 16. `.github/ISSUE_TEMPLATE/`

**Window:** Wk 16.

Two templates: `bug_report.md` and `feature_request.md`. Tiny effort, large polish signal.

### 17. `.github/workflows/ci.yml`

**Window:** Wk 4.

GitHub Actions running: ruff check, pytest, leakage tripwire test. Must pass on every PR. The green ✓ next to commits is a real signal.

---

## Tier C — Marketing & narrative (the post-build push)

### 18. Two blog posts

**Window:** Wk 16.

Post #1 — Technical deep-dive: how ARIS works under the hood. Physics + ML + LLM + conformal. ~1500 words. Cross-post: GitHub README link section + Medium + dev.to.

Post #2 — Motivation/story: why I built it, what I learned, what surprised me. ~1000 words. More personal. Different audience (recruiters, not engineers).

### 19. LinkedIn build-in-public series

**Window:** Wk 1, 4, 7, 9, 11, 13, 15. Then long-form #8, #9 in Wk 16. (Already in your plan.)

Each post pinned to its phase deliverable. Don't post if there's nothing new to show.

### 20. Demo video (covered above)

### 21. Hugging Face Space

**Window:** Wk 15 (Tier C, optional).

Deploy ARIS Watch mode publicly on HF Spaces. Free signal. Tag the repo with `motorsport`, `formula-1`, `time-series`, `conformal-prediction`.

### 22. GitHub profile README

**Window:** Wk 0 (the very first task).

Pin order, top to bottom: ARIS, MATLAB validation, FastF1 cache utility, hackathon repos by F1-relevance. Bio: one line, "London-based CS undergrad building ARIS — always-on F1 race intelligence." Photo. Location. Contact.

---

## Tier D — Tests & quality signals

### 23. `tests/` directory with real tests

**Window:** Throughout. Critical commits: Wk 5 (`test_no_leakage.py`), Wk 6 (physics invariants), Wk 8 (counterfactual property tests), Wk 13 (LLM regression tests).

Coverage doesn't have to be 90%. It has to be *thoughtful*. Reviewers look for: does the leakage test exist? Are physics invariants tested? Is there a CI run that exercises a real race end-to-end?

### 24. `tests/test_no_leakage.py` — THE most important test

**Window:** Wk 5, Day 1 of Phase 3, BEFORE any model code.

This single file is the answer to "how did you handle data splits?" — the question that gets every ML student into trouble. It must:
- Build the race-by-race CV harness
- Fail explicitly if any held-out race appears in any training fold
- Run in CI on every push

### 25. `LOG.md`

**Window:** Daily, from Wk 1 Day 1 onwards.

Two lines per working day. What you did, what's blocked, what's next. Ugly is fine. Visible is the point.

### 26. Commit message hygiene

**Window:** Always.

No `update`, `fix`, `wip`, `asdf`. Real messages. Imperative mood ("Add", "Fix", "Refactor"), <72 chars first line, optional body. Reviewers spot-check 10 random commits — half meaningful = bad signal.

---

## Tier E — Stretch documentation (if Tier S–D is locked)

### 27. `docs/api.md`

If you expose a Python API for `simulate(state, action_change)`, document it Sphinx-style (or even just docstrings + a generated page). Optional.

### 28. Public Kaggle dataset

If you've built a clean processed dataset on top of FastF1, publish it on Kaggle with a notebook showing how to use it. Free CV signal, costs nothing once data is already cleaned.

### 29. Talk / meetup

Submit a 5-minute lightning talk to a London Python meetup, sim-racing meetup, or motorsport engineering society. Even getting accepted (regardless of quality) goes on the CV.

### 30. Open-source PR to FastF1 or OpenF1

Already discussed. One merged PR to either of these libraries is a permanent signal.

---

## What this catalogue means in priority order

If you only do **Tier S**: you have a presentable repo. ~20% of the way.
If you do **Tier S + Tier A**: you have a defensible repo. ~60% of the way.
If you do **Tier S + A + B**: you have a professional repo. ~85% of the way.
If you do **Tier S + A + B + C + D**: you have a *shipped* project. 100% — what the August 31 success criterion is calibrated for.
Tier E is stretch.

Most students who fail the placement leg of `ARIS-SUCCESS-CRITERIA.md` Dimension 4 do so because they shipped Tier S only. The repo looks fine on first scroll, then falls apart on second click. A reviewer's eyes go straight to `docs/decisions/` — if it's not there, the question becomes "did you actually think through your choices, or did you just code?" That question rarely ends well.

---

## Calendar — when to write what

| Week | What to write |
|---|---|
| Wk 0 | GitHub profile README, repo's `LICENSE`, empty `architecture.md` outline |
| Wk 1 | First real `architecture.md` pass, ADR 001 (why FastF1), `LOG.md` first entry |
| Wk 2 | ADR 002 (why Postgres) |
| Wk 3 | First README pass with live URL, ADR 008 (why Streamlit) |
| Wk 4 | `docs/setup.md` v1, `.github/workflows/ci.yml` |
| Wk 5 | `tests/test_no_leakage.py`, ADR 006 (why race-by-race CV) |
| Wk 6 | `docs/physics-model.md`, ADR 003 (why physics + residual) |
| Wk 7 | ADR 004 (why XGBoost), ADR 005 (why conformal) |
| Wk 9 | Hero GIF for README |
| Wk 11 | `docs/runbook.md`, `docs/observability.md`, `docs/latency-budget.md`, ADR 010 (tiered ticks) |
| Wk 12 | ADR 007 (why local Llama) |
| Wk 13 | LLM regression tests, ADR 009 (why MATLAB port) |
| Wk 14 | `docs/eval.md`, `docs/strategy-backtest.md` |
| Wk 15 | Demo video, README final revision, HF Space |
| Wk 16 | Both blog posts, `CONTRIBUTING.md`, issue templates |
| Wk 17 | Final README polish, `CHANGELOG.md` retrospective entries, freeze |

This calendar is *additive* to the technical work in `ARIS-PHASES-WEEKLY-PLAN.md`. Total documentation overhead is ~30–40 hours across 17 weeks — about 2 hrs/week — but front-loaded toward Wk 14–17.
