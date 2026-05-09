# ARIS — Build Log

A daily journal of what got built, what broke, and what I learned. One bullet per day, Mon–Sat. Sundays off (non-negotiable).

**Companion docs:** [`ARIS-FINAL-PLAN.md`](./ARIS-FINAL-PLAN.md) · [`ARIS-EXECUTION-PLAN.md`](./ARIS-EXECUTION-PLAN.md) · [`ARIS-PHASES-WEEKLY-PLAN.md`](./ARIS-PHASES-WEEKLY-PLAN.md)

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
- **2026-05-09 (Sat):**
- **2026-05-10 (Sun):** *off*

**Weekly retro (Wk 1):**
- Shipped:
- Slipped:
- Changes for Wk 2:

### Week 2 (May 11 – May 17) — pandas + first FastF1 plot

- **2026-05-11 (Mon):**
- **2026-05-12 (Tue):**
- **2026-05-13 (Wed):**
- **2026-05-14 (Thu):**
- **2026-05-15 (Fri):**
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
