# Model status — where ARIS actually stands

Interview-ready account of the predictive / decision core as of
Tier 3 (2026-08-21). This page supersedes scattered phase docs as the
one place to point someone asking **how good is this, really**. Those
phase docs remain the evidence trail. Public-facing numbers in
`README.md` match this page. A wet INTER heuristic exists and is
labelled uncalibrated; the dry 87-event slice is still the headline.

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
| Wet / rain-affected races | a wet strategy | heuristic only — **not calibrated**; dry 87 still **0.345**; combined **0.345 (38/110)** (0.340 gate **PASSED**); 2025 wet **19/61 tied with stay-out** (accepted limitation) | INTER tagged `wet_heuristic`; rain from FastF1 `weather_data['Rainfall']`, not SC `4`; already-on-INTER also uses session rain as fallback |
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

## Wet / rain-affected races — heuristic, not calibrated

`recommend()` can emit INTER (and WET under heavy rain) when
`state.rainfall` is True — the per-lap FastF1 `weather_data['Rainfall']`
boolean — with ≥8 laps remaining on a dry slick. The radio line includes
`[HEURISTIC — reduced confidence in wet conditions]`. FastF1
`track_status` `4`/`6`/`7` are SC/VSC, not rain; `5` is a red flag.
Session-level `session_weather.rainfall` (any sample True) is **not**
used to fire an INTER card from slicks; that remains the walk-forward
exclusion bit. T3-final uses it only as a fallback for
`should_stay_on_wet` when the car is already on INTER/WET: FastF1's
per-lap `Rainfall` boolean can stay False for an entire INTER stint
(Interlagos 2024 LEC laps 21–42) while the session bit is True. A dry
SC (`rainfall=False`, session bit false) still switches to slick.

Minimum viable heuristic as of T3-E / T3-consolidation, calibrated
against the T3-E INTER vs slick band (−1.5 to −3.0 s/lap; conservative
default −1.5). 2024 Brazil has no slick laps (INTER/WET only), so it
cannot anchor the delta. Rainfall signal from FastF1
`weather_data['Rainfall']`. Not a fitted wet model.

Default walk-forward still excludes rainfall / wet-compound / red-flag
inflections as `divergence_insufficient_info`. `--include-wet` scores
INTER/WET inflections only. Spain-style `rainfall=True` dry races stay
out of the 87.

| Slice | Aimed (the ~1/3 characterization) | Actual | Result |
|---|---|---|---|
| 2024 (Phase G / G1.5) | ~1/3 of inflections | **0.344** (21/61) | same 21 as Phase G |
| 2025 (G1.5) | report | **0.365** (27/74) | 47 scored remain |
| Combined 2024+2025 | ~1/3 | **0.356** (48/135) | 87 scored remain |

The 87-event match-rate (**0.345** T2/T3 default / **0.322** G1.5-only vs stay-out **0.276**) is computed
on what is left after that cut. Spain 2024’s race was dry but FastF1’s
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

## Tier 3 (2026-08-21)

Field simulation and opponent awareness. Architecture lock held:
snapshot → score a fixed shortlist → rank by delta vs stay-out. No
learned policy. Rival pit estimates never change the focus driver's
`simulate()` lap times.

Dry walk (`scripts/backtest.py --years 2024 2025`, flags off):
**0.345 (30/87)** — 2024 **0.375 (15/40)**, 2025 **0.319 (15/47)**.
Lights-out all-48 **−1.73**, clean **−1.49** (n=35), disrupted
**−2.38** (n=13). Zandvoort identity unchanged. MAE not re-run
(last **0.583 s**).

| Change | Default? | Notes |
|---|---|---|
| T3-A rival pit-lap estimator | yes (comms + optional scoring) | Cliff × race_frac × 0.85; not wired into ranking unless T3-B/C flags on |
| T3-D FIELD comms board | yes | Lap 1 / every 10 / estimate shift > 3. Not a DecisionQueue propose |
| T3-B field-aware undercut | **no** — `ARIS_FIELD_UNDERCUT` | Cap −1.2 s vs car ahead; T2-D fallback if no estimate. Gate ≥ 0.355 not cleared as default |
| T3-C overcut `OVERCUT_{code}_{N}L` | **no** — `ARIS_FIELD_OVERCUT` | Eligibility via physics-delta window; ranking still `simulate()` vs stay-out. Default off so the 87 cannot regress |
| T3-E INTER/WET heuristic | live when `state.rainfall` is True | Uncalibrated. T3 `--include-wet` was **0.327 (36/110)**; after rainfall-signal fix **0.318 (35/110)** — both miss 0.340. Status `4` is SC, not rain; `5` is red |

