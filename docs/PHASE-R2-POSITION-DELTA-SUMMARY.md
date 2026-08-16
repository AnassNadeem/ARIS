# Phase R.2 summary — position-delta root cause

Executed 2026-08-16 in the **research worktree**
`C:\Users\anass\OneDrive\Desktop\aris-research-position-delta` on branch
`research/position-delta` (from `a908e79`). Separate from G.6 and from
the cornering-load research tree. Nothing was merged back to `main`.

Scope: Blocks R2.1–R2.5. Leading hypothesis first: lights-out prewrite
simulation runs 70+ laps from lap 1, and G1.1 chained error had never
been measured at that horizon. Every numeric result states aimed vs
actual.

Artefacts: `results/r2/r21_rollout.json`, `r22_plans.json`,
`r23_bias_cancel.json`, `r24_distribution.json`. Diagnostic:
`scripts/_r2_diagnose.py`.

---

## Verdict (read this first)

**The leading hypothesis is rejected for the production simulator.**
Residual-chained error still matches G1.1 exactly at +20 (aimed 2.790,
actual **2.790**), but that is not what `simulate()` does after G1.4.
Physics-delta MAE on the same stretches is **1.114 s** at +20 and
**1.516 s** at +40 (n=27). There are **zero** 20+ lap green stretches
that reach +60 or +70, so full-race-length chained error in the G1.1
sense cannot be measured — it does not exist in the 2024 sample.

**The +2.96 headline is a re-ranking identity failure**, not
compounding. When ARIS_sim equals team_sim, position-delta vs official
P5 is nonzero on **46/48** races (aimed 0; actual mean **+4.69**). The
same identity vs the time-rank field is **0/48**. Official-delta
decomposes exactly as:

`+2.96 = (time_rank − official P5) + (ARIS time-rank − actual time-rank)`
`= +4.69 + (−1.73)`.

Fix: score position-delta as ARIS time-rank minus actual time-rank on
the same field. After that, 2024+2025 mean is **−1.73** (aimed ≤ 0).
G1.4's evidence-ceiling discount is **not** extended to lights-out —
R2.1 does not support it.

This does **not** claim ARIS would have scored more FIA points. The
model still thinks its locked Strat B is ~15 s faster than the team's
schedule; a fair re-rank of *that* number is negative. Whether those
15 s are real remaining-race time is a physics question, not the
+2.96 bug.

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| G1.1 residual-chained MAE +1/+5/+10/+20 | 0.861 / 1.861 / 2.444 / 2.790 | **0.861 / 1.861 / 2.444 / 2.790** | **reproduced** |
| Physics-delta MAE +20 vs G1.1 chained 2.790 | report (production path) | **1.114** (bias +0.175) | does not compound like G1.1 |
| Physics-delta MAE +40 / +60 / +70 | report | **1.516** (n=27) / **n=0** / **n=0** | no 70-lap green data |
| Teacher-forced MAE at +1…+40 | ~0.76–0.86 at every horizon | 0.861 / 0.765 / 0.762 / 0.791 / 0.987 | **holds** |
| `recommended=True` is min A/B/C sim time | 0 mismatches | **0/48** | **PASS** |
| Identity: ARIS_sim=team_sim ⇒ delta 0 vs official P5 | 0 nonzero | **46/48**, mean **+4.69** | **FAIL** (the bug) |
| Identity vs time-rank field | 0 nonzero | **0/48**, mean **0.00** | **PASS** |
| Official position-delta 2024+2025 (old metric) | ≤ 0 | **+2.96** (median +2; 9/5/34) | **MISS** (explained) |
| Time-rank position-delta after fix | ≤ 0 | **−1.73** (median −1; 27/21/0) | **PASS** |
| Spain +15 driving the mean? | report | Spain 2024 **+3** official / **0** time-rank; mean without Spain **+3.07** official | **no** (Phase G +15 is stale) |
| Full pytest after the re-rank fix | green | **258 passed**, 0 failed | **PASS** |

---

## R2.1 — Chained rollout at full-race horizons (checkpoint)

Same method as G1.1: 477 green stretches of 20+ laps from the 2024
held-out calendar (HARD 290 / MEDIUM 168 / SOFT 19). Start 3 green laps
in so opening lags are real. Residual-chained feeds prior *predictions*
as lags (G1.1 path, pre-G1.4). Physics-delta applies the residual once,
then adds tyre+fuel physics deltas (current `simulate()`). Teacher-forced
uses observed lags at every step.

### Aggregate (all compounds)

| Horizon | n | Residual-chained MAE (bias) | Physics-delta MAE (bias) | Teacher-forced MAE (bias) |
|---|---:|---:|---:|---:|
| +1 | 477 | **0.861** (+0.235) | **0.861** (+0.235) | **0.861** (+0.235) |
| +5 | 477 | **1.861** (+0.389) | **0.907** (+0.226) | **0.765** (+0.055) |
| +10 | 477 | **2.444** (+0.566) | **0.955** (+0.271) | **0.762** (+0.006) |
| +20 | 354 | **2.790** (+0.572) | **1.114** (+0.175) | **0.791** (−0.111) |
| +40 | 27 | **2.228** (−1.309) | **1.516** (+0.406) | **0.987** (−0.452) |
| +60 | 0 | — | — | no green stretch this long |
| +70 | 0 | — | — | no green stretch this long |

