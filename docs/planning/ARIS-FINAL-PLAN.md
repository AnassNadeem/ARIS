# ARIS — Final Plan (May → August 2026, then placement applications)

**Owner:** Anass (Brunel CS Y1 → Y2, placement target Nov 2026)
**Date locked:** 2026-04-27 · **Revised:** 2026-04-29 (Tier A+B grafts from deep-research synthesis applied)
**Target role-shape:** Software Engineer — Vehicle Performance Software / Strategy Tools (Williams VPS, Aston Martin Software, Mercedes AMG HPP Software & Controls, McLaren Engineering, Red Bull Race Strategy Student Placement as the long-shot stretch). The CS-undergrad route into F1 is **Software placement → grad scheme → strategy specialisation**, not Race Strategy Engineer at Y2 entry. ARIS proves the same thing either way — that you can build and ship — and software opens more doors.
**One-line pitch:** *ARIS is an always-on race-strategy software system that watches a live race, predicts what's about to happen, and proposes the next decision with a quantified lap-time delta and a calibrated confidence interval — built on real F1 telemetry, validated end-to-end on held-out races.*

---

## 0. What changed on 2026-04-29 (Tier A + Tier B grafts)

After running the plan through four independent deep-research reviewers (ChatGPT, Claude, Gemini, Perplexity — all returned `GO_WITH_CHANGES`, three at confidence 7/10, Gemini at 9/10), the following grafts are now baked into this plan. None of them cut scope — they de-risk it.

**Tier A (free, before Day 1):**
- **Recalibrated MAE.** Floor < 1.0s, target < 0.7s, stretch < 0.5s. The previous < 0.5s target was over-claimed against the silent public baseline.
- **Reframed CV target role.** Software Engineer (Vehicle Performance Software / Strategy Tools), not Race Strategy Engineer.
- **GitHub profile cleaned before May 4.** NeuroSim purged. ARIS pinned. Daily commits from Day 1.
- **Brunel Racing severed as a dependency, kept as upside.** Hard kill moves Wk6 → **Wk3 Day 5** (Phase 1 Day 21). FastF1 + sim telemetry is the permanent pipeline. WhatsApp goes Day 1 regardless; in-person test-day visit Wk8/9 regardless.
- **Physics positioning reframed.** "Lightweight + interpretable + LLM-narrated" — NOT "physics-grounded." The latter invites comparison with TUMFTM/Mercedes/Imperial multi-body sims you can't match.
- **5s tick latency stops being marketed.** It's the cost of running locally, not a feature. Frame as "tiered ticks for human-readable cadence."

**Tier B (inside the 17 weeks):**
- **Conformal prediction calibration in Phase 6 (~2 days).** Single highest-leverage technical addition. Answers "how did you handle uncertainty?" in interviews.
- **Race-by-race CV harness + leakage unit test, Day 1 of Phase 2, before any model code.** Train/test leakage is the #1 risk flagged by Claude.
- **MATLAB/Simulink port of the bicycle module (~1 week, evenings parallel to Phase 4–5).** Separate pinned repo `aris-matlab-validation`. Closes the Mercedes HPP / RB Powertrains "good to have" line.
- **Phase 1 cloud deploy moves Wk4 → Wk3.** Recovered week absorbs Phase 2 leakage debugging.
- **Statistical baseline (moving average of sector times) by Wk2,** so dashboard, ingest, and DB layer can be debugged against dummy data while ML is still learning.
- **Pit-stop and fuel logic added to the physics layer.** Even simple pit-loss constant + linear fuel-burn term widens scope to match what an F1 strategy reviewer expects.
- **One-page backtest report in strategy language** alongside the README — "undercut risk", "SC sensitivity", "pit-window deltas" — not just MAE/RMSE.

