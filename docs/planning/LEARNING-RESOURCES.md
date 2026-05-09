# LEARNING RESOURCES — Sequenced Plan

**Companion to** `MASTER-PLANNER.xlsx` (Resources sheet) **and** `ARIS-PHASES-WEEKLY-PLAN.md`.

This document tells you *what to learn, when, in what order, with what fallback if the primary doesn't work for you, and how you'll know you're actually done* — not "felt good about it" done, but *can-defend-it-in-an-interview* done.

---

## How to use this

1. **Sequence matters.** Don't open Rajamani in Week 1; you don't have the Python yet. Don't grind LeetCode in Week 1; you don't have a foundation. Each track has a window.
2. **One primary, one backup per resource.** If the primary isn't clicking after 2–3 hours, switch. Don't power through a bad-fit teacher.
3. **Verification criterion is the test.** A course is "Done" when you've passed the *verification*, not when the videos finished playing.
4. **Free where possible. Pay only where the time-saving is real.** Most paid options have free alternatives that are 80% as good.
5. **Always-on tracks run alongside ARIS.** DSA, F1 strategy literacy, and writing are *daily small doses*, not sprints.

---

## Track 1 — Python (Wk 0–2, ~30 hrs total)

**Goal:** Read FastF1, work fluently in pandas/numpy, write OO code without thinking.
**Window:** Pre-flight + first two weeks. Heaviest in Wk 1.

### 1A — Python fundamentals + OOP

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Boot.dev** — Python track + OOP | ~30 | Paid (~£25/mo, free trial) |
| **Backup** | **Mosh Hamedani** Python full course on YouTube + **Real Python** intermediate articles | ~25 | Free |

**Verify Done when:** You can write a `class` with `__init__`, `__repr__`, properties, and inheritance from memory. You can explain what `self` actually is. You've solved 20+ small exercises without copy-pasting.

**Why these two:** Boot.dev forces you to write code (no passive watching), which is the bottleneck. Mosh's free course is the cleanest free alternative — fewer exercises but excellent explanations. Both teach the same patterns; pick whichever clicks faster in the first 2 hours.

### 1B — pandas

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **James Powell — pandas tutorials** (YouTube, ~2 hrs) | 2 | Free |
| **Backup** | **Kaggle "Pandas" micro-course** (kaggle.com/learn/pandas) | 4 | Free |

**Verify Done when:** Given a new CSV, you can load it, filter rows, group-and-aggregate, and plot a basic chart in one notebook in under 15 minutes — without Googling syntax for `groupby`, `merge`, or `pivot`.

**Why these two:** Powell's tutorials show *how working pandas users actually code* — terse, idiomatic. Kaggle is more hand-holdy and verifies via exercises. If you learn from doing rather than watching, do Kaggle. If you learn from seeing the patterns demonstrated, do Powell.

### 1C — Idiomatic Python (during ARIS, not before)

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Fluent Python** (Ramalho), Ch. 1–3 | 6 | Brunel library |
| **Backup** | **Effective Python** (Slatkin), items 1–30 | 5 | Brunel library |

**Verify Done when:** You can explain duck typing, dunder methods, and the descriptor protocol (Fluent) — *or* you've applied 5+ specific items from Slatkin to your ARIS code and can name them.

---

## Track 2 — Machine Learning Foundations (Wk 2–5, ~50 hrs)

**Goal:** Understand what XGBoost is doing, what cross-validation actually controls for, what a residual model is, and why per-lap splits leak.
**Window:** Start by Wk 2 (parallel to building the Phase 2 dashboard); finish by Wk 5 before Phase 3 modelling begins.

### 2A — Foundation course

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Andrew Ng — Machine Learning Specialization** (Coursera) | ~40 | Free (audit) / Paid for cert |
| **Backup** | **fast.ai Practical Deep Learning Part 1** | ~40 | Free |

**Verify Done when:** Course 1 + 2 of Ng's specialization audited. You can explain bias/variance, regularization, gradient descent, and *what cross-validation is actually validating* without notes.

**Why these two:** Ng is theory-first, math-light, slow-paced — best for someone new to ML who needs the conceptual scaffolding. fast.ai is code-first, top-down, faster — best if you learn by doing and tolerate not understanding everything immediately. They produce different skill profiles. **For ARIS specifically, Ng is the correct primary** because Phase 3 is regression with a small model — fast.ai's deep-learning emphasis is overkill.

