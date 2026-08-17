# Phase R.2.1 merge summary — position-delta onto main

Executed 2026-08-17 in the **main** tree `C:\Users\anass\OneDrive\Desktop\ARIS`, not
a worktree. Scope: Blocks R21.1–R21.5. Rehearsal-grade: this is the tree
used on 21–23 Aug.

Every numeric result states aimed vs actual.

---

## Verdict (read this first)

**Merge is clean and the Zandvoort demo path is unchanged.**
`research/position-delta` is on `main` at fast-forward `47500b2`.
`bias_cancelled_delta()` and its identity test are in this tree.
`docs/PHASE-R2-POSITION-DELTA-SUMMARY.md` is a tracked file here, not
left in the worktree.

The absolute `team_sim − actual` offset is a **per-circuit bicycle
intercept**, stable year-to-year on undisrupted weekends, with red-flag /
long-SC races as a second downward shock and a handful of YAML-vs-timed
lap mismatches on top. It is **not** a street-vs-permanent constant.
Excluding major disruptions tightens std (aimed: meaningfully stable;
actual: 544.0 → 392.9 s) but does not make a common-mode number you
could subtract everywhere.

No opt-in physics intercept was shipped. Global and street/permanent
corrections make std **worse**. A per-circuit intercept helps 2025
out-of-sample (449.0 → 313.1 s) but leave-one-year-out on all 48 is
still 422.6 s, and a lap-constant intercept cannot move
bias-cancelled position-delta. Honest non-result; default path
untouched.

The two largest time-rank gains are **not** clean “better-timed stop”
wins. 2024 Austria −6 is one-stop HARD vs a green three-stop including
a 7-lap late SOFT, resting on G1.5’s 0.03 HARD slope for a 43-lap
stint. 2025 Canada −6 is one-stop vs a race that ended with three
consecutive SC pits.

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Pre-merge main HEAD | current `main`, clean tree | `a908e79`, **dirty** H.2 uncommitted | **reported**, stashed then restored |
| Research HEAD | R.2 fix committed | worktree was uncommitted at `a908e79`; committed as **`47500b2`** | **corrected** |
| Merge conflicts | resolve explicitly if any | **none** (fast-forward) | **PASS** |
| `bias_cancelled_delta` + identity test | present in merged tree | `postrace.py` + `test_bias_cancel_identity_zero_when_sims_equal` | **PASS** |
| `docs/PHASE-R2-POSITION-DELTA-SUMMARY.md` | in this tree’s `docs/` | tracked at `C:\Users\anass\OneDrive\Desktop\ARIS\docs\PHASE-R2-POSITION-DELTA-SUMMARY.md` | **PASS** |
| Full pytest | 258 passed (R.2 isolated) | **253 passed, 5 failed**; 258 collected | **see R21.1** |
| Zandvoort smoke | G1.5 identity | **SMOKE OK**; same recommend / clock / L25 | **PASS** |
| Offset: street/permanent constant? | report | per-lap means **18.4 / 16.8**; type intercept **worsens** std | **no** |
| Exclude major disruptions | stabilize offset | std 544.0 → **392.9**; street 807.0 → **508.5** | **partial, not enough** |
| Opt-in intercept on `physics_pred` | tighter stable common-mode | not shipped; see R21.4 | **honest non-result** |
| 2024 Austria −6 / 2025 Canada −6 | genuine strategy vs HARD-deg assumption | mixed / SC-contaminated | **see R21.5** |

---

## R21.1 — Merge

### 1. Main HEAD and working tree

| Check | Aimed | Actual |
|---|---|---|
| Branch | `main`, tracking `origin/main` | `main`, up to date with `origin/main` before merge |
| HEAD | current main | **`a908e79`** `docs: add Phase G.6 pre-event rehearsal and day-of overlay/log checklist` |
| Working tree | clean | **dirty**: H.2 Ask-isolation / persist tagging (7 modified tracked + `tests/conftest.py`, `tests/test_ask_model_version.py`, `docs/PHASE-H2-SUMMARY.md` untracked) |