**Tier C (add-ons, only after Tier A+B is locked):**
- Hugging Face Spaces deployment of ARIS (free CV signal).
- Llama 3.2 3b instead of 3.1 8b if 8GB VRAM is tight; Groq free tier as fallback.
- pybind11 C++ Monte Carlo inner loop **only if** pure NumPy misses the latency budget. Don't pre-optimise.
- One LeetCode-easy block per week (≤2 hrs, replacing buffer inside the 36 hrs).
- Drill the five canonical strategy interview questions (undercut/overcut, gap-to-leader vs gap-ahead, 1-stop vs 2-stop in mixed weather, pit-stop walkthrough, "defend a decision under time pressure") before the Y2 application sprint.
- Public Kaggle/HF dataset of FastF1-derived backtest task — own the benchmark.

The detailed why-this-matters writeup is in `ARIS-IMPROVEMENT-SYNTHESIS.md`.

---

## 1. Three things to settle first (so you can stop second-guessing)

### 1a. Why this is NOT a "world model"

A **world model** (DeepMind / Wayve / Tesla style) is a learned neural network that *internally simulates the environment* — you feed it the current state and an action, it hallucinates the next state, and you train a policy by rolling out imagined futures inside it. RSSM, Dreamer, GAIA-1 — those are world models. They need:

- Massive compute (8+ A100s for weeks)
- Millions of trajectories
- A research team to stop training collapse
- A PhD-level person to debug latent-space drift

You have **4 months, no GPU cluster, no PhD, beginner Python.** Building a real world model in that window is the same fantasy as the previous NeuroSim plans. It is why those plans never produced a working artifact.

**ARIS is a hybrid predictor + counterfactual simulator + recommender:**
- A *physics-grounded lap-time model* (bicycle model + tire degradation curve) — hardcoded, deterministic, you understand every line.
- A *residual ML correction* (small XGBoost or tiny MLP) trained on FastF1 data — learns what physics misses.
- A *perturbation engine* — "what if driver lifts 0.2s earlier in T7?" — runs the same model with modified inputs.
- An *always-on loop* — every N seconds, takes current race state, runs ~50 candidate actions through the model, surfaces the top 3 with predicted deltas.
- An *LLM narrator* (Llama 3.1 local, Claude API last 2 months) — turns the structured recommendation into a sentence.

This is **what F1 strategy teams actually run.** It is not a world model and you should never call it one — that's an over-claim that any strategy engineer will see through in 30 seconds. Call it a **race intelligence system** or **strategy co-pilot.** Both are honest.

### 1b. Why you cannot call it UDX (yet)

UDX = "Universal Decision & Strategy Intelligence System with motorsport + finance plugins." It is a *platform* claim. To make a platform claim honestly you need at minimum **two working plugins** that share the L0–L6 architecture from the PDF.

Right now you have zero plugins. If you call your single F1 prototype "UDX" on a placement application:
- F1 hiring managers will think you're unfocused (why is a CS Y1 talking about quant finance?)
- Quant hiring managers will think the F1 angle is the real interest and the finance is a bolt-on (correct)
- Both will downgrade you because the claim outpaces the artifact

**Strategy:** This summer ship **ARIS** as a complete, focused F1 product. Internally, **architect it as if it were the motorsport plugin of UDX** — same L0 (data ingest), L1 (state estimation), L2 (prediction), L3 (counterfactuals), L4 (recommendation), L5 (narration), L6 (UI) layering. That way, when you build the second plugin (QDIE for quant) in Year 2 or summer 2027, you're not refactoring — you're slotting. *Then* you can rename the umbrella to UDX and the platform claim becomes honest.

In every external message this summer: **"I am building ARIS."** Save UDX for when it earns the name.

### 1c. CS with AI is the right pick

You already concluded this and you're right. The Y3 final-year project being AI-flavoured is a free signal on your CV that costs you nothing in Y2 module flexibility. Every F1 strategy / vehicle dynamics / software role above lists Python, MATLAB, machine learning, or simulation — "AI" on the degree title is a free filter pass. **Lock it in. Stop revisiting.**

### 1d. What ARIS actually IS — precise classification

This matters because interviewers will ask, and over-claiming kills credibility instantly.

**Honest one-line classification:**
> *"A hybrid AI decision support system that combines physics-based simulation, machine learning, and large language models for race strategy."*

