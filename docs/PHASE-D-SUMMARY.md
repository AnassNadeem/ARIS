# Phase D summary — Full-calendar track coverage

Executed 2026-08-11. Scope was **only** Phase D (Blocks D1–D6). No Phase E
(tyre degradation), F (backtest), or later work started.

---

## Verdict (read this first)

**Track configs now exist for essentially every circuit in the 2018–2026
scope, but the predictor does not “work for every race” at Phase C quality.**

| Metric (held-out overall) | Phase C (5 races) | Phase D (full 2024 calendar, 24 races) |
|---|---:|---:|
| MA(2) baseline | 0.469 | **0.549** |
| Physics-only | 15.211 | **17.349** |
| Physics+residual | 0.787 | **3.150** |
| Blended | 0.549 | **1.605** |

Broadening coverage **regresses** residual and blended MAE sharply. The old
five held-out races (China/Monaco/Spain/Belgium/Abu Dhabi) remain relatively
strong; many newly configured circuits (Japan, Canada, Mexico, Las Vegas,
Australia, Imola, Austria, …) still have large residual errors even with
local geometry. Plain answer to “does it work for every race?”: **configs
yes; predictor accuracy no — not yet at Phase C levels calendar-wide.**

---

## Block D1 — Coverage needs (read-only)

Resolved via FastF1 event schedules / session events (not hand-typed).

### Circuit coverage table

| Circuit | Seasons needed | Had config before? | Added in D2? | Notes |
|---|---|---|---|---|
| Sakhir (Bahrain GP) | 2018–2025 | Y | — | |
| Shanghai | 2018–19, 2024–26 | Y | — | |
| Monaco / Monte Carlo | 2018–26 | Y | — | |
| Barcelona (Catalunya) | 2018–26 | Y | — | Layout flag (see below) |
| Spa-Francorchamps | 2018–26 | Y | — | Mild lap-length variance |
| Yas Marina / Yas Island | 2018–26 | Y | aliases fixed | Layout flag; UAE match fixed |
| Melbourne | 2018–19, 2022–26 | N | **Y** (2025) | Layout flag |
| Jeddah | 2021–25 | N | **Y** (2025) | |
| Suzuka | 2018–19, 2022–26 | N | **Y** (2025) | |
| Miami / Miami Gardens | 2022–26 | N | **Y** (2025) | |
| Imola | 2020–22, 2024–25 | N | **Y** (2025) | |
| Montréal | 2018–19, 2022–26 | N | **Y** (2025) | |
| Spielberg | 2018–26 | N | **Y** (2025) | |
| Silverstone | 2018–26 | N | **Y** (2025) | |
| Budapest | 2018–26 | N | **Y** (2025) | |
| Zandvoort | 2021–26 | N | **Y** (2025) | |
| Monza | 2018–26 | N | **Y** (2025) | |
| Baku | 2018–19, 2021–26 | N | **Y** (2025) | |
| Singapore / Marina Bay | 2018–19, 2022–26 | N | **Y** (2025) | Layout flag |
| Austin (COTA) | 2018–19, 2021–26 | N | **Y** (2025) | |
| Mexico City | 2018–19, 2021–26 | N | **Y** (2025) | |
| Interlagos | 2018–19, 2021–26 | N | **Y** (2025) | |
| Las Vegas | 2023–26 | N | **Y** (2025) | |
| Lusail | 2021, 2023–26 | N | **Y** (2025) | |
| Le Castellet | 2018–19, 2021–22 | N | **Y** (2022) | Historical |
| Hockenheim | 2018–19 | N | **Y** (2019) | Historical |
| Nürburgring | 2020 | N | **Y** (2020) | Historical |
| Mugello | 2020 | N | **Y** (2020) | **0 corners from FastF1** |
| Portimão | 2020–21 | N | **Y** (2021) | Historical |
| Istanbul | 2020–21 | N | **Y** (2021) | Historical |
| Sochi | 2018–21 | N | **Y** (2021) | Historical |
| **Madrid (2026 Spanish GP)** | 2026 | N | **Held off** | Must not reuse Catalunya |
| **Sakhir outer (2020 Sakhir GP)** | 2020 | N | **Held off** | Wrongly aliases to `bahrain` |

Before D2, missing circuits silently fell back to **Bahrain defaults**
(57 laps, 21.0 s pit, `bahrain_2024` geometry). Matching was also fixed so
shared-country circuits (Italy / USA / Germany) and Location-before-Country
resolution work; Abu Dhabi aliases now include `united arab emirates` /
`yas island`.

