# ARIS — Hardcode Month (no-Claude, 25 Jun → 24 Jul 2026)

> One month off the AI tooling. The goal is **not** to learn Python syntax — you can
> already read and write the codebase. The goal is to *own the concepts, the maths, and
> the stats* underneath everything ARIS already does, and to **hand-build the missing
> Phase-3 ML half** (tire-deg curve → residual model → eval harness) line by line, with
> no autocomplete writing it for you.
>
> Two threads run every day:
> 1. **VALIDATE** — prove you understand something already in the repo. The test is
>    always *whiteboard it cold* or *re-implement it from a blank file*, never "re-read it."
> 2. **BUILD** — write the next planned thing by hand. Every line owned.
>
> Cadence (mirrors the repo): **~6 hrs/day × 6 days, Sundays off.** Suggested split:
> 2 hrs concept/maths (read + derive on paper), 1 hr lecture/video, 3 hrs hardcode coding.
>
> Rule of the month: **if you can't derive it on paper, you don't know it — re-read,
> don't move on.** Write your paper derivations into `learning/notes/` so there's a
> committed record (the same discipline as `bicycle-model.md`).

---

## How to use this file

- Each week has a **theme**, a **concept block** (with sub-topics + named free resources),
  and a **build block** (the repo code you ship that week, by hand).
- Every concept has a **✅ Validation gate** — a concrete "can I prove I know this?" test.
  Don't tick it unless you actually did the cold test. Be as honest as `BUILD-LOG.md` is.
- Run the suite the same way as always (OneDrive venv-lock workaround):
  `.venv/Scripts/python.exe -m pytest`. Keep every new module green + `ruff`-clean.
- Log each day in `BUILD-LOG.md` exactly as you have been — friction included. This plan
  doesn't replace the build log; it's the syllabus the build log reports against.

**Sundays off:** 28 Jun, 5 Jul, 12 Jul, 19 Jul.

---

# WEEK 1 — Foundations you've been *using* without deriving (25 Jun → 1 Jul)

**Theme:** consolidate the maths/stats/CS already baked into Phase 0–3 so far. No new
features ship this week; you re-derive and re-implement from blank files to expose the
gaps. This is the week that makes the rest honest.

## Concept block

### 1.1 Linear algebra you actually use
- **Sub-topics:** vectors & dot products; matrix–vector product as a linear map;
  what "broadcasting" *is* mathematically (rank/shape alignment); L1 vs L2 norm
  (this is literally your MAE vs RMSE); mean as a projection.
- **Where:** 3Blue1Brown *Essence of Linear Algebra* (YouTube, ch. 1–4, 9). Gilbert
  Strang MIT 18.06 lectures 1–2 if you want rigour.
- **✅ Validation:** on a blank page, write MAE and RMSE as norms of the residual
  vector `r = y_true − y_pred`. State which one penalises outliers more and *why*
  (square term). Then explain, in one sentence each, why Miami's red-flag laps moved
  RMSE more than MAE in your Wk-2 numbers.

### 1.2 Statistics — the scoring layer
- **Sub-topics:** mean, variance, std; median vs mean (why `summarise_stints` uses
  *median* pace, not mean); MAE vs RMSE vs MAPE; what an "error metric in the units of
  the target" means; sampling vs population.
- **Where:** StatQuest (Josh Starmer) — "Statistics Fundamentals" playlist, the
  mean/variance/median videos. Khan Academy stats for the gaps.
- **✅ Validation:** re-implement `src/aris/eval/scoring.py` (`mae`, `rmse`,
  `per_race_mae`) from a **blank file**, NumPy only, including the NaN/shape guards —
  then diff against the real one. Explain why median pace is robust to a single
  safety-car lap but mean isn't.

### 1.3 Time-series leakage & cross-validation (the keystone)
- **Sub-topics:** what data leakage *is*; train/test contamination; why time-series
  needs *temporal* splits not random; `shift(1).rolling(k)` and exactly which lap each
  feature is allowed to see; leave-one-group-out CV; why you CV by **race**, not by lap.