H.2 was **not** discarded. It was stashed
(`stash@{0}: R21.1: stash H.2 uncommitted work before position-delta merge`),
merge ran on a clean-enough tree (only `.cursor/` and
`docs/PHASE-R1-CORNERING-LOAD-SUMMARY.md` untracked), then restored.
`stash@{1}` still holds the H.1 G.2–G.6 backup; do not `stash pop` it.

### 2. `research/position-delta` vs R.2

| Check | Aimed | Actual |
|---|---|---|
| Branch / worktree | reachable | `C:\Users\anass\OneDrive\Desktop\aris-research-position-delta` on `research/position-delta` |
| HEAD vs R.2 | R.2 committed | **`a908e79` with uncommitted files** — same pattern as H.1 / Phase H |

R.2 lived as 3 modified + 2 untracked files. Merging `a908e79` into
main would have been a no-op. Committed in the worktree as:

**`47500b2`** `fix(eval): score position-delta on the time-rank field, not official P5`

Files: `src/aris/eval/postrace.py`, `src/aris/eval/backtest.py`,
`tests/test_postrace.py`, `scripts/_r2_diagnose.py`,
`docs/PHASE-R2-POSITION-DELTA-SUMMARY.md`.

No overlap with H.2’s Ask / persist files. `simulate.py` /
`recommend.py` / `tires.py` were not in the R.2 commit.

### 3. Merge

```
git merge research/position-delta
```

**Fast-forward** `a908e79` → `47500b2`. Strategy not required. **0
conflicts.** 5 files, 1464 insertions, 6 deletions. No ours/theirs
choice.

`bias_cancelled_delta()` is in `src/aris/eval/postrace.py`.
`_score_outcome` calls it. Tests
`test_bias_cancel_identity_zero_when_sims_equal` and
`test_bias_cancel_negative_delta_when_aris_sim_faster` are in
`tests/test_postrace.py`.

`docs/PHASE-R2-POSITION-DELTA-SUMMARY.md` arrived as a tracked file
in this merge (it did **not** exist in this tree before). Path:
`C:\Users\anass\OneDrive\Desktop\ARIS\docs\PHASE-R2-POSITION-DELTA-SUMMARY.md`.

### CHECKPOINT — full pytest

Docker `aris-postgres` healthy (Up 6 days). `ARIS_DB_URL` from `.env`.
`ARIS_FAST_CLOCK` / `ARIS_TRUE_COMPOUND_SLOPES` unset. Live
`results/decisions/` present. H.2 `tests/conftest.py` was **not**
restored yet (pytest on the merged tree, same isolation hole H.1
documented).

| Suite | Aimed | Actual | Result |
|---|---|---|---|
| Full pytest | **258 passed** (R.2 isolated worktree) | **253 passed, 5 failed**, 258 collected, 275 s | **not 258 passed** |

The 5 failures are the same Ask-test isolation pattern as H.1. Live
JSONL is indexed instead of the 14-event fixture:

| Test | Why it failed on live corpus |
|---|---|
| `test_decision_source_is_real_jsonl` | first SAI lap-21 is not 2024 NL; aimed delta **−72.72805747985858**, actual **−2.251042938232149** |
| `test_grounding_ten_plus_logged_decisions` | builds one question per **all** proposes, not 14 |
| `test_grounding_does_not_guess_when_nothing_retrieved` | FIFA question retrieved 2025 Mexico PIA L60 instead of `ABSTAIN` |
| `test_grounding_does_not_mix_another_lap_delta` | 2024 NL SAI L21 not top-ranked |
| `test_follow_up_uses_session_memory_not_a_new_guess` | same L21 miss |

No failure appeared outside that known Ask set. The two new
`bias_cancelled_delta` tests are not in the FAILED list. Non-Ask:
**253 passed** (R.2’s 258 minus the 5 Ask tests that only pass without
live JSONL). 258 collected = 258 isolated. Merge did not break
simulate / recommend / strategy tests.

