# Model status — where ARIS actually stands

Interview-ready account of the predictive / decision core as of
Tier 2 (2026-08-20), the day before the 21–23 August 2026 Dutch GP.
This page supersedes scattered phase docs as the one place to point
someone asking **how good is this, really**. Those phase docs remain
the evidence trail. Public-facing numbers in `README.md` match this
page. Wet races are out of scope (see below) — same class of named
limit as G1.5 and the physics-offset close.

Every number is aimed vs actual. Overlay env
`ARIS_TRUE_COMPOUND_SLOPES` is **unset**. G1.5 slopes stay the tyre
prior. Circuit-conditioned OLS (`ARIS_USE_CIRCUIT_DEG`) is **off**
until it clears its own gate.

---

## The short answer

ARIS beats a never-box policy on mid-race pit/SC **match-rate**. It
does **not** beat a moving-average lap-time baseline. Lights-out
position-delta is identity-safe and negative, but a green one-stop vs
the team's pit list is not FIA points, and SC-contaminated stops are
part of that comparison. Absolute sim totals are uncalibrated by
~17 s/lap; that offset cannot be subtracted usefully and cannot move
the ranking metric. Tyre slopes are a physical prior, not a fitted
sensor. The Zandvoort demo identity is unchanged.

| Question | Aimed | Actual | Honest reading |
|---|---|---|---|
| One-step lap time vs MA(2) | beat baseline | E3 2024 blend **0.583 s** vs MA(2) **0.522** | closest stack; **does not beat** |
| Mid-race match-rate vs stay-out | > 0.276 | **0.345** (30/87) | **beats** never-box; T2 default (G1.5 + SC pit cost + dynamic undercut + approach trigger). G1.5-only was 0.322 (28/87) |
| Lights-out position-delta (all 48) | ≤ 0 | **−1.73** | identity-safe; not FIA points |
| Same, clean races only | report, don't hide | **−1.49** (n=35) | both numbers required |
| Same, disrupted (red or SC run ≥ 5) | report, don't hide | **−2.38** (n=13) | more negative, not a cherry-pick |
| Absolute `team_sim − actual` | a stable intercept | mean **+989 s**, std **544** | **closed** — do not subtract |
| Tyre slopes from lap time | physical C1<…<C5 | G2/G3/G4 miss; T2-A identity **moved** | **G1.5 locked**; `ARIS_USE_CIRCUIT_DEG` stays off |
| Wet / rain-affected races | a wet strategy | **none** — **0.356** (48/135) inflections excluded | **out of scope**, not an eval choice |
| Zandvoort recommend identity | Pit 33 HARD / Pit 30 HARD / Stay out | same on the **default** path | demo path **untouched** unless T2-A is forced on |

---

## Predictor (one-step, real lags)

Held-out MAE uses observed lag1/lag2. That is **not** what a 40-lap
`simulate()` used to do (see rollout below).

**Full 2024 calendar (Phase E3, the current one-step number):**

| Stack | Aimed | Actual |
|---|---|---|
| MA(2) baseline | the floor | **0.522 s** |
| Physics-only (bicycle + tyre + fuel) | — | **17.378 s** |
| Physics + residual | — | **0.948 s** |
| Inverse-variance blend | ≤ 1.5× baseline (**0.783**) | **0.583 s** (**PASS** vs 1.5×; **MISS** vs beating MA(2)) |

Per-race: **23/24** inside 1.5× that race's MA(2). China is the miss
(blend **0.596** vs aimed **0.563**). Netherlands 2024 blend **0.502**
(aimed ≤ 0.640).

The README's five-race Phase C row (MA(2) **0.469** · physics **15.211**
· residual **0.787** · blend **0.549**) is the older short held-out.
E3 is the calendar figure to quote.

Teacher-forced MAE on 477 green 20+ lap stretches (G1.1, 2024 held-out)
stays ~0.76–0.86 s at every horizon through +20. That is the same world
as one-step MAE: real lags, no compounding.

---

## Rollout (`simulate()` remaining-race)

Before G1.4 the simulator chained its own predictions back as lags.
Chained MAE compounded: aimed G1.1 **0.861 / 1.861 / 2.444 / 2.790** at
+1/+5/+10/+20; actual **exact match**. By +20 that is ~3.5× teacher-
forced.

**Shipped path (G1.4 physics-delta):** residual once on the first
remaining lap, then tyre slope + fuel only.

| Horizon | Aimed (report production path) | Physics-delta MAE (R.2) |
|---|---|---|
| +20 | not G1.1's 2.790 | **1.114 s** (bias +0.175, n=354) |
| +40 | report | **1.516 s** (n=27) |
| +60 / +70 | report | **n=0** — no 20+ lap green stretch that long |