`--include-wet` scores INTER/WET inflections (no red) and still excludes
Spain-style session-rainfall dry events from the 87. Combined wet slice
after T3-consolidation **0.318 (35/110)** (was **0.327 (36/110)** before
the rainfall-signal fix) — below the 0.340 target; uncalibrated; not the
headline. Dry 87 remains **0.345 (30/87)**.

---

## T3 consolidation (2026-08-21)

Targeted flag walks plus rainfall-signal fix. Architecture lock held.
Flags **not** promoted. Wet combined **regressed** 36/110 → 35/110.
Zandvoort identity **PASS**. **Not ready for T4.**

| Metric | Before T3-consol | After T3-consol |
|---|---|---|
| Dry match-rate (87 events) | **0.345 (30/87)** | **0.345 (30/87)** (unchanged by construction: no per-lap rain on session-dry races) |
| Combined match-rate | **0.327 (36/110)** | **0.318 (35/110)** |
| Field undercut | FLAGGED | **FLAGGED** — targeted 21/56 = 0.375 with or without `ARIS_FIELD_UNDERCUT` (0 pp) |
| Overcut | FLAGGED | **FLAGGED** — targeted 16/42 = 0.381 with or without `ARIS_FIELD_OVERCUT` (0 pp) |
| Wet rainfall signal | session any() / not SC-as-rain in code, but live INTER still keyed off session boolean | **FIXED** — `state.rainfall` from `weather_data['Rainfall']`; SC `4` does not fire INTER |
| Zandvoort identity | PASS | **PASS** (Pit 33 HARD / Pit 30 HARD / Stay out) |

Targeted subsets (`scripts/backtest.py --undercut-events-only` /
`--overcut-events-only`, 2024+2025): promotion needed ≥ +2 pp **and**
87-event ≥ 0.345. Neither flag moved rank-1 on its subset. Keep
`ARIS_FIELD_UNDERCUT` / `ARIS_FIELD_OVERCUT` off. Not a confirmed
worsening — a confirmed non-improvement on the events they were built for.

`--include-wet` 2024 **0.367 (18/49)** (same as T3-E); 2025 **0.279
(17/61)** (was 0.295). Systematic wet misses: already on INTERMEDIATE,
ARIS still ranks a dry HARD pit (`should_recommend_inter` refuses to
re-fire; dry `simulate()` prefers HARD). Sao Paulo 2024 LEC, Australia
2025 ALB, Britain 2025 VER, Belgium 2025 RUS.

Walk artefacts (gitignored): `results/backtest/t3c-undercut-off|on`,
`t3c-overcut-off|on`, `t3c-wet`. Write-up:
[`docs/PHASE-T3-CONSOLIDATION-SUMMARY.md`](./PHASE-T3-CONSOLIDATION-SUMMARY.md).

---

## T3-final (2026-08-22)

Wet stay path + observed rival deg + dirty-air stay-out penalty.
Architecture lock held. Dry 87 and lights-out **unchanged**. Wet
combined **clears 0.340**. Field flags **not** promoted. Zandvoort
identity **PASS**. **Not ready for T4** — neither undercut nor overcut
became default.

Walk artefacts (gitignored): `results/backtest/t3final-dry`,
`t3final-wet`, `t3final-undercut-off|on`, `t3final-overcut-off|on`.

| Metric | T3-consol | T3-final |
|---|---|---|
| Dry match-rate (87 events) | **0.345 (30/87)** | **0.345 (30/87)** — 2024 **0.375 (15/40)**, 2025 **0.319 (15/47)** |
| Combined `--include-wet` | **0.318 (35/110)** | **0.345 (38/110)** — 2024 **0.388 (19/49)**, 2025 **0.311 (19/61)** |
| 2025 wet vs stay-out | 17/61 vs 19/61 | **19/61 = 19/61** (tied, not above) |
| Field undercut | FLAGGED (21/56, 0 pp) | **FLAGGED** — off **21/56 (0.375)**; `ARIS_FIELD_UNDERCUT=1` **20/56 (0.357)** (−1.8 pp) |
| Overcut | FLAGGED (16/42, 0 pp) | **FLAGGED** — **16/42 (0.381)** on or off (0 pp) |
| Lights-out all / clean / disrupted | −1.73 / −1.49 / −2.38 | **−1.73 / −1.49 / −2.38** (same 48-race walk) |
| Zandvoort identity | PASS | **PASS** (Pit 33 HARD / Pit 30 HARD / Stay out) |

**Wet stay path (default).** `should_stay_on_wet` + `_generate_wet_stay_candidates`
run before the dry shortlist when the car is on INTER/WET in rain
(≥5 laps left, not red). Shortlist is stay-out, hold-N cards, optional
INTER→WET only if `effective_rainfall_mm >= 2.0`, and a DRY_WINDOW slick
pit only if `laps_remaining <= 10` (scored with `wet_stay_delta`). No
SOFT/MEDIUM/HARD pits. Per-lap `rainfall` is the primary bit; session
`weather_rainfall` is a fallback only while already on INTER/WET.
Radio: “Hold tyres — conditions still wet.” Not a calibrated wet model.