Log: `results/r21/pytest.log`. H.2 files were restored after this
checkpoint.

---

## R21.2 — Zandvoort smoke, merged tree

`python scripts/_e1_smoke_strategy_zandvoort.py` against local
Postgres. Compared to G1.5 (`docs/PHASE-G1-SUMMARY.md`), same lock
every phase since E4.1. This fix is `eval/postrace.py` scoring, not
simulate / recommend / tires — confirmed, not assumed.

| Check | Aimed (G1.5) | Actual (merged main) | Result |
|---|---|---|---|
| Setup | 2025 Netherlands session_id 123, VER | **123**, VER, driver_id **2448** | **PASS** |
| Track | 72 laps, pit_loss **18.5**, slopes **0.08 / 0.05 / 0.03** | **72 / 18.5 / 0.08, 0.05, 0.03** | **PASS** |
| Prewrite windows | A:[18] B:[29] C:[18, 40] | **same** | **PASS** |
| Weekend form | n=20 | **20** | **PASS** |
| Clock | 287 ticks → lap 72 complete | **287** ticks, lap **72**, complete | **PASS** |
| Live state L25 | MEDIUM, tyre_life=2 | **MEDIUM / 2** | **PASS** |
| Recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **Pit lap 33 for HARD; Pit lap 30 for HARD; Stay out on current tyres** | **PASS** |
| Smoke exit | SMOKE OK | **SMOKE OK** | **PASS** |

What-if MC is unseeded and not a locked identity. This run: delta
**−11.92 s**, MC P10/P90 **−147.55 / +29.33** (same printed delta as
H.1 / H.2). Log: `results/r21/zandvoort-smoke.log`.

---

## R21.3 — Why the +989 s offset is unstable

R.2: `team_sim − actual` mean **+989.4 s**, std **544.0 s** (n=48);
permanent n=34 mean **+966.2** std **384.4**; street n=14 mean
**+1046.0** std **807.0**. Aimed this block: a real breakdown
(circuit / race length / red flag / SC), not a guess. Diagnosis only;
no product-code change.

Source: R.2’s 48 lights-out rows plus Postgres `laps.track_status`
(FastF1 codes: `5` red, `4` SC, run of `4` ≥ 5 = lengthy SC).
Major disruption = any red lap **or** longest SC run ≥ 5. Shortened =
timed laps < configured YAML laps − 2.

Artefact: `results/r21/r213_offset_breakdown.json`. Re-run:
`python scripts/_r21_offset_breakdown.py`.

### Per-lap is the G1.2 bicycle, not a 989 s constant

| Slice | Aimed | Actual |
|---|---|---|
| All, absolute | mean +989.4, std 544.0 (R.2) | **+989.4 / 544.0** (reproduced) |
| All, per configured lap | ~G1.2 physics-only **+18 s/lap** | mean **+17.3 s/lap**, std **9.8** |
| Permanent per lap | report | **+16.8**, std 7.6 |
| Street per lap | report | **+18.4**, std 13.7 |

Pearson `r(offset, per_lap_offset)` = **+0.962**. The huge seconds
number is mostly `s/lap × race length`. Street vs permanent **means
are almost the same** (18.4 vs 16.8). That split is not the lever.

### Circuit, not race length, is the stable structure

Year-pairs on the same GP (mean offset, std across the two years):

| GP | n | Mean offset (s) | Std across years | Notes |
|---|---:|---:|---:|---|
| Austria | 2 | **+779.0** | **7.0** | both clean |
| Las Vegas | 2 | **+2099.8** | **13.7** | both clean, **0 red, 0 SC** |
| Japan | 2 | **+1650.2** | **14.1** | 2024 has 1 red lap |
| Abu Dhabi | 2 | **+1056.1** | **8.3** | both clean |
| Singapore | 2 | **+547.3** | **26.3** | both clean |
| Miami | 2 | **+1601.9** | **44.9** | 2024 SC run 5 |
| Monaco | 2 | **+18.9** | **1136.5** | 2024 red-flag **−1117.6** vs 2025 clean **+1155.5** |
| Canada | 2 | **+774.5** | **442.3** | 2024 SC run 5 **+332**; 2025 **+1216.8** |
| Emilia Romagna | 2 | **+101.0** | **171.4** | YAML 53 vs timed **63** both years |

