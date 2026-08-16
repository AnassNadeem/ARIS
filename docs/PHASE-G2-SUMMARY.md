# Phase G.2 summary — tyre degradation at compound identity

Executed 2026-08-14. Scope: Blocks G2.1–G2.7. Fix the slope at the C-code
root cause, not a fourth correction on SOFT/MEDIUM/HARD labels. Every
numeric result states aimed vs actual. Unmapped races were left unmapped;
no C-code was invented.

---

## Verdict (read this first)

The mapping is real. The physical claim is not. Re-keying E3.2 onto true
C-codes does **not** produce monotonic C1→C5/C6 degradation in any era,
does **not** restore Zandvoort SOFT>MEDIUM>HARD, does **not** shrink
chained-rollout compounding, and **loses** the G1.5 match-rate floor.

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Web access (do not guess C-codes without it) | confirmed | confirmed | **PASS** |
| FastF1 `Compound` contains C1–C6 | absent | absent (SOFT/MEDIUM/HARD/INT/WET/UNKNOWN; 2018 SUPERSOFT/ULTRASOFT) | **PASS** (mechanism confirmed) |
| Netherlands 2021–2026 mapping | complete, sourced | 6/6 Pirelli, including 2026 C2/C3/C4 | **PASS** |
| 2024 / 2025 mapping | full calendars | 24/24 and 24/24 Pirelli | **PASS** |
| 2026 mapping | announced races only | 14 sourced; 9 not yet announced, unmapped | **PASS** (no guesses) |
| True-compound slopes monotonic C1→C5/C6 within era | **yes** | **no** in all four eras | **MISS** |
| Zandvoort event-relative SOFT>MED>HARD after re-key | **yes** | **no** in 2021, 2022, 2023, 2024, 2025, 2026 | **MISS** |
| Chained MAE +5 / +10 / +20 vs G1.1 | **improve** on 1.861 / 2.444 / 2.790 | **1.911 / 2.442 / 2.820** | **MISS** |
| 2024 match-rate | **> 0.250** (10/40 stay-out); G1.5 was 0.325 (13/40) | **0.225** (9/40) | **MISS** (below stay-out; below G1.5) |
| 2025 match-rate | **> 0.298** (14/47 stay-out); G1.5 was 0.319 (15/47) | **0.170** (8/47) | **MISS** |
| 2024+2025 match-rate | **> 0.276** (24/87 stay-out); G1.5 was 0.322 (28/87) | **0.195** (17/87) | **MISS** |
| Mean position-delta 2024 / 2025 / combined | **≤ 0** | **+2.50 / +4.17 / +3.33** | **MISS** (2024 slightly better than G1.5 +2.63; 2025 and combined worse) |
| Full pytest | green | **208 passed** | **PASS** |

The root-cause hypothesis — three prior ordering failures were an artifact
of event-relative labels hiding different C-codes — is **not supported**
by this E3.2 re-key. The labels were wrong. The fitted C-code slopes are
still not physically ordered. Shipping those slopes into `simulate()`
made strategy worse on the walk-forward.

Negative C-code slopes were **not clipped**. The brief said re-key the
fitter, do not redesign it.

---

## G2.1 — Mechanism and existing sources

**Web access: confirmed.** press.pirelli.com, FastF1 issue tracker, and
GitHub were fetched. No C-code in this file was interpolated.

### FastF1 `session.laps['Compound']`

FastF1 **3.8.3**. Cached races 2018–2025 were sampled. Unique values:

- dry/wet labels: `HARD`, `MEDIUM`, `SOFT`, `INTERMEDIATE`, `WET`
- 2018 extras: `SUPERSOFT`, `ULTRASOFT`, and null/`NAN`
- never `C1`–`C6`, never `UNKNOWN` as a C-code stand-in in the sampled cache

Timing columns present: `Compound`, `TyreLife`, `FreshTyre`. No compound
identity field. This matches FastF1 issue #332 (C-codes are not in the
timing feed).

### Existing datasets (checked before manual sourcing)

