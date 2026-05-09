# ARIS — Success Criteria

**Companion to `ARIS-FINAL-PLAN.md` and `ARIS-EXECUTION-PLAN.md`.**

The goal of this doc: by August 31, 2026, you should be able to look at a checklist and answer *"did I succeed"* without ambiguity, self-flattery, or moving the goalposts. Every criterion is binary or numeric. No "felt good about it."

There are **five dimensions**. You need to clear the **floor** on all five to call this a success. Hitting **target** on most makes you genuinely competitive for placements. Hitting **stretch** anywhere is a bonus you can over-claim a little in a cover letter.

---

## Dimension 1 — Technical (does the system actually work?)

This is what an engineer reviewing your repo will care about.

| Metric | Floor (must hit) | Target (real success) | Stretch (over-deliver) |
|---|---|---|---|
| Held-out lap-time MAE (point estimate) | < 1.0s | < 0.7s | < 0.5s |
| Conformal prediction interval coverage @ 90% | Built, coverage measured | Empirical coverage 85–95% on held-out | Coverage 88–92% + per-stint width reported |
| Number of validated races (held-out) | 3 | 5 | 10+ |
| Cross-validation discipline (race-by-race, no per-lap leakage) | Race-by-race CV harness committed Day 1 of Phase 2 | + leakage unit test in CI | + leakage test fails on a known-bad split (negative control) |
| Always-on loop tick latency | < 15s | < 5s | < 2s |
| Counterfactual perturbation runs | 1 working action type | 5 action types | 5 + multi-action chains |
| Monte Carlo sample size feasible in <5s | 100 | 1000 | 10000 |
| Recommendation hit-rate (direction correct on validatable laps) | > 50% | > 65% | > 75% |
| LLM narration is accurate (no hallucinated numbers) | Spot-check 20, ≤2 wrong | Spot-check 50, ≤2 wrong | Structured-output enforced, 0 hallucinated numbers |
| End-to-end demo runs without crash for 1 full race replay | Yes | Yes, on a fresh laptop | Yes, on the user's phone via the deployed URL |
| Tiered tick architecture working (monitor / micro / macro + event-driven) | Tier 1 + Tier 3 only | All three tiers + event-driven recompute <1s | All tiers + sub-400ms event recompute |
| Competitor pivot triggers correctly (e.g. faster-on-hards detection) | 1 worked example in eval | 3 worked examples across different scenarios | 5+ examples + auto-flag in recommendation feed |
| Ask ARIS Q&A pane returns grounded answers (cited evidence, no hallucinated numbers) | 15/20 spot-checks pass | 18/20 pass | 20/20 pass with structured-output enforcement |
| MATLAB/Simulink validation artefact (bicycle module ported) | Bicycle module runs in MATLAB, plot matches Python within 5% | + Simulink block diagram + signed-off README | + Simulink model used to cross-validate one full stint |
| Backtest report written in strategy language (not just ML metrics) | One-page PDF: undercut risk, SC sensitivity, pit-window deltas | Multi-page report tied to 5 held-out races | Same + recruiter-friendly executive summary |