Las Vegas is **not** a red-flag story. Both years +2100 s, zero SC.
Japan / Miami / Belgium sit at **+26 to +31 s/lap**; Singapore / Austria
/ Spain at **+8 to +12 s/lap**. That is bicycle-vs-circuit (no
downforce, `mu=1.5`), the same G1.2 ~18 s intercept with a
circuit-varying residual of about ±10–20 s/lap.

Race-length bins do not save it: `[50,60)` n=28 std **492**; `[70,90)`
n=14 std **635** (Monaco 2024 in the long bin). `r(offset, total_laps)`
= **−0.338**.

### Disruptions pull the offset **down**, they do not create Vegas

Red / long SC inflates **actual** (slow laps stay in the sum) while
`simulate_full_race` still runs green physics for YAML `total_laps`.
`team_sim − actual` therefore falls:

| Slice | n | Mean (s) | Std (s) |
|---|---:|---:|---:|
| Has red flag | 3 | **+270.1** | 1124.3 |
| No red flag | 45 | **+1037.4** | 441.1 |
| Major (red or SC run ≥ 5) | 13 | **+621.5** | 701.0 |
| Not major | 35 | **+1126.1** | 392.9 |
| Longest SC run ≥ 5 | 10 | **+726.9** | 459.8 |
| Shortened (timed < cfg−2) | 7 | **+1270.4** | 651.0 |

Monaco 2024 RUS: timed 77 / cfg 78, **1 red + 2 SC**, offset
**−1117.6 s** (−14.3 s/lap) — actual clock is *slow*, sim is green.
Las Vegas 2025 SAI: timed 50 / cfg 56, **0 red, 0 SC**, offset
**+2113.5 s** (+37.7 s/lap). Opposite sign, different mechanism.

`r(offset, n_red)` = **−0.341**; `r(offset, longest SC run)` = **−0.320**.

YAML vs timed distance is a third, smaller term. `|cfg − timed| ≥ 3`
on 9 / 48 races. Emilia Romagna **53 vs 63** both years (sim short).
Las Vegas **56 vs 50** both years (sim long). Britain 2025 **52 vs 46**
(SC-shortened).

### Exclusion test — does dropping major disruptions stabilize?

Aimed: remaining std clearly tighter than 544 (and street 807 /
permanent 384). This is **calibration analysis only**, not a
walk-forward filter.

| Exclusion | n | Mean (s) | Std (s) | vs 544.0 |
|---|---:|---:|---:|---|
| None | 48 | +989.4 | **544.0** | — |
| Drop red only | 45 | — | **441.1** | some |
| Drop shortened | 41 | +941.5 | **508.3** | almost none |
| Drop major | 35 | +1126.1 | **392.9** | **partial** |
| Permanent drop major | 34→25 | +966.2→+1043.3 | 384.4→**297.9** | some |
| Street drop major | 14→10 | +1046.0→+1333.1 | 807.0→**508.5** | still huge |

**It does not stabilize enough to treat as a common-mode constant.**
Std 544.0 → 392.9 is a real ~28% cut (the left tail was Monaco 2024 /
Imola 2025 / Canada 2024). Mean **rises** (989 → 1126) because
disruptions were pulling the offset down. Street remaining std is
still **508.5** — Las Vegas and clean Monaco 2025 are still in. The
leftover is circuit structure, not residual noise.

---

## R21.4 — Calibration attempt (not shipped)

R21.3’s addressable piece is a **per-circuit s/lap intercept**, not
street vs permanent. Aimed: tighter, more stable `team_sim − actual`.
Tried offline on the 48-row table (2024 clean intercepts applied
forward; leave-one-year-out). Did **not** wire `physics_pred`.