| Source | Years | Status | Used? |
|---|---|---|---|
| [VforVitorio/F1_Strat_Manager](https://github.com/VforVitorio/F1_Strat_Manager) `tire_compounds_by_race.json` | 2023–2025 | Verified vs seed: NL 2023 C1/C2/C3, NL 2024 C1/C2/C3, NL 2025 C2/C3/C4 — all match | **cross-check only** |
| [harningle/fia-doc](https://github.com/harningle/fia-doc/blob/main/tyres.json) `tyres.json` | linked from FastF1 #332 | **404** on current `main` | **not used** |

Canonical file is `data/compounds/nominations.json` (98 sourced rows).
Every row has a `source_url`. 2023 rest-of-calendar uses RacingNews365's
season table, cross-checked against the seed and VforVitorio.

---

## G2.2 — Compound-identity mapping

Eras (physical compounds are **not** comparable across cuts):

| Era | Meaning |
|---|---|
| `2019-2021` | 13-inch C1–C5 |
| `2022` | 18-inch first generation. **2022 C1 ≠ 2023 C1** (renamed C0) |
| `2023-2025` | after C0 reclassification; C6 added 2025 |
| `2026` | range recalibrated for lower-downforce cars; C1–C5 only, C6 not homologated |

### Coverage

| Slice | Aimed | Actual | Sourced vs unmapped |
|---|---|---|---|
| Netherlands / Zandvoort | all available years, 2021 and 2026 included | **2021–2026 complete** (6/6) | all Pirelli. 2020 and earlier NL unmapped (no sourced C-codes) |
| 2024 calendar (walk-forward) | 24/24 | **24/24** | all Pirelli |
| 2025 calendar (walk-forward) | 24/24 | **24/24** | all Pirelli |
| 2026 to date + announced | announced only | **14 mapped** | 11 completed races + NL + Italy + Madrid. **9 unmapped** (not announced as of the 28 July 2026 Zandvoort/Monza/Madrid release) |
| 2023 (training) | as time allows | **22/22** (Imola cancelled) | NL+Italy Pirelli; rest RacingNews365 season table |
| 2022 (training) | as time allows | **13 mapped / 9 unmapped** | Pirelli preview **text** only. Graphics-only / 404 previews not guessed |
| 2019–2021 | as time allows | **NL 2021 only** | season tables are images |
| 2018 | C-codes if they exist | **entire season unmapped** | FastF1 uses SUPERSOFT/ULTRASOFT/HYPERSOFT; no C-codes |

### Netherlands seed (priority a) — Pirelli, not re-derived

| Year | Round | H/M/S | Era | Source |
|---|---:|---|---|---|
| 2021 | 13 | C1/C2/C3 | 2019-2021 | https://press.pirelli.com/2021-dutch-grand-prix--preview/ |
| 2022 | 15 | C1/C2/C3 | 2022 | https://press.pirelli.com/2022-dutch-grand-prix--preview/ |
| 2023 | 13 | C1/C2/C3 | 2023-2025 | https://press.pirelli.com/news-and-tyre-choices-for-zandvoort-and-monza/ |
| 2024 | 15 | C1/C2/C3 | 2023-2025 | https://press.pirelli.com/all-compounds-on-track-over-next-three-races/ |
| 2025 | 15 | C2/C3/C4 | 2023-2025 | https://press.pirelli.com/changes-and-status-quo-when-it-comes-to-compound-choices-for-the-rest-of-the-season0/ |
| 2026 | 12 | C2/C3/C4 | 2026 | https://press.pirelli.com/tyre-compounds-selected-for-zandvoort-monza-and-madrid/ |

2026 Dutch GP **is announced** (28 July 2026): C2/C3/C4. Same step as 2025,
new generation.

### 2024 (24/24)

| R | Event | H/M/S | R | Event | H/M/S |
|---|---|---|---|---|---|
| 1 | Bahrain | C1/C2/C3 | 13 | Hungary | C3/C4/C5 |
| 2 | Saudi Arabia | C2/C3/C4 | 14 | Belgium | C2/C3/C4 |
| 3 | Australia | C3/C4/C5 | 15 | Netherlands | C1/C2/C3 |
| 4 | Japan | C1/C2/C3 | 16 | Italy | C3/C4/C5 |
| 5 | China | C2/C3/C4 | 17 | Azerbaijan | C3/C4/C5 |
| 6 | Miami | C2/C3/C4 | 18 | Singapore | C3/C4/C5 |
| 7 | Emilia Romagna | C3/C4/C5 | 19 | United States | C2/C3/C4 |
| 8 | Monaco | C3/C4/C5 | 20 | Mexico City | C3/C4/C5 |
| 9 | Canada | C3/C4/C5 | 21 | Sao Paulo | C3/C4/C5 |
| 10 | Spain | C1/C2/C3 | 22 | Las Vegas | C3/C4/C5 |
| 11 | Austria | C3/C4/C5 | 23 | Qatar | C1/C2/C3 |
| 12 | Britain | C1/C2/C3 | 24 | Abu Dhabi | C3/C4/C5 |

All Pirelli. URLs in `nominations.json`.

### 2025 (24/24)

| R | Event | H/M/S | R | Event | H/M/S |
|---|---|---|---|---|---|
| 1 | Australia | C3/C4/C5 | 13 | Belgium | **C1/C3/C4** |
| 2 | China | C2/C3/C4 | 14 | Hungary | C3/C4/C5 |
| 3 | Japan | C1/C2/C3 | 15 | Netherlands | C2/C3/C4 |
| 4 | Bahrain | C1/C2/C3 | 16 | Italy | C3/C4/C5 |
| 5 | Saudi Arabia | C3/C4/C5 | 17 | Azerbaijan | C4/C5/C6 |
| 6 | Miami | C3/C4/C5 | 18 | Singapore | C3/C4/C5 |
| 7 | Emilia Romagna | C4/C5/C6 | 19 | United States | **C1/C3/C4** |
| 8 | Monaco | C4/C5/C6 | 20 | Mexico City | **C2/C4/C5** |
| 9 | Spain | C1/C2/C3 | 21 | Sao Paulo | C2/C3/C4 |
| 10 | Canada | C4/C5/C6 | 22 | Las Vegas | C3/C4/C5 |
| 11 | Austria | C3/C4/C5 | 23 | Qatar | C1/C2/C3 |
| 12 | Britain | C2/C3/C4 | 24 | Abu Dhabi | C3/C4/C5 |

Non-consecutive nominations (Spa, COTA, Mexico) are sourced, not errors.
Brazil C2/C3/C4 from https://press.pirelli.com/harder-compounds-for-the-sao-paulo-sprint-weekend/.

### 2026 (14 mapped, 9 unmapped)

Mapped: Australia C3/C4/C5, China C2/C3/C4, Japan C1/C2/C3, Miami C3/C4/C5,
Canada C3/C4/C5, Monaco C3/C4/C5, Spain C2/C3/C4, Austria C3/C4/C5,
Britain C1/C2/C3, Belgium C2/C3/C4, Hungary C3/C4/C5, Netherlands C2/C3/C4,
Italy C3/C4/C5, Madrid C2/C3/C4.

**Unmapped 2026** (not announced): Azerbaijan, Bahrain (Sepang), Singapore,
United States, Mexico City, Sao Paulo, Las Vegas, Qatar, Abu Dhabi.
Original Bahrain/Saudi slots were cancelled; Bahrain later listed at Sepang.

### 2023 (22/22)

Same H/M/S as the RacingNews365 season table. NL C1/C2/C3 and Italy C3/C4/C5
also on Pirelli. Imola cancelled — not mapped.

### 2022 (13 mapped)

Bahrain C1/C2/C3, Saudi C2/C3/C4, Australia **C2/C3/C5** (non-consecutive,
Pirelli preview text), Emilia Romagna C2/C3/C4, Miami C2/C3/C4, Spain
C1/C2/C3, Monaco C3/C4/C5, Azerbaijan C3/C4/C5, Canada C3/C4/C5, Britain
C1/C2/C3, France C2/C3/C4, Netherlands C1/C2/C3, Italy C2/C3/C4.

**Unmapped 2022:** Austria, Hungary, Belgium, Singapore, Japan, United States,
Mexico City, Sao Paulo, Abu Dhabi. Preview URLs 404'd or graphics-only.

### Explicitly unmapped (do not guess)

- **2018:** entire season
- **2019:** entire season
- **2020:** entire season
- **2021:** all except Netherlands
- **2022:** nine races listed above
- **2023:** Emilia Romagna (cancelled)
- **2026:** nine not-yet-announced races listed above

---

## G2.3 — Join and refit

`join_compound_identity` keeps FastF1 `Compound` (event-relative, still
what the engineer sees) and adds `CompoundIdentity` (C-code). Wets stay
INTERMEDIATE/WET.

Fit: `scripts/fit_true_compound_slopes.py` — E3.2 method re-keyed
(fuel-corrected race DegSlope, clean-lap filter, Stint/pit-out split,
session IV pool), grouped by C-code **within era**. Not redesigned.

n stints by era (from `data/compounds/true_compound_slopes.json`):
2019-2021 **79**, 2022 **890**, 2023-2025 **4597**, 2026 **740**.
Total fitted **6306**.

### True-compound slopes (s/lap) — aimed monotonic C1 < C2 < … < C5/C6

| Era | n | Fitted | Monotonic? |
|---|---:|---|---|
| 2019-2021 | 79 | C1=**0.0976**, C2=**0.0353**, C3=**0.1029** | **NO** |
| 2022 | 890 | C1=**0.0849**, C2=**0.0381**, C3=**−0.0423**, C4=**−0.0039**, C5=**0.1368** | **NO** |
| 2023-2025 | 4597 | C1=**0.0369**, C2=**0.0359**, C3=**0.0461**, C4=**0.0283**, C5=**−0.1892**, C6=**−0.012** | **NO** |
| 2026 | 740 | C1=**0.0353**, C2=**−0.0082**, C3=**0.0195**, C4=**−0.0008**, C5=**0.0101** | **NO** |

Aimed: yes in every era. Actual: **no in every era**. The 2023-2025 pool
(the walk-forward era) has C5/C6 **negative** and C4 slower-degrading than
C1–C3. That is what Zandvoort 2025 and most 2024/2025 races now inject
into HARD/MEDIUM/SOFT.

---

## G2.4 — Per-race HARD/MEDIUM/SOFT from true-compound fits

`load_track_config(country, year=..., round_no=...)` overlays
`event_relative_slopes`. Mapped race with a fit: HARD/MEDIUM/SOFT take
that race's nominated C-codes' era slopes. Unmapped, or mapped with no
fit: `None` overlay, YAML / global 0.08 / 0.05 / 0.03 remain, logged as
`global_fallback`.

Call sites pass year: `simulate.py`, `state.py`, `eval/backtest.py`,
`plan/prewrite.py`, `models/features.py` (`build_from_fastf1`),
Strategy page, Zandvoort smoke, G1.1 diagnose.

CHECKPOINT: tests green (208) after overlay + the physics-delta unit test
updated to load the year-keyed track (it was still asserting YAML slopes
against a 2024 Bahrain overlay).

---

## G2.5 — Zandvoort event-relative ordering

Aimed: SOFT > MEDIUM > HARD in event-relative terms, for the compounds
Zandvoort actually runs.

| Year | Nomination | HARD / MEDIUM / SOFT slopes (s/lap) | SOFT>MED>HARD |
|---|---|---|---|
| 2021 | C1/C2/C3 | 0.0976 / 0.0353 / 0.1029 | **NO** |
| 2022 | C1/C2/C3 | 0.0849 / 0.0381 / −0.0423 | **NO** |
| 2023 | C1/C2/C3 | 0.0369 / 0.0359 / 0.0461 | **NO** (SOFT>HARD but MEDIUM is the slowest-degrading) |
| 2024 | C1/C2/C3 | 0.0369 / 0.0359 / 0.0461 | **NO** (same era as 2023) |
| 2025 | C2/C3/C4 | 0.0359 / 0.0461 / 0.0283 | **NO** (SOFT is the *slowest*-degrading) |
| 2026 | C2/C3/C4 | −0.0082 / 0.0195 / −0.0008 | **NO** |

Aimed yes. Actual **no every year**. Three prior attempts failed on
mislabeled data; this attempt fails on correctly labeled data with the
same fitter. The labels were not the thing that was going to make
SOFT>MEDIUM>HARD true.

---

## G2.6 — 2026 generation

Today is 2026-08-14. Zandvoort is round 12, 21–23 August 2026 — **not yet
run**. Eleven 2026 races have already happened (Australia through Hungary).

`fastf1.get_event_schedule(2026)` failed on all backends. `get_session(2026,
gp, "R")` **worked** for completed races. 2026 Netherlands has no timing.

**2026 era was fitted on real 2026 data (740 stints).** 2024/2025 C-code
slopes were **not** transferred onto 2026. The 2026 fit is itself
non-monotonic (C2 and C4 negative). Anything 2026-relevant in this phase
uses that fit, not a 2023-2025 proxy.

---

## G2.7 — Downstream re-run

### G2.7.12 — G1.1 chained rollout, true-compound slopes

Same diagnostic as G1.1 (residual-chained `predict_lap_time` on 477 green
2024 stretches, HARD 290 / MEDIUM 168 / SOFT 19), so the comparison is
slope-only. `simulate()` itself still uses G1.4 physics-delta; the walk
in G2.7.13 is that path. This block answers: does a more-correct slope
constant shrink compounding on the original chained path?

Aimed: chained MAE at +5/+10/+20 **improves** vs G1.1 **1.861 / 2.444 / 2.790**.

| Horizon | n | G1.1 chained MAE (bias) | G2 chained MAE (bias) | Teacher-forced G2 MAE |
|---|---:|---|---|---|
| +1 | 477 | **0.861** (+0.235) | **0.859** (+0.231) | 0.859 |
| +5 | 477 | **1.861** (+0.389) | **1.911** (+0.409) | 0.771 |
| +10 | 477 | **2.444** (+0.566) | **2.442** (+0.656) | 0.783 |
| +20 | 354 | **2.790** (+0.572) | **2.820** (+0.664) | 0.788 |

+1: aimed improve, actual 0.859 vs 0.861 — flat.
+5: aimed improve, actual **worse** (1.911 vs 1.861).
+10: aimed improve, actual 2.442 vs 2.444 — flat; bias **worse** (+0.656 vs +0.566).
+20: aimed improve, actual **worse** (2.820 vs 2.790).

Compounding is still ~3.3× from +1 to +20. The two issues were **not**
interacting the way the hypothesis wanted: correcting the slope constant
does not fix chained residual error, and the new constant is not a
physical C1→C5 order anyway.

By compound (G2 chained MAE / bias):

| Compound | n | +1 | +5 (bias) | +10 (bias) | +20 (bias) |
|---|---:|---|---|---|---|
| HARD | 290 | 0.845 | 1.906 (+0.649) | 2.482 (+0.983) | 2.699 (+0.644) n=230 |
| MEDIUM | 168 | 0.831 | 1.801 (+0.294) | 2.226 (+0.483) | 2.825 (+1.128) n=115 |
| SOFT | 19 | 1.324 | 2.968 (−2.234) | 3.732 (−2.797) | 5.823 (−4.742) n=9 |

SOFT chained error **grew** vs G1.1 (aimed shrink; actual +20 5.823 vs
4.183). Direction still “SOFT looks faster than it was.”

Named examples, chained (teacher-forced) at +1 / +5 / +10 / +20:

| Stint | G1.1 | G2 |
|---|---|---|
| Netherlands HUL HARD L19–71 | +1.08 / +0.88 / +0.75 / +0.37 | +1.11 / +1.10 / +0.99 / +0.80 |
| Emilia Romagna BOT HARD L13–62 | +0.44 / −0.51 / −0.58 / −1.04 | +0.50 / −0.38 / −0.37 / −0.67 |
| Singapore PIA MEDIUM L4–37 | +1.31 / **+7.12** / **+9.39** / **+9.33** | +1.24 / **+6.94** / **+9.13** / **+8.86** |
| Belgium TSU SOFT L20–44 | +0.62 / +0.48 / +3.78 / +4.33 | +0.47 / −0.92 / +0.81 / +2.22 |

Singapore PIA is still the picture: teacher-forced inside ~0.4 s; chained
already ~7 s at five laps. Slope overlay did not remove that.

Artefact: `results/g2/g11_rollout.json`.

### G2.7.13 — Walk-forward 2024 + 2025 (same method as G1.5)

`mc_draws=0`, classified P5, same match / stay-out / hindsight rules.
2024 elapsed **910 s**. 2025 elapsed **2101 s**. Not shortcut.

#### 2024 (same 40 scored events)

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Match-rate | **> 0.250** (10/40 stay-out); G1.5 **0.325** (13/40) | **0.225** (9/40) | **MISS** |
| Position-delta | **≤ 0**; G1.5 **+2.63** | **+2.50** | **MISS** (0.13 better than G1.5, still positive) |
| ARIS-hindsight / team-hindsight / insufficient | — | 28 / 3 / 21 | more ARIS-hindsight than G1.5's 22 / 5 / 21 |
| Rolling match at R24 | — | **0.100** (G1.5 was **0.300**) | worse at the end |
| Rolling pos-delta at R24 | — | **+4.4** (G1.5 **+4.4**) | unchanged |

#### 2025 (full season, never in residual training)

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Match-rate | **> 0.298** (14/47 stay-out); G1.5 **0.319** (15/47) | **0.170** (8/47) | **MISS** |
| Position-delta | **≤ 0**; G1.5 **+3.29** | **+4.17** | **MISS** (worse than G1.5) |
| ARIS-hindsight / team-hindsight / insufficient | — | 35 / 4 / 27 | heavier ARIS-hindsight than G1.5's 30 / 2 / 27 |
| Rolling match at R24 | — | **0.133** (G1.5 **0.200**) | worse |
| Rolling pos-delta at R24 | — | **+5.8** (G1.5 **+3.4**) | worse |

#### Combined 2024+2025 (48 races, 87 scored inflections)

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Match-rate | **> 0.276** (24/87 stay-out); G1.5 **0.322** (28/87) | **0.195** (17/87) | **MISS** |
| Position-delta | **≤ 0**; G1.5 **+2.96** | **+3.33** | **MISS** |

Copy-last-year combined 8/36 = 0.222, still **not trusted** (same FastF1
historical-schedule caveat as Phase G). Primary baseline remains
always-stay-out. G2 is **below** stay-out on every slice.

This is the “two wrong calculations” interaction, measured: G1.4
physics-delta + G2 true-compound slopes. Physics-delta with YAML
0.08/0.05/0.03 *beat* stay-out (G1.5). Physics-delta with the C-code
overlay *loses* to stay-out. The overlay is the regression.

Artefacts: `results/g2/backtest/2024_summary.json`, `2025_summary.json`,
`2024_2025_combined_summary.json`.

### G2.7.14 — Zandvoort smoke vs locked E4.1 / F.8 / F1.1 / G.8

`scripts/_e1_smoke_strategy_zandvoort.py` still **SMOKE OK**. Identity vs
the locked row, then vs G1.4:

| Check | Aimed / locked (E4.1) | G1.4 actual | G2 actual | vs lock | vs G1.4 |
|---|---|---|---|---|---|
| Track laps / pit | 72 / 18.5 | same | 72 / 18.5 | **PASS** | same |
| Track slopes H/M/S | **0.08 / 0.05 / 0.03** | same | **0.0359 / 0.0461 / 0.0283** | **MOVED** | **MOVED** |
| Prewrite windows | A:[18] B:[29] C:[18,40] | same | same | **PASS** | same |
| Weekend form | n=20 | n=20 | n=20 | **PASS** | same |
| Clock | 287 ticks → lap 72 | 287 → 72 | 287 → 72 | **PASS** | same |
| L25 state | MEDIUM tyre_life=2 | same | MEDIUM tyre_life=2 | **PASS** | same |
| Ask/recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | same | **Plan: L31→SOFT, L46→HARD; Pit lap 33 HARD; Stay out** | **MOVED** | **MOVED** |
| What-if delta | **−13.00 s** | **−11.92 s** | **−2.34 s** | **MISS** | moved again |
| What-if MC P10/P90 | **−32.62 / −13.35** | **−147.55 / +29.33** | **−137.96 / +38.92** | **MISS** | still unusable |

Slopes moved because 2025 Netherlands is mapped C2/C3/C4 in era
2023-2025: HARD=C2=0.0359, MEDIUM=C3=0.0461, SOFT=C4=0.0283. Prewrite
windows only use total laps and pit loss, so they did not move. Recommend
identity moved because SOFT now degrades *slower* than HARD, so a
SOFT-then-HARD two-stop outranks pit-now HARD. What-if delta shrank
because HARD is no longer a 0.03 vs 0.08 story.

Log: `results/g2/zandvoort_smoke.log`.

---

## Tests

Full pytest after mapping/wiring, after overlay, after the year-keyed
physics-delta test fix, after diagnose `--out-dir`, and after backtest
`--out-dir`: **208 passed**, 0 failed. Final log: `results/g2/pytest.log`.

One test failed in the middle of the overlay landing
(`test_later_laps_follow_physics_delta_not_chained_residual`): it loaded
`load_track_config(state.country)` without year, so expected YAML 0.08/0.05/0.03
while `simulate()` used the 2024 Bahrain C1/C2/C3 overlay. The test now
passes year/round. That is the test matching production, not a fitter change.

---

## What this does and does not claim

Does: prove FastF1 has no C-codes; ship a sourced (year, round) → C-code
map with explicit holes; join identity next to the relative label; refit
E3.2 by C-code within era, including a real 2026 pool; wire mapped races
off global SOFT/MEDIUM/HARD defaults.

Does not: produce monotonic C1→C5/C6 degradation; restore Zandvoort
SOFT>MEDIUM>HARD; improve chained compounding; hold the G1.5 match-rate
floor. The honest global-fallback state was beating stay-out. This overlay
is not yet a replacement for it.

---

STOP — waiting for review.