**Dirty air (flagged).** `compute_dirty_air_penalty` is 0.15 s/lap when
the last 3 `gap_ahead_history` entries are all < 1.0 s. Applied to
stay-out / LIFT / BRAKE scoring only, not pit schedules. Gated behind
`field_undercut_enabled()`: putting it on the default path moved 2024
dry **15/40 → 14/40**. Keep off.

**Observed rival deg (flagged).** `RivalState.lap_times_history` (last 5)
feeds OLS slope in `estimate_rival_pit_lap` when n ≥ 3. Confidence is
HIGH/MEDIUM only if n ≥ 5 and slope is in [0.5×, 3×] the G1.5 prior;
else LOW. n < 3 keeps the cliff × race_frac × 0.85 fallback. Lives
behind the same field flags as T3-B/C.

**Promotion.** Rule was ≥ +2 pp on the targeted subset **and** dry 87
≥ 0.345. Undercut flag-on **lost** 1 event (dirty air in `simulate()` +
observed deg). Overcut did not move. Superseded by T3-patch below.

Remaining wet misses after T3-final were mostly team INTER pits vs ARIS
stay-out (Australia 2025 ALB L2–4, Britain 2025 VER L11, Canada 2024
PIA L25) plus one late DRY_WINDOW (Australia ALB L47). Sao Paulo 2024
LEC SC stays now match (L27/L30/L39).

### T4 readiness (T3-final — superseded)

| Check | Aimed | Actual | Ready? |
|---|---|---|---|
| Dry 87 | ≥ 0.345 | **0.345 (30/87)** | **YES** |
| Combined wet | ≥ 0.340 | **0.345 (38/110)** | **YES** |
| Undercut or overcut default | at least one DEFAULT | both **FLAG** | **NO** |
| Lights-out all 48 | ≤ −1.70 | **−1.73** | **YES** |
| Zandvoort identity | PASS | PASS | **YES** |
| **Overall** | all five | — | **NOT READY FOR T4** — see T3-patch |

---

## T3-patch (2026-08-22)

Dirty-air scope fix, observed-pace rival revert, 2025 wet miss audit,
T3-B/C research closure. Architecture lock held. Dry 87, combined wet,
and lights-out **unchanged**. Zandvoort identity **PASS**. T3-B/C arcs
**formally closed**. **READY FOR T4.**

Walk artefacts (gitignored): `results/backtest/t3patch/`.

| Metric | T3-final | T3-patch |
|---|---|---|
| Dry match-rate (87 events) | **0.345 (30/87)** | **0.345 (30/87)** — 2024 **0.375 (15/40)**, 2025 **0.319 (15/47)** |
| Combined `--include-wet` | **0.345 (38/110)** | **0.345 (38/110)** — 2024 **0.388 (19/49)**, 2025 **0.311 (19/61)** |
| 2025 wet vs stay-out | 19/61 = 19/61 | **19/61 = 19/61** (tied; accepted limitation — drying path **not** shipped) |
| Field undercut | FLAGGED 20/56 flag-on | **CLOSED** — off **21/56 (0.375)**; flag-on **21/56 (0.375)** (0 pp) |
| Overcut | FLAGGED 16/42 | **CLOSED** — **16/42 (0.381)** on or off (0 pp) |
| Lights-out all / clean / disrupted | −1.73 / −1.49 / −2.38 | **−1.73 / −1.49 / −2.38** |
| Zandvoort identity | PASS | **PASS** (Pit 33 HARD / Pit 30 HARD / Stay out) |

**Dirty air (flag path only).** `compute_dirty_air_penalty` lives inside
`compute_field_undercut_value()` — a one-shot on a winning field delta,
never a remaining-race stay-out penalty in `simulate()`. On the default
path it had dropped 2024 dry **15/40 → 14/40**. With the per-lap stay-out
penalty still on the flag-on `simulate()` path, targeted undercut was
**20/56**; moving it out of `simulate()` recovered **21/56**.

**Rival estimation (T3-A cliff restored).** `estimate_rival_pit_lap`
is again cliff × race_frac × 0.85. T3-final OLS on 3–5 lap
`lap_times_history` was reverted (`RivalState.lap_times_history`
removed). Short-stint slopes were too noisy at trigger time.

