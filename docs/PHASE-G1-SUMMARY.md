# Phase G.1 summary — why the walk lost to always-stay-out

Executed 2026-08-13. Scope: Blocks G1.1–G1.7. Diagnosis first (no code
until G1.4). A real negative on position-delta is reported as a miss;
match-rate is not dressed up.

Phase G (`docs/strategy-backtest.md`) is unchanged as the pre-fix
artefact: **5/40 = 0.125** vs always-stay-out **10/40 = 0.250**.

---

## Verdict (read this first)

| Metric | Aimed | Actual | Result |
|---|---|---:|---|
| 2024 match-rate (same 40 scored events as Phase G) | **> 0.250** (always-stay-out 10/40) | **0.325** (13/40) | **PASS** |
| 2025 match-rate (full season, never in training) | **> 0.298** (always-stay-out 14/47) | **0.319** (15/47) | **PASS** (by one extra match) |
| 2024+2025 combined match-rate | **> 0.276** (always-stay-out 24/87) | **0.322** (28/87) | **PASS** |
| Mean position-delta 2024 (ARIS pos − actual P5) | **≤ 0** | **+2.63** | **MISS** |
| Mean position-delta 2025 | **≤ 0** | **+3.29** | **MISS** |
| Mean position-delta 2024+2025 | **≤ 0** | **+2.96** | **MISS** |

The walk now beats a never-box policy on decision match-rate. It still
does **not** put classified P5 ahead of reality after bias-cancelling.
Those are different questions; only the first was the Phase G floor.

---

## G1.1 — Chained rollout accuracy (distinct from held-out MAE)

Held-out MAE scores each lap with **real** lag1/lag2. `simulate()` did
not: it fed its own previous prediction back as lag input. That chained
path had never been measured.

Method: 477 green stretches of 20+ laps from the 2024 held-out calendar
(HARD 290 / MEDIUM 168 / SOFT 19). Start 3 green laps in (so opening
lags are real), then roll forward with `predict_lap_time` exactly as
`_simulate_remainder` did. Teacher-forced control uses observed lags at
every step (held-out-MAE style). Bias = pred − observed; positive =
too slow.

### Aggregate (all compounds)

| Horizon | n | Chained MAE (s) | Chained bias (s) | Teacher-forced MAE (s) | Teacher-forced bias (s) |
|---|---:|---:|---:|---:|---:|
| +1 | 477 | **0.861** | +0.235 | **0.861** | +0.235 |
| +5 | 477 | **1.861** | +0.389 | **0.765** | +0.055 |
| +10 | 477 | **2.444** | +0.566 | **0.762** | +0.006 |
| +20 | 354 | **2.790** | +0.572 | **0.791** | −0.111 |

Teacher-forced MAE stays ~0.76–0.86 s at every horizon (same world as
held-out MAE). Chained MAE **compounds**: 0.86 → 1.86 → 2.44 → 2.79 s.
By +20 it is about **3.5×** the one-step number. This is the metric
`simulate()` actually used for counterfactuals.

### By compound (chained MAE / bias)

| Compound | n stints | +1 MAE | +5 MAE (bias) | +10 MAE (bias) | +20 MAE (bias) |
|---|---:|---:|---:|---:|---:|
| HARD | 290 | 0.867 | 1.870 (+0.564) | 2.565 (+0.821) | 2.825 (+0.653) n=230 |
| MEDIUM | 168 | 0.815 | 1.806 (+0.331) | 2.157 (+0.452) | 2.612 (+0.700) n=115 |
| SOFT | 19 | 1.191 | 2.211 (−1.773) | 3.133 (−2.297) | 4.183 (−3.110) n=9 |

HARD/MEDIUM chained bias is **positive** (old tyres look slower than
they were). SOFT chained bias is **negative** and grows (SOFT looks
faster than it was) — small n, but the direction matches G1.3 preferring
SOFT over HARD.

### Named examples (error at +1 / +5 / +10 / +20)