**Component breakdown** (memorise for technical interviews):

| Component | Classification | Why |
|---|---|---|
| Bicycle model + tire degradation | Physics simulator (deterministic) | Hand-coded, not learned |
| Residual predictor (XGBoost / small MLP) | Supervised ML | Trained on labelled lap-time data |
| Counterfactual perturbation + action search | Search-based planning (classical AI) | Enumerate → score → rank |
| Monte Carlo race continuation | Stochastic simulation | Sampling, not learning |
| Always-on loop with recommendation feed | Deliberative agent | Perceives state, plans, recommends per tick |
| Llama 3.1 narration | LLM (transformer NN) | Pretrained, inference only, retrieval-grounded |

**What ARIS is NOT — say this clearly:**
- **NOT a world model.** No learned latent dynamics. The simulator is hand-coded physics + ML residual.
- **NOT reinforcement learning.** No learned policy, no reward signal. Action selection is search, not policy gradient. *(See §1f for why ARIS still improves over time.)*
- **NOT an LLM agent (LangChain-style).** The LLM narrates; it does not control.
- **NOT deep learning at its core.** The deep component is the LLM, used pretrained.

**The 30-second interview answer:**
> *"ARIS is a hybrid AI race strategist. The core is a physics simulator — bicycle model with tire degradation — corrected by a machine-learning residual trained on FastF1 data. An action-search engine evaluates dozens of candidate driver and strategy actions per tick, scores them with Monte Carlo confidence intervals, and an LLM turns the top recommendation into a sentence. It runs always-on against a live race replay. It is not a world model and not reinforcement learning — it is classical decision support stitched together with modern ML and LLMs."*

### 1e. Tiered tick architecture (the answer to "every-second data")

ARIS does NOT recompute the full strategy every second. It runs three cadences in parallel, plus event-driven recomputes:

| Tier | Cadence | What it does | Output |
|---|---|---|---|
| **Tier 1 — Monitor** | every 1–2s | Anomaly detection on telemetry, tire-temp drop as rain proxy, competitor pace residuals | Alerts only, no strategy change |
| **Tier 2 — Micro** | every sector (~20–30s) | Re-run predictor with current state, update *driving* recommendations (lift/brake/line) | "Lift 30m earlier T7, +0.18s gain" |
| **Tier 3 — Macro** | every lap or on event | Full action search across pit/compound/defend/attack branches + Monte Carlo over remaining race + competitor strategy reassessment | Strategic recommendations with win-prob delta |
| **Event-driven recompute** | <400ms | Triggered by: SC/VSC, competitor pit, weather threshold crossed, pace residual exceeded | Tier 3 immediately regardless of cadence |

**Spatial inference as a first-class concern:** rain-in-T3 falls out of sector-time residuals + tire-temp drops. ARIS does not need a single "raining: yes/no" boolean — it builds a per-sector wet-probability map.

**Multi-driver competitor modelling:** top-5 threats Monte-Carlo'd in Tier 3. If a competitor's pace residual exceeds threshold, ARIS refits their compound's deg curve in real-time and triggers a strategy pivot recommendation.

This tiered architecture is **how real F1 strategy software is engineered.** Mercedes/Red Bull/McLaren run the same pattern at different tick rates and budgets. Saying it correctly in interviews demonstrates you understand event-driven systems, latency budgets, and the difference between *monitoring* and *deciding*.

### 1f. Why ARIS improves over time without RL

ARIS is *not* reinforcement learning. ARIS *does* improve over time. These are not contradictory.

- **Online RL during a race: NO.** N=1 sample size, sparse delayed reward, no replay, huge action space → wrong tool. Real F1 teams don't do this either.
- **Offline supervised retraining across races: YES.** After every race, ARIS compares predictions to actuals, identifies systematic errors (e.g. "tire cliff arrived 2 laps early in heat"), and refits coefficients. After ~100 races, MAE drops from ~0.5s toward ~0.2s, recommendation hit-rate climbs from ~65% toward ~80%.