2024 clean global intercept: **+18.803 s/lap** (aimed ~G1.2 +18;
actual **+18.803**).

| Correction | Eval | Mean (s) | Std (s) | vs raw |
|---|---|---:|---:|---|
| Raw all | n=48 | +989.4 | **544.0** | — |
| Global 2024-clean s/lap | all 48 | −138.0 | **618.2** | **worse** |
| Global | 2025 OOS n=24 | −68.9 | **500.0** | vs 2025 raw **449.0**, worse |
| Street/permanent 2024-clean | all 48 | −155.2 | **643.8** | **worse** |
| Street/permanent | 2025 OOS | −86.0 | **496.4** | not a win |
| Per-circuit 2024-clean | all 48 | −119.9 | **493.2** | modest |
| Per-circuit 2024-clean | 2025 OOS n=24 | −50.7 | **313.1** | vs 2025 raw **449.0**, better |
| Per-circuit 2024-clean | 2025, circuit seen in 2024 clean n=16 | −75.2 | **236.1** | holes remain |
| LORO per-circuit | all 48 | −149.8 | **422.6** | 544.0 → 422.6 |
| LORO per-circuit | clean eval n=35 | −28.8 | **260.4** | best, but drops the hard cases |

Street/permanent was the example in the brief. Actual 2024-clean
fits: permanent **+17.34 s/lap**, street **+23.21 s/lap**. Applying
them **increases** std. Global does the same: Monaco 2024 −1117.6
minus 18.8×78 becomes **−2584 s**.

Per-circuit is the only direction that helps, and only where the
other year was clean. 2024-clean has 16 circuits; Japan / Monaco /
Miami / Mexico / China / Qatar / Canada / São Paulo were major in
2024 and fall back to global. Japan 2025 leftover under that fallback
is the **+667.7** max.

A lap-constant intercept also **cannot change bias-cancelled
position-delta**: `adjusted = actual + (ARIS_sim − team_sim)` and
both sims shift by `b × n_laps`. The metric R.2 just fixed would not
move.

**Not shipped.** No `ARIS_*` flag, no change to `predict_physics` /
`simulate()`. Default path unchanged. Aimed a tighter stable
common-mode; actual best honest OOS (2025 per-circuit) is std **313.1**
vs 449.0 — not stable, and not a reason to touch lights-out physics
before Zandvoort. Probe: `results/r21/r214_intercept_probe.json`.

---

## R21.5 — Hand-audit of the two −6s

Lights-out Strat B is the same menu everywhere: start MEDIUM, box
once for HARD (windows B). Team schedules below are from Postgres
laps, not a guess. Model slopes are G1.5 **0.08 / 0.05 / 0.03**.
`tire_pace_loss` last-lap deg on a 43-lap HARD stint is **1.26 s**
(`0.03 × 42`).

### 2024 Austria VER — time-rank delta **−6**

| | Aimed to check | Actual |
|---|---|---|
| ARIS Strat B | one-stop late HARD | start **MEDIUM**, pit **L28 HARD**; expected **5853.6 s** |
| Strat A / C | report | A L17 HARD **5857.0**; C L18 HARD + L39 MEDIUM **5869.7** |
| Team | real pit list | start **MEDIUM**; pits **L23 HARD, L51 MEDIUM, L64 SOFT** |
| Sim gap (R.2) | ARIS − team | **−22.36 s** |
| Disruptions on VER laps | SC/red? | **none** (all four stints essentially green) |

Actual stints: MEDIUM 23 (mean 70.93 s) → HARD 28 (70.85) → MEDIUM 13
(73.32) → SOFT 7 (74.53). Last pit is L64 onto SOFT for seven laps,
not a red-flag dart. Extra team stops vs ARIS: **2**. Austria
`pit_loss_s` **17.5**; extra pit cost **~35.0 s**. That 35 s minus
stint-deg differences is the same order as the **−22 s** sim gap.