| Stint | +1 chained (forced) | +5 | +10 | +20 |
|---|---|---|---|---|
| Netherlands HUL HARD L19–71 | +1.08 (+1.08) | +0.88 (+0.70) | +0.75 (−0.19) | +0.37 (−0.29) |
| Emilia Romagna BOT HARD L13–62 | +0.44 (+0.44) | −0.51 (−0.51) | −0.58 (−0.21) | −1.04 (+0.21) |
| Singapore PIA MEDIUM L4–37 | +1.31 (+1.31) | **+7.12** (+0.50) | **+9.39** (+0.15) | **+9.33** (+0.08) |
| Belgium TSU SOFT L20–44 | +0.62 (+0.62) | +0.48 (+0.20) | +3.78 (+1.06) | +4.33 (+1.42) |

Singapore PIA is the clearest single picture: teacher-forced stays
inside 0.5 s; chained is already +7 s at five laps ahead.

Artefact: `results/g1/g11_rollout.json`.

---

## G1.2 — Compound / tyre-age extrapolation (single-step, real lags)

Not chained. Real lag1/lag2 at every lap. 20 572 clean 2024 held-out
laps. Positive bias = model makes old tyres look slower than they were.

### tyre_life ≥ 25

| Compound | n | Model MAE (s) | Model bias (s) | Physics-only MAE / bias (s) |
|---|---:|---:|---:|---:|
| HARD | 2995 | 0.842 | **−0.003** | 17.68 / +17.68 |
| MEDIUM | 898 | 0.910 | **−0.430** | 17.58 / +17.58 |
| SOFT | 23 | 1.196 | **−0.360** | 18.03 / +18.03 |

HARD at high life is unbiased once lags are real. MEDIUM/SOFT are
slightly too fast (−0.43 / −0.36 s). Physics-only is ~+18 s everywhere
— that is the bicycle offset, not a tyre-age slope story, and the
residual + real lags already cancel it.

### Bias by tyre-life bucket (model, pred − observed)

| Bucket | HARD | MEDIUM | SOFT |
|---|---:|---:|---:|
| 1–10 | +0.413 (n=3447) | +0.289 (n=3071) | −0.282 (n=788) |
| 11–20 | +0.256 (n=4173) | −0.123 (n=2671) | −0.719 (n=553) |
| 21–24 | +0.049 (n=1204) | −0.015 (n=685) | −0.888 (n=64) |
| 25–34 | −0.062 (n=1891) | −0.323 (n=707) | −0.360 (n=23) |
| 35–80 | +0.097 (n=1104) | −0.824 (n=191) | n=0 |

There is **no** systematic “old HARD looks worse than reality” in
single-step. SOFT late-life is scarce (n=23 at ≥25, none ≥35). MEDIUM
at 35+ is too fast (−0.82 s, n=191). The Phase G hindsight pattern is
**not** explained by missing high-life HARD data.

Artefact: `results/g1/g12_tyre_age.json`.

---

## G1.3 — Divergence case audits

33 `divergence_aris_hindsight` cases in the Phase G walk. Label mix:
25 pit / 4 line / 3 stay / 1 multi-stop plan. Eight audits across
tracks, with the predicted remaining-race delta broken into pit-loss,
physics (base + fuel + tyre deg), and damped residual.

ARIS minus team: negative = ARIS's action looks faster in the (then)
chained `simulate()`.

| Race | Team action | ARIS top rec | Δ total (s) | Δ tyre (s) | Δ residual (s) | Δ pit-loss (s) |
|---|---|---|---:|---:|---:|---:|
| Hungary VER L21 | pit now HARD | Pit lap 29 MEDIUM | **−141.8** | +15.5 | **−157.4** | 0.0 |
| Singapore LEC L36 | pit now HARD | Pit lap 37 SOFT | **−24.0** | +16.1 | **−40.0** | 0.0 |
| Italy HAM L15 | pit now HARD | Pit lap 20 MEDIUM | **−16.6** | +9.6 | **−26.2** | 0.0 |
| Bahrain RUS L11 | pit now HARD | stay / Brake T7 | **−232.2** | +101.8 | **−312.2** | −21.8 |
| Belgium NOR L29 | pit now HARD | stay / Brake T10 | **−48.5** | +4.8 | **−38.7** | −14.6 |
| Azerbaijan VER L49 | pit now SOFT | Stay out | **−17.6** | +0.7 | −0.6 | **−17.7** |
| United States PIA L3 | stay out | Pit now HARD | **−33.2** | −34.0 | −19.3 | +20.1 |
| Mexico City RUS L1 | stay out | Plan L30 SOFT, L45 HARD | **−45.3** | −81.4 | −2.1 | +38.2 |