**Interview phrasing:**
> *"ARIS continuously refits its physics-residual model on new race data using supervised learning. We deliberately avoided reinforcement learning because the problem has terrible sample efficiency for RL — sparse rewards, no replay, N=1 per race. The same reason real F1 teams use ensembles + Monte Carlo + supervised models, not policy-gradient methods."*

### 1g. The dashboard — four modes, one tab

ARIS exposes four interaction modes from one Streamlit app, all sharing the same data layer:

1. **Watch** (default) — recommendations stream into a scrolling feed; each card has a `[Why?]` button revealing the full reasoning chain (evidence, alternatives considered, risks, confidence breakdown)
2. **Ask** — natural-language Q&A pane. The LLM answers grounded in ARIS's structured state (retrieval-augmented generation), not from its own training data. Every answer cites the model fits, residuals, or MC runs it drew from.
3. **What-if** — counterfactual playground. Drag sliders for pit lap, compound, lift point, driver style; see the predicted outcome shift in real-time. *This is the killer demo screen for placement interviews.*
4. **Replay** — scrub past laps, see what ARIS *would have* recommended at any moment vs what actually happened. *This is the recording surface for the 90-second demo video.*

**Critical sequencing rule:** the pretty Streamlit UI is **the last 2 weeks** of the build (Phase 7). Phases 0–6 are CLI + Jupyter notebooks. Many student projects look great and predict nothing — do not invert this.

---

## 2. What F1 teams actually want (verified, not guessed)

I searched the live 2026 listings. The pattern across McLaren, Williams, Red Bull, Mercedes AMG HPP, and the strategy-engineer literature:

