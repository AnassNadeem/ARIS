# ARIS — Cross-Review Synthesis & Path from 7 → 9/10

**Date:** 2026-04-29
**Inputs:** Deep Research Answers from ChatGPT, Claude, Gemini, Perplexity
**Verdicts:** All four = `GO_WITH_CHANGES`. Confidence: ChatGPT 7, Claude 7, Gemini 9, Perplexity 7.
**Estimated placement probability (range across reviewers):** 15–40%.

---

## 1. Why three of four capped you at 7 (not 9–10)

The 7s are not "the plan is bad." They are "the plan is internally honest but has six load-bearing weak points that, if any one fails, collapses the demo or the interview story." A 9 requires neutralising those weak points before Day 1, not during execution.

The six weak points, ranked by how often they appeared across reviewers:

| # | Weak point | Cited by | Why it caps the score |
|---|------------|----------|----------------------|
| 1 | **MAE < 0.5s target is uncalibrated** | All 4 | No published benchmark; realistic floor is 0.7–1.8s. Over-claiming on the README is an interview footgun. |
| 2 | **Phase 2 in 3 weeks (lap-time predictor)** | All 4 | Claude: "fantasy timeline." Gemini: 15% odds. Perplexity: "non-trivial as a whole project, not 3 weeks." |
| 3 | **Train/test leakage in Phase 2** | Claude (named #1 risk), Perplexity, ChatGPT | Per-lap splits = leakage. Frontiers 2025 explicitly flags this. A great-looking MAE that collapses under interview scrutiny is the worst outcome. |
| 4 | **Brunel Racing data hard-kill at Wk6 is too late** | Gemini (fatal), Claude (acceptable but tight) | Hardware/CAN parsing routinely slips. Six weeks of ML schedule held hostage to a dependency you don't control. |
| 5 | **Targeting "Race Strategy Engineer" not "Software Engineer (Performance/Strategy Tools)"** | Claude, Gemini | Race Strategy at Y2 entry is gated to **one** role (RB Race Strategy Student Placement). The CS-undergrad path is Software → grad scheme → strategy specialisation. Wrong CV header = filtered before human review. |
| 6 | **No uncertainty quantification on outputs** | Claude (named #1 graft), Perplexity | "How did you handle uncertainty?" is the canonical interview follow-up. XGBoost point estimates can't answer it; conformal prediction or quantile regression can. |

Secondary weaknesses (mentioned by 1–2 reviewers, lower priority but cheap to fix):
- No pit-stop logic or fuel model in the physics layer (ChatGPT) — narrower than full team tools.
- No MATLAB/Simulink artefact (Claude, Gemini, Perplexity) — explicitly listed as "good to have" by Mercedes HPP, RB Powertrains, Williams VD.
- 5s tick latency advertised as a feature (Claude: "footgun" — real F1 is sub-second; don't market the number).
- Streamlit + Postgres + Ollama 8B on 8GB VRAM = OOM risk (Gemini).
- GitHub still says "NeuroSim", contribution graph sparse (ChatGPT, Gemini).
- No backtest report written in **strategy language** ("undercut risk", "SC sensitivity") — only ML metrics (Perplexity).

---

## 2. The grafts that move you from 7 → 9

These are additions and re-framings, not scope cuts. None of the reviewers recommended descoping ARIS; they recommended de-risking it. In priority order:

### Tier A — Do before Day 1 (May 4). Free, hours of work, biggest score lift.

1. **Recalibrate the README success criteria.** Floor: MAE < 1.0s. Target: < 0.7s. Stretch: < 0.5s. Calibrating below the field's silent baseline is what makes the number credible. (Claude, Gemini, Perplexity all converge here.)
2. **Reframe the CV target role.** From "Race Strategy Engineer" → "Software Engineer, Vehicle Performance Software / Strategy Tools." Map ARIS modules 1:1 against the Williams VPS and Aston Martin Software placement listings in `docs/architecture.md`. (Claude, Gemini.)
3. **Purge NeuroSim from your GitHub profile.** New profile README that leads with ARIS. Pin order: ARIS, MATLAB validation, FastF1 cache utility, hackathon repos by F1-relevance. Daily commits start May 4. (ChatGPT, Gemini.)
4. **Sever Brunel Racing as a dependency, keep it as upside.** Hard kill date moves Wk6 → Wk3. If clean CSV telemetry isn't in hand by Day 21, FastF1 + sim-racing telemetry becomes the permanent pipeline. Send the WhatsApp Day 1; attend a test day in person Wk8/9 regardless. (Gemini = fatal flag; Claude = same direction, softer wording.)
5. **Reframe physics positioning.** "Lightweight + interpretable + LLM-narrated" — NOT "physics-grounded." The latter invites comparison with TUMFTM and Mercedes/Imperial RSRL multi-body sims you can't match. (Claude.)
6. **Stop marketing 5s tick latency.** It's not a feature; it's the cost of running locally. Frame as "tiered ticks for human-readable cadence." (Claude.)

### Tier B — Inside the existing 17 weeks. Small additions, large signal.

7. **Add conformal prediction calibration in Phase 6 (≈2 days).** This is the single most defensible technical detail in the whole project and the answer to "how did you handle uncertainty?" Claude calls this the smallest change with the largest odds lift. **Do this one for sure.**
8. **Race-by-race cross-validation in Phase 2, never per-lap.** Build the CV harness on Day 1 of Phase 2, before any model training. Document leakage tests explicitly. (Claude, Perplexity, the Frontiers 2025 paper all flag this.)
9. **Add a 1-week MATLAB/Simulink port of the bicycle module, parallel to Phase 5.** Closes the explicit "good to have" line at Mercedes HPP and RB Powertrains. Listing it as a separate pinned repo doubles your perceived stack. (Claude, Gemini, Perplexity converge.)
10. **Move Phase 1 cloud deploy from Wk4 → Wk3.** Postgres + Streamlit can compress; the recovered week goes into Phase 2 to absorb leakage debugging. (Claude.)
11. **Statistical baseline by Wk2 (moving average of sector times), iterate physics in by Wk5.** Lets the dashboard, ingest, and DB layer be debugged against dummy data while ML is still learning. (Gemini.)
12. **Add explicit pit-stop and fuel logic to the physics layer.** Even a simple pit-loss constant + linear fuel-burn term widens scope to match what an F1 strategy reviewer expects to see. (ChatGPT.)
13. **Backtest report in strategy language alongside the README.** "Undercut risk reduced 17% vs naive baseline on 2024 Monaco" reads differently to a strategy hiring manager than "MAE = 0.83s." Both numbers, framed for the audience. (Perplexity.)

### Tier C — Nice to have, only if Tier A+B is locked.

14. Hugging Face Spaces deployment of ARIS — free CV signal, listable URL.
15. Llama 3.2 3b instead of 3.1 8b if RAM is tight; Groq free tier as fallback. (Claude.)
16. pybind11 C++ Monte Carlo inner loop **only if** the pure-NumPy version misses the latency budget. Don't pre-optimise. (Gemini suggested this; Claude/Perplexity didn't think it was load-bearing.)
17. One LeetCode block per week (≤2 hrs, inside the 36, replacing buffer). Software placement screens are auto-graded; ARIS doesn't help you pass them. (Claude Plan F.)
18. Drill the five canonical strategy interview questions before Y2 application sprint (undercut/overcut, gap-to-leader vs gap-ahead, 1-stop vs 2-stop in mixed weather, pit-stop walkthrough, "defend a decision under time pressure"). (Claude.)

---

## 3. What a 9/10 plan actually looks like

Combine all of Tier A + all of Tier B. The plan now says:

- Target role: **Software Engineer (Vehicle Performance Software).** Race Strategy is the long-shot stretch, not the headline.
- Success metric: **MAE < 1.0s floor, < 0.7s target.** Conformal-calibrated 90% prediction intervals reported alongside the point estimate.
- Eval discipline: **race-by-race CV harness built Day 1 of Phase 2.** Leakage tests in CI.
- Brunel Racing: **upside, not dependency.** Pipeline runs on FastF1 from Wk3 onward.
- Physics positioning: **"lightweight, interpretable, narrated"** — not "physics-grounded."
- Artefacts at Nov 2026: ARIS live demo + GitHub repo (≥100 commits) + MATLAB validation repo + backtest report in strategy language + 5-min demo video + 2 blog posts + HF Space.
- GitHub profile: **NeuroSim purged.** ARIS pinned. Dense commit graph from May.

That plan is a 9. The only reason it's not a 10 is that **execution risk is real** — leakage, OOM, FastF1 cache failures, English-fluency under interview pressure. Reviewers won't give a 10 to a plan-on-paper for a single-author 17-week build. A 10 is reserved for what the plan looks like in November after it actually shipped.

Gemini's 9 is the outlier because Gemini scored the **revised** plan with all the grafts already applied (sever Brunel at Wk3, reframe to Software role, pybind11). The other three scored the **current** plan and told you what to change. Apply the grafts and you converge on Gemini's 9.

---

## 4. The single biggest risk all four reviewers agree on

Phase 2. Specifically: **producing a lap-time MAE number that looks great in the README and falls apart when an interviewer asks "how did you split your data?"**

Mitigation is one paragraph: build the race-by-race CV harness before you train anything, write the leakage test as the first commit in Phase 2, and report MAE with conformal intervals not as a single number.

Do that and the worst-case interview question becomes your strongest answer.

---

## 5. The single biggest opportunity all four reviewers agree on

**Always-on FastF1 + counterfactual engine + LLM narration is unbuilt in the open as of April 2026.** TUMFTM has the physics. undercut-f1 has the always-on UI. Pit-stop-simulator has the RL strategy. **Nobody** has the combination, and nobody has the LLM narration layer.

This is the differentiator. Lead with it in the README, the demo video, and every cover letter. Don't lead with the physics (TUMFTM is better) or the latency (real teams are sub-second). Lead with **"the only public tool that explains its strategy recommendations in natural language, calibrated with prediction intervals."**

---

## 6. Action list for the next 5 days (T-5 to T-0)

- May 4: Replace GitHub profile README. Purge NeuroSim. Pin ARIS placeholder repo with one-line description.
- May 4: Send Brunel Racing WhatsApp. Frame as upside, not dependency.
- May 4: First commit on ARIS repo (architecture.md mapping modules to Williams VPS / AM Software listings).
- May 5: Update `ARIS-SUCCESS-CRITERIA.md` with recalibrated MAE floors and conformal-interval success criterion.
- May 5: Update `ARIS-EXECUTION-PLAN.md` — Brunel Racing kill moves to Wk3, Phase 1 deploy moves to Wk3, MATLAB port slotted parallel to Phase 5, conformal calibration added to Phase 6.
- May 6: Write the leakage-test scaffold. It's 30 lines of pytest. Commit it before any model code.
- May 7: Read TUMFTM `racesim_basic` source. Working code teaches faster than Rajamani Ch.2.
- May 8: Stop rereading the plan. Day 1 is May 9.