Aimed at +20: G1.1 chained MAE **2.790**, teacher-forced **0.791**.
Actual residual-chained **2.790** / forced **0.791** — exact reproduction.
Physics-delta at the same horizon is **1.114 s**, about 1.4× teacher-forced
rather than 3.5×.

Cumulative (sum of per-lap errors to that horizon), physics-delta:
+20 MAE **17.3 s** bias **+4.4 s**; +40 MAE **37.9 s** bias **+13.2 s**
(n=27, Monaco-heavy). Residual-chained cumulative at +20 is already
**44.4 s**. Lights-out ranking uses totals, so the production path still
accumulates, but at ~0.9–1.5 s/lap, not G1.1's 2.8 s/lap.

Longest available stretch: Netherlands HUL HARD L19–71, 56 green laps,
53 steps. Last-lap chained **−0.10 s**, physics-delta **−0.09 s**,
forced **−0.10 s**. No 63+ consecutive green laps exist in this sample,
so “70+ lap chained error” is not a G1.1-style number we can print.
Lights-out still *simulates* 70+ laps; it does so with pits and SC, which
this diagnostic correctly refuses to pretend are one green stint.

SOFT (n=19) still looks too fast when residual-chained (+20 MAE **4.183**,
bias **−3.110**). Physics-delta cuts that to MAE **2.050**, bias **−0.446**.
That is G1.4 working, not a reason to put the residual-chained path back.

**Checkpoint reading:** full-race compounding of the *old* chain is real
and still matches G1.1. Full-race compounding of the *shipped* chain is
mild, and the 70-lap green measurement does not exist. Do not treat G1.1's
+20 table as a 70-lap lights-out error. Proceed to the re-rank.

---

## R2.2 — Prewrite `recommended=True` is the best-simulated plan

Aimed: 0 mismatches on 48 scored races (2024+2025 classified P5).
Actual: **0/48**.

`generate_strat_plans` overwrites the hot-track flag with
`recommended = (i == 0)` after sorting on `simulate_full_race`. The
Strategy-page lock is the model's own fastest of A/B/C, verified, not
assumed.

| Rec | n | Notes |
|---|---:|---|
| Strat B (one-stop late) | 46 | default winner |
| Strat C (two-stop) | 2 | Spain 2024 LEC and Spain 2025 HUL |
| Strat A | 0 | — |

A/B/C spread (max − min expected time): min **7.2 s**, median **16.4 s**,
max **20.2 s**. The menu is close; B wins by a small margin almost
everywhere. Position-delta is therefore “late one-stop HARD vs the team's
actual pit list”, not a hidden A/C mix-up.

---

## R2.3 — Bias-cancel identity and stability

`adjusted_time = actual + (ARIS_sim − team_sim)`, then re-rank against
other drivers' **summed lap times**.

### Controlled identity

Synthetic field, ARIS_sim = team_sim = 6120 s, SAI actual = 5040 s (P5).
Aimed delta **0**. Actual delta **0**. The arithmetic works when both
ranks live on the same field.

### Real races, ARIS schedule forced equal to the team (identity)

| Check | Aimed | Actual |
|---|---|---|
| Nonzero delta vs official classified P5 | 0/48 | **46/48**, mean **+4.69** |
| Nonzero delta vs time-rank of the same sums | 0/48 | **0/48**, mean **0.00** |

Official finish_pos and sum-of-laps time-rank are different orderings.
DNFs and partial races have smaller sums, so they rank *ahead* of
classified P5 in `field_race_times`. Time-rank of P5 is typically
official+5 (examples: 2024 Bahrain RUS time-rank 15, Singapore LEC 17,
2025 Austria RUS 16). Subtracting official P5 from a time-rank therefore
injects a ~+5 place offset *even when the two sims are identical*.

### Is the cancelled “bias” stable?

`team_sim − actual` is the common-mode physics offset (G1.2 ~18 s/lap
uncalibrated intercept, no lags at lights-out). Aimed: report, not a
target.

| Slice | n | Mean team_sim − actual (s) | Std (s) | Mean ARIS_sim − team_sim (s) | Std (s) |
|---|---:|---:|---:|---:|---:|
| All 48 | 48 | **+989.4** | 544.0 | **−14.7** | 17.9 |
| Permanent | 34 | +966.2 | 384.4 | −13.1 | 12.5 |
| Street-ish | 14 | +1046.0 | 807.0 | −18.5 | 26.5 |

The absolute offset is huge and not stable (Monaco 2024 RUS
team−actual **−1118 s**, red-flag/shortened clock; Las Vegas 2025
**+2114 s**). Bias-cancel is *supposed* to drop that common mode, and
the identity-vs-time-rank result says it does. What it cannot cancel is
the comparison of the remaining time-rank to FIA classification.