Hungary is the type specimen: **physics/tyre says ARIS is 15.5 s worse**
(later MEDIUM vs immediate HARD); residual then awards ARIS **157 s**.
Singapore is the same shape on SOFT vs HARD (+16 s tyre against ARIS,
−40 s residual for ARIS). Bahrain's −312 s residual on a stay-vs-HARD
is the chained-lag compound-change failure at full remaining-race
horizon.

Azerbaijan is **not** that story: residual ≈ 0; the 17.6 s is almost
entirely avoided pit-loss with 2 laps remaining. Residual is not every
case, but it is the cases that made the 33/2 split look like “ARIS
found undercuts.”

G1.1/G1.2 **do** explain the one-sided hindsight: chained residual on
fake lags, not a lack of HARD 25+ laps, and not a single-step tyre-age
bias. SOFT looking too fast when chained (G1.1) plus residual overpowering
compound physics (G1.3) is specifically why later SOFT/MEDIUM stops
beat the team's HARD inside `simulate()`.

Artefact: `results/g1/g13_audits.json`.

---

## G1.4 — What was actually fixed, and why

Not (b) extra residual features: G1.2 already shows single-step + real
lags is unbiased on HARD ≥25. Not more data (see G1.6).

**(1) Physics-delta rollout in `simulate()`**, justified by G1.1 and
G1.3. The residual is applied **once**, on the first lap, with the real
lags sitting on `RaceState`. Every later lap adds only the physics
delta (tyre slope + fuel). After a pit, the new compound inherits the
anchored pace; SOFT vs HARD then differs by slope (0.08 vs 0.03 s/lap),
not by a re-applied residual on the previous compound's predicted pace.

Unit check: on a 2-lap remainder, total = first `predict_lap_time` +
physics delta of lap 2, within 1e-6 s. Long remaining race: pit-now
HARD finishes ahead of pit-now SOFT (the reverse of G1.3's residual
ranking).

**(2) Extrapolation confidence**, justified by G1.1 compounding and
G1.2 SOFT n=23 at life ≥25. Evidence ceilings (tyre life after which
held-out support thins): SOFT 16, MEDIUM 32, HARD 50. Beyond that:

- ranking delta vs stay-out is discounted `1 / (1 + 0.05 × beyond)`
- MC / displayed σ gains `0.10 s × beyond` (G1.1 ~0.10 s MAE per
  lap-ahead)
- caveat copy, same channel as SC/VSC: *“this call extends {compound}
  to tyre life {n}, beyond typical observed stints — lower confidence”*

Surfaced on `Recommendation.narration_context` (`confidence_caveat`,
`extrapolation_beyond_laps`, `extrapolation_weight`) and therefore in
the decision JSONL and the existing callout `aris-caveat` strip.

The discount is mild and was **not** tuned to force the match-rate
through 0.250. Physics-delta is the ranking change; the caveat is so a
user can see when a call is past usual evidence.

---

## G1.5 — Walk-forward re-run, 2024 and 2025

Same walker, `mc_draws=0`, classified P5, same match / stay-out /
hindsight rules. 2025 ingested from FastF1 (24/24 races, idempotent
on the already-present Netherlands session). 2025 was never in residual
training (2018–2023).

Elapsed: 2024 **674 s** (~11 min; physics-delta is cheaper than
per-lap XGB). 2025 **890 s** (~15 min). Not shortcut.

### 2024 (same 24-race held-out calendar as Phase G)

| Metric | Aimed | Actual | Result |
|---|---|---:|---|
| Match-rate | **> 0.250** (10/40 stay-out) | **0.325** (13/40) | **PASS** |
| Position-delta | **≤ 0** | **+2.63** | **MISS** |
| ARIS-hindsight / team-hindsight / insufficient | — | 22 / 5 / 21 | hindsight less one-sided than Phase G's 33 / 2 / 21 |
| Rolling match at R24 | — | **0.300** (was **0.000**) | — |
| Rolling pos-delta at R24 | — | **+4.4** (was **+4.2**) | still poor at the end |

Phase G was 5/40 = 0.125. The scored denominator stayed 40.

