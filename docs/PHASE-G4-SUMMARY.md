# Phase G.4 summary — pooled context-aware tyre degradation

Executed 2026-08-14. Scope: Blocks G4.1–G4.5. Every numeric result states
aimed vs actual. Same discipline as G3: validate offline behind an opt-in
flag. Do **not** switch the shipped default.

The pooled overlay is **not** a default-candidate. At typical race context
the GBT restores C1 < C2 < … < C6 order (the G4.3 headline), but the
finite-difference slopes it emits are too steep, not robust in every
context, and they lose the walk-forward to both stay-out and G1.5.

---

## Verdict (read this first)

Shipped path is still G1.5 globals (**SOFT 0.08 / MEDIUM 0.05 / HARD 0.03**)
plus G1.4 physics-delta. `ARIS_TRUE_COMPOUND_SLOPES=pooled` overlays
event-level GBT slopes when set; unset / `off` / unknown stays G1.5.
Netherlands 2025 without the env is still 0.08 / 0.05 / 0.03.

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Default path unchanged (G1.5 + G1.4, no C-code overlay) | yes | yes | **PASS** |
| Covariate coverage measured, not assumed 100% | report real join rates | weather **1.000**, gap **0.983**, n_corners **0.950**, fuel **1.000**, tyre_life **0.994**, stint **1.000**, C-code **0.329** | **PASS** (see G4.1) |
| One pooled GBT, LORO knobs on pre-2024 only | yes | depth=4, η=0.05, rounds≤120; full LORO CV MAE **4.233 ± 2.400 s** on 36 pre-2024 events | **PASS** |
| Fixed-context C1 < C2 < … < C6 (global median) | the test | **yes**: 0.1286 < 0.1538 < 0.1658 < 0.1707 < 0.2867 < 0.3028 | **holds at median context** |
| Order robust in every probe context | report plainly | **no**: free-air C5>C6; cool-track C3>C4 | not universal |
| Chained MAE +5/+10/+20 vs G1.1 **1.861 / 2.444 / 2.790** | improve | **1.976 / 2.790 / 4.079** | **MISS** (all three worse) |
| 2024 match-rate vs stay-out **0.250** and G1.5 **0.325** | beat **both** | **0.300** (12/40) | beats stay-out; **below G1.5** |
| 2025 match-rate vs stay-out **0.298** and G1.5 **0.319** | beat **both** | **0.234** (11/47) | **loses to both** |
| Combined match-rate vs stay-out **0.276** and G1.5 **0.322** | beat **both** | **0.264** (23/87) | **loses to both** |
| Default-candidate flag | only if beat both | **not a candidate** | same rule as G3.5.11 |
| `docs/research-backlog.md` written | yes | four items, one paragraph each | **PASS** |
| Full pytest | green | **230 passed**, 0 failed | **PASS** |

---

## G4.1 — covariate availability (no fabrication)

Corpus: `REFERENCE_RACES` (2018–2023) + `HELD_OUT_RACES` (2024). Aimed:
report real completeness. Actual: **149** events attempted, **148**
loaded, **1** failed (2018 Italian GP `DataNotLoadedError` on annotate).
**161,793** laps (train 135,189 / held-out 26,604).

Nearest-timestamp join to FastF1 `session.weather_data` (not session-level
Postgres medians). Gap-to-nearest reused from G3.3 (`gaps_at_completed_laps`
in `src/aris/physics/traffic.py`). `n_corners` from YAML only — Bahrain's
15 is used only for Bahrain's `physics_profile`, never as a silent fallback.

| Covariate | Aimed | Actual (all 161,793 laps) |
|---|---|---|
| air / track / humidity (nearest timestamp) | real coverage | **1.000** present; median \|Δt\| **14.98 s**; within 60 s **0.999** |
| gap-to-nearest (G3.3 construction) | reuse, don't rebuild | **0.983** (158,969 / 161,793) |
| n_corners from YAML | no Bahrain fallback for other tracks | **0.950** (153,647 / 161,793) |
| fuel (`estimate_fuel_kg`) | existing | **1.000** |
| tyre_life | existing | **0.994** (160,866 / 161,793) |
| stint_position (`StintId`) | existing | **1.000** |
| C-code identity (mapped nominations only) | mapped only | **0.329** overall; **0.917** on 2024 held-out; **1.000** on 53,259 mapped C-code laps |