Lights-out still *simulates* 70+ laps. It does so with pits, not as one
green stint. Full-race chained error in the G1.1 sense is unmeasurable.

G1.4 also discounts ranking deltas past typical stint lengths. That
caveat is **not** extended to lights-out prewrite (R2.5): prewrite
ranks absolute totals and never calls `extrapolation_weight`.

---

## Tyre degradation — closed (G.5)

Shipped default: global slopes SOFT **0.08** / MEDIUM **0.05** / HARD
**0.03** s per lap of tyre age, plus physics-delta. That is a physical
prior, not a fitted sensor.

The gate (G3.5.11 onward): a fitted overlay becomes the default only if
it beats **both** always-stay-out **and** G1.5 on combined 2024+2025
match-rate.

| Attempt | Combined match-rate | vs stay-out 0.276 | vs G1.5 0.322 |
|---|---|---|---|
| **G1.5 (shipped tyre prior)** | **0.322** (28/87) | beat | — |
| G2 unconstrained C-code | 0.195 (17/87) | lose | lose |
| G3 isotonic PAVA | 0.299 (26/87) | beat | lose |
| G4 pooled GBT | 0.264 (23/87) | lose | lose |
| T2-A circuit OLS (flagged) | not default | — | Zandvoort identity **moved**; keep `ARIS_USE_CIRCUIT_DEG` off |

T2-B/D/C (not a tyre overlay) raise the **default** combined match-rate to
**0.345** (30/87) on the same 87 inflections, still using G1.5 slopes.

Lap time is not a tyre sensor. FastF1 has no C1–C6 and no temp /
pressure / energy. HARD stints run in freer air than SOFT (median
min-gap **1.82 s** vs **1.40 s**). Every more sophisticated fit on that
signal missed the gate. Full write-up:
[`docs/tyre-degradation-research.md`](./tyre-degradation-research.md)
(Phase G.5 close). Cornering-load as a non-lap-time proxy is scoped,
not built (`docs/future-research-cornering-load.md`; R.1 cheap check
did not fire the stop gate).

---

## Decision match-rate (inflection walk-forward)

Walker ticks the live engine on classified P5, 2024+2025. Scored
inflections exclude rainfall / wet compound / red-flag as
`divergence_insufficient_info` — not forced into match/mismatch.
That exclusion is **0.356** (48/135) of all inflections. It is the
wet-strategy gap below, not a way to dress the 87-event match-rate.

Always-stay-out matches every non-pit inflection and misses every pit.

| Year | Aimed (beat stay-out) | Actual (T2 default) | Stay-out | G1.5-only |
|---|---|---|---|---|
| 2024 | > **0.250** (10/40) | **0.375** (15/40) | 10/40 | 0.325 (13/40) |
| 2025 | > **0.298** (14/47) | **0.319** (15/47) | 14/47 | 0.319 (15/47) |
| Combined | > **0.276** (24/87) | **0.345** (30/87) | 24/87 | 0.322 (28/87) |

T2-B/D/C add **two** combined matches on the same 87 inflections. 2025
is unchanged vs G1.5 (still one extra match over stay-out). 2024 is
the gain. T2-A is **not** in this table.

This metric is `recommend()` at real pit/SC/compound inflections, not
the lights-out prewrite.

---

## Lights-out position-delta

Prewrite Strat B (one-stop late HARD on 46/48 races; Strat C on both
Spains) vs the team's actual pit list. Bias-cancel:

`adjusted = actual + (ARIS_sim − team_sim)`

then re-rank on the **same** summed-lap-time field. Official P5 mixed
with that field was the +2.96 bug (R2.3: 46/48 identity misses, mean
**+4.69**). After the re-rank, identity vs time-rank is **0/48**.

### All 48 (headline, not dropped)

| Stat | Aimed | Actual |
|---|---|---|
| Mean | ≤ 0 | **−1.73** |
| Median | — | **−1.00** |
| Better / same / worse | — | **27 / 21 / 0** |
| 2024 / 2025 | ≤ 0 | **−2.04** / **−1.42** |

Zero races worse than the driver's own time-rank. This is the model
preferring its own ~15 s-faster Strat B, re-ranked fairly. It is **not**
a claim that classified P5 would have finished six places higher on
Sunday.

### Clean vs disrupted (R22.2) — both numbers required

Flag = R21.3 major disruption: any red-flag lap **or** longest SC run
≥ 5. Same discipline as walk-forward insufficient-info: do not force
disrupted races into the clean headline, and do not drop them silently.