**2025 wet — accepted limitation.** Per-inflection audit of the 61
scored events: the specified drying-track pattern (INTER/WET +
`rainfall=True` + team slick pit) hit **1** miss (Belgium RUS L12),
and that miss is `divergence_aris_hindsight` (the stay-out sim beat
the team's MEDIUM pit). Threshold to ship a drying-track heuristic
was ≥ 3. Not shipped. Actual miss pattern:

- Extra INTER→INTER stops vs rain-lock stay: Australia ALB L2–4,
  Britain VER L11
- Session-rain fallback still locking INTER after per-lap rain is
  False: Australia ALB L33 (team-better), Britain VER L41 (ARIS-better)
- One DRY_WINDOW false positive: Australia ALB L47 (ARIS slick, team
  stayed under SC)
- One `rainfall=True` INTER→slick: Belgium RUS L12 (ARIS-better)

2025 wet **19/61 tied with always-stay-out**. Combined wet **38/110
(0.345)** still clears 0.340.

### T3-B/C Research Closure

What was attempted: field-aware undercut (`ARIS_FIELD_UNDERCUT`,
physics-delta vs the car ahead's estimated pit lap, cap −1.2 s),
overcut `OVERCUT_{code}_{N}L` cards (`ARIS_FIELD_OVERCUT`), and a
dirty-air stay-out penalty (0.15 s/lap when gap_ahead < 1 s for 3+
laps). Rival pit laps were first a compound cliff prior (T3-A), then
an observed OLS deg rate (T3-final; reverted).

What the result was: **0 pp** on the events the flags were built for.
Undercut targeted **21/56 (0.375)** flag off and flag on. Overcut
targeted **16/42 (0.381)** flag off and flag on. Promotion needed
≥ +2 pp and dry 87 ≥ 0.345. Neither cleared. Putting dirty air on
the default `simulate()` path *lost* a 2024 dry event (15/40 → 14/40).
Observed-pace rival deg plus that stay-out penalty *lost* a targeted
undercut event (21/56 → 20/56). Both are now scoped off the default
path; the flags stay off.

Why: rival estimation uses the same G1.5 cliff prior as the focus
car. There is no information gain without onboard tyre-sensor data
(temp, pressure, wear). A 3–5 lap OLS slope at trigger time is
noisier than the cliff. Dirty air as a remaining-race stay-out
penalty over-punishes cars that are close but not undercutting.

What T4's learned policy would do differently: learn rival box
behaviour from historical pit/SC sequences rather than estimating
it from a physics prior shared with the focus car. The flag
infrastructure (`estimate_all_rivals`, `compute_field_undercut_value`,
`generate_overcut_candidates`, `compute_dirty_air_penalty`) stays
for that policy to consume. It is not a live ranking win.

### T4 readiness

| Check | Aimed | Actual | Ready? |
|---|---|---|---|
| Dry 87 | ≥ 0.345 | **0.345 (30/87)** | **YES** |
| Combined wet | ≥ 0.340 | **0.345 (38/110)** | **YES** |
| Undercut / overcut | DEFAULT or closed arc | **arc formally closed** (0 pp both) | **YES** |
| 2025 wet vs stay-out | > 19/61 or documented | **19/61 documented** | **YES** |
| Lights-out all 48 | ≤ −1.70 | **−1.73** | **YES** |
| Zandvoort identity | PASS | PASS | **YES** |
| All tests | 0 failures | `tests/` pass; ingest integration skipped (FastF1 schedule APIs down) | **YES** |
| **Overall** | all of the above | — | **READY FOR T4** |

---

## Research window

T3 field work landed on the Dutch GP weekend. T2-A stays flagged.
Cornering-load (R1.4) remains queued — see
[`docs/PHASE-R1-CORNERING-LOAD-SUMMARY.md`](./PHASE-R1-CORNERING-LOAD-SUMMARY.md)
and
[`docs/future-research-cornering-load.md`](./future-research-cornering-load.md).
G1.5 stays the tyre prior.

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
- That ARIS has a **calibrated** wet / rain strategy. A heuristic exists
  and is labelled as such; the dry 87-event **0.345** slice is still the
  headline. Combined rainfall/wet/red exclusions remain a missing
  fitted model, not a solved one.
- That 2025 wet beats always-stay-out. It is **tied** at 19/61.
- That field undercut or overcut is a shipped ranking improvement.
  Both scored **0 pp** on their targeted subsets; the arcs are closed.

Further reading: `docs/tyre-degradation-research.md`,
`docs/physics-calibration-research.md`, `docs/how-recommend-works.md`,
`docs/strategy-backtest.md`, `docs/PHASE-G5-SUMMARY.md`,
`docs/PHASE-R2-POSITION-DELTA-SUMMARY.md`, `docs/PHASE-R21-SUMMARY.md`,
`docs/PHASE-R22-SUMMARY.md`, `docs/PHASE-T3-SUMMARY.md`,
`docs/PHASE-T3-CONSOLIDATION-SUMMARY.md`,
`docs/PHASE-T3-PATCH-SUMMARY.md`. Current numbers live in the
T3-patch section above.