n_corners holes as measured: 2018–2023 **Spanish Grand Prix** (`"spain"`
was not a substring of `"spanish"`) and **2020 Tuscan** (`mugello.yaml`
has `corners: []`). Alias `spanish` was added to `data/tracks/spain.yaml`
after this coverage run; the JSON was **not** re-run. Tuscany empty-corners
is still a genuine `None`. Artefact: `results/g4/covariate_coverage.json`.

---

## G4.2 — pooled model

E3.2 prep reused exactly: `detect_stints`, `filter_clean_laps`, drop first
lap of stint, `detrend_fuel_pace` on race only. Target = fuel-corrected
`LapTimeS` minus the median of the two lowest-`TyreLife` clean laps in that
stint. Fitting approach is the only change: one XGBoost (same
`DEFAULT_XGB_PARAMS` toolkit as the residual model) across mapped C-codes.

Categorical identity is **one-hot** (`compound_C1`…`C6`, `era_*`). Native
XGBoost categorical `DMatrix` on this dataframe raised
`ValueError: could not convert string to float: 'C3'` (XGBoost 3.2 fell
through to numpy). One-hot is the same booster, a numeric matrix.

Training frame after recovering 2022/2023 from cache (first collect had
only Netherlands for those years because of livetiming rate limits):

| | Aimed | Actual |
|---|---|---|
| Mapped laps | G2 nomination corpus | **118,034** laps, **94** events |
| Pre-2024 LORO pool | year < 2024, not 2024 held-out | **43,654** laps, **36** events (2021 NL + 13×2022 + 22×2023) |
| By C-code | all six | C1 9517, C2 22975, C3 46115, C4 30450, C5 8517, C6 **460** |
| Fit-frame weather / gap / n_corners | real | **1.000** / **0.9997** / **1.000** |

Hyperparameters: 4-config grid, strided LORO then full LORO on the top 2,
**never** 2024. Selected: **max_depth=4, eta=0.05, num_boost_round=120**.
Aimed: pick by LORO-CV MAE. Actual full-LORO CV MAE **4.233 ± 2.400 s**
(36 folds). Shallower/faster configs were close (depth-3 η=0.1 was 4.269).

Slopes for the overlay are finite differences **tyre_life 2 → 12** at
fixed context, mapped back to SOFT/MEDIUM/HARD via the nomination.
Event table first, era table fallback. Opt-in only:
`ARIS_TRUE_COMPOUND_SLOPES=pooled` (aliases `g4` / `context` / `gbt`).

Shipped file: `data/compounds/true_compound_slopes_pooled.json` (94 event
rows). Booster: `models/pooled_deg_xgb.json` (gitignored) and
`results/g4/pooled_deg_xgb.json`. Fit report: `results/g4/pooled_deg_report.json`.

CHECKPOINT: pytest **230 passed** after the one-hot encoding change.

---

## G4.3 — does context-conditioning restore order?

**Headline: at global median context, yes.** Holding air 24.8 °C, track
36.1 °C, humidity 51%, gap 1.94 s, 16 corners, stint position 2, and
varying only C-code:

C1 **0.1286** < C2 **0.1538** < C3 **0.1658** < C4 **0.1707** < C5 **0.2867** < C6 **0.3028** s/lap.

That is the same string in every era. Era one-hots move intercept, not
this 2→12 slope, at this context. Zandvoort relative H/M/S is
SOFT > MED > HARD every year 2021–2026 under that mapping.

G2's inversion is therefore partly confounding, not “tyres have no
order.” Two caveats sit next to that sentence:

1. **C1–C4 are a tight cluster** (0.129–0.171); C5/C6 jump. C6 has 460
   laps. This is order, not a wide physical spacing.
2. **Order is not universal.** Same model, other contexts:

| Context | Aimed (monotonic) | Actual |
|---|---|---|
| Global median / traffic (gap 0.8 s) / Monza corners / Zandvoort corners | C1<…<C6 | **yes** (same numbers as median) |
| Free air (gap 5.0 s) | C1<…<C6 | **no**: C5 **0.3766** not < C6 **0.3648** |
| Hot track (50 / 35 °C) | C1<…<C6 | **yes**, but all slopes drop (C1 **0.0516**) |
| Cool track (20 / 15 °C) | C1<…<C6 | **no**: C3 **0.0502** not < C4 **0.0379** |