**Hard requirements (must-have, every listing):**
- Predicted 2:1 or above in Engineering / Maths / Science / Computing (you're CS — fine)
- Python (universal — Red Bull Powertrains lists it explicitly, Williams lists Python alongside C#/Java/C++, Mercedes lists MATLAB/Simulink which is adjacent)
- Data analysis from simulations or physical tests (Red Bull explicit; Williams' Vehicle Dynamics / Vehicle Performance roles assume it)
- Working with deadlines under pressure, presenting clearly to a team

**"Good to have" (which means **should have** — you called this correctly):**
- MATLAB / Simulink (Mercedes, Red Bull)
- Vehicle dynamics / first-principles physics (Williams Vehicle Performance, Red Bull Powertrains "engineering principles + maths")
- Familiarity with simulation tooling (CFD/FEA/MBD adjacent — for software roles, your "simulator" claim covers this)
- API/JSON integration (Williams Tech & Innovation explicit)
- Communicating results to non-engineers (every listing — your demo video covers this)

**Race Strategy specific (Red Bull Race Strategy placement):**
- "Excellent academic results in Engineering/Maths/Science/Computing"
- ML for strategy is now in academic literature (Frontiers 2025 paper on deep-learning pit-stop decisions, TUM open-source race-simulation, Cambridge ML4F1 project) — **this is your moat**: a Y1 CS student who has actually built a strategy simulator, in 2026, with FastF1 data, is rare.

**What to put on your CV / WhatsApp / cover letter (mapping):**
| F1 ad says... | Your evidence... |
|---|---|
| Python | ARIS codebase on GitHub |
| Data from simulations / tests | FastF1 telemetry pipeline + Brunel Racing logs (if/when) |
| Vehicle dynamics first principles | Bicycle model + Pacejka-style tire curve, hardcoded |
| Machine learning | Residual MLP / XGBoost on lap-time prediction |
| Simulation tooling | Counterfactual perturbation engine |
| Communicating to non-engineers | 90-second demo video + blog posts |
| Working under deadlines | Shipped MVP in 17 weeks while in Y2 |

This table goes on the CV under the project, in the exact role-listing language. **You're not lying — you're mapping.**

### Sources for these claims
- [McLaren Engineering Placement 2026 — Bright Network](https://www.brightnetwork.co.uk/graduate-jobs/mclaren-racing/engineering-placement-2026)
- [Williams Technology & Innovation Industrial Placement](https://careers.williamsf1.com/job/technology-and-innovation-industrial-placement-in-grove-jid-274)
- [Williams Vehicle Engineering Industrial Placement](https://careers.williamsf1.com/job/vehicle-engineering-industrial-placement-in-grove-jid-278)
- [Red Bull Racing Industrial Student Placements](https://www.redbullracing.com/int-en/projects/industrial-student-placements)
- [Red Bull Race Strategy Student Placement](https://www.motorsportjobs.com/en/job/race-strategy-student-placement-2024-25)
- [Mercedes AMG HPP Software & Controls 12-Month Placement](https://www.gradcracker.com/hub/398/mercedes-amg-hpp/work-placement-internship/39495/software-and-controls-12-month-placement-scheme)
- [Mercedes AMG HPP Engineering Placement 2026 — Bright Network](https://www.brightnetwork.co.uk/graduate-jobs/mercedes-amg-high-performance-powertrains/engineering-placement-2026)
- [Frontiers 2025 — Deep learning for F1 pit-stop decisions](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1673148/full)
- [TUM open-source race-simulation repo](https://github.com/TUMFTM/race-simulation)
- [Cambridge ML for F1 project page](https://mlatcl.github.io/internal/projects/machine-learning-for-modelling-formula-one-races.html)

---

## 3. FS-AI — what to do with it

**Decision: not this summer. On the radar for summer 2027 / Y2 if Brunel Racing has an AI subteam, otherwise as a Y3 elective project.**

Why not now:
- FS-AI rules require a working autonomous stack (perception → SLAM → planning → control). That's a year of work for a multi-person team, not a side feature.
- ARIS is a *strategy* system. FS-AI is *autonomy*. Different code, different libraries, different selling story.
- Doing both badly beats neither, but doing ARIS *well* beats both badly.

What to keep alive:
- When you message Brunel Racing, ask in passing whether the team competes in (or plans to enter) FS-AI. If yes, that becomes Y2 commitment, not a summer commitment.
- If they say no, you have an opening: **"Once ARIS is solid, the same engine extends to FS-AI — perception in, strategy out."** That's a 2027 conversation, not a 2026 one.
- Keep the architecture FS-AI-friendly: clean separation between data ingest, state estimation, prediction, recommendation. If FS-AI ever becomes the move, you swap the data source and reuse the rest.

---

## 4. WhatsApp message — final version (does NOT ask to sit in meetings)

> Hey [name], hope you're well. Quick one — I'm a CS Y1 finishing this May and I'm spending the summer building a piece of software called ARIS: it's a race-strategy tool that watches live telemetry and proposes the next driver action with a predicted lap-time delta (e.g. "lift 30m earlier into T7, predicted +0.18s gain"). It runs on FastF1 data right now.
>
> Two things I'd love your view on:
> 1. Is there anything like this Brunel Racing already uses, or a gap where a tool like this could be useful?
> 2. If/when I have a working version (aiming end of August), would the team be open to me running it on a session of your real telemetry, even just a single test day's logs, so I can validate the predictions against what actually happened?
>
> No rush — happy to share progress along the way and you can tell me if I'm building the wrong thing. Thanks!

**What this message does right:**
- Concrete artifact ("ARIS"), concrete output ("+0.18s gain") — they immediately know what you mean.
- Asks a *yes/no* question first ("is there a gap") — easy to answer, opens dialogue.
- Asks for *data*, not *time* — much smaller ask than "can I sit in meetings."
- Gives them an out ("happy to share progress") — they don't have to commit now.
- No FS-AI, no UDX, no world model, no "I want a placement" — just the build.

**Send Day 1 of Week 1. Not before. You want to be already coding when they reply.**

---

## 5. The build — May 4 → August 31, 2026 (17 weeks)

This is the same plan as before, with the four critical fixes from the self-review applied:
- Phase 5 (Monte Carlo strategy) **cut**.
- Phase 2 (lap-time predictor) **extended to 3 weeks** — that was the fantasy timeline.
- Demo + eval **combined to 2 weeks**.
- Phase 8 = **placement applications prep**, not buffer.
- Brunel Racing **hard kill at Week 6** — if no engagement by then, switch to "validated against held-out FastF1 races" as the proof-of-fit story.

### Default cadence assumption (until you tell me otherwise)
- **6 hours/day, 6 days/week = 36 hrs/week** ("hardcore" floor)
- Sunday off — non-negotiable, you'll burn out otherwise
- If you can do 8/day great, the plan absorbs it; if you can only do 4/day, Phases 5 and 7 compress, not stretch

### Phase 0 — Python foundations + first FastF1 plot (Weeks 1–2, May 4–17)
- Boot.dev Python track (or equivalent) — through OOP and basic numpy
- pandas: 2-hour James Powell tutorials on YouTube
- FastF1 install, pull one race, plot one driver's lap times
- **Deliverable:** GitHub repo `aris`, README, one matplotlib chart committed
- **WhatsApp goes Day 1**

### Phase 1 — Postgres ingest + Streamlit dashboard (Weeks 3–4, May 18–31)
- Postgres locally (Docker), schema for sessions/laps/telemetry
- FastF1 ingest script, idempotent
- Streamlit page: pick driver/race, show lap times + sector breakdown
- Deploy to Streamlit Community Cloud — **public URL by end of Week 4**
- **Deliverable:** live URL you can paste into a message

### Phase 2 — Lap-time predictor (Weeks 5–7, June 1–21) **← extended**
- **Day 1 of Phase 2 (before any model code):** commit `tests/test_no_leakage.py` — race-by-race CV harness + a unit test that fails if any held-out race appears in the training fold. This is the leakage tripwire and the single most important commit in Phase 2.
- Week 5: bicycle model from a textbook chapter (Rajamani Ch.2 or Milliken simplified). Hand-code in Python. Plot predicted vs actual on one stint — it will be wrong, that's fine. Add simple **fuel-burn linear term** and **pit-loss constant** so the physics layer covers what a strategy reviewer expects to see.
- Week 6: tire degradation curve (linear-with-fuel + exponential wear). Add to model. Plot again.
- Week 7: residual layer — XGBoost or tiny sklearn MLP, target = (actual lap time − physics prediction). Train/test split **by race**, never by lap. Report MAE *with conformal 90% prediction intervals* — point estimate alone is not enough.
- **Deliverable:** notebook + script that predicts a stint's lap times to floor < 1.0s / target < 0.7s / stretch < 0.5s on 5 held-out races, with the residual contribution visualised and conformal intervals plotted.
- **Brunel Racing hard checkpoint moved to Phase 1 Day 21 (end of Wk3):** if no clean CSV telemetry in hand by then, commit publicly in `LOG.md` to *"validated on held-out FastF1 races"* and stop chasing. The 6-week dependency was fatal per Gemini; Wk3 is the right kill date.

### Phase 3 — Counterfactual simulator (Weeks 8–9, June 22 – July 5)
- Perturbation API: `simulate(state, action_change) → predicted_delta`
- Action vocabulary: lift point, brake point, line offset, pit lap, compound choice
- Streamlit page: pick a real lap, perturb one action, see new predicted lap time + chart
- **Deliverable:** the screenshot you'll put in the demo video — "lift 30m earlier in T7 → +0.18s"

### Phase 4 — Always-on loop (Weeks 10–11, July 6–19)
- Replay a real race lap-by-lap (FastF1 has historical, treat it as live)
- Every 5s: take current state, run top-K action perturbations, surface top 3 with predicted deltas
- Recommendation feed UI in Streamlit
- **Deliverable:** the "always on" claim is now true — feed updates without you asking

### Phase 5 — *(cut — was Monte Carlo strategy; 3-day MC slim layer reinstated as Phase 4.5 in execution plan)*
You reclaim ~2 weeks. Do not refill them with new scope. Use them as cushion absorbed into Phase 2 (already extended), the conformal calibration in Phase 6, and the MATLAB/Simulink port (parallel evening work, ~1 week, separate repo `aris-matlab-validation`).

### Phase 6 — LLM narration (Weeks 12–13, July 20 – August 2)
- Local Llama 3.1 via Ollama (free) — turn structured recommendation into a sentence
- Prompt template that takes the JSON output of Phase 4 and produces "Box this lap — undercut window opens for 2 laps before traffic catches Hamilton"
- Last week of August (when you have budget): swap in Claude API for the demo recording — better narration quality for the video only
- **Deliverable:** narrated recommendation feed

### Phase 7 — Eval harness + conformal calibration + 90-second demo video + strategy backtest report (Weeks 14–15, August 3–16)
- Eval: backtest on 5 held-out races, report MAE *with conformal 90% prediction intervals*, % of recommendations that "would have been right" vs what actually happened.
- **Conformal calibration (~2 days, Tier B graft):** split-conformal on a calibration fold; report empirical coverage on held-out; plot per-stint interval width. This is the single most defensible technical detail in the project.
- **Strategy-language backtest report (~1 day):** `docs/strategy-backtest.md` written for a strategy hiring manager — undercut risk, SC sensitivity, pit-window deltas, not just MAE/RMSE.
- Demo video: 90 seconds, voiceover, screen recording. Three beats:
  1. "Here's a real lap from [race]. ARIS is watching live."
  2. "Lap 23, ARIS recommends X with predicted +0.2s ± 0.15s. Driver did Y, lost 0.3s."
  3. "Trained on 5 seasons of FastF1, validated on held-out races with conformal intervals, runs locally on a laptop."
- **Deliverable:** YouTube unlisted link + GitHub repo with eval numbers + strategy-language report + MATLAB validation repo linked from main README

### Phase 8 — Placement applications prep (Weeks 16–17, August 17–31)
- CV rewrite: ARIS at top, mapped to the role-language table in §2
- 2 blog posts on the project (one technical, one motivation/story) — LinkedIn + Medium
- Cover-letter template per team (McLaren, Williams, Red Bull, Mercedes HPP, M-Sport, Alpine, Williams Advanced Engineering, Red Bull Advanced Technologies, AP Racing, Stray Systems, Bentley Motors)
- 3 cold messages/week to alumni who placed at those firms (LinkedIn — search Brunel + company name)
- Mock interview prep — vehicle dynamics first principles, your code (be ready to walk through any line)
- **Deliverable:** placement application pack ready to fire on Day 1 of Year 2

### Year 2 (Sept 2026 onward)
- Submit applications November 2026 — that's the placement window
- Continue ARIS lightly: 1 commit/week minimum to keep the GitHub graph green
- Bi-weekly LinkedIn post on a small refinement
- Friday 2-hour interview prep block (vehicle dynamics, leetcode-easy, behavioural)

---

## 6. The 20/80 rule (hardcoded vs AI-assisted)

**20% hardcoded — you must know every line:**
- Bicycle model (Phase 2)
- Tire degradation function (Phase 2)
- Counterfactual perturbation API surface (Phase 3)
- Always-on loop control flow (Phase 4)
- Eval metrics computation (Phase 7)

**80% AI-assisted — you understand the logic, not every line:**
- FastF1 ingest scripts
- Postgres schema migrations
- Streamlit UI layout
- LLM prompt scaffolding
- Docker / deploy plumbing

**Interviewer test (apply before each component):**
1. What does this do?
2. Why this approach over the obvious alternative?
3. Where does it break?
4. What would you change with more time?
5. Show me the line that does X.

If you cannot pass these 5 questions on a hardcoded component, it is not done — go back. AI-assisted components only need questions 1–4.

---

## 7. Kill criteria — when to change course

- **Week 3 Day 5 (revised), no Brunel Racing reply or path to data:** drop Brunel angle, pivot story to held-out FastF1 validation. Do not chase further — you're not entitled to their data. (Was Week 6 — moved earlier per Gemini's "fatal timeline" flag.)
- **Week 7, lap-time predictor MAE > 1.5s on held-out data:** simplify the model, drop residual MLP, ship the physics-only version with honest conformal intervals. Honesty about scope > over-claim.
- **Week 11, always-on loop won't hit 5s update cadence:** loosen to 15s, document the tradeoff. Don't sink a week on optimisation.
- **Week 14, demo video is taking more than 5 days:** ship a 60-second version. Done > perfect.

---

## 8. What you do not do this summer

- Quant finance plugin (QDIE) — not yet
- FS-AI — not yet
- Reinforcement learning — wrong tool for this problem at your level
- A research paper — not the goal, placement is
- World-model anything — see §1a
- Calling it UDX — see §1b
- Asking to sit in Brunel Racing meetings — see §4
- Spending money before Week 12 — Ollama is free, Streamlit Community Cloud is free, Postgres is free

---

## 9. What's still open (need your input before Day 1)

1. **Hardcore hours:** confirm 6/day × 6/week, or tell me your real number — the phasing assumes this floor
2. **CS(AI) module list for Y2/Y3** — paste it when you have it; I'll flag any modules that are dead weight vs ARIS-relevant
3. **Brunel Racing contact's name + role** — so the WhatsApp opener uses the right framing (suspension lead vs aero lead implies different curiosity hooks)
4. **Confirm: ARIS is the project, this is the path, May 4 is Day 1** — once you say yes, I write the Week 1 Monday-morning kickoff (exact links, first commit, FastF1 install command, GitHub repo template)

## 10. Hardware context

**Machine:** Lenovo Legion 5 — AMD Ryzen AI 7, RTX 5070 (mobile, 8GB VRAM), 32GB RAM.

This was bought for the original NeuroSim plan but it changes ARIS in three ways:

- **Llama 3.1 8B (q5 quantized) runs locally on the GPU at ~5–10× CPU speed.** Phase 6 (LLM narration) runs locally throughout — no Claude API needed for the demo. Saves ~£40 budget, removes one external dependency.
- **Small NN training (residual MLP, optional sequence models) runs locally.** No cloud GPU rental needed in Y2 ML coursework either.
- **Sim-racing extension (Y2) is hardware-feasible** — laptop runs iRacing/ACC + ARIS side-by-side without thermal throttle.

**What it does NOT unlock:**
- Real world models (Dreamer/RSSM need 24GB+ VRAM for weeks). Don't be tempted.
- Fine-tuning 7B+ LLMs properly (QLoRA only, slow).
- Anything that justifies adding RL to Phase 4. The plan stays as-is.

## 11. Existing artefacts to clean up before Day 1

- **GitHub profile** ([github.com/AnassNadeem](https://github.com/AnassNadeem)) — current README mentions NeuroSim. **Replace before May 4** with an ARIS-aligned profile. Hackathon repos are real signal — keep, pin the strongest.
- **PHP internship at TallyMarks Consulting (Pakistan, 1 month, 2024)** — keep on CV as a single line under "Experience." Proves prior professional exposure. Do *not* expand it on F1 cover letters; it's not stack-relevant. Don't bury it either — it shows you can hold a real role.

## 12. Year 2 — sim-racing extension (kept-for-later, design-aware now)

After ARIS ships, the natural Y2 extension is a **sim-racing live telemetry adapter**: iRacing / ACC / Le Mans Ultimate / rFactor 2 expose telemetry via UDP / shared memory. Write one adapter conforming to ARIS's `DataSource` interface and the rest of the system is unchanged.

**Why it matters:**
- Solves the Brunel-Racing data dependency (sim data is yours, generated on demand)
- "Live on a real driver in their cockpit" beats "replay-as-live on FastF1" as a demo story
- Interactive interview demo: interviewer plays a few laps, watches ARIS narrate. Unforgettable.

**Do NOT build this in May–August.** Just don't *prevent* it: keep the data ingest layer behind a clean `DataSource` abstract class. FastF1 is one implementation. Sim sources will be future ones.

**Cover-letter line (November 2026):**
> *"Currently extending ARIS to read sim-racing telemetry, enabling live narration during human driving sessions."*

---

*This document supersedes every previous plan in `previous-plans/`. Those were research fantasies. This one ships.*