Street vs permanent changes the *absolute* offset more than the
differential (`sim_gap` std 26.5 vs 12.5). All 48 reference drivers are
official P5, so there is no position-slice of the offset to report
beyond that single bin.

---

## R2.4 — Distribution of the old +2.96 (48 races)

Lights-out outcome only (no inflection walk). Same `_score_outcome` path
G1.5 used, before the R2.5 fix. Aimed mean ≤ 0; G1.5 actual **+2.96**.

| Stat | Aimed | Actual (official P5 baseline) |
|---|---|---|
| n | 48 | **48** |
| Mean | ≤ 0 | **+2.96** |
| Median | — | **+2.00** |
| Std | — | ~3.7 (p10 **−2**, p25 **0**, p75 **+6**, p90 **+8**) |
| Better / same / worse | — | **9 / 5 / 34** |
| Mean without Spain | — | **+3.07** (n=46) |

Spain 2024 LEC: official delta **+3** (time-rank 8, sim_gap **−0.2 s**).
Spain 2025 HUL: official delta **−2**. The Phase G Spain **+15** in
`docs/strategy-backtest.md` is the pre-physics-delta artefact. It is
**not** what drives G1.5's +2.96. The mean is broad: 34/48 worse on the
official baseline, median already +2, not one outlier.

On the identity-safe baseline (same field, ARIS time-rank − actual
time-rank), **before any code change**:

| Stat | Aimed | Actual |
|---|---|---|
| Mean | ≤ 0 | **−1.73** |
| Median | — | **−1.00** |
| Better / same / worse | — | **27 / 21 / 0** |

Zero races worse than the driver's own time-rank. Same-distance field
(drop cars ≥3 laps short) gives the **same** −1.73 — DNFs are a
constant offset in both ranks, so they move the *level* of
`aris_finish_pos` but not this delta.

Decomposition that closes the books:

| Term | Mean (48 races) |
|---|---:|
| actual time-rank − official P5 (identity vs official) | **+4.69** |
| ARIS time-rank − actual time-rank (model's own gap) | **−1.73** |
| Sum = official position-delta | **+2.96** |

---

## R2.5 — Evidenced fix (re-rank), not a horizon discount

G1.4's evidence-ceiling discount applies to `recommend()` ranking of
*remaining-race delta vs stay-out*. Lights-out `generate_strat_plans`
ranks absolute `simulate_full_race` totals and never calls
`extrapolation_weight`. R2.1 says the production rollout does not
compound like G1.1, and there is no +70 green measurement to hang a
new horizon discount on. **Do not extend the G1.4 discount to
lights-out.**

The re-ranking method *is* the problem. `_score_outcome` subtracted
official `finish_pos` from a time-rank. That fails the identity test
R2.3 required.

**Change:** `bias_cancelled_delta()` in `src/aris/eval/postrace.py`.
Both ARIS and the baseline are `estimate_position` on the same summed
lap times. `ARIS_sim == team_sim` ⇒ delta 0, unit-tested.
`actual_finish_pos` remains official P5 for context;
`actual_time_rank` is stored alongside.

After the fix, re-score of the same 48 lights-out plans (no new walk):

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Combined mean position-delta | ≤ 0 | **−1.73** | **PASS** |
| 2024 mean | ≤ 0 | **−2.04** | **PASS** |
| 2025 mean | ≤ 0 | **−1.42** | **PASS** |
| Better / same / worse | — | **27 / 21 / 0** | no race worse than own time-rank |
| Identity vs time-rank | 0 | 0 | **PASS** |

Largest gains (most negative): 2024 Austria **−6**, 2025 Canada **−6**,
2024 Britain **−5**. Spain 2024 **0**; Spain 2025 **−5**.

Honest limit: −1.73 is the model preferring its own ~15 s-faster Strat B
over the team's pit list, re-ranked fairly. It is **not** a claim that
classified P5 would have finished P3 on Sunday. Match-rate (inflection
`recommend()`, aimed > stay-out 0.276, G1.5 actual 0.322) is unchanged.

Full pytest after the change: **258 passed**, 0 failed.

---

## What this does and does not claim

Does: G1.1 still holds on the dead residual-chained path; physics-delta
does not grow to 2.8 s by +20; 70-lap green error is unmeasurable;
recommended Strat B *is* the sim-best of A/B/C; the +2.96 official
metric fails identity because it mixes FIA order with summed lap times;
an identity-safe delta is −1.73.

Does not: calibrate the ~989 s lights-out physics offset; prove Strat B
would have beaten the real pit stop; restore E4.1 What-if bands; merge
to `main`.

---

## How to re-run

```powershell
# from this worktree, overlay off
$env:ARIS_TRUE_COMPOUND_SLOPES = "off"
python scripts\_r2_diagnose.py --only r21   # FastF1; ~3 min cached
python scripts\_r2_diagnose.py --only r22
python scripts\_r2_diagnose.py --only r23
python scripts\_r2_diagnose.py --only r24
```