### Layout-change flags (do not treat one year as silently safe for all)

| Circuit | Evidence | Recommendation |
|---|---|---|
| **Yas Marina** | 2019: 21 corners / ~5504 m / 55 laps → 2021+: 16 / ~5215–5251 m / 58 laps | Keep 2024-derived config for modern years; optional pre-2021 YAML if training physics for old Abu Dhabi matters |
| **Singapore** | 2019: 23 / ~5041 m / 61 → 2023+: 19 / ~4887 m / 62 | 2025 config is correct for modern calendar; old layout for 2018–19 training only if needed |
| **Barcelona** | 2019–21: 16 corners → 2023+: 14 | Existing `spain.yaml` is post-chicane (2024); pre-2023 residual training still uses this geometry |
| **Melbourne** | 2019 ~5276 m → 2022 ~5205 m (corners still 14) | 2025 config used; pre-2021 Albert Park differs |
| **Spa** | Corners stable at 19; lap length ~6968→6929→6944 m | One config acceptable; variance is small |
| **Sakhir outer (2020)** | 87-lap outer layout vs GP 57 / 15 corners | Separate config or rename alias — **needs decision** |
| **Madrid 2026** | New circuit; Country=Spain | Do not ship until race telemetry exists; currently would have mismatched via “spanish” (alias removed) |

---

## Block D2 — Configs added

**25 new YAMLs** under `data/tracks/` (strict pit-loss matcher from Phase C):

| File | Source year | total_laps | pit_loss_s | corners | lap_length_m |
|---|---:|---:|---:|---:|---:|
| `australia.yaml` | 2025 | 57 | 9.0† | 14 | 5238.7 |
| `saudi_arabia.yaml` | 2025 | 50 | 17.7 | 27 | 6073.7 |
| `japan.yaml` | 2025 | 53 | 21.6 | 18 | 5767.5 |
| `miami.yaml` | 2025 | 57 | 13.3 | 19 | 5324.8 |
| `imola.yaml` | 2025 | 63 | 21.4 | 19 | 4884.3 |
| `canada.yaml` | 2025 | 70 | 16.1 | 14 | 4295.2 |
| `austria.yaml` | 2025 | 70 | 17.5 | 10 | 4295.8 |
| `britain.yaml` | 2025 | 52 | 18.7 | 18 | 5817.8 |
| `hungary.yaml` | 2025 | 70 | 18.5 | 16 | 4355.0 |
| `netherlands.yaml` | 2025 | 72 | 16.4 | 14 | 4236.1 |
| `italy.yaml` | 2025 | 53 | 21.3 | 11 | 5738.6 |
| `azerbaijan.yaml` | 2025 | 51 | 17.7 | 20 | 5937.0 |
| `singapore.yaml` | 2025 | 62 | 15.8 | 19 | 4890.5 |
| `usa.yaml` | 2025 | 56 | 20.1 | 20 | 5449.8 |
| `mexico.yaml` | 2025 | 71 | 19.1 | 17 | 4242.6 |
| `brazil.yaml` | 2025 | 71 | 18.5 | 15 | 4233.7 |
| `las_vegas.yaml` | 2025 | 50 | 15.8 | 17 | 6140.7 |
| `qatar.yaml` | 2025 | 57 | 23.0 | 16 | 5391.7 |
| `france.yaml` | 2022 | 53 | 13.8 | 15 | 5762.4 |
| `hockenheim.yaml` | 2019 | 64 | 19.3 | 17 | 4568.5 |
| `nurburgring.yaml` | 2020 | 60 | 20.8 | 15 | 5118.2 |
| `mugello.yaml` | 2020 | 59 | 16.6 | **0** | 5230.6 |
| `portugal.yaml` | 2021 | 66 | 22.2 | 15 | 4633.9 |
| `turkey.yaml` | 2021 | 58 | 20.3 | 14 | 5263.8 |
| `russia.yaml` | 2021 | 53 | 20.5 | 18 | 5789.6 |

† Australia `pit_loss_s=9.0` looks low vs typical Albert Park figures — flagged
under decisions. Mugello has empty `corners:` (FastF1 circuit info returned
none) so physics still falls back to Bahrain geometry for that one-off.