**Failure mode to watch:** numbers that look great because of leakage (training on the race you're predicting). The eval split must be **by race**, not by lap. If MAE is suspiciously low, you have a leak — find it before the demo, not in the interview. The race-by-race CV harness and a leakage unit test must be committed *Day 1 of Phase 2, before any model code.*

**Calibration note (revised 2026-04-29 after deep-research synthesis):** the previous floor of < 1.0s and target < 0.5s was over-claimed against the published baseline. No public FastF1 lap-time predictor reports < 0.5s held-out MAE; honest public numbers cluster around 0.7–1.8s. Floor stays at < 1.0s but target moves to < 0.7s and stretch becomes < 0.5s. Calibrating below the field's silent baseline is what makes the number credible in interviews. Pair every point estimate with a conformal 90% prediction interval — that combination is the answer to *"how did you handle uncertainty?"* and is the single highest-leverage technical addition in the project.

---

## Dimension 2 — Career (does this get you placement interviews?)

This is what the next 12 months actually depend on. The build is a *means* — the placement is the goal.

**Target role-shape (revised 2026-04-29):** the CV header reads **"Software Engineer — Vehicle Performance Software / Strategy Tools"**, not *Race Strategy Engineer*. The Race Strategy Engineer placement at Y2 entry is gated to a single role (Red Bull Race Strategy Student Placement). The documented CS-undergrad path is **Software placement → grad scheme → strategy specialisation**. Software placements at Williams (Vehicle Performance Software, Tech & Innovation), Aston Martin (Software, AMPT VP), Mercedes AMG HPP (Software & Controls), McLaren (Engineering / Software) all map 1:1 to ARIS modules. Lead with software; race strategy is the long-shot stretch, not the headline. The project still proves the same thing — that you can build and ship a real system end-to-end — and software is the door that opens.

| Metric | Floor | Target | Stretch |
|---|---|---|---|
| Placement applications submitted by Nov 30, 2026 | 8 | 15 | 25+ |
| First-stage interviews (phone screen / online assessment passed) | 2 | 5 | 10+ |
| Final-stage interviews (on-site / final panel) | 1 | 3 | 5+ |
| Placement offer received | 0 (acceptable if pipeline is healthy) | 1 | 2+ (so you can pick) |
| LinkedIn alumni messages sent | 30 | 60 | 90+ |
| LinkedIn alumni replies | 5 | 12 | 20+ |
| Recruiter inbound from LinkedIn (cold) | 0 | 1 | 3+ |
| Brunel Careers 1:1 sessions used | 1 | 3 | 5+ |
| Mock interviews completed | 5 | 10 | 15+ |
| Recognised courses completed (cert or audit) | 1 (MATLAB Onramp) | 3 (MATLAB + Andrew Ng + Vehicle Dynamics) | 4+ including one paid cert |
| MATLAB/Simulink port of bicycle module (Tier B graft) | Bicycle ported, plot matches Python | + Simulink block diagram, separate pinned repo `aris-matlab-validation` | + cross-validated stint, MATLAB Onramp + Simulink Onramp both completed |
| Conformal-prediction calibration shipped in Phase 6 | 90% intervals computed and reported | + interval coverage validated on held-out | + per-stint width chart in README |
| Backtest report in strategy language alongside README | One-page PDF in `docs/strategy-backtest.md` | Multi-page, used in cover letter | Recruiter-friendly executive summary on its own page |

**Reality check:** You can hit every technical metric and still fail this dimension if you don't apply. The placement is **not** the natural consequence of a great repo — it's the consequence of a great repo *plus* shipping 15+ tailored applications. Treat applications as a Phase 7 deliverable, not an afterthought.

**Failure mode:** "I'll polish ARIS one more week before applying." No. By August 31 the project is frozen for the application sprint. Polish in commits, not in delays.

---

## Dimension 3 — Process (did you actually learn?)

This matters because of the **interviewer test**: any senior engineer can spend 15 minutes with your repo and tell whether you wrote it or your AI wrote it. If you can't defend the code, the project is *worse* than no project — it actively damages credibility.

| Criterion | How to verify | Pass = |
|---|---|---|
| You can derive the bicycle model on a whiteboard | Practice with a friend | Done from memory, ≤10 min |
| You can explain why XGBoost vs MLP for the residual | Mock interview | One-paragraph answer with reasoning, not vibes |
| You can walk through any file in `src/aris/` and explain it | Open repo, pick file at random | No "I'd have to look that up" on the 20% hardcoded modules |
| You can name 3 limitations of ARIS unprompted | Mock interview | All 3 are real (not "I'd add more data") |
| You can explain why this is not a world model | Mock interview | One sentence + one follow-up |
| You can explain why it's not called UDX yet | Mock interview | One sentence about platform claim discipline |
| You can recite the 30-second classification answer (hybrid AI, not world model, not RL) | Cold open with a friend | Verbatim or close, ≤35 seconds |
| You can explain the tiered tick architecture (monitor/micro/macro + event-driven) | Mock interview | Each tier in one sentence, name a real trigger |
| You can explain why ARIS still improves over time without RL | Mock interview | Offline supervised retraining, refits residual on new race data |
| You can re-derive Phase 2 results in a notebook on a fresh checkout | Try it Aug 25 | Runs end-to-end, numbers match README |
| You wrote at least 30% of total LOC by hand (not AI) | Git history sanity check | Honest self-assessment — if no, fix in Y2 |

**The 5-question interviewer test (apply to any hardcoded module):**
1. What does this do?
2. Why this approach over the obvious alternative?
3. Where does it break?
4. What would you change with more time?
5. Show me the line that does X.

If you fail any of the 5 on a hardcoded module, that module is not done — go back. AI-assisted modules only need 1–4.

---

## Dimension 4 — Artifact quality (is the repo/demo presentable?)

The first 60 seconds an engineer spends with your work decides everything. Optimise that 60 seconds.

| Criterion | Pass = |
|---|---|
| GitHub profile README rewritten (NeuroSim mention removed, ARIS-aligned) by Day 1 | Done before first ARIS commit |
| All 4 dashboard modes shipped (Watch, Ask, What-if, Replay) | All 4 working end-to-end |
| README has the one-line pitch in the first 3 lines | Yes |
| README has a hero GIF or screenshot above the fold | Yes |
| README has results table with held-out numbers | Yes |
| README has 1-command install + run | `docker compose up && streamlit run app/Home.py` works on a fresh clone |
| Live URL works on phone | Tested on your own phone, mobile network not WiFi |
| 90-second demo video on YouTube unlisted, embedded in README | Yes |
| Repo has ≥80 commits across the 17 weeks | Yes (~5/week) |
| Commit messages are real (not "update", "fix", "wip") | Spot-check 10 random commits |
| `LOG.md` has a daily bullet for ≥80% of working days | ~85 bullets minimum |
| At least 2 written blog posts published | 1 technical, 1 motivation/story |
| At least 5 LinkedIn posts during the build | Yes |
| Code passes `ruff check` with no errors | Yes |
| `pytest` runs and passes (any tests, even basic) | Yes |
| No secrets / API keys in git history | `git log -p` clean |

**The cold-open test:** ask a friend who has never seen the project to open the repo URL on their phone for 60 seconds. Then ask: "what does this do?" and "would you click into the live demo?" If they can't answer the first or say no to the second, fix it before applying.

---

## Dimension 5 — Brunel Racing engagement (the unfair-advantage dimension)

This is **optional success** — bonus, not floor. The project must stand alone. But if any of these land, your story goes from "CS Y1 built a thing" to "CS Y1 built a thing teams use," which is a different conversation in interviews.

| Outcome | Score |
|---|---|
| Brunel Racing replied to your WhatsApp at all | +1 (real engagement signal) |
| Got a meeting/call with the team | +2 |
| Got access to a single test day's telemetry | +3 (huge — now your CV says "validated on real Brunel Racing data") |
| Ran ARIS on their data and showed results back | +5 (you are now collaborating with a Formula Student team) |
| Team adopted any part of ARIS for their workflow | +8 (lead anecdote in every cover letter) |

**Hard kill criteria, repeated for clarity:** if Week 6 ends with no reply or no path to data, **drop it.** Pivot story to "validated on held-out FastF1 races." Do not chase, do not double-message past the one polite follow-up. The project must succeed without them; treat any engagement as upside.

---

## Composite scoring

| Tier | What you cleared | Verdict |
|---|---|---|
| **Failed** | Missed floor on any of Dimensions 1, 2, 3, 4 | Regroup. Probably means scope was wrong, not effort. |
| **Shipped** | Floor on 1, 2, 3, 4 | You have a real project. Apply with confidence. |
| **Succeeded** | Target on 1, 3, 4 + floor+ on 2 | You're a competitive applicant. Expect interviews. |
| **Crushed it** | Target on all 4 + 1+ on Dim 5, OR Stretch on any 2 | Strong applicant. Multiple offers plausible. |
| **Exceptional** | Stretch on 2+ dims + Dim 5 ≥ +3 | Rare. This is "people remember your name" territory. |

**Realistic expectation for a CS Y1 in a 17-week sprint with beginner Python on Day 1:** **Shipped → Succeeded** is the honest target. Crushed it is achievable but requires Brunel Racing to engage *and* the technical numbers to land. Exceptional requires luck.

---

## What does NOT count as success (anti-criteria)

A common trap is to redefine success after the fact. Pre-commit to these *not* counting:

- "I learned a lot." → Useful, not measurable, not a placement signal.
- "The architecture is really clean." → Not visible from outside the repo.
- "I could have shipped if I had more time." → Time was the constraint; meeting the constraint was the test.
- "Real F1 teams have better tools." → Of course they do. You're a CS Y1, not a competitor.
- "It would work great with more data." → If it doesn't work on the data you have, the design is wrong.
- "I could productise this." → Not the goal. Placement is the goal.
- "I got a lot of GitHub stars." → Vanity metric. Recruiters do not look at stars.
- "The demo video has 10k views." → Same. Cool, irrelevant to placements.

The only measure is the checklist above.

---

## When to evaluate

- **Weekly (every Sunday evening, 30 min):** scan the floor metrics for the current phase. Are you on track? If not, cut scope *now*, not next week.
- **End of each phase:** all "Done means" boxes ticked, or the phase is not done. No partial credit.
- **August 31, 2026 (the final review):** sit down with this document, score every line. Be brutal. Then write the Year 2 plan based on the actual scores.
- **November 30, 2026 (post-application):** revisit Dimension 2. If applications-submitted < 8, the project succeeded technically but failed at the actual goal. That's a process problem to fix in Y2.
- **Spring 2027 (placement decision):** if a placement landed, the system worked. If not, this document tells you which dimension failed and where to invest next time.

---

## The single sentence that summarises success

> *By August 31, 2026, a senior software engineer on an F1 vehicle-performance or strategy-tools team can spend 60 seconds with the ARIS repo on their phone, understand what it does, watch a 90-second demo with real held-out numbers (point estimate + conformal interval), and conclude: "this CS first-year built and shipped a real system — worth a phone screen for the software placement."*

If that sentence is true on August 31, you succeeded. If not, you didn't — regardless of how much you learned, how clean the code is, or how hard you worked.

The placement is the test. ARIS is the answer.