- **Where:** scikit-learn user guide §3.1 (cross-validation) + the "TimeSeriesSplit"
  and "GroupKFold" sub-sections. StatQuest "Cross Validation" video.
- **✅ Validation:** re-implement `race_by_race_folds` (`models/cv.py`) from blank, and
  re-derive the leakage tripwire logic on paper: *why* does perturbing lap i's own
  target, or any future lap, prove a leak if feature i changes? Draw the
  one-driver-one-stint frame and mark which laps feature N is allowed to touch. Then
  break it on purpose (drop the `shift(1)`) and watch `test_no_leakage.py` go red.

### 1.4 pandas internals you lean on
- **Sub-topics:** split-apply-combine (`groupby`); `transform` vs `agg` (one returns
  same-shape, one reduces — you use both in `stint.py`); `shift`/`rolling`/`cumsum`;
  why sort-before-shift matters for correctness.
- **Where:** the James Powell "Pandas From The Ground Up" talk (you used it in Phase 0)
  — rewatch the groupby/transform section only. Fill `learning/notes/pandas-gaps.md`
  (it's still empty from May — close that loop).
- **✅ Validation:** without looking at `stint.py`, reconstruct the three-guard
  leakage-safe stint baseline (sort → groupby → shift-before-rolling) and explain what
  breaks if you swap the order. Explain `CompoundChange = (s != s.shift(1))` →
  `cumsum()` as a stint-ID generator out loud.

### 1.5 SQL / Postgres you shipped
- **Sub-topics:** SELECT/JOIN/GROUP BY; window functions (the MA(2) is a SQL window —
  know `OVER (PARTITION BY ... ORDER BY ...)`); CTEs; idempotency & `ON CONFLICT DO
  UPDATE` vs `DO NOTHING`; primary/foreign keys; why the dual pandas/SQL cross-check
  proves losslessness.
- **Where:** PostgreSQL Tutorial — the "Window Functions" section specifically.
  Re-read your own `db/queries/baseline_ma2.sql`.
- **✅ Validation:** on paper, write the window-function SQL for a 2-lap moving average
  of `LapTimeS` partitioned by stint, ordered by lap, *shifted by one* (no
  self-inclusion). Explain why your gear-clean used `DO UPDATE SET gear` for one column
  but everything else stays `DO NOTHING`.

## Build block (Week 1)
No new feature. Deliverable is **proof of understanding committed:**
- `learning/notes/week1-derivations.md` — your paper derivations, photographed or
  typed: MAE/RMSE as norms, the leakage argument, the SQL window MA.
- A throwaway `learning/scratch/` with your blank-file re-implementations of `scoring.py`
  and `cv.py` (keep them out of `src/`; they're evidence, not production).
- Close `learning/notes/pandas-gaps.md`.

---

# WEEK 2 — Vehicle dynamics mastery + the tire-deg curve (2 Jul → 8 Jul)

**Theme:** own the physics you already shipped, then build the **missing Week-6
deliverable: `src/aris/physics/tires.py`**. This is the first real piece of new code,
and it's also your first hand-rolled regression — the bridge into the ML weeks.

## Concept block

### 2.1 Re-derive the bicycle model from Newton (don't trust your past self)
- **Sub-topics:** centripetal force `mv²/R`; friction limit `μmg`; the cancellation that
  gives `v=√(μgR)` and *why mass drops out*; the friction circle (lateral + longitudinal
  grip trade-off); longitudinal load transfer `ΔF = m·a·h/L`; cornering stiffness `Cα`
  and slip angle `α` (the linear-tyre assumption); why no-downforce makes you ~16 s slow.
- **Where:** Rajamani *Vehicle Dynamics and Control* Ch. 2 (re-read; you took notes in
  May). "The Racing Line" YouTube bicycle-model + tire-load videos.
- **✅ Validation:** derive `v=√(μgR)` from `F=ma` on a blank whiteboard, start to
  finish, narrating each step out loud (this is a literal Phase-2 deliverable:
  *"derive the bicycle model from Newton's 2nd law on a whiteboard"*). Explain the
  −16.66 s residual on VER's Bahrain stint as a structured, interpretable error, not a
  bug. Explain why fuel is an *additive* term, not mass re-entering cornering.

### 2.2 Tire degradation & the Pacejka intuition
- **Sub-topics:** linear-with-fuel vs exponential thermal/wear deg; compound differences
  (soft/medium/hard trade pace for life); the cold-tyre out-lap; tire-load sensitivity;
  the *simplified* Pacejka Magic Formula (read the simplified form, ignore the
  14-coefficient version); `TyreLife` vs `lap-in-stint`.
- **Where:** Wikipedia "Hans B. Pacejka" → Magic Formula (simplified). The-Race "tire
  degradation explained." Your own `compute_stint_metrics` already fits a per-stint
  deg *slope* with `np.polyfit` — read it as your starting point.
- **✅ Validation:** explain why the *first lap of a stint* is the worst-fit point in
  notebook 06, and why deg shows up as a late-stint upward climb in the residual.
  Sketch the expected `lap-time vs tyre-life` curve for soft vs hard.

### 2.3 Linear regression *by hand* (this is the maths under the curve)
- **Sub-topics:** ordinary least squares; the cost function (sum of squared residuals);
  the closed-form solution `β = (XᵀX)⁻¹Xᵀy`; what `np.polyfit(x, y, 1)` is *actually*
  computing; slope/intercept interpretation; R²; residuals.
- **Where:** StatQuest "Linear Regression, Clearly Explained" + "Least Squares". Andrew
  Ng ML (Coursera/YouTube) week-1 linear-regression lectures.
- **✅ Validation:** derive the OLS slope/intercept for one variable from
  `d/dβ Σ(y−ŷ)² = 0` on paper. Then **code OLS from scratch in NumPy** (normal equation)
  and confirm it matches `np.polyfit` on one of your real stints to machine precision.

## Build block (Week 2) — `src/aris/physics/tires.py`
Hand-write, following the plan's spec (Phase 2 / Week 6 in `ARIS-EXECUTION-PLAN.md`):
- `tire_pace_loss(compound, lap_in_stint, fuel_load) -> seconds_lost_per_lap`.
- Fit coefficients **per compound** from FastF1 historical stints by linear regression
  (you now know exactly what the fit is doing — you derived it in 2.3). Reuse the
  green-only `filter_clean_laps` and drop the cold out-lap, mirroring
  `compute_stint_metrics`.
- Tests `tests/test_tires.py`: monotonic in `lap_in_stint`; soft degrades faster than
  hard; zero/at-stint-start sanity; coefficients are finite and physically signed.
- Notebook: add the per-compound deg curves overlaid on real stint data; re-score the
  bicycle+tire prediction (the plan expects the residual to shrink from ~16 s — be
  honest about what actually happens, like the Day-3 fuel entry was).
- Commit shape: `feat(physics): per-compound tyre-degradation curve fit from FastF1`.

---

# WEEK 3 — Supervised ML theory + the residual model (9 Jul → 15 Jul)

**Theme:** the heart of the month. Learn how supervised learning, trees, and gradient
boosting actually work — then build the **residual XGBoost model** and the **eval
harness**, which are the two biggest missing Phase-3 pieces.

## Concept block

### 3.1 The supervised-learning frame
- **Sub-topics:** features `X` → target `y`; train vs validation vs test; the
  bias–variance trade-off; overfitting vs underfitting; why **residual learning**
  (`actual − physics`) is more sample-efficient than end-to-end ML; loss functions
  (squared error, absolute error).
- **Where:** Andrew Ng ML lectures (bias/variance, regularization). StatQuest
  "Bias and Variance", "Regularization".
- **✅ Validation:** explain, in interview form (a Phase-2 deliverable), *why a residual
  on physics is more sample-efficient than end-to-end ML* — i.e. the physics carries the
  signal, the ML only learns the structured leftover (cold tyre, deg, downforce bias).
  Define overfitting with reference to your race-by-race CV.

### 3.2 Gradient descent (the optimiser under everything)
- **Sub-topics:** the gradient as direction of steepest ascent; learning rate; batch vs
  stochastic; convergence; why you minimise a loss surface; local vs global minima.
- **Where:** 3Blue1Brown "Gradient descent" (neural-net series ch. 2). StatQuest
  "Gradient Descent, Step by Step".
- **✅ Validation:** **code gradient descent from scratch in NumPy** to fit the *same*
  linear stint model you solved in closed form in Week 2 (2.3) — confirm GD converges to
  the OLS answer. Plot the loss curve. Explain what the learning rate being too high
  does.

### 3.3 Decision trees → gradient boosting → XGBoost
- **Sub-topics:** a decision tree (recursive splits, impurity/variance reduction);
  ensembles; bagging vs boosting; gradient boosting = fitting each new tree to the
  *residual* of the previous ones (note: this is *literally* what ARIS does at the model
  level — boosting on the physics residual); the hyperparameters that matter
  (`max_depth`, `eta`/learning rate, `n_estimators`, subsample).
- **Where:** StatQuest has the canonical series — "Decision Trees", "Gradient Boost
  Part 1–4", "XGBoost Part 1–4". Watch them in order; they build on each other.
- **✅ Validation:** explain why gradient boosting on `(actual − physics)` is
  conceptually a *second* residual layer on top of your hand-coded one. Code a tiny
  regression tree (one or two splits) from scratch in NumPy on toy data. Name the three
  XGBoost hyperparameters you'd tune first and what each trades off.

### 3.4 Cross-validation & honest evaluation (revisited, deeper)
- **Sub-topics:** k-fold vs leave-one-group-out; why your folds are *races*; how a leaked
  model produces a great MAE that collapses; calibration vs accuracy; reporting MAE per
  stint/per race not just global.
- **Where:** scikit-learn §3.1 again, now with the model in hand.
- **✅ Validation:** state the floor/target/stretch from the plan (< 1.0 / < 0.7 / < 0.5 s)
  and what it means to beat the **0.460 s** MA(2) floor *without leaking*. Explain how the
  Week-1 tripwire guarantees it.

## Build block (Week 3) — features + residual model + eval harness
1. **Feature set** → parquet: weather, track temp, lap number, fuel estimate, compound,
   stint age, sector grip. Built **through the leakage-safe path** — every feature for
   lap N sees only laps `< N` within `(driver, stint)`. Run it past `test_no_leakage.py`.
2. **`src/aris/models/residual.py`** — XGBoost fit on `residual = actual − physics`,
   **cross-validated by race** using `race_by_race_folds`. Write the *why-CV-by-race*
   comment the plan demands.
3. **`src/aris/eval/laptime.py`** — held-out MAE per stint/per race via the CV harness;
   reuse `eval/scoring.py`. This is the number that has to beat 0.460 s honestly.
4. Tests + README results table (floor/target/stretch, honest if not hit — no over-claim).
5. Commits: `feat(models): residual XGBoost on physics error, race-CV` +
   `feat(eval): held-out lap-time harness + results table`.

---

# WEEK 4 — Neural nets, uncertainty, and close-out (16 Jul → 24 Jul)

**Theme:** the deep-learning comparison the plan asks for (a tiny MLP), plus a head-start
on the two concepts Phases 4.5 & 6 will need (Monte Carlo, conformal prediction). Lighter
build, heavier on the maths that scares people in interviews — because you'll have
*coded* it, not just watched it.

## Concept block

### 4.1 Neural networks & backprop from scratch
- **Sub-topics:** a neuron (weighted sum + bias + nonlinearity); activation functions
  (ReLU); an MLP as stacked linear layers; forward pass; the chain rule = backprop;
  why GPUs aren't needed for a 2-layer net on this data; why XGBoost usually wins on
  tabular data this size.
- **Where:** 3Blue1Brown neural-network series (all 4 videos — this is the best 1 hour
  in ML education). Andrej Karpathy "micrograd" video if you want the from-scratch build.
  PyTorch "Learn the Basics" (8 short pages).
- **✅ Validation:** **code a 2-hidden-layer MLP forward+backward pass in pure NumPy**
  (no PyTorch) on toy data — derive the backprop updates by hand for one layer first.
  Then re-build the same net in PyTorch and confirm they agree. Explain, with reference
  to your own data size, *why XGBoost probably beats the MLP here*.

### 4.2 Monte Carlo (Phase 4.5 head-start)
- **Sub-topics:** sampling from distributions; law of large numbers; `numpy.random`
  generators, seeds, reproducibility; sampling vs optimisation; conditional probabilities
  (safety-car-per-lap, weather change).
- **Where:** Brandon Foltz "Monte Carlo simulation" (15 min). TUM race-simulation README
  assumptions doc.
- **✅ Validation:** explain *sampling vs optimisation in one sentence* (a Phase-4.5
  deliverable). Code a toy Monte Carlo: sample 1000 race continuations with a stochastic
  safety-car probability and return the finish-position distribution. Seed it; prove it's
  reproducible.

### 4.3 Conformal prediction (Phase 6 head-start)
- **Sub-topics:** prediction intervals vs point predictions; split-conformal; the
  calibration set; empirical coverage; interval width; why this is the honest answer to
  *"how did you handle uncertainty?"*
- **Where:** Angelopoulos "A Gentle Introduction to Conformal Prediction" (first 6
  pages). `mapie` docs (split-conformal in 5 lines).
- **✅ Validation:** explain split-conformal in plain words: how a calibration fold's
  residual quantile becomes a 90% interval on new predictions. State what "empirical
  coverage of 85–95%" would mean for your held-out races.

### 4.4 PyTorch MLP comparison (build)
- Tiny MLP (2 hidden layers, 64 units) on the same residual target as Week 3's XGBoost.
  Keep it in `experiments/` per the plan (XGBoost stays the shipped model). Document
  which won and by how much.

## Build block (Week 4)
- `experiments/mlp_residual.py` — the PyTorch MLP, head-to-head MAE vs XGBoost, race-CV.
- `learning/scratch/` — your from-scratch NumPy MLP + toy Monte Carlo (evidence).
- README: a one-line honest note on MLP-vs-XGBoost outcome.
- **Phase-3 close-out:** if the residual model beats 0.460 s on held-out without leaking,
  you've effectively finished Phase 3's hard part by hand. Tag-readiness for
  `v0.3-predictor` is the milestone.

---

# End-of-month self-exam (do this cold, Wed 23 / Thu 24 Jul)

Sit down with a blank page and a whiteboard. No notes, no repo open. You pass the month
if you can, in ~60–90 minutes:

1. Derive `v=√(μgR)` from Newton's 2nd law, and explain the mass cancellation.
2. Write MAE & RMSE as norms; say which is outlier-sensitive and why.
3. Derive the OLS slope/intercept for one variable from the squared-error cost.
4. Explain gradient descent and why it converges to the OLS answer on a convex loss.
5. Explain gradient boosting as residual-fitting, and how ARIS stacks *two* residual
   layers (physics, then boosting).
6. Explain data leakage in time-series, and prove your tripwire catches a dropped
   `shift(1)`.
7. State why CV-by-race, not CV-by-lap, and what beating 0.460 s "honestly" means.
8. Sketch a backprop update for one MLP layer via the chain rule.
9. Explain sampling vs optimisation (Monte Carlo) and split-conformal coverage in one
   sentence each.
10. Open the repo cold and narrate the Phase-3 architecture (physics backbone → tire
    curve → residual ML → leakage-guarded eval) in 5 minutes.

Anything you can't do, that's your first week back on the tooling — logged honestly in
`BUILD-LOG.md`, same as everything else.

---

## Concept → repo cross-reference (so nothing already built goes un-validated)

| Concept | Lives in | Validated in week |
|---|---|---|
| Dataclasses, type hints, frozen models | `physics/bicycle.py`, `physics/stint.py` | W1 (read), W2 (rebuild tires.py) |
| NumPy arrays, norms, broadcasting | `eval/scoring.py` | W1.1, W1.2 |
| MAE / RMSE / per-race MAE | `eval/scoring.py` | W1.2 |
| pandas groupby/transform/shift/rolling/cumsum | `physics/stint.py`, `eval/baseline.py` | W1.4 |
| Time-series leakage & leave-one-race-out CV | `models/cv.py`, `tests/test_no_leakage.py` | W1.3, W3.4 |
| SQL joins / window functions / idempotent upsert | `io/db.py`, `io/ingest.py`, `db/queries/` | W1.5 |
| Bicycle model, friction circle, load transfer | `physics/bicycle.py` | W2.1 |
| Fuel-burn + pit-loss linear terms | `physics/bicycle.py` | W2.1 |
| Tire degradation (polyfit slope) | `physics/stint.py` → new `physics/tires.py` | W2.2, W2.3 (build) |
| Linear regression / OLS / polyfit | `physics/stint.py` (`np.polyfit`) → tires.py | W2.3 |
| Gradient descent | (new, scratch) | W3.2 |
| Trees / gradient boosting / XGBoost | (new) `models/residual.py` | W3.3 (build) |
| Held-out eval, floor/target/stretch | (new) `eval/laptime.py` | W3.4 (build) |
| Neural nets / backprop / MLP | (new) `experiments/mlp_residual.py` | W4.1 (build) |
| Monte Carlo sampling | (Phase 4.5 head-start) | W4.2 |
| Conformal prediction | (Phase 6 head-start) | W4.3 |

---

## Resource quick-list (all free)

- **Maths intuition:** 3Blue1Brown — Essence of Linear Algebra, Neural Networks, Gradient Descent.
- **Stats + ML, canonical:** StatQuest (Josh Starmer) — Statistics Fundamentals, Linear
  Regression, Bias/Variance, Regularization, Cross Validation, Decision Trees, Gradient
  Boost 1–4, XGBoost 1–4.
- **ML lectures:** Andrew Ng — Machine Learning (linear regression, bias/variance, regularization weeks).
- **From-scratch DL:** Andrej Karpathy — "The spelled-out intro to neural networks" (micrograd).
- **Vehicle dynamics:** Rajamani Ch. 2 (have it); The Racing Line (YouTube).
- **Tire model:** Wikipedia Pacejka (simplified Magic Formula); The-Race deg explainer.
- **scikit-learn:** user guide §1.1, §3.1, §3.3.
- **XGBoost:** official Python intro.
- **PyTorch:** "Learn the Basics" (8 pages).
- **Monte Carlo:** Brandon Foltz (15 min); TUM race-simulation README.
- **Conformal:** Angelopoulos "Gentle Introduction" (first 6 pages); `mapie` docs.

> Bottom line: by 24 Jul you should have (a) hand-derived every maths result already in
> ARIS, (b) shipped `tires.py`, `models/residual.py`, and `eval/laptime.py` — the missing
> Phase-3 ML half — written entirely by your own hand, and (c) a head-start on the
> Monte-Carlo and conformal concepts Phases 4.5 & 6 need. That's a month that moves the
> ship date *forward*, not a month of treading water.