Also: `tracks._match_track_file` prefers specific aliases over ambiguous
country; `features.build_from_fastf1` resolves Location before Country;
Spain dropped the `spanish` alias so 2026 Madrid cannot silently get Catalunya.

**Tests after D2:** green (123 passed at that checkpoint; suite grew in D4).

---

## Block D3 — Strict pit_loss_s consistency (existing 6)

Same Phase C Belgium matcher on 2024 race data:

| Track | Old pit_loss_s | New (strict) |
|---|---:|---:|
| Bahrain | 21.0 | **21.8** |
| China | 17.1 | **17.4** |
| Monaco | 23.0 | **19.2** |
| Spain | 17.2 | **19.0** |
| Belgium | 14.6 | **14.6** (unchanged) |
| Abu Dhabi | 21.4 | **21.8** |

Previous values stored in each YAML `source.pit_loss_previous_s`.

**Tests after D3:** green.

---

## Block D4 — Prewrite strategy windows

**Factual check:** `src/aris/plan/prewrite.py` had **hardcoded** Strat A/B/C
pit laps (`[15]`, `[24]`, `[14, 32]`) — Bahrain-shaped — even though
`total_laps` from track config was already used for simulation length.

**Change:** `derive_pit_windows(total_laps, pit_loss_s, high_deg=…)` scales
fractions (~26% / ~42% / ~25%+56%) with a small pit-loss nudge. Bahrain still
lands on 15 / 24 / 14+32; Monaco vs Belgium diverge:

| Track | Windows A / B / C |
|---|---|
| Bahrain (57) | 15 / 24 / 14+32 |
| Monaco (78) | 20 / 32 / 20+44 |
| Belgium (44) | 10 / 17 / 11+25 |

Tests in `tests/test_prewrite.py` assert Monaco ≠ Belgium windows.

**Tests after D4:** **125 passed**.

---

## Block D5 — Broadened held-out evaluation

`HELD_OUT_RACES` expanded to the **full 2024 calendar (24 races)**, still
disjoint from `REFERENCE_RACES` (2018–2023 only). Columns added:
`d5_physics_only_mae_s`, `d5_physics_residual_mae_s`, `d5_blended_mae_s`
(plus refreshed `baseline_mae_s` / `n_laps`).

### Overall

| Mode | MAE (s) | n laps |
|---|---:|---:|
| MA(2) baseline | **0.549** | 21286 |
| Physics-only | **17.349** | 22285 |
| Physics+residual | **3.150** | 22285 |
| Blended | **1.605** | 22285 |

### Per-race MAE (D5)

| Race | n | MA(2) | Phys | P+R | Blend |
|---|---:|---:|---:|---:|---:|
| 2024 Bahrain | 961 | 0.328 | 16.645 | 0.396 | 0.371 |
| 2024 Saudi Arabia | 783 | 0.489 | 20.555 | 0.480 | 0.478 |
| 2024 Australia | 831 | 0.486 | 24.734 | 4.372 | 1.657 |
| 2024 Japan | 724 | 0.685 | 26.699 | 6.360 | 3.681 |
| 2024 China | 716 | 0.400 | 10.031 | 0.574 | 0.485 |
| 2024 Miami | 908 | 0.413 | 26.205 | 3.969 | 2.277 |
| 2024 Emilia Romagna | 1139 | 0.453 | 21.729 | 6.335 | 2.871 |
| 2024 Monaco | 1148 | 0.634 | 13.578 | 0.874 | 0.673 |
| 2024 Canada | 870 | 1.271 | 8.801 | 7.182 | 3.260 |
| 2024 Spain | 1166 | 0.484 | 11.176 | 0.757 | 0.576 |
| 2024 Austria | 1215 | 0.379 | 12.061 | 5.223 | 2.756 |
| 2024 Britain | 808 | 1.347 | 18.505 | 1.167 | 1.248 |
| 2024 Hungary | 1202 | 0.511 | 11.984 | 3.662 | 1.411 |
| 2024 Belgium | 711 | 0.444 | 26.065 | 1.350 | 0.633 |
| 2024 Netherlands | 1327 | 0.427 | 18.363 | 0.975 | 0.634 |
| 2024 Italy | 907 | 0.469 | 16.868 | 1.984 | 0.816 |
| 2024 Azerbaijan | 835 | 0.528 | 20.245 | 4.595 | 2.115 |
| 2024 Singapore | 1087 | 0.526 | 8.112 | 1.782 | 0.800 |
| 2024 United States | 843 | 0.394 | 24.662 | 4.723 | 2.283 |
| 2024 Mexico City | 1024 | 0.386 | 21.900 | 6.591 | 3.216 |
| 2024 Sao Paulo | 777 | 1.114 | 3.555 | 3.859 | 2.092 |
| 2024 Las Vegas | 813 | 0.632 | 26.156 | 5.939 | 3.441 |
| 2024 Qatar | 644 | 0.352 | 18.672 | 2.201 | 0.610 |
| 2024 Abu Dhabi | 846 | 0.299 | 18.248 | 0.418 | 0.329 |
| **OVERALL** | **22285** | **0.549** | **17.349** | **3.150** | **1.605** |