| Slice | Aimed | Actual | Better / same / worse |
|---|---|---|---|
| All 48 | −1.73 (R.2) | **−1.73** | 27 / 21 / 0 |
| Clean (not major) | report | **−1.49** (n=35) | 17 / 18 / 0 |
| Disrupted | report | **−2.38** (n=13) | 10 / 3 / 0 |

Disrupted is **more** negative than clean. Excluding those 13 would
make ARIS look *worse*, not better. That is why both numbers sit side
by side.

**Excluded (disrupted) races:** 2024 Japan NOR −4, China SAI 0, Miami
SAI 0, Monaco RUS −4, Canada PIA −3, Mexico City RUS 0, São Paulo LEC
−3, Qatar GAS −2; 2025 Australia ALB −1, Emilia Romagna ALB −4, Spain
HUL −5, Britain VER −1, Netherlands ALB −4.

**Austria 2024 VER −6** is **not** SC-driven. Under this flag:
`major_disruption=False`, 0 red, longest SC run **0**, team pits
L23/L51/L64 all green. The −6 stays in the clean bucket. Classification
does not change: mixed (two extra green pit-losses plus G1.5's 43-lap
HARD at 0.03), not a clean strategy win. See R21.5.

**Canada 2025 LEC −6** has three consecutive SC pits (L67–L69) but
longest SC run **4**, so it is **not** major under the reused flag. It
stays in the clean n=35. R22.1 still counts those three pits as
SC-contaminated for stop-count. Do not widen the flag to catch them.

---

## SC-contamination of team pit events (R22.1)

The stop-count / pit-loss comparison uses every `pit_in` on the
reference driver, including SC/VSC stops the green sim charges as pit-
loss.

| Check | Aimed | Actual |
|---|---|---|
| Races | 48 | **48** |
| Team pit events | report | **85**, of which **21** under SC/VSC (**0.247**) |
| Races with ≥1 SC/VSC team pit | report | **12 / 48** |
| Major-disruption races | 13 (R21.3) | **13 / 48** (0 flag mismatches) |
| Overlap (major **and** SC/VSC pit) | report | **8** |
| SC/VSC pit but **not** major (short SC) | report | **4** (incl. 2025 Canada LEC) |

Among the 12 contaminated races, mean fraction of team pits under
SC/VSC is **0.73**. Extra team stops vs ARIS: raw mean **+0.73**; after
dropping SC/VSC pits **+0.29**. Canada 2025 extra stops **+4 → +1**.

---

## Physics offset — closed (R21.4)

`team_sim − actual` mean **+989.4 s**, std **544.0**. Per configured
lap **+17.3 s** (aimed ~G1.2 +18). Circuit-varying, not street vs
permanent. Global and street/permanent intercepts make std **worse**.
Per-circuit 2025 OOS std **313.1** vs raw 449.0 is the only helpful
direction, and leave-one-year-out on all 48 is still **422.6**. A
lap-constant cannot move bias-cancelled position-delta.

**Not shipped.** Full write-up:
[`docs/physics-calibration-research.md`](./physics-calibration-research.md).

This is a limitation on reading `expected_race_time_s` as a stopwatch.
It is not a blocker for `recommend()` remaining-race deltas (lags are
present) or for the identity-safe ranking.

---

## Wet / rain-affected races — out of scope

Named as plainly as the tyre lock and the physics-offset close: **there
is no wet-strategy logic.** `recommend()`'s candidate menu is dry
(stay / pit SOFT-MEDIUM-HARD / two-stop sketches / lift-brake). There
is no wet pit-loss, no intermediate cliff, and no “box for slicks as
the track dries” search. FastF1 C-code mapping leaves INTERMEDIATE/WET
as relative labels. Shipping the G1.5 dry slope table into a wet race
would be a new error, not a fix.

Walk-forward therefore excludes rainfall / wet-compound / red-flag
inflections as `divergence_insufficient_info` instead of scoring them
as match or mismatch.

| Slice | Aimed (the ~1/3 characterization) | Actual | Result |
|---|---|---|---|
| 2024 (Phase G / G1.5) | ~1/3 of inflections | **0.344** (21/61) | same 21 as Phase G |
| 2025 (G1.5) | report | **0.365** (27/74) | 47 scored remain |
| Combined 2024+2025 | ~1/3 | **0.356** (48/135) | 87 scored remain |

The 87-event match-rate (**0.345** T2 default / **0.322** G1.5-only vs stay-out **0.276**) is computed
on what is left after that cut. The cut reflects a missing model, not
an evaluation convenience. Spain 2024’s race was dry but FastF1’s
`rainfall` bit can fire on any session moisture; Monaco 2024 was
`rainfall=False` and still unscored (red-flag / status-5). Both sit in
the 48. See `docs/strategy-backtest.md` and
`docs/research-backlog.md` (wet-race strategy).

