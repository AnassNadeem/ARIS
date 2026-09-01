# ARIS

[![ci](https://github.com/AnassNadeem/ARIS/actions/workflows/ci.yml/badge.svg)](https://github.com/AnassNadeem/ARIS/actions/workflows/ci.yml)

> **Disclaimer:** ARIS is an unofficial project. It is not affiliated with,
> associated with, authorized by, endorsed by, or in any way officially
> connected to Formula 1, the FIA, Formula One Group, or any Formula 1
> team or rights holder. “Formula 1”, “F1”, and related marks are
> trademarks of their respective owners.

ARIS (Always On Race Intelligence System) is a race-strategy decision-support
console: it watches a live or replayed Grand Prix, scores stay-out vs pit
calls against real telemetry, and races an ARIS ghost against the field so
every recommendation comes with a quantified lap-time delta — classical
decision support stitched with modern ML, not a black box.

**For reviewers:** open [arisf1.tech](https://arisf1.tech), pick a 2024 or 2025
race, turn ARIS on, and watch the timing tower and ghost run the plan you
chose. The headline result is mid-race match-rate **0.345** (30/87) vs stay-out,
with a 2024 calendar blend MAE of **0.583 s** that does **not** beat MA(2).

### ▶ Live — [**arisf1.tech**](https://arisf1.tech)

**Strategy / Replay app:** [arisf1.tech](https://arisf1.tech) — Next.js console
(timing tower, track map, ARIS ghost).
**Lap explorer (Phase 2):** Streamlit — see
[`docs/legacy-streamlit-deploy.md`](./docs/legacy-streamlit-deploy.md).

**Where it stands today** (every figure is aimed vs actual; full account in
[`docs/model-status.md`](./docs/model-status.md)):

| Question | Aimed | Actual |
|---|---|---|
| 2024 calendar one-step blend MAE | ≤ **0.783** (1.5× MA(2) **0.522**) | **0.583 s** — closest stack, does **not** beat MA(2) |
| Mid-race match-rate vs stay-out | > **0.276** (24/87) | **0.345** (30/87) T2 default; G1.5-only was 0.322 |
| Lights-out position-delta | ≤ 0 | **−1.73** all 48 / **−1.49** clean (n=35) |
| Tyre slopes from lap time | physical C1<…<C5 | G2/G3/G4 miss the gate — **G1.5 locked** |
| Physics `team_sim − actual` intercept | a stable intercept | mean **+989 s**, std **544** — **closed**, do not subtract |

Phase 2 (`v0.2-pipeline`) is tagged and live: FastF1 → Postgres ingest, a
pandas-vs-SQL MA(2) canary at **machine epsilon**, and the public Streamlit
lap explorer. That ingest floor — **0.460 s MAE on green-flag laps** across
eight reference races — is still the lossless-ingest check, not the predictor
headline. The five-race Phase C row (blend **0.549 s** vs MA(2) **0.469**) is
superseded by the E3 calendar figure above. Tags past `v0.2-pipeline` have
not been cut.

**Wet / rain-affected races are not calibrated.** A conservative INTER/WET
heuristic exists (`src/aris/physics/wet.py`) and is tagged `wet_heuristic` on
the radio call. The dry headline remains the **87-event 0.345** slice.
`--include-wet` scores INTER/WET inflections only; Spain-style `rainfall=True`
dry races stay out of that 87. The wet slice after T3-patch is **0.345
(38/110)** — the 0.340 gate passes; still an uncalibrated heuristic, not
a headline. T3-B/C field undercut / overcut arcs are formally closed
(0 pp on targeted events); flags stay off. **READY FOR T4.**

---

## Status

| | |
|---|---|
| **Started** | 2026-05-04 |
| **Ship target** | 2026-08-31 (`v1.0-shipped`); Dutch GP demo **21–23 August 2026** |
| **Current phase** | Public-facing refresh, T−4 to Zandvoort. Predictor / match-rate / ranking numbers in [`docs/model-status.md`](./docs/model-status.md). Strategy demo on `main`, untagged past `v0.2` |
| **Live** | [arisf1.tech](https://arisf1.tech) |
| **Last tag** | [`v0.2-pipeline`](https://github.com/AnassNadeem/ARIS/releases/tag/v0.2-pipeline) — Postgres ingest + live lap explorer; ingest canary **0.460 s MAE** on green-flag laps across 8 races / 6383 laps |
| **Held-out predictor MAE** | E3 2024 calendar blend **0.583 s** vs aimed ≤ **0.783** (1.5× MA(2) **0.522**). Does **not** beat MA(2). China is the 1.5× miss (**0.596** vs aimed **0.563**) |
| **Mid-race match-rate** | **0.322** (28/87) vs stay-out **0.276** (24/87) |
| **Lights-out position-delta** | **−1.73** all 48 / **−1.49** clean (n=35) / **−2.38** disrupted (n=13). Identity-safe ranking, not FIA points |
| **Shipped tyre model** | **G1.5 locked** (Phase G.5): global compound slopes SOFT **0.08** / MEDIUM **0.05** / HARD **0.03** s/lap plus G1.4 physics-delta rollout. Fitted C-code overlays (G2/G3/G4) remain opt-in only. See [`docs/tyre-degradation-research.md`](./docs/tyre-degradation-research.md). |
| **Physics offset** | **Closed.** `team_sim − actual` mean **+989 s**, std **544**; per configured lap **+17.3 s**. Do not subtract. See [`docs/physics-calibration-research.md`](./docs/physics-calibration-research.md). |
| **Wet races** | **Out of scope.** No wet-strategy logic. Combined walk-forward **0.356** (48/135) inflections excluded as rainfall / wet compound / red-flag — a model gap, not an eval choice |
| **Cadence** | 6 hrs/day × 6 days/week (Sundays off) |

This repo is **under active construction**. Phases ship sequentially as
tagged releases; nothing in this README is an over-claim of state.

---

## What ARIS is

A **hybrid AI race strategist**. Six components, layered:

| Layer | Component | Approach |
|---|---|---|
| L0 | Telemetry ingest | FastF1 historical + live timing |
| L1 | State estimation | Per-tick `RaceState` snapshot |
| L2 | Lap-time predictor | Hand-coded bicycle model + tire deg curve, with an XGBoost residual learned on FastF1 data |
| L3 | Counterfactual simulator | Perturb action → predict outcome (`simulate(state, action) → delta`) |
| L4 | Recommender | Action search + Monte Carlo over remaining race, MC percentile bands (not calibrated conformal) |
| L5 | Narrator | Local Llama 3.1 turns top recommendation into one-sentence radio call |
| L6 | Dashboard | Streamlit (`apps/`): lap explorer + Strategy (Watch · Ask · What-if · Replay) |

It runs **always-on** against a race replay (FastF1 historical, treated
as live), updating recommendations on a tiered cadence:
1–2 s monitor · sector-level micro · lap-level macro · event-driven recompute.
That replay **is** `engine/clock.py` + `engine/session.py` — the original
`replay.py` was never added, on purpose. Walk-forward backtest
(`scripts/backtest.py`) drives those same objects unattended; see
[`docs/replay-architecture.md`](./docs/replay-architecture.md).

ARIS models the full range of race-engineer decisions throughout a race
(pit timing, compound choice, pace targets, SC/VSC reactions) in service of
the best realistic outcome for the driver — not a narrow pit/no-pit binary.
Given real data constraints, the explicit goal is the best achievable
decision support within those constraints, not a claim of perfect or
superhuman strategy.

## What ARIS is NOT

| | |
|---|---|
| ❌ **A world model** | No learned latent dynamics. The simulator is hand-coded physics + ML residual. Not Dreamer, RSSM, or GAIA-1. |
| ❌ **Reinforcement learning** | No learned policy, no reward signal. Action selection is search-based, not policy-gradient. |
| ❌ **An LLM agent** | The LLM narrates. It does not control. |
| ❌ **Deep learning at its core** | The deep component is the LLM, used pretrained for narration only. |

The discipline matters: F1 hiring managers can spot over-claims in 30s.
ARIS is *classical decision support* stitched together with *modern ML
and LLMs* — and that's what gets it through interview scrutiny.

---

## Stack

**Core:**
Python 3.11 · NumPy · pandas · scikit-learn · XGBoost · FastF1

**Data + dashboard (Phase 2):**
Postgres 16 · SQLAlchemy 2.0 · Streamlit · Docker

**Inference + narration (Phase 6):**
Ollama · Llama 3.1 8B (q5_K_M, local on RTX 5070)

**Validation (parallel, Phase 5–6):**
MATLAB / Simulink port of the bicycle module — separate repo
[`aris-matlab-validation`](#) (link when published)

---

## Roadmap

Status key: ✅ tagged · ◐ code on `main`, tag not cut · ○ not done.
“◀ next” marks the next **tag** to cut after Phase A review — not “nothing exists yet.”

| Phase | Weeks | Output | Tag | Status |
|---|---|---|---|---|
| 0 | 0 | Loadout — Python, Docker, Ollama, NVIDIA + CUDA, repo skeleton | (prep, untagged) | ✅ |
| 1 | 1–2 | Python foundations + first FastF1 plot | `v0.1-foundation` | ✅ |
| 2 | 3–4 | Postgres ingest + Streamlit lap explorer, deployed | `v0.2-pipeline` | ✅ |
| 3 | 5–7 | Lap-time predictor (physics + residual ML); honest held-out MAE published | `v0.3-predictor` | ◐ code yes; E3 calendar blend **0.583 s** vs aimed ≤ **0.783** (MA(2) **0.522**); tag not cut |
| 4 | 8–9 | Counterfactual simulator (pit + lift/brake actions) | `v0.4-counterfactual` | ◐ pit + lift/brake on `main`; tag not cut |
| 5 | 10–11 | Always-on Strategy loop + MC bands; MATLAB port begins | `v0.5-always-on` | ◐ engine + Strategy UI + MC; MATLAB not started; tag not cut |
| 6 | 12–13 | LLM narration + grounded Ask; MATLAB validation finish | `v0.6-narrated` | ◐ narration + keyword Ask; true RAG / MATLAB open; tag not cut |
| 7 | 14–15 | Eval harness, real conformal (mapie), backtest report, demo video | `v1.0-shipped` | ○ (Phase A only stabilized naming/leakage) |
| 8 | 16–17 | Placement-applications-ready CV + cover letters | `v1.0-placement-ready` | ○ |

---

## Repo layout

```
ARIS/
├── src/aris/           # production logic (io, eval, physics, models, strategy)
│   ├── io/             # Postgres + FastF1 ingest
│   ├── eval/           # baselines, scoring, laptime harness
│   ├── physics/        # bicycle model, tyres, stint detection
│   ├── models/         # features, residual XGBoost, predict
│   ├── state.py        # RaceState snapshot
│   ├── simulate.py     # counterfactual pit/stay-out
│   ├── montecarlo.py   # slim MC confidence layer
│   ├── recommend.py    # top-3 strategy search
│   └── narrate.py      # Ollama radio-call narration
├── frontend-next/      # Next.js Strategy / Replay console (canonical UI)
├── backend/            # FastAPI broker (Heroku in production)
├── apps/               # Streamlit lap explorer (Phase 2)
├── scripts/            # ingest, train_residual, smoke_strategy, deploy_to_neon
├── models/             # gitignored trained artefacts (residual_xgb.json)
├── tests/
└── docs/               # model-status, replay architecture, research notes
```

---

## First-time setup (after cloning)

```powershell
# Build the residual predictor
python scripts/train_residual.py `
    --years 2018 2019 2020 2021 2022 2023
# Build the CQL training dataset
python scripts/build_cql_dataset.py `
    --years 2018 2019 2020 2021 2022 2023
# Train the CQL Q-network
python scripts/train_cql.py --dataset data/cql_dataset.parquet
```

CQL scoring is opt-in (`recommend(..., scoring="cql"|"blend")`) until it
beats the dry 87-event physics walk. Default `recommend()` scoring stays
`physics`. Torch is an optional extra: `uv sync --extra cql`.

## Getting started

The fastest way to see ARIS is the live console at [arisf1.tech](https://arisf1.tech).
To run it yourself, clone and set up the environment (uv is the
recommended path; a plain-pip fallback is in `requirements.txt`):

```powershell
git clone https://github.com/AnassNadeem/ARIS.git
cd ARIS

# uv (recommended — mirrors CI exactly)
uv sync --extra dev

# ...or plain pip
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run the test suite (DB integration tests skip without ARIS_DB_URL)
uv run pytest
```

**Run the dashboard locally (Phase 2).** Bring up Postgres, ingest a season, then
launch Streamlit. The app reads `ARIS_DB_URL` from a repo-root `.env` (see
[`.env.example`](./.env.example)). Production Strategy/Replay deploy:
[`DEPLOY.md`](./DEPLOY.md). Streamlit Cloud:
[`docs/legacy-streamlit-deploy.md`](./docs/legacy-streamlit-deploy.md).

```powershell
docker compose up -d                       # local Postgres on :5432
python scripts\ingest_season.py 2024       # idempotent — re-running never duplicates
streamlit run apps\streamlit_app.py        # → http://localhost:8501
```

**Replay the baseline cross-check** — the canary that proves the ingest is lossless:

```powershell
python scripts\baseline_crosscheck.py      # SQL vs pandas MA(2), must match to ~1e-15 s
python -m aris.eval.run_baseline_all_races # regenerate the 0.460 s green-flag floor
```

The FastF1 cache lands in `fastf1_cache/` (gitignored — regenerable); subsequent
`session.load()` calls return in ~1 second.

---

## v1 strategy demo (end-to-end)

ARIS v1 adds a **Race Strategy** page: pick a replay lap, optionally override
compound/fuel, and get top-3 pit/stay-out recommendations with a narrated radio call.

**Shipped tyre model (G1.5, locked).** `simulate()` / `recommend()` / the
Strategy UI use global compound slopes (SOFT 0.08 / MEDIUM 0.05 / HARD 0.03)
and a physics-delta rollout: the residual is applied once on the first
remaining lap, then only tyre slope + fuel. Four evidenced attempts to
replace those globals with a fitted C-code overlay (unconstrained, isotonic,
context-aware GBT) did not beat this path on the walk-forward gate. The
overlays stay behind `ARIS_TRUE_COMPOUND_SLOPES`; unset is G1.5. That is a
considered lock, not a provisional fallback — full account in
[`docs/tyre-degradation-research.md`](./docs/tyre-degradation-research.md).

**Wet races are out of scope.** The candidate menu is dry (SOFT / MEDIUM /
HARD). Combined walk-forward **0.356** (48/135) inflections are excluded as
rainfall / wet compound / red-flag. That gap is why, not a scoring trick.

**Ask ARIS** on the public demo retrieves from a committed **snapshot** of
14 real G1.5 decision records plus classified results and cited concepts —
not the local JSONL log or the on-disk FAISS index. The panel is labeled
**snapshot, not live**.

**Prerequisites:** Postgres with 2024 season ingested, FastF1 cache warmed, and
(optionally) the trained residual model in `models/residual_xgb.json`.

```powershell
# 1. Environment
docker compose up -d
uv sync --extra dev          # or: pip install -r requirements.txt
python scripts\ingest_season.py 2024

# 2. Train the XGBoost residual (first run only; ~2 min with warm cache)
python scripts\train_residual.py

# 3. Launch dashboard — use the "Strategy" page in the sidebar
streamlit run apps\streamlit_app.py

# 4. CLI smoke test (Bahrain 2024 R, VER, lap 15)
python scripts\smoke_strategy.py --no-llm

# 5. Held-out lap-time MAE eval
python -m aris.eval.laptime
```

**Ollama narration (optional):** install [Ollama](https://ollama.com), pull
`llama3.1:8b-instruct-q5_K_M`, and leave the "Use Ollama narration" checkbox on
in the Strategy page. If Ollama is down, ARIS falls back to a template radio call.

**Honest predictor note:** the physics + tyre + XGBoost stack is wired end-to-end.
The figure to quote is the **E3 2024 calendar** (24 races, overlay unset):
**MA(2) 0.522 · physics-only 17.378 · physics+residual 0.948 · blended
0.583 s**, aimed ≤ **0.783** (1.5× MA(2)). **The blend does not beat MA(2).**
China is the 1.5× miss (blend **0.596** vs aimed **0.563**). The older
five-race Phase C row (MA(2) **0.469** · blend **0.549 s** on China, Monaco,
Spain, Belgium, Abu Dhabi) remains in `results/heldout-laptime-mae.csv` as
the short held-out; it is not the headline.

Raw next-lap MAE is not the only metric that matters for ARIS. MA(2) has no
action-conditional or counterfactual capability: it cannot answer “what if we
pit / lift / brake here?” Mid-race match-rate vs stay-out is **0.322**
(28/87) vs aimed > **0.276**. Lights-out position-delta is **−1.73** all 48 /
**−1.49** clean — identity-safe ranking, not FIA points. Those are additional
context, not an excuse: the calendar blend still does not beat MA(2).

---

## Phase 1 artefact — first FastF1 pull

![Verstappen fastest race lap — Bahrain 2024 (speed vs distance)](assets/screenshots/bahrain-2024-ver-fastest-lap.png)

*Where this started: Max Verstappen's fastest race lap at Bahrain 2024 (lap 39,
1:32.608, soft tyre), speed vs distance over the 5.41 km lap, straight from FastF1
telemetry in [`notebooks/01-fastf1-first-pull.ipynb`](./notebooks/01-fastf1-first-pull.ipynb).
This was the Phase 1 hero; the live dashboard above is the Phase 2 one.*

---

## License

MIT — see [`LICENSE`](./LICENSE).

---

## Author

**Anass Nadeem** · CS with AI, Brunel University of London ·
[github.com/AnassNadeem](https://github.com/AnassNadeem)

Building ARIS as the centrepiece project for 2027 industrial placements
in F1 / motorsport software (Vehicle Performance Software, Strategy Tools).