**Hold up / improve / regress?** **Regress** vs Phase C’s five-race snapshot.
Original five remain decent (blended ~0.33–0.67); calendar-wide blended is
1.605 s because several new circuits stay multi-second even after blend.

**Tests after D5:** green (held-out is a script, not pytest).

---

## Block D6 — docs/ gitignore split

`.gitignore` changed from blanket `docs/` to:

```
docs/planning/
docs/learning/
docs/REPO-STATUS-*.md
```

Confirmed trackable (`git status --untracked-files=all docs/`):

- `docs/PHASE-A-SUMMARY.md`, `PHASE-B-SUMMARY.md`, `PHASE-C-SUMMARY.md`
- `docs/actions.md`, `data-sources.md`, `decision-schema.md`
- (and this `PHASE-D-SUMMARY.md` once written)

Still ignored: `docs/planning/`, `docs/learning/`, `docs/REPO-STATUS-*.md`.

---

## Test suite

Docker Postgres up; `ARIS_DB_URL` set.

| Checkpoint | Result |
|---|---|
| After D2 | **123 passed** |
| After D3+D4 | **125 passed** (+2 prewrite window tests) |
| **End of Phase D** | **125 passed**, 0 failed, 0 skipped |

---

## Files created / modified (high level)

### Created
| File | Reason |
|---|---|
| `data/tracks/{25 new}.yaml` | Full-calendar + historical configs |
| `docs/PHASE-D-SUMMARY.md` | This summary |

### Modified
| File | Reason |
|---|---|
| `scripts/build_track_config.py` | Expanded meta, `--phase-d2` / `--phase-d3-pit`, strict default |
| `src/aris/tracks.py` | Disambiguated matching (specific > country) |
| `src/aris/models/features.py` | Location before Country |
| `data/tracks/{bahrain,china,monaco,spain,belgium,abu_dhabi}.yaml` | Strict pit_loss refresh / UAE aliases / no `spanish` |
| `src/aris/plan/prewrite.py` | Track-config-driven Strat windows |
| `tests/test_prewrite.py` | Monaco vs Belgium window tests |
| `src/aris/eval/laptime.py` | Full-2024 `HELD_OUT_RACES` |
| `results/heldout-laptime-mae.csv` | D5 columns + 24 races |
| `.gitignore` | docs/ public vs planning/learning/REPO-STATUS private |

---

## Needs Anas's decision

1. **Accept calendar-wide MAE regression as the honest coverage answer?**
   Configs are in place; residual/blend do not generalize to Phase C levels
   on every 2024 race. Next accuracy work is Phase E+ (not started).

2. **Madrid 2026** — hold off until FastF1 has race geometry, then build a
   dedicated `madrid.yaml` (do not reuse Catalunya). Confirm.

3. **2020 Sakhir outer** — separate YAML vs leave known wrong-alias on
   `bahrain`/`sakhir`? Recommend separate config if that race is ever scored.

4. **Australia pit_loss_s = 9.0** — empirical under strict matcher but low.
   Re-derive from another year, or accept?

5. **Mugello corners = []** — FastF1 returned no markers; physics falls back
   to Bahrain geometry for that one-off. Manual corners worth it?

6. **Per-era track YAMLs** for Yas / Singapore / Melbourne / Barcelona
   layout changes, or keep “most recent year” only?

7. **2026 Bahrain Location=`Kuala Lumpur` in FastF1 schedule** — data quirk;
   currently matches Bahrain by Country. Watch when that weekend arrives.

8. **Proposed tag (not cut)** — e.g. `v0.5-phase-d-tracks` for full-calendar
   configs + honest wide held-out MAE. Confirm name / whether to cut.

---

## Stop

Phase D is complete pending review of this summary. No Phase E (or later)
work will start until you say so.
