# ARIS

**An always-on race-strategy software system that watches a live race,
predicts what's about to happen, and proposes the next decision with a
quantified lap-time delta and a calibrated confidence interval — built
on real F1 telemetry, validated end-to-end on held-out races.**

---

## Status

| | |
|---|---|
| **Started** | 2026-05-04 |
| **Ship target** | 2026-08-31 (`v1.0-shipped`) |
| **Current phase** | Phase 0 — Python foundations + first FastF1 plot |
| **Cadence** | 6 hrs/day × 6 days/week (Sundays off) |

This repo is **under active construction**. Phases ship sequentially as
tagged releases; nothing in this README is an over-claim of state. See
[`BUILD-LOG.md`](./BUILD-LOG.md) for the daily log — friction included.

---

## What ARIS is

A **hybrid AI race strategist**. Six components, layered:

| Layer | Component | Approach |
|---|---|---|
| L0 | Telemetry ingest | FastF1 historical + live timing |
| L1 | State estimation | Per-tick `RaceState` snapshot |
| L2 | Lap-time predictor | Hand-coded bicycle model + tire deg curve, with an XGBoost residual learned on FastF1 data |
| L3 | Counterfactual simulator | Perturb action → predict outcome (`simulate(state, action) → delta`) |
| L4 | Recommender | Action search + Monte Carlo over remaining race, conformal prediction intervals |
| L5 | Narrator | Local Llama 3.1 turns top recommendation into one-sentence radio call |
| L6 | Dashboard | Streamlit, four modes: Watch · Ask · What-if · Replay |

It runs **always-on** against a race replay (FastF1 historical, treated
as live), updating recommendations on a tiered cadence:
1–2 s monitor · sector-level micro · lap-level macro · event-driven recompute.

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

**Data + dashboard (Phase 1):**
Postgres 16 · SQLAlchemy 2.0 · Streamlit · Docker

**Inference + narration (Phase 6):**
Ollama · Llama 3.1 8B (q5_K_M, local on RTX 5070)

**Validation (parallel):**
MATLAB / Simulink port of the bicycle module — separate repo
[`aris-matlab-validation`](#) (Phase 4.7, link when published)

---

## Roadmap

| Phase | Weeks | Output | Tag |
|---|---|---|---|
| 0 | 1–2 | First FastF1 plot, repo skeleton | `v0.1-foundation` |
| 1 | 3–4 | Postgres ingest + Streamlit dashboard, deployed | `v0.2-pipeline` |
| 2 | 5–7 | Lap-time predictor (physics + residual ML), MAE < 1.0 s on held-out | `v0.3-predictor` |
| 3 | 8–9 | Counterfactual simulator, "lift 30 m T7 → +0.18 s" demo | `v0.4-counterfactual` |
| 4 | 10–11 | Always-on loop + recommendation feed | `v0.5-always-on` |
| 4.5 | 12 | Monte Carlo strategy slim layer | folded into v0.5 |
| 4.7 | 11–12 evenings | MATLAB / Simulink validation repo | (separate repo) |
| 6 | 12–13 | LLM narration | `v0.6-narrated` |
| 7 | 14–15 | Eval harness, conformal calibration, 90-second demo video, strategy backtest report | `v1.0-shipped` |
| 8 | 16–17 | Placement-applications-ready CV + cover letters | `v1.0-placement-ready` |

---

## Repo layout

```
ARIS/
├── src/aris/           # production logic (physics, models, eval, simulate)
├── scripts/            # one-off CLIs (ingest, prewarm, eval)
├── notebooks/          # exploration only; ≤5 across Phases 0–2
├── tests/              # pytest, including the leakage tripwire
├── data/               # gitignored (raw + processed parquet)
├── models/             # gitignored (trained artefacts)
├── results/            # gitignored (eval outputs)
├── BUILD-LOG.md        # daily journal, honest about slips
└── ARIS-EXECUTION-PLAN.md
```

---

## Getting started (Phase 0)

Clone, set up the pinned Python interpreter, install FastF1, pre-warm
the race cache.

```powershell
git clone https://github.com/AnassNadeem/ARIS.git
cd ARIS

# Pin Python 3.11.9 via uv (https://docs.astral.sh/uv/)
uv venv --python 3.11.9
.\.venv\Scripts\Activate.ps1

# Install FastF1
uv pip install fastf1

# Pre-warm the FastF1 cache (8 race sessions, runs once)
python scripts\prewarm_cache.py
```

The cache will land in `fastf1_cache/` (gitignored — regenerable).
Subsequent `session.load()` calls in notebooks return in ~1 second.

---

## License

MIT — see [`LICENSE`](./LICENSE).

---

## Author

**Anass Nadeem** · CS with AI, Brunel University of London ·
[github.com/AnassNadeem](https://github.com/AnassNadeem)

Building ARIS as the centrepiece project for 2027 industrial placements
in F1 / motorsport software (Vehicle Performance Software, Strategy Tools).
