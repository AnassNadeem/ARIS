# ARIS — Deep Research / R&D Pre-Flight Prompt

**How to use this file:** paste the entire **§ PROMPT** block (everything between the two horizontal rules) into a deep-research-capable model — Claude with extended thinking + web search, ChatGPT with browsing, Gemini Deep Research, Perplexity Pro Deep Research, or run it through `/codex` for a second opinion. Run it **before** writing a single line of ARIS code. Read the report. Update the plan files. Then start.

The goal is to spend ~$5 and 30 minutes of compute to find every reason this plan might fail, every prior-art collision, and every market signal you don't know — before you sink 4 months in.

---

## § PROMPT (paste everything below this line)

---

You are acting as a **principal-level R&D advisor + careers strategist + market analyst** doing a feasibility and positioning study before a 20-year-old UK student commits 4 months of full-time work plus 2 academic years to a project that determines his career trajectory. Be brutal, specific, and source every non-obvious claim.

### 1. Subject context (read fully before responding)

**Person:**
- 20-year-old, finishing Year 1 Computer Science at Brunel University of London (May 2026), starting CS with Artificial Intelligence specialisation in Year 2 (September 2026)
- UK student visa (cannot be self-employed, must do placement through university)
- Current Python level: working knowledge of syntax, basic numpy, has used SQLite + Postgres lightly. Has not trained a neural network yet but is actively committing 36+ hrs/week to closing this gap. **Treat the skill stack as a learning curve to manage, not a constraint that justifies descoping the project.** See § 4 anti-vibes guardrails.
- **GitHub:** [github.com/AnassNadeem](https://github.com/AnassNadeem) — *please actually fetch this profile and read it before writing the report.* The visible repos include real hackathon work (genuine, not padding). The profile README currently mentions "NeuroSim" — that's outdated and will be replaced; do not weight it. Comment specifically on: (a) what the existing repos signal about coding maturity, (b) what's missing on the profile that an F1 hiring manager would look for, (c) concrete README/profile changes to make before May 4.
- **Prior internship:** 1-month PHP intern at TallyMarks Consulting (Pakistan, 2024). Real experience but stack-irrelevant to F1. Question to answer: how should this be framed on a UK F1 placement CV — kept as evidence of professional exposure, repositioned, or buried?
- Speaks limited English, anxious in person, working on it
- Has a WhatsApp contact in Brunel Racing (Formula Student team) — Suspension Lead, Aero & Cooling, Chassis Design Lead are known team members; team competes in FS-Combustion, unclear on FS-AI
- 4 months full-time available May 4 – August 31, 2026, then Year 2 with reduced hours
- Budget: free tools only until Week 12, ~£40 last 2 weeks for Claude API + paid certs
- Idols Musk/Zuckerberg/Huang but does not fit Musk's risk profile; visa makes founder track infeasible until graduation
- **Goal hierarchy (weighted, do not flatten):**
  - **(1) ~70% weight: F1 team placement, Year-2-summer 2027** — top priority. Aston Martin F1, Williams, McLaren, Mercedes-AMG Petronas, Red Bull Racing, Alpine, Ferrari UK ops. The whole plan is optimised for this.
  - **(2) ~25% weight: F1-adjacent placement** — Mercedes AMG HPP, Red Bull Powertrains, Red Bull Advanced Technologies, McLaren Applied, Williams Advanced Engineering, M-Sport, Prodrive, Multimatic, AP Racing, sim companies (rFpro, Ansible Motion). Acceptable but not the goal — treat as fallback.
  - **(3) ~5% weight: optionality** for Year-3 graduate scheme at an F1 team if Y2 placement misses, plus Global Talent visa / quant pivot post-graduation.
  - **Implication for your analysis:** when ranking trade-offs and counterfactual plans, weight outcomes by F1-fit. A counterfactual that improves overall placement odds but reduces F1-team odds is a *worse* plan, not a better one.

**Project (ARIS — Always-on Race Intelligence Strategist):**
- **Classification:** A *hybrid AI decision support system* combining physics-based simulation, supervised machine learning, classical search-based planning, Monte Carlo sampling, and a retrieval-grounded LLM narrator. Explicitly **not** a world model (no learned latent dynamics; the simulator is hand-coded bicycle model + Pacejka tire degradation + ML residual). Explicitly **not** reinforcement learning (no learned policy, no reward signal — action selection is search, not policy gradient). Improvement over time comes from *offline supervised retraining* of the residual model as new race data is ingested, not online RL.
- **What it does:** watches a live race (replay-as-live from FastF1 historical data, with a Y2 plan to extend to live sim-racing telemetry), predicts what's about to happen, and proactively surfaces top-3 candidate driver/strategy actions with predicted lap-time deltas and Monte Carlo confidence intervals. Detects competitor pace residuals (e.g. "Hamilton's hards 0.2s/lap faster than my model predicts") and triggers strategy pivots automatically.
- **Architecture layers:** data ingest (FastF1 → Postgres, behind a `DataSource` interface so sim-racing slots in later) → state estimation → physics-grounded lap-time predictor (bicycle model + Pacejka-style tire degradation) → residual ML correction (XGBoost or small MLP) → counterfactual perturbation engine → action search + Monte Carlo sampling → multi-driver competitor modelling → recommendation feed → LLM narrator + grounded Q&A pane (Llama 3.1 8B local on GPU) → Streamlit UI with four interaction modes.
- **Tiered tick architecture (this is core, not optional):**
  - Tier 1 — Monitor (every 1–2s): anomaly detection on telemetry, tire-temp drop as rain proxy, competitor pace residuals — alerts only
  - Tier 2 — Micro (every sector ~20–30s): driving recommendations (lift/brake/line)
  - Tier 3 — Macro (every lap or on event): full action search + Monte Carlo + competitor strategy reassessment
  - Event-driven recompute (<400ms): SC/VSC, competitor pit, weather threshold crossed, pace residual exceeded → triggers Tier 3 immediately
- **Dashboard exposes 4 interaction modes** in one Streamlit app: **Watch** (passive recommendation feed with expandable `[Why?]` reasoning chains) · **Ask** (natural-language Q&A grounded in structured race state via RAG, not free LLM generation) · **What-if** (counterfactual sliders for pit lap / compound / lift point with live-updating MC outcome distribution) · **Replay** (timeline scrubber to see what ARIS would have recommended at any past lap).
- Internally architected as the motorsport plugin of an eventual umbrella platform (UDX) with a future quant-finance plugin (QDIE) — but externally branded only as ARIS until the second plugin exists.
- **Hardware:** Lenovo Legion 5, AMD Ryzen AI 7, RTX 5070 mobile (8GB VRAM), 32GB RAM. Llama 3.1 8B (q5 quantized) runs locally on the GPU at ~5–10× CPU speed → no cloud LLM API needed during build. Cannot run real world models or fine-tune 7B+ LLMs (correctly, those are out of scope).
- **Target deliverables by August 31, 2026:** deployed Streamlit URL, ≥80 GitHub commits, 90-second YouTube demo video with held-out race numbers, 2 blog posts, lap-time MAE < 0.5s on 5 held-out races, all 4 dashboard modes working, tiered tick architecture documented, competitor-pivot capability demonstrated in eval.
- **Year-2 stretch (architected for now, built later):** sim-racing live telemetry adapter (iRacing / ACC / Le Mans Ultimate / rFactor 2). Solves the Brunel Racing data dependency. Hardware-feasible on the Legion 5.
- **Post-summer plan:** November 2026 placement applications, primary targets Aston Martin F1 Race Strategy / Software / Performance student placements (best F1 shot — three role shapes match ARIS exactly) + Williams Performance Systems / Vehicle Performance + Mercedes / McLaren / Red Bull strategy and software placements + WRC and sim-tooling adjacent firms.

### 2. What I want from you — eight deliverables, in order

For each deliverable, **cite at least 3 sources** with URLs. If you cannot find a source for a claim, mark it **[SPECULATIVE]** and explain your reasoning. Do not pad. Bullet density > paragraph density. If a section has no useful findings, say so explicitly — empty results are a finding.

#### Deliverable 1 — Plan & scope critique
- Where is the technical scope unrealistic for a beginner Python user in 17 weeks? Be specific by phase.
- Where is it *too small* — i.e., where is the project under-claiming relative to what an F1 strategy hiring manager would expect to see?
- Are the success criteria (held-out MAE < 0.5s, recommendation hit-rate > 65%, tick latency < 5s) calibrated correctly for this dataset and approach? Find any published benchmarks (e.g. Frontiers 2025 F1 pit-stop paper, TUMFTM/race-simulation, ML4F1 Cambridge project) and compare.
- Is the bicycle-model + tire-degradation + residual-MLP stack the right architectural choice, or would a different decomposition (e.g. Gaussian process, pure XGBoost on raw features, sequence model on telemetry) outperform for this use case at this scale?
- Is the Monte Carlo addition right-sized at 3 days, or is it secretly bigger / smaller?

#### Deliverable 2 — Execution plan critique
- Pace check: 6 hours/day × 6 days/week = 36 hrs/week. Is this enough, given beginner Python on Day 1 and the volume of new concepts (vehicle dynamics, ML, async, LLM prompt engineering, Postgres, Streamlit, Docker)?
- Where are the hidden time sinks I'm not budgeting for? (Telemetry data quirks, FastF1 cache issues, Streamlit deployment friction, Postgres on Windows, etc.)
- Which named learning resources in the plan (CS50P, Boot.dev, Andrew Ng ML Specialization, James Powell pandas, Rajamani Ch.2, Michigan Vehicle Dynamics) are objectively the best for this purpose, and which should be replaced?
- What is the realistic probability of hitting the Phase 2 deadline (lap-time predictor working in 3 weeks) given the prerequisite stack?
- The plan has a Brunel Racing hard kill at Week 6. Is that the right week, or earlier/later?

#### Deliverable 3 — Prior art & competitive landscape
Find and rank by relevance. **Search across all of GitHub, LinkedIn, Reddit, Stack Overflow, Hacker News, YouTube, Medium, Substack, arXiv, Google Scholar, Twitter/X, Discord servers, and the FastF1 community.** Empty-search-result findings are themselves a finding — report them.

- **Open-source race-strategy or lap-time-prediction projects** on GitHub. For each: stars, last-commit date, scope, whether ARIS overlaps or extends it. Specifically check: TUMFTM/race-simulation, FastF1 ecosystem repos, F1-Tempo, jasper-is-greppable's F1 work, any FS-AI driverless stacks (AMZ Driverless, MUR Driverless, KA-RaceIng), pit-stop-simulator, virtual-strategy-engineer implementations. Also do a fresh GitHub search for the keywords: `fastf1`, `f1 strategy`, `lap time prediction`, `race strategy simulator`, `f1 telemetry`, `tire degradation model`.
- **LinkedIn search** — find people who:
  - Have "F1 strategy," "race strategy," "motorsport software," or "lap-time prediction" in their headlines, posts, or featured projects
  - Have published recent posts (last 12 months) about side projects in this space — especially students, hobbyists, indie builders (not just team employees)
  - Have written articles on LinkedIn about FastF1, race strategy ML, or motorsport data science
  - List the top 10 by follower-count or engagement. Note what they're building, whether it's open or closed, and whether it competes with ARIS or complements it.
- **Reddit** — search r/F1Technical, r/formula1, r/MachineLearning, r/datascience, r/cscareerquestions, r/learnpython, r/MotorsportEngineering for threads in the last 24 months on:
  - "F1 strategy simulator," "FastF1 project," "lap time predictor," "race strategy ML," "tire degradation model"
  - Any post that says "I built X" or "show HN/show reddit" with race-strategy content
  - Any thread where someone asks "how do F1 teams do strategy?" — the top-voted answers tell you what the public *thinks* this looks like, which is what your demo video must align with or challenge
  - List 10 most-relevant threads with link, post date, top-comment summary, OP's stated motivation
- **Stack Overflow** — search for FastF1 tags, lap-time-prediction questions, race-strategy questions. Volume of questions = community size. Are people stuck on things ARIS solves, or stuck on things that would derail ARIS in Week 3? Capture the 10 most-recent FastF1 questions and what they reveal.
- **Hacker News** — `hn.algolia.com` search for "F1," "FastF1," "race strategy," "Formula 1 ML," "motorsport ML." Any past Show HN? What was the reception?
- **Discord** — is there a FastF1 Discord, an r/F1Technical Discord, an "F1 data" community? Active member count? What topics are discussed? (Just describe — do not join on the user's behalf.)
- **YouTube + blogs + Substack** — F1Metrics, StatF1, FastF1's own examples, Mahaveer Sai's tutorials, Jasper Greppable's work, Codetrip F1 videos, any active F1 data Substack. Who's loudest? Who's actually building tools vs writing analysis?
- **Twitter / X** — search "FastF1," "F1 telemetry," "race strategy ML." Find the 5 most-active accounts in the F1-data niche.
- **Academic papers** in the last 5 years on F1/race strategy ML. Authors, institutions, methods, datasets, results. Search Google Scholar, arXiv, Frontiers, Springer.
- **Commercial products** — Pirelli Tyre Strategy app, AWS Race Insights for F1, Riedel, Sportable, MathWorks F1 collaboration, OptimumG, PACETEQ, TruckSim/CarSim, Canopy Simulations. Are any doing what ARIS does? What's the differentiation?

- **Synthesis questions (answer these explicitly):**
  1. Has anyone — anywhere on the open internet — built an *always-on, proactive, counterfactual race strategist with LLM narration* using FastF1 as the data layer? If yes, name them, link them, describe how close they are to ARIS. If no, state "no evidence found" and explain what searches you tried.
  2. What is the **closest existing project** to ARIS by feature set? List its features in a table side-by-side with ARIS so the gap is visible.
  3. **Differentiation playbook — give me 7 distinct ways ARIS can be made unique** vs the closest prior art, ranked by (a) effort to add, (b) credibility gain for an F1 hiring manager, (c) defensibility against fast-followers. For each, name the feature, the cost in days, and the specific F1 role it would impress.
  4. If ARIS's core idea has been built before, what is the **single twist** that makes the user's version worth showing in 2026 — driver-personalised models, real-Brunel-Racing data validation, conformal-prediction-style confidence intervals, multi-language narration, mobile-first UX, something else?
  5. Reverse angle: are there *adjacent ideas in the F1-data community that nobody has built yet* and would be easier wins? Name 3 unbuilt projects that the niche is asking for (evidence from Reddit/HN/SO threads) and would still satisfy the placement goal.

#### Deliverable 4 — F1 / motorsport hiring market analysis (UK, 2026 cycle)
- For each team — McLaren, Mercedes-AMG Petronas, Mercedes AMG HPP, Red Bull Racing, Red Bull Powertrains, Red Bull Advanced Technologies, Williams, Aston Martin F1, Alpine F1, Ferrari (UK presence) — list:
  - Every Race Strategy / Software / Performance / Data Science / Vehicle Dynamics placement role currently or recently advertised
  - Application open/close dates for the 2027 cycle (which opens Summer 2026)
  - Stated requirements (degree, software, languages)
  - Estimated total intake (rough — count from LinkedIn "current placement student" tags per team if possible)
  - Stipend / salary range if public
- Same for adjacent UK firms: M-Sport, Prodrive, Multimatic Vehicle Dynamics, Williams Advanced Engineering, AP Racing, Stray Systems, Bentley Motorsport, McLaren Applied (separate from McLaren Racing), rFpro, Ansible Motion, Cosworth, Mercedes-Benz Grand Prix Engineering.
- Identify the top 5 highest-conversion roles for an ARIS-shaped applicant. Justify with named evidence.
- Trend signals: where is hiring growing or shrinking? Find evidence (press releases, layoffs, new tech partnerships e.g. Mercedes/Microsoft Azure deal Jan 2026, McLaren cloud partners, Aston Martin Silverstone campus expansion).

#### Deliverable 5 — People paths (this is the highest-value section)
Find **at least 10 real people** currently working as Race Strategy Engineer, Performance Engineer, Software Engineer, or Data Scientist at the named UK F1 / motorsport teams above. For each (LinkedIn search + public profiles only — do not invent):
- Name, current role, current team
- Undergraduate degree, university, graduation year
- Side projects / personal repos / blog posts visible online
- Path: did they enter via placement → graduate scheme → full-time, or via masters → graduate, or lateral?
- Any public talks, papers, podcasts (PDF, YouTube)
- Any indication of what landed them their first role (a project, a connection, a publication)

Then synthesise:
- What is the **modal path** to a UK F1 strategy / software role?
- What % entered via undergrad placement vs masters vs PhD vs lateral?
- What universities over-index? (Brunel, Imperial, Cambridge, Oxford, Bath, Loughborough, Cranfield?)
- What side projects appear most often in the backgrounds of these people?
- Is there a visible "alumni network" pattern at any specific team that Brunel CS has tapped before?

#### Deliverable 6 — Skill matrix per target role
Build a table: rows = top 8 target roles from Deliverable 4. Columns = the skills ARIS will plausibly demonstrate (Python, FastF1, Postgres, Streamlit, bicycle model, tire degradation, residual ML, counterfactual simulation, Monte Carlo, LLM integration, demo video, blog writing, async loop, Docker). Mark each cell:
- **MUST** (role explicitly requires this)
- **STRONG** (role lists as preferred)
- **NEUTRAL** (not mentioned but won't hurt)
- **NEGATIVE** (might signal wrong focus)

Then identify the **3 biggest skill gaps** ARIS leaves uncovered for these roles, and recommend the smallest possible additions to close them (e.g. "add a 1-week MATLAB rewrite of the bicycle model module to satisfy MATLAB requirements at Mercedes HPP and Red Bull Powertrains").

#### Deliverable 7 — Risk register
List the top 10 risks ranked by probability × impact. For each: trigger condition, early-warning signal, mitigation. Required to include — but not limited to:
- Brunel Racing never engages
- Lap-time predictor MAE plateaus above 1s
- Project finishes but feels generic in interviews
- Language barrier kills phone-screen conversion despite strong CV
- Visa issue with placement timing (mid-degree, July 2027 start)
- An AI tool (e.g. some OpenAI/Anthropic agent product) ships something ARIS-shaped during the build period and makes it look unoriginal
- Health / burnout from 36 hrs/week + Y2 academics
- F1 hiring contraction due to budget cap or sponsor exits
- Quant pivot becomes more attractive mid-build and creates split-focus
- Brunel CS+AI degree specifics turn out to misalign with what teams actually want

#### Deliverable 7.5 — GitHub & online presence audit
Fetch and inspect [github.com/AnassNadeem](https://github.com/AnassNadeem). Then:
- For each visible repo: name, what it appears to do, signal it sends to an F1 hiring manager (positive / neutral / negative), and whether to keep / pin / archive / delete before May 4
- Profile README — what it currently says (note: NeuroSim mention is outdated, will be replaced) vs what it *should* say for an F1 strategy / software placement applicant. Provide a rewritten profile README in markdown, ready to paste.
- Hackathon work visible on the profile is genuine — assess whether it strengthens or distracts from the F1 narrative
- Pinned repos strategy: which 6 should be pinned by August 31, in what order, with what one-line descriptions
- Contribution graph: current state vs what it needs to look like by November 2026 application date
- Username, profile photo, bio, location, links — any changes needed
- Compare against 3 currently-employed F1 software/strategy engineers' GitHub profiles (find them via LinkedIn → GitHub link). What patterns do they share? What does the user's profile lack?

#### Deliverable 8 — Counterfactual plans (the alternatives I should consider)
Honestly evaluate whether a different summer plan would have higher placement conversion than ARIS. Score each on (a) probability of completion, (b) placement conversion, (c) optionality, (d) match to subject's stated values:
- **Plan B — FS-AI driverless stack contribution.** Join an existing FS-AI team's autonomy code (perception/SLAM/planning), even unofficially via open source. Smaller original artifact, but signals team-collaboration and direct FS-AI relevance.
- **Plan C — Quant-flavoured project.** Build a small market-microstructure simulator + alpha research notebook, target quant interns at Optiver/Jane Street/Citadel London. Higher pay, harder skill ramp, less visa risk.
- **Plan D — Open-source FastF1 ecosystem contribution.** Don't build a product — make 50+ meaningful PRs to FastF1, telemetry-fastf1, F1-Tempo. Lower originality, higher visibility, faster placement signal.
- **Plan E — DeepMind / research-residency targeting.** Reproduce one F1 paper rigorously, write up cleanly, target research-engineer roles. Lower placement conversion, higher upside.
- **Plan F — Hybrid: smaller ARIS + 30% time on leetcode + Brunel Racing in-person involvement.** Trades scope for interview-readiness and Brunel-network-building.

For each, give a one-sentence verdict and a recommendation on whether to switch.

### 3. Format requirements

- Use clear `## Section` headers per deliverable
- Tables for any comparison data
- All URLs as inline markdown links
- One **bottom-line verdict** at the very end (max 200 words): "If I were this student, I would [keep ARIS as-is / change X / switch to Plan Y] because…"
- Maximum 6000 words total. If you can't fit, drop sections — don't dilute.
- Mark every speculative claim **[SPECULATIVE]** and every cited claim with a footnote-style URL.

### 4. Anti-vibes guardrails (read carefully)

- Do **not** say "this is a great project" or "you have a strong chance" without numerical/comparative evidence
- Do **not** invent people, papers, or roles. If you cannot find evidence, say "no evidence found."
- Do **not** soften critique. The user explicitly wants brutal. A polite report that misses a fatal flaw is worse than a harsh report that catches it.
- Do **not** repeat the plan back to me — I wrote it. Tell me what I don't already know.
- Do **not** spend more than 500 words on Deliverable 1 — I already self-reviewed scope. Spend the budget on Deliverables 3, 4, 5 (prior art, market, people paths). These are where outside research adds the most value.
- **Do NOT recommend reducing scope on the grounds of "beginner Python" or "no prior ML."** The user has explicitly committed to closing those gaps via 36+ hrs/week of focused work plus named courses (Andrew Ng, MATLAB Onramp, Michigan Vehicle Dynamics). The skill ramp is a constraint to *manage*, not a reason to *descope*. If you think a phase is unrealistic, recommend (a) better learning resources, (b) earlier-stage scaffolding, (c) parallelisation, or (d) tighter weekly milestones — **not** "do less." A scope cut recommendation is only acceptable if you can prove with cited evidence that even a perfectly-executed learning curve cannot close the gap in the available time. The user will reject and ignore any "shrink the project" suggestion that does not meet this bar.
- **Weight your trade-off analysis by the F1-fit goal hierarchy** in §1. A recommendation that increases overall offer probability while reducing F1-team offer probability is a *worse* recommendation. Say so explicitly when comparing counterfactuals.
- Where there is genuine uncertainty (e.g. exact placement intake numbers per team), give a range and explain what would resolve it.

### 5. Specific questions to weave in (do not skip any)

1. Has anyone built an "always-on race strategist" with FastF1 + LLM narration before? Public repo, blog, video, paper?
2. What are the Brunel CS / Brunel Racing alumni who are *currently* at named F1 / motorsport firms? Names, current roles, what they did at Brunel.
3. Is "Race Strategy Engineer" actually accessible from a CS+AI undergrad placement, or is it gated to mechanical/aerospace engineering grads in practice?
4. What's the latency tolerance in real-world F1 strategy software? Is the 5-second tick I'm targeting impressively fast, embarrassingly slow, or irrelevant?
5. How important is MATLAB/Simulink *in practice* (not in listings) for early-career F1 software roles? Worth a 1-week rewrite of one ARIS module?
6. Is there a public dataset or competition (Kaggle, AIcrowd) I could submit to as additional credibility — F1-related or motorsport-adjacent?
7. What does the entry-level F1 strategy interview actually look like? Find writeups, Glassdoor reviews, YouTube debriefs. List the 5 most-asked technical questions.
8. Is the language-barrier disadvantage real or overstated for these roles? Find any UK F1 engineers whose first language is not English and infer.
9. Salary / stipend reality check: what does a UK F1 placement actually pay? What does a graduate scheme pay? What does a senior strategy engineer pay 5–10 years in? Are these numbers worth the optimisation?
10. If ARIS shipped exactly as planned and got zero placements, what is the "consolation prize" optionality — could it pivot to a side income, a research paper, a conference talk, a startup wedge?
11. **PHP internship at TallyMarks Consulting (Pakistan, 1 month, 2024) — how should this appear on a UK F1 placement CV?** Keep prominent (proves prior professional work), demote to a single line, or omit? Find evidence from comparable F1-placement CVs (alumni LinkedIn profiles).
12. **F1-priority lens:** if you had to choose one role-shape for the user to optimise the *entire* ARIS project around, which is it: Race Strategy Engineer, Performance Engineer, Software Engineer, or Data Scientist? Justify with named evidence about competition density, alumni placement rates from CS+AI undergrads, and ARIS's natural fit. Then specify the smallest plan tweak that would tilt ARIS most toward that one shape without breaking the others.
13. **GitHub starting position:** given the existing profile at github.com/AnassNadeem, what is the realistic ceiling for "GitHub presence at application time" by November 2026? Is the current state a meaningful disadvantage vs other applicants, neutral, or recoverable in 7 months?

### 6. Final scoring

End the report with this structured JSON block (or markdown table if JSON not supported):

```json
{
  "go_no_go": "GO" | "GO_WITH_CHANGES" | "PIVOT" | "NO_GO",
  "confidence_in_recommendation_0_to_10": <int>,
  "single_biggest_risk": "<one sentence>",
  "single_biggest_opportunity": "<one sentence>",
  "smallest_change_that_most_improves_odds": "<one sentence>",
  "estimated_placement_offer_probability_if_executed_as_planned": "<percentage range>",
  "would_you_personally_invest_4_months_in_this_plan": "yes" | "no" | "yes_with_changes",
  "rationale": "<≤80 words>"
}
```

---

## § END PROMPT

---

## How to run it (operational notes for me, not for the model)

1. **Where to paste:**
   - **Best:** Claude.ai with extended thinking enabled + web search on
   - **Alternative:** ChatGPT-5 with browsing + DeepResearch mode (allow ~30 min)
   - **Alternative:** Gemini 2.5 Deep Research (longest report, 20-min wait)
   - **Cross-check:** run again on `/codex` for an adversarial second opinion using the same prompt
   - **Budget:** ≤$5 across all runs combined

2. **What to do with the output:**
   - Read once end-to-end. Don't react.
   - Re-read with a marker — circle every claim that contradicts something in `ARIS-FINAL-PLAN.md`, `ARIS-EXECUTION-PLAN.md`, or `ARIS-SUCCESS-CRITERIA.md`.
   - For every contradiction: either update the plan or write a one-line `decision-log.md` entry explaining why you're keeping the plan as-is.
   - For every people-path finding: open LinkedIn, find the person, send a 3-line connection request before May 4.
   - For every prior-art project found: clone, run, document differences in a `docs/prior-art.md` so you can cite them in interviews.
   - For every market signal: update the cover-letter template to reference it (e.g. cite Mercedes×Microsoft AI deal, McLaren Software & Data Science department).

3. **Hard rule:** if the report's `go_no_go` field returns `PIVOT` or `NO_GO`, **do not start ARIS on May 4.** Spend Week 1 re-planning. The cost of a week of re-planning is trivial; the cost of 17 weeks on the wrong plan is the entire summer.

4. **Re-run cadence:** run a lighter version of this prompt at end of Week 8 (mid-build checkpoint) to recalibrate against any new signals.