### 2025 (full season)

| Metric | Aimed | Actual | Result |
|---|---|---:|---|
| Match-rate | **> 0.298** (14/47 stay-out) | **0.319** (15/47) | **PASS** |
| Position-delta | **≤ 0** | **+3.29** | **MISS** |
| ARIS-hindsight / team-hindsight / insufficient | — | 30 / 2 / 27 | still ARIS-hindsight heavy |
| Rolling match at R24 | — | **0.200** | — |
| Rolling pos-delta at R24 | — | **+3.4** | — |

One extra match over never-box on 47 scored events. That is a pass on
the stated rule, not a strong strategist.

### Combined 2024+2025 (48 races, 87 scored inflections)

| Metric | Aimed | Actual | Result |
|---|---|---:|---|
| Match-rate | **> 0.276** (24/87 stay-out) | **0.322** (28/87) | **PASS** |
| Position-delta | **≤ 0** | **+2.96** | **MISS** |

Copy-last-year on the combined set printed 8/36 = 0.222 and is still
**not trusted** (FastF1 503 on historical schedules, same caveat as
Phase G). Primary baseline remains always-stay-out.

Lights-out position-delta did not improve. Physics-delta changes
*mid-race ranking at inflections* more than it changes the prewrite
plan vs the team's actual pit schedule after bias-cancel. The match-rate
floor is met; the outcome floor is not.

Artefacts: `results/backtest/2024_summary.json`,
`2025_summary.json`, `2024_2025_combined_summary.json`,
`results/g1_walk_2024.log`, `results/g1_walk_2025.log`.

---

## G1.6 — External data check

**Not run.** G1.1–G1.3 point at a modeling / rollout issue (chained
residual on predicted lags), not a hole FastF1 fails to fill.

HARD tyre_life ≥ 25 already has **n=2995** held-out laps. MEDIUM ≥25
has 898. Extra timing from Kaggle / Jolpica / F1DB is the same public
feed. SOFT ≥25 is scarce (n=23), but SOFT chained error is already
large at +10 on stints that never reach life 25 (G1.1 SOFT n=19).
More SOFT 30-lap stints would not stop `simulate()` from feeding
predictions back as lags — and that was the mechanism that ranked
SOFT over HARD by tens of seconds.

---

## G1.7 — README scope

README now states: ARIS models the full range of race-engineer
decisions (pit timing, compound, pace targets, SC/VSC reactions) for
the best realistic outcome for the driver, not a pit/no-pit binary;
the goal is the best achievable support inside real data constraints,
not superhuman strategy.

---

## Tests and Zandvoort smoke

Full pytest after G1.4: **194 passed**, 0 failed
(`results/g1_pytest.log`).

Zandvoort Strategy smoke (`scripts/_e1_smoke_strategy_zandvoort.py`)
still **SMOKE OK**. Locked identity vs E4.1:

| Check | Aimed / locked | Actual | Result |
|---|---|---|---|
| Track | 72 laps, pit 18.5, slopes 0.08/0.05/0.03 | same | **PASS** |
| Prewrite windows | A:[18] B:[29] C:[18,40] | same | **PASS** |
| Weekend form | n=20 | n=20 | **PASS** |
| Clock | 287 ticks → lap 72 | 287 → 72 | **PASS** |
| L25 state | MEDIUM tyre_life=2 | MEDIUM tyre_life=2 | **PASS** |
| Ask/recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | same | **PASS** |
| What-if delta | **−13.00 s** | **−11.92 s** | **MISS** |
| What-if MC P10/P90 | **−32.62 / −13.35** | **−147.55 / +29.33** | **MISS** |

The What-if numbers moved because `simulate()` changed. That is
expected and is not restored to the locked −13.00 s. Recommend
*identity* at the smoke tick is unchanged. Log:
`results/g1_zandvoort_smoke.log`.

---

## What this does and does not claim

Does: the Phase G loss to always-stay-out had a measured cause (chained
residual, not missing HARD long-runs); a fix tied to that evidence now
beats stay-out on 2024, on 2025, and combined.

Does not: improve classified P5 after bias-cancel; make ARIS-hindsight
disappear; restore the locked Zandvoort What-if delta; or claim the
2025 margin (one extra match) is a robust strategist.