### 2B — Intuition + algorithm-specific

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **StatQuest with Josh Starmer** (YouTube) — XGBoost, Gradient Boosting, Conformal Prediction, Cross-Validation playlists | ~8 | Free |
| **Backup** | **3Blue1Brown** — Neural Networks playlist (4 videos) | ~3 | Free |

**Verify Done when:** You can sketch on paper how XGBoost combines weak learners, what gradient boosting is doing geometrically, and what conformal prediction guarantees. (You'll be asked. Probably exactly this.)

### 2C — Reference text

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **The Hundred-Page Machine Learning Book** (Burkov) | 8 | Free draft chapters at themlbook.com |
| **Backup** | **Designing Machine Learning Systems** (Huyen), Ch. 4–6 | 6 | Brunel library / O'Reilly |

**Verify Done when:** You can answer "what's the difference between a parametric and non-parametric model" without looking it up — *and* "when would you use ensemble methods over a single deep network."

---

## Track 3 — Vehicle Dynamics (Wk 4–6, ~18 hrs)

**Goal:** Derive a bicycle model from first principles. Understand tire force generation. Speak the language of slip angle, lateral load transfer, and weight distribution.
**Window:** Start late Wk 4, finish by mid-Wk 6 — *before* you write Phase 3 physics code.

### 3A — Core text

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Rajamani — Vehicle Dynamics and Control**, Ch. 1–3 | 8 | Brunel library (reserve in Wk 0) |
| **Backup** | **MIT OCW 2.04A** — relevant lateral dynamics + tire lectures | 6 | Free |

**Verify Done when:** You can derive the bicycle model on a whiteboard from memory in ≤10 minutes. (Listed as a Process success criterion in `ARIS-SUCCESS-CRITERIA.md`.)

**Why these two:** Rajamani is the *standard* — it's what your interviewers will have read. MIT OCW is a video-based alternative if you bounce off the dense math. Read Rajamani if you can; fall back to OCW if you're losing days to it.

### 3B — Reference (skim, don't read cover to cover)

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Milliken & Milliken — Race Car Vehicle Dynamics**, Ch. 1, 5, 14 | 4 | Brunel library |
| **Backup** | **TUMFTM `racesim_basic` source code** | 6 | Free, GitHub |

**Verify Done when:** Skim done, OR you've read TUMFTM's ingest + sim core and understand how stints are simulated end-to-end.

**Why these two:** Milliken is the bible but it's a doorstop — strategic skim, not full read. TUMFTM is *working code that does what ARIS is doing*; reading it teaches faster than any book for a coder. Do both if time allows; if one only, do TUMFTM.

---

## Track 4 — Conformal Prediction (Wk 6–7, ~7 hrs)

**Goal:** Understand split-conformal prediction well enough to defend its use in interview. Implement on a toy regression problem. Wire into ARIS Phase 3.
**Window:** Specifically Wk 6–7. This is the single highest-leverage technical addition to ARIS.

### 4A — Theory

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Angelopoulos & Bates — A Gentle Introduction to Conformal Prediction** (arxiv 2107.07511) | 4 | Free |
| **Backup** | **MAPIE library tutorials** (sklearn-contrib/MAPIE) | 3 | Free |

**Verify Done when:** Implemented split-conformal on a toy regression *from scratch* (not just calling MAPIE). Plotted empirical coverage. Can explain coverage guarantees in one paragraph.

**Why these two:** Angelopoulos & Bates is *the* tutorial, written for non-statisticians, ~30 readable pages. MAPIE is the production library — if the paper is too dense, MAPIE's tutorial gives you a working example to learn from, then go back to the paper.

### 4B — Time-series specifics (because lap times *are* time-series)

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Hyndman — Forecasting: Principles and Practice**, Ch. 1–3, 5 | 6 | Free at otexts.com/fpp3 |

**Verify Done when:** You can explain why per-lap CV leaks, what a "rolling-origin" evaluation is, and what makes a forecast "good."

---

## Track 5 — Software Engineering (Wk 3–7, parallel to ARIS, ~22 hrs)

**Goal:** Pass the "Software Engineer (Vehicle Performance Software)" CV header smell test. Know what a hiring manager expects of someone with that title.
**Window:** Spread across Phase 2 and Phase 3 evenings.

### 5A — Core text

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Designing Data-Intensive Applications** (Kleppmann), Ch. 1–4, 7 | ~14 | Brunel library |
| **Backup** | **System Design Primer** (donnemartin GitHub repo) | ~6 | Free |

**Verify Done when:** You can explain replication, partitioning, and serializability. You can sketch how Postgres handles concurrent writes. You can explain CAP without getting it wrong.

**Why these two:** DDIA is the bible — dense but unmatched. System Design Primer is bite-sized notes and diagrams; faster but shallower. Read DDIA if you can stomach the pace; use the primer to skim what you don't have time for.

### 5B — Deployment hygiene

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **The Twelve-Factor App** (12factor.net) | 1 | Free |

**Verify Done when:** You've audited ARIS deployment against all 12 factors and noted gaps. Read once. It's about 30 minutes.

### 5C — Roadmap

**Primary:** **roadmap.sh — Backend roadmap** (roadmap.sh/backend) — ~2 hrs

Walk it once. Identify 3 specific gaps your ARIS work doesn't fill (likely: caching, message queues, observability). Patch the smallest one with a small side-experiment. **Use this as a checklist of "what concept am I missing," not a curriculum to grind through.**

**Secondary:** **roadmap.sh — AI Engineer roadmap** — skim, you're already living in this space via ARIS.

---

## Track 6 — MATLAB/Simulink (Wk 11–13, ~9 hrs)

**Goal:** Port the bicycle model from Python to MATLAB + Simulink. Closes the "good to have" line at Mercedes HPP, RB Powertrains, Williams VD.
**Window:** Phase 5–6, evenings, parallel to main ARIS work.

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **MATLAB Onramp + Simulink Onramp** (matlabacademy.mathworks.com) | 6 | Free + cert |
| **Backup** | **MathWorks Vehicle Dynamics Onramp** (if available in your region) | 3 | Free |

**Verify Done when:** Both Onramp certificates earned. Bicycle model running in Simulink, comparison plot vs Python within 5%. `aris-matlab-validation` repo committed and pinned.

**Why these two:** Onramp is the *only* certification recruiters at Mercedes/RB look for as a baseline MATLAB signal. The Vehicle Dynamics Onramp specifically — if available — is gold. They cost nothing.

---

## Track 7 — LLM Applications (Wk 10–12, ~9 hrs)

**Goal:** Build a RAG-grounded narration layer for ARIS. Ship a prompt template that converts structured JSON to clean human sentences with citations.
**Window:** Late Phase 5 + Phase 6.

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **DeepLearning.AI short courses** — RAG + LangChain courses (learn.deeplearning.ai) | 6 | Free |
| **Backup** | **Anthropic Cookbook** (github.com/anthropics/anthropic-cookbook) — RAG + tool use recipes | 3 | Free |

**Verify Done when:** Built a toy RAG over your own ARIS state JSON, with citations in every answer. Prompt regression tests passing.

---

## Track 8 — DSA / Interview Prep (ALWAYS-ON, Wk 1 onwards, ~100 hrs total)

**Goal:** Pass auto-graded screens. 100 problems by August, 150 by application time.
**Window:** Daily. ~30–60 min/day. **Non-negotiable. Skipping this fails the placement equation regardless of how good ARIS is.**

### 8A — Problem set

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **NeetCode 150** (neetcode.io) | ~100 | Free |
| **Backup** | **Grokking Coding Interview Patterns** (Educative) | ~30 | Paid (free trial) |

**Verify Done when:** 100 of 150 problems Done by Aug 31, 150 by Nov. Tracked in `MASTER-PLANNER.xlsx` DSA Tracker sheet.

**Why NeetCode primary:** It's free, organized by pattern (which is *how the test actually grades*), and has video explanations for every problem. Grokking pulls ahead only if you find pattern-based theory before practice helps you more than the reverse.

### 8B — Pure practice (after patterns absorbed)

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **LeetCode** — company-tagged problems | ongoing | Free + paid premium |
| **Backup** | **CSES Problem Set** (cses.fi) — Sorting + Searching, Graph sections | ~30 | Free |

CSES is more rigorous and free; LeetCode has the company-specific question patterns. Use CSES for sharpening, LeetCode for company-targeted prep.

---

## Track 9 — Behavioral & Mock Interviews (Wk 14+, ~12 hrs)

**Goal:** Don't fail STAR. Don't fail "tell me about a time." Be calm under live technical questioning.
**Window:** Final 4 weeks of summer, then ongoing through application season.

### 9A — Mocks

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Pramp** (pramp.com) — peer mocks | ~10 | Free |
| **Backup** | **interviewing.io** — anonymous mocks with pros | ~6 | Free + paid |

**Verify Done when:** 5 behavioral + 5 technical Pramps completed; written reflection after each. Plus the Wk 17 mock with a friend.

### 9B — Behavioral text

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Cracking the Coding Interview** (Laakmann McDowell) — behavioral chapters only | 4 | Brunel library |

Skip the technical chapters; their DSA coverage is dated. The behavioral content is still excellent — STAR method, "tell me about a time" templates, what to say when stuck.

---

## Track 10 — Quant Prep (Wk 14+ if targeting quant, ~20 hrs)

**Optional. Only if applying to G-Research, Optiver, IMC, Jane Street, Citadel, etc.**

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **A Practical Guide to Quantitative Finance Interviews** (Xinfeng Zhou) | ~12 | Brunel library / PDF |
| **Backup** | **Heard on the Street** (Crack) | ~8 | Brunel library / PDF |

**Verify Done when:** Solved 30+ probability/brain-teaser problems unaided. Can do mental math under pressure. Know the standard derivations (Black-Scholes intuition, expected value of dice games, conditional probability).

---

## Track 11 — F1 Strategy Literacy (ALWAYS-ON, ~ongoing)

**Goal:** Speak the language. Understand undercut, overcut, gap-to-leader, gap-ahead, pit window, tire compound calls. Cite real strategy decisions when discussing ARIS.
**Window:** Ongoing. ~30 min/week. Background knowledge that compounds.

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **F1: Beyond the Grid** podcast (strategy episodes) — Spotify | ~10 | Free |
| **Backup** | **The Race YouTube** (Mark Hughes columns + race briefings) | ~8 | Free |

**Verify Done when:** You can answer the five canonical strategy interview questions (undercut/overcut, gap-to-leader vs gap-ahead, 1-stop vs 2-stop in mixed weather, pit-stop walkthrough, defend a decision under time pressure). Listed in `ARIS-PHASES-WEEKLY-PLAN.md` Wk 17.

---

## Track 12 — Writing & Positioning (Wk 4 onwards, ~3 hrs total)

**Goal:** Your LinkedIn posts and blog posts don't read like a CS undergrad's. They read like a builder's.
**Window:** Read once early, apply forever.

| Slot | Resource | Hours | Cost |
|---|---|---|---|
| **Primary** | **Julian Shapiro's writing guide** (julian.com/guide/write) | 2 | Free |
| **Required reading** | **Patio11 — Don't Call Yourself a Programmer** (kalzumeus.com) | 0.5 | Free |

**Verify Done when:** Read both. Applied Shapiro's "specificity > generality" rule to LinkedIn post #2 (the first one with a real artefact). Re-read Patio11 before writing your CV.

---

## What to read FIRST — the strict order

If you want a single ordered list, here it is:

1. **Now (Wk 0):** Patio11 essay (30 min). Set the framing.
2. **Wk 0 → Wk 2:** Boot.dev Python (or Mosh). Get fluent fast.
3. **Wk 1 → Wk 2:** Powell pandas tutorial. 2 hours, massive ROI.
4. **Wk 2 → Wk 5:** Andrew Ng Course 1 + 2 + relevant StatQuest videos.
5. **Wk 4 → Wk 5:** Rajamani Ch. 1–3.
6. **Wk 4 → Wk 5:** TUMFTM source code skim.
7. **Wk 6:** Angelopoulos & Bates conformal prediction tutorial.
8. **Wk 3 onwards (parallel evenings):** Kleppmann DDIA Ch. 1–4 spread across 5 weeks.
9. **Wk 11 → Wk 12:** MATLAB Onramp + Simulink Onramp.
10. **Wk 1 onwards (daily, never stops):** NeetCode 150.
11. **Wk 14+:** Mock interviews. CtCI behavioral chapters.
12. **Always-on:** F1 podcasts during commute / cooking / walks.

---

## What you do NOT need (resist the temptation)

These come up in CS YouTube / Twitter and *look* like they belong on this list. They don't, not for your goal:

- **Full deep-learning curriculums** (DL Book, Goodfellow et al.) — overkill for tabular regression.
- **Reinforcement learning courses (Sutton & Barto, OpenAI Spinning Up)** — RL is on the explicit "do not do" list. The temptation to use it for "race strategy" will be enormous. Don't.
- **Generic web-dev courses (The Odin Project, freeCodeCamp full-stack)** — Streamlit is enough for ARIS; you don't need React.
- **Cloud certifications (AWS SAA, GCP)** — useless for an undergrad placement; recruiters discount them.
- **Java / Spring / Go courses** — wrong stack for ARIS, wrong audience for the placement.
- **Long Coursera specializations beyond Andrew Ng's** — diminishing returns; one strong specialization > three half-finished ones.

If you find yourself pulled toward any of these, the answer is: *spend that hour on NeetCode instead.*
