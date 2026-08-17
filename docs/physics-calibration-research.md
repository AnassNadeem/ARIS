# Physics-offset calibration research — R21.3 through R21.4

This is the interview account of the attempts to subtract a lap-constant
from lights-out `team_sim − actual` so the ~989 s common-mode offset
would look like a calibrated race time. The conclusion is already
shipped: **no intercept is on the default path**. The rest of this note
is why that is a considered choice, not a placeholder.

Phases: R.2 2026-08-16, R.2.1 2026-08-17. Every number below is aimed vs
actual from those phase summaries. Nothing here changes `simulate()`,
`predict_physics`, or `recommend()`.

This thread is **closed**, same status as tyre degradation
([`docs/tyre-degradation-research.md`](./tyre-degradation-research.md)):
a real, evidenced limitation on absolute-value display, not a blocker
for decision quality.

---

## The conclusion, first

Lights-out `simulate_full_race` has no residual lags. The bicycle runs
green physics for YAML `total_laps`. Against summed real lap times that
is a **per-circuit intercept** of about **+17 s/lap** (aimed G1.2 ~+18;
actual all-48 per configured lap **+17.3**, std **9.8**). The huge
seconds number is mostly `s/lap × race length` (Pearson `r(offset,
per_lap_offset)` = **+0.962**).

That intercept is **not** a street-vs-permanent constant, **not**
stable enough to subtract everywhere, and **cannot move** the
bias-cancelled position-delta R.2 just made identity-safe. A
lap-constant `b` shifts both `ARIS_sim` and `team_sim` by `b × n_laps`,
so `adjusted = actual + (ARIS_sim − team_sim)` is unchanged.

The shipped path therefore **does not** apply a physics intercept.
Absolute sim totals stay uncalibrated. Ranking and match-rate do not
need them.

---

## Why the offset exists

G1.2 already measured an uncalibrated bicycle intercept of ~18 s/lap
when lags are absent. Lights-out prewrite is that path: lap 1, no
observed pace. R.2 measured the 48 classified-P5 races:

| Slice | Aimed | Actual |
|---|---|---|
| All, `team_sim − actual` | report | mean **+989.4 s**, std **544.0** (n=48) |
| Permanent | report | **+966.2**, std 384.4 (n=34) |
| Street | report | **+1046.0**, std 807.0 (n=14) |
| Per configured lap | ~G1.2 +18 s/lap | **+17.3**, std 9.8 |

Street vs permanent **means are almost the same per lap** (18.4 vs
16.8). The split is not the lever. Circuit is: Las Vegas both years
~+2100 s with **zero** SC; Singapore / Austria / Spain sit at +8 to
+12 s/lap; Japan / Miami / Belgium at +26 to +31. Year-pairs on the
same GP are tight when both weekends are clean (Austria std **7.0 s**,
Las Vegas **13.7**, Abu Dhabi **8.3**).

Red flags and long SC pull the offset **down**, they do not create
Vegas. Slow real laps stay in the sum; the sim still runs green YAML
distance. Monaco 2024 RUS: **−1117.6 s**. Dropping major disruptions
(R21.3: any red lap or longest SC run ≥ 5) tightens std 544.0 →
**392.9** (n=35) but the leftover is still circuit structure, not
noise. Street remaining std is **508.5**.

YAML vs timed distance is a third, smaller term (Emilia Romagna 53 vs
63 both years; Las Vegas 56 vs 50).

---

## What was tried

Offline on the 48-row table. 2024 clean intercepts applied forward;
leave-one-year-out. **Not wired** into `physics_pred`. Probe:
`results/r21/r214_intercept_probe.json`. 2024-clean global intercept:
aimed ~G1.2 +18; actual **+18.803 s/lap**.

### Global intercept — worse

Subtract `18.803 × n_laps` from every race.

| Eval | Aimed | Actual | vs raw |
|---|---|---|---|
| All 48 | tighter than std 544.0 | mean **−138.0**, std **618.2** | **worse** |
| 2025 out-of-sample n=24 | tighter than 2025 raw 449.0 | **−68.9 / 500.0** | **worse** |

Monaco 2024 −1117.6 minus 18.8×78 becomes **−2584 s**. A constant
cannot fit both Vegas and a red-flag Monaco.

### Street / permanent intercept — worse

The brief's example split. 2024-clean fits: permanent **+17.34 s/lap**,
street **+23.21 s/lap**.

| Eval | Aimed | Actual | vs raw |
|---|---|---|---|
| All 48 | tighter | **−155.2 / 643.8** | **worse** |
| 2025 OOS | a win | **−86.0 / 496.4** | not a win |