Hotter → *smaller* predicted slope is not a clean “temperature cooks
the tyre” effect. Some event contexts go negative (2022 Spain
HARD/MED/SOFT **−0.367 / −0.295 / −0.283** at 49 °C track, 7% humidity,
gap 3.26 s). The GBT finite difference is not a guaranteed positive
physical slope.

### Feature importances (gain, normalised)

Aimed: does gap-to-nearest matter as much as G3.3 suggested? Does
temperature?

| Feature | Gain share |
|---|---:|
| compound_id (sum of C1–C6 dummies) | **0.184** |
| tyre_life | **0.168** |
| era (sum of era dummies) | **0.108** |
| stint_position | **0.107** |
| n_corners | **0.105** |
| humidity_pct | **0.096** |
| gap_to_nearest_s | **0.089** |
| air_temp_c | **0.079** |
| track_temp_c | **0.064** |

Gap is real (**8.9%**) but not dominant. G3.3's finding was *selection*:
HARD/C1 stints run in freer air. Putting gap in the model as a covariate
does not make it the top splitter of a fuel-corrected early-stint residual.
Temperature together is ~14% (air+track), behind tyre_life, compound, era,
stint position, and corner count.

---

## G4.4 — offline validation (opt-in only)

Same 477 green 2024 stretches as G1.1. Overlay on via
`ARIS_TRUE_COMPOUND_SLOPES=pooled`. `mc_draws=0`. Default path not
touched.

### Chained rollout vs G1.1

| Horizon | n | Aimed (G1.1) | Actual (pooled) | Result |
|---|---:|---:|---:|---|
| +5 | 477 | **1.861** | **1.976** | worse |
| +10 | 477 | **2.444** | **2.790** | worse |
| +20 | 354 | **2.790** | **4.079** | worse |

Bias at +20 is **+2.592 s** (over-degradation). The overlay slopes
(~0.13–0.17 s/lap on C1–C4, ~0.29 on C5) are several times G1.5's
0.08/0.05/0.03. Artefact: `results/g4/g11_rollout.json`.

### Walk-forward vs stay-out and G1.5

| Year | Aimed vs stay-out | Aimed vs G1.5 | Actual | vs stay-out | vs G1.5 |
|---|---|---|---|---|---|
| 2024 | **> 0.250** (10/40) | **> 0.325** (13/40) | **0.300** (12/40) | beat | miss |
| 2025 | **> 0.298** (14/47) | **> 0.319** (15/47) | **0.234** (11/47) | miss | miss |
| Combined | **> 0.276** (24/87) | **> 0.322** (28/87) | **0.264** (23/87) | miss | miss |

Mean position-delta combined: aimed ≤ 0, actual **+3.48** (G1.5 was
**+2.96**). Not the gate, still worse.

Artefacts: `results/g4/backtest/2024_summary.json`,
`2025_summary.json`, `2024_2025_combined_summary.json`.

### Default-candidate verdict

**Not a candidate.** Combined 0.264 loses to stay-out 0.276 and to G1.5
0.322. 2025 alone is below a never-box policy. Restoring C-code order
inside a GBT is not the same as a better `recommend()` slope table.
Leave `ARIS_TRUE_COMPOUND_SLOPES` off. Same rule as G3.5.11.

---

## G4.5 — research backlog

`docs/research-backlog.md` lists four post-event items, one paragraph
each, documentation only:

1. Position-delta root cause (separate from tyre degradation)
2. Wet-race strategy (currently unhandled)
3. `physics_pred` absolute calibration debt
4. Monte Carlo interval calibration

Not executed here.

---

## Tests

Full pytest after the one-hot encoding change and at close: **230 passed**,
0 failed (was 214 at G3 close; G4 added traffic, n_corners, pooled-deg,
Spanish alias). Docker/Postgres up, `ARIS_DB_URL` set. Log:
`results/g4/pytest.log`.

Opt-in wiring: `pooled` / `g4` / `context` / `gbt` → overlay;
unset / `0` / `off` / unknown → G1.5. Year alone does not overlay.

---

## What this does and does not claim

Does: join real weather/gap/corners/fuel; fit one leakage-safe pooled
GBT; show that **at typical context** C1–C6 degradation order returns;
show that this overlay still loses the strategy gate.

Does not: claim tyres are now a solved physical series. C1–C4 remain
close, some contexts invert or go negative, and the walk prefers G1.5's
small global prior. Does not change `load_track_config` default.

**STOP.** Wait for review before any default behaviour change.