ARIS implied stints on YAML 70 laps: MEDIUM 27 (model deg sum 19.05 s,
last-lap 1.30) + HARD **43** (deg sum 28.59 s, last-lap **1.26 s**).
Team’s longest HARD stint was 28 laps (last-lap deg 0.81 s). Strat C
is only **16.1 s** slower than B in the model — B wins because a
43-lap HARD at 0.03 looks cheap.

**Verdict: mixed, not a clean strategy win.** The team ran a green
three-stop including a late SOFT; ARIS never proposed that menu. Some
of the −6 is real stop-count (two extra pit-losses). Some of it is
G1.5’s generous HARD slope making the one-stop the sim-best of A/B/C
by 3–16 s. This is not evidence classified P5 would have finished six
time-ranks higher on a 43-lap HARD.

### 2025 Canada LEC — time-rank delta **−6**

| | Aimed to check | Actual |
|---|---|---|
| ARIS Strat B | one-stop late HARD | start **MEDIUM**, pit **L28 HARD**; expected **6682.3 s** |
| Team | real pit list | start **HARD**; pits **L28 HARD, L53 MEDIUM, L67 MEDIUM, L68 MEDIUM, L69 MEDIUM** |
| Sim gap (R.2) | ARIS − team | **−50.56 s** |
| Late pits | strategy or SC? | **L67, L68, L69** all `track_status` contains `4`; lap times **114.9 / 110.8 / 123.0 s** |

Strategic stints before the chaos: HARD 28 (green, mean 77.59) → HARD
25 (76.17) → MEDIUM 14 (77.91, 1 SC lap). Then three consecutive
one-lap MEDIUM “stints” under SC. Extra team stops vs ARIS: **4**.
Canada `pit_loss_s` **16.1**; if all four count, extra pit cost
**~64.4 s** (same order as the −50.6 s gap). Lights-out sim does not
see SC; it charges those three pits as green pit-loss.

ARIS again: MEDIUM 27 + HARD **43** at 0.03. Team started HARD and
two-stopped HARD→HARD then MEDIUM — then the SC pits.

**Verdict: not a genuine better-timed stop.** Three of five team pits
are consecutive SC laps at the end of the race. Comparing a green
one-stop to that clock is not a strategy claim. What remains
(MEDIUM→HARD one-stop vs HARD→HARD two-stop) is the same long-HARD
assumption as Austria.

---

## What this does and does not claim

Does: land the identity-safe position-delta scorer on the event tree;
confirm G1.5 Zandvoort smoke; show the +989 s offset is per-circuit
bicycle + disruption shocks + a few YAML distance bugs; refuse a
calibration that does not stabilize it; hand-audit the two −6s
honestly.

Does not: commit H.2; change `simulate()` / `recommend()` / tyre
slopes; claim −1.73 time-rank delta is FIA points; fix Las Vegas YAML
56 vs 50 or Imola 53 vs 63 in this phase.

---

## Isolation / paths

| Tree | Branch | HEAD | Notes |
|---|---|---|---|
| `C:\Users\anass\OneDrive\Desktop\ARIS` | `main` | **`47500b2`** | this summary lives here |
| `aris-research-position-delta` | `research/position-delta` | `47500b2` | source of the fast-forward |
| `ARIS-cornering-load` | `research/cornering-load` | `a908e79` | not used |
| `ARIS-grounded-rag` | `feature/grounded-rag` | `3fddb9b` | not used |

**This file path is under the main ARIS repo `docs/`, not a worktree:**
`C:\Users\anass\OneDrive\Desktop\ARIS\docs\PHASE-R21-SUMMARY.md`.

Also in this main tree, from the merge:
`C:\Users\anass\OneDrive\Desktop\ARIS\docs\PHASE-R2-POSITION-DELTA-SUMMARY.md`.

H.2 files remain uncommitted on this working tree, as they were
before R21.1.

**STOP.**