Street vs permanent was the wrong axis. Per-lap means were already
almost equal.

### Per-circuit intercept — helps 2025, not enough

2024-clean has 16 circuits. Japan / Monaco / Miami / Mexico / China /
Qatar / Canada / São Paulo were major in 2024 and fall back to global.

| Eval | Aimed | Actual | vs raw |
|---|---|---|---|
| All 48 | tighter | **−119.9 / 493.2** | modest |
| 2025 OOS n=24 | tighter than 449.0 | **−50.7 / 313.1** | better |
| 2025, circuit seen in 2024 clean n=16 | report | **−75.2 / 236.1** | holes remain |
| LORO per-circuit, all 48 | a common-mode you could ship | **−149.8 / 422.6** | 544.0 → 422.6 |
| LORO, clean eval n=35 | best case | **−28.8 / 260.4** | drops the hard cases |

Per-circuit is the only direction that helps, and only where the other
year was clean. Japan 2025 leftover under the global fallback is the
**+667.7** max. Leave-one-year-out on all 48 is still std **422.6** —
not a number you put on a dashboard as "calibrated race time."

---

## Why a lap-constant cannot move position-delta

R.2 scores lights-out as

`adjusted = actual + (ARIS_sim − team_sim)`

then re-ranks on the same summed-lap-time field. Identity: `ARIS_sim ==
team_sim` ⇒ delta 0 (unit-tested).

A lap-constant intercept `b` applied to both sims:

`ARIS_sim' = ARIS_sim + b × n_laps`
`team_sim' = team_sim + b × n_laps`

so `ARIS_sim' − team_sim' = ARIS_sim − team_sim`. The metric R.2 fixed
does not move. Calibrating the absolute clock cannot manufacture a
strategy claim.

R22.2's clean / disrupted split of that same delta (clean n=35 mean
**−1.49**; disrupted n=13 mean **−2.38**; all 48 still **−1.73**) is
also unchanged by any of the intercepts above. See
[`docs/model-status.md`](./model-status.md).

---

## Scoreboard

Raw all-sample std is **544.0**. A correction ships only if it is
tighter **and** stable out of sample, without dropping the races that
hurt.

| Attempt | Eval | Mean (s) | Std (s) | vs raw 544 | Ship? |
|---|---|---:|---:|---|---|
| None (shipped) | n=48 | +989.4 | **544.0** | — | **yes — display the uncalibrated total, or don't** |
| Drop major (analysis only) | n=35 | +1126.1 | **392.9** | partial | no — leftover is circuit |
| Global 2024-clean s/lap | n=48 | −138.0 | **618.2** | worse | **no** |
| Street/permanent 2024-clean | n=48 | −155.2 | **643.8** | worse | **no** |
| Per-circuit 2024-clean | 2025 OOS n=24 | −50.7 | **313.1** | better on 2025 | **no** — LORO all-48 still 422.6 |
| LORO per-circuit | n=48 | −149.8 | **422.6** | some | **no** |

---

## What this rules out

1. **"Subtract ~18 s/lap everywhere."** Global makes std worse. Monaco
   2024 becomes thousands of seconds more wrong.
2. **"Street vs permanent is the missing flag."** Per-lap means 18.4 vs
   16.8. Type intercepts increase std.
3. **"A per-circuit table from last year."** Helps 2025 where 2024 was
   clean. Does not cover major-disruption circuits, and LORO on all 48
   is still 422.6 s.
4. **"Fix the offset and position-delta will move."** Arithmetic
   forbids it. Bias-cancel already drops the common mode.

Further work on YAML vs timed distance (Imola 53 vs 63, Vegas 56 vs 50)
is a config bug, not a physics intercept. It is not this thread.

---

## Honest close

The bicycle is slow by a circuit-varying ~10–30 s/lap at lights-out.
That is a real limitation if someone asks to read `expected_race_time_s`
as a stopwatch. It is **not** a blocker for `recommend()` (remaining-
race deltas, lags present) or for identity-safe position-delta (the
common mode cancels).

No `ARIS_*` flag. No change to `predict_physics` / `simulate()`.
Default path untouched. Same status as G1.5's tyre slopes: the
investigation mapped the ceiling and stopped.

Further reading: `docs/PHASE-R2-POSITION-DELTA-SUMMARY.md`,
`docs/PHASE-R21-SUMMARY.md`, `docs/PHASE-R22-SUMMARY.md`,
`docs/model-status.md`.