---

## What the Zandvoort demo actually shows

Locked since E4.1, re-confirmed on the T2 **default** path (T2-A off):

- 2025 Netherlands session 123, VER, 72 laps, pit-loss 18.5, slopes
  0.08 / 0.05 / 0.03
- Recommend: **Pit lap 33 for HARD; Pit lap 30 for HARD; Stay out on
  current tyres**
- What-if is G1.4 (**−11.92 s**), not E4.1 −13.00 s, because physics-
  delta stays. MC bands are unseeded.

Forcing `ARIS_USE_CIRCUIT_DEG=1` **moves** the labels (Pit 26/27 SOFT).
That path is not shipped.

---

## Tier 2 (2026-08-20)

Search-based increments on the G1.5 + G1.4 path. No learned policy.
Walk-forward: `scripts/backtest.py --years 2024 2025` →
`results/backtest/t2/`.

| Change | Default? | Combined match-rate | Notes |
|---|---|---|---|
| T2-B SC/VSC current-lap pit loss (0.35 / 0.55) | **yes** | part of 0.345 | Future `PIT_LAP` stops still pay green YAML loss |
| T2-D dynamic undercut bonus (cap −0.8 s) | **yes** | part of 0.345 | Stay-out remains in top-3 |
| T2-C approaching-window trigger (stable key) | **yes** | part of 0.345 | Denominator still **87** inflections |
| T2-A circuit OLS slopes 2018–2023 | **no** — `ARIS_USE_CIRCUIT_DEG` | not scored as default | Flag-on Zandvoort identity **moved** to Pit 26/27 SOFT |
| T2-E background Postgres ingest | ops only | n/a | `recommend`/`plans` no longer block; `INGESTING` badge |

**Gate vs locked G1.5 0.322 (28/87):** default T2 combined **0.345 (30/87)**.
2024 **0.375 (15/40)** (≥ 0.325). 2025 **0.319 (15/47)** (≥ 0.319).
Lights-out all-48 **−1.73** (clean **−1.49** n=35 / disrupted **−2.38** n=13).

Do **not** claim 0.340 from T2-A + T2-B as a shipped tyre model. T2-A
failed the un-flag rule: Netherlands OLS SOFT **−0.057** / MEDIUM
**0.001** / HARD **0.009** vs G1.5 0.08 / 0.05 / 0.03, and the demo
labels moved. Unset / `0` / `false` keeps G1.5. File:
`models/circuit_deg_slopes.json` (`meta.max_year` 2023).

One-step blend MAE was not re-measured here: FastF1 season schedule
APIs failed (`Failed to load any schedule data`), and T2 default does
not change the residual/blend predictor. Last calendar figure remains
E3 **0.583 s** (aimed ≤ 0.620 s).

Zandvoort identity on the default path (L25, MEDIUM, tyre_life 2,
`mc_draws=0`): **Pit lap 33 for HARD; Pit lap 30 for HARD; Stay out**.

---

## Research window — closed until after the event

No further model-accuracy research will be attempted before 21–23
August 2026. Tier 2 search-based work is in; T2-A stays flagged.
Cornering-load (R1.4) remains queued, not abandoned — see
[`docs/PHASE-R1-CORNERING-LOAD-SUMMARY.md`](./PHASE-R1-CORNERING-LOAD-SUMMARY.md)
and
[`docs/future-research-cornering-load.md`](./future-research-cornering-load.md).
G1.5 stays the tyre prior through the event.

---

## What this does not claim

- Beating MA(2) on lap time.
- That Strat B would have scored more FIA points.
- That −1.73 (or −1.49 clean) is a strategy edge independent of G1.5's
  HARD slope.
- That a physics intercept is "coming."
- That T2-A circuit OLS is a shipped tyre sensor (Zandvoort identity
  moved; the flag stays off).
- That the 0.345 match-rate is a C-code / GBT overlay. It is G1.5
  slopes plus SC pit cost, undercut bonus, and approach triggers.
- That ARIS has a wet / rain strategy. Combined **0.356** (48/135)
  inflections are excluded because that model does not exist.

Further reading: `docs/tyre-degradation-research.md`,
`docs/physics-calibration-research.md`, `docs/how-recommend-works.md`,
`docs/strategy-backtest.md`, `docs/PHASE-G5-SUMMARY.md`,
`docs/PHASE-R2-POSITION-DELTA-SUMMARY.md`, `docs/PHASE-R21-SUMMARY.md`,
`docs/PHASE-R22-SUMMARY.md`.
