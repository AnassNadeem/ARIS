# Phase R.1 summary — cornering-load cheap check

Executed 2026-08-16 in the **research worktree**
`C:\Users\anass\OneDrive\Desktop\ARIS-cornering-load` on branch
`research/cornering-load` (from `a908e79`). The main demo-lock tree
`C:\Users\anass\OneDrive\Desktop\ARIS` on `main` was not modified.
Nothing was merged.

This is the cheap validation in
[`docs/future-research-cornering-load.md`](./future-research-cornering-load.md),
not the 1.5–3 week G4-replacement build.

---

## Verdict (read this first)

**The stop gate did not fire.** Circuit-level \(\sum s_i/R_i\) does **not**
correlate with real per-lap \(v^2/R\) at >0.9, so lap-and-circuit speed is
new information relative to G4's geometry constant. The exhibit is Monaco
vs Suzuka: Monaco has the tightest YAML geometry and **not** the highest
load, because the cars are slow.

That is **not** a commitment to the full 1.5–3 week build. Most of the
load variance is *between circuits* (η² **0.887**), not lap-to-lap, and
the FastF1 cache is **not** a full 2018–2025 telemetry calendar. Do a
bounded G4 swap on cache-complete years next; do not start a calendar
ingest.

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Worktree isolated from G.6 / `main` | separate dir, no merge | `ARIS-cornering-load` / `research/cornering-load`; main only `?? .cursor/` | **PASS** |
| Cheap check Pearson \(r(\sum s/R,\;\sum v^2 s/R)\) | stop if **>0.9** | **0.276** (green, no pit, n=7900) | **continue** |
| Same, circuit means (n=8) | report | **0.344** | well below 0.9 |
| \(\sum s/R\) vs G4 `n_corners` (circuit means) | design-doc stop if **>0.9** | **0.693** | not a stop |
| Per-lap load vs `n_corners` | report | Pearson **0.365** | weaker than a redundant feature |
| Between-circuit share of load variance | report | η² **0.887** | mostly a circuit feature |
| Mean within-race CV of load | prove lap-varying speed exists | **0.102** | exists, smaller than between-circuit |
| Cache telemetry enough for a multi-race sample? | report real coverage | sample **8/8**; 2025 **24/24**; all years **116/186 = 0.624**; 2024 **14/24**; 2026 **0/13** | sample yes; full corpus no |
| Feature uses only speed + geometry + mass | no `LapTimeS` / lags / `physics_pred` | signature + tests; those names absent from the module | **PASS** |
| Full pytest after code change | green | **268 passed**, 6 skipped (no `ARIS_DB_URL`) | **PASS** |
| Merged to `main` | **no** | not merged | **PASS** |

Artefacts (gitignored under `results/`): `results/r1/cheap_correlation.json`,
`results/r1/lap_loads.csv`. Re-run: `python scripts/_r1_cheap_correlation.py`.

---

## R1.1 — cheap correlation (go/no-go)

### Sample

Aimed: 5–8 real races spanning track types, YAML \(\sum s_i/R_i\), FastF1
cache speed-vs-distance for real laps.

2024 was the first candidate year. **10/24** 2024 races have no
`car_data.ff1pkl`, including Monza, Hungary, Silverstone, and Zandvoort.
The sample is therefore **2025**, where every race weekend has car data.

| Year | GP | Track type | `n_corners` | \(\sum s_i/R_i\) | YAML vs `circuit_info` count |
|---|---|---|---|---|---|
| 2025 | Bahrain | stop-go / `physics_profile` | 15 | **14.280** | 15 = 15 |
| 2025 | Monaco | slow street | 19 | **20.792** | 19 = 19 |
| 2025 | Italy | high-speed, few corners (Monza) | 11 | **9.587** | 11 = 11 |
| 2025 | Britain | high-speed flowing (Silverstone) | 18 | **13.352** | 18 = 18 |
| 2025 | Hungary | twisty high-downforce | 16 | **14.799** | 16 = 16 |
| 2025 | Belgium | mixed long (Spa) | 19 | **15.356** | 19 = 19 |
| 2025 | Singapore | night street | 19 | **13.514** | 19 = 19 |
| 2025 | Japan | technical flowing (Suzuka) | 18 | **16.264** | 18 = 18 |

Bahrain uses `bahrain_2024()` radii (YAML has no `corners:` list), zipped
by index onto FastF1 distance markers. Count matched; still an eyeballed
profile, not a circle-fit.

### Per-lap quantity

Aimed: real per-lap \(v^2/R\) from cache telemetry, not a bicycle
stand-in.

Actual: for each corner, median FastF1 `Speed` (converted km/h → m/s) in
the same ±40 m window `scripts/build_track_config.py` uses, expanding to
±90 m only when the narrow window is empty. Empty windows are **dropped**,
not filled. Primary correlate is unit-mass energy \(\sum_i v_i^2 s_i / R_i\)
(design-doc \(E_i/m\)). \(\sum_i v_i^2/R_i\) is reported as a sensitivity.
Mass is applied for the feature (`Car.mass_kg` **798** + `estimate_fuel_kg`)
but cancelled for this correlation so fuel burn cannot inflate \(r\).

Primary slice: green-flag (`TrackStatus` starts with `1`, no SC/VSC
codes), not an in/out lap. Aimed: racing laps, not SC crawls. Actual
n = **7900**.

### Correlation

| Comparison | Aimed | Actual |
|---|---|---|
| Pearson, lap-level energy vs \(\sum s/R\) | **>0.9** ⇒ stop | **0.276** |
| Spearman, same | report | **0.561** |
| Pearson, \(\sum v^2/R\) vs \(\sum s/R\) | report | **0.488** |
| Pearson, energy vs `n_corners` | report | **0.365** |
| Pearson, \(\sum s/R\) vs `n_corners` (lap-level) | design-doc >0.9 ⇒ geometry ≈ count | **0.693** |
| Pearson, circuit-mean energy vs \(\sum s/R\) | report | **0.344** |
| Pearson, circuit-mean energy vs `n_corners` | report | **0.445** |
| η² (between-circuit / total SS of energy) | report | **0.887** |
| Mean within-race CV of energy | report | **0.102** |

All-laps (n=8877, includes pits/SC): Pearson **0.252**. Green + every
corner sampled (n=7883): Pearson **0.277**. The gate is not slice-sensitive.

### Circuit means (green, no pit) — the ranking that G4's count cannot see

| GP | n laps | \(\sum s/R\) | mean energy | mean \(\sum v^2/R\) | CV | mean peak \(a_\mathrm{lat}\) (m/s²) |
|---|---|---|---|---|---|---|
| Japan | 1017 | 16.264 | **43301** | 659.0 | 0.064 | 75.7 |
| Belgium | 747 | 15.356 | **39530** | 603.3 | 0.098 | 86.9 |
| Bahrain | 992 | 14.280 | 27205 | 420.3 | 0.107 | 78.3 |
| Britain | 506 | 13.352 | 26852 | 423.9 | 0.162 | 50.4 |
| Hungary | 1308 | 14.799 | 25561 | 389.4 | 0.064 | 58.7 |
| Monaco | 1227 | **20.792** | 24941 | 471.6 | 0.080 | **107.1** |
| Singapore | 1181 | 13.514 | 21941 | 374.7 | 0.063 | 38.97 |
| Italy | 922 | **9.587** | **19853** | 299.7 | 0.174 | 64.8 |

Monaco is the most “corner-dense” circuit on YAML and has the highest
peak \(a_\mathrm{lat}\), but integrated energy is mid-pack. Suzuka and Spa
carry speed through long arcs. Monza is lowest on both count and energy.
`n_corners` is 19 at Monaco, Singapore, *and* Spa — those three are not
the same load.

**Gate: continue.** Aimed stop threshold 0.9; actual 0.276.

---

## R1.2 — telemetry availability (cache, not Postgres)

Aimed: confirm whether FastF1 cache telemetry is enough for a reasonable
multi-race sample. Do not assume.

Filesystem scan of `fastf1_cache/*/ */ *_Race/car_data.ff1pkl` (the same
tree the main checkout already has; worktree uses a junction):

| Corpus | Aimed | Actual |
|---|---|---|
| Events with a Race folder in cache | report | **186** |
| Of those, with `car_data.ff1pkl` | report | **116 / 186 = 0.624** |
| 2025 | useful if complete | **24 / 24 = 1.000** |
| 2024 | G4.4 held-out year | **14 / 24 = 0.583** |
| 2026 | live / upcoming | **0 / 13 = 0.000** |
| R1.1 sample sessions, timing laps with a speed trace | report | **8887 / 8887 = 1.000** |
| Of those, at least one corner window sampled | report | **8877 / 8887 = 0.999** |
| YAML / `circuit_info` count mismatch in sample | none preferred | **0 / 8** |

2024 races **without** cached car data (would have to be downloaded before
a 2024 walk-forward): Emilia Romagna, Canada, Britain, Hungary, Netherlands,
Italy, Azerbaijan, United States, Mexico City, São Paulo. That list includes
Zandvoort and Monza.

On the eight 2025 sample sessions, cache telemetry was sufficient: every
timing lap had car data; Italy dropped **10 / 974** laps where a window
had no samples (aimed: drop, do not invent; actual: dropped). No Postgres
`telemetry` ingest was used or needed for this phase.

**Cache-only is enough to fit a sample and a 2025-only walk. It is not
enough for the design doc's full 2018–2025 LORO + 2024+2025 walk without
filling holes, and it is not a live-Strategy path for 2026.**

---

## R1.3 — feature on the sample, not the calendar

Implemented in this worktree only:

- `src/aris/physics/cornering_load.py` — window median speed, drop empty
  windows, \(E_i = m \cdot v_i^2 / R_i \cdot s_i\), optional tight-corner
  split (\(R < 50\) m) and peak \(a_\mathrm{lat}\).
- `scripts/_r1_cheap_correlation.py` — the eight-race computation above.
- `tests/test_cornering_load.py` — closed-form constant-speed energy,
  empty-window drop, wide-window fallback, mass = min weight + fuel,
  signature independence.

Independence (aimed: speed and geometry only):

| Check | Aimed | Actual |
|---|---|---|
| `lap_cornering_load` parameters | `distance_m`, `speed_ms`, `corners`, `mass_kg` | those four (+ `tight_radius_m`) |
| `LapTimeS`, `lag1_pace`, `lag2_pace`, `physics_pred` in the module | absent | absent |
| Fuel mass | existing `estimate_fuel_kg` + `Car.mass_kg` 798 | used; not a lap-time input |
| Wired into `load_track_config` / `recommend()` | **no** | not wired | **PASS** |

Computed for the same 5–8 race sample, not the full corpus. Per-lap rows:
**8877**. Not a G4 booster, not a DegSlope on `LapTimeS`.

---

## R1.4 — recommendation

**Do not start the full 1.5–3 week build as written.**

The cheap check asked one question: is per-lap \(v^2/R\) basically
\(\sum s/R\) (or `n_corners`) in disguise? **No.** Pearson **0.276** vs
aimed stop **>0.9**. Speed-weighted load reorders circuits (Suzuka/Spa
vs Monaco/Singapore) in a way count cannot. That is a real, useful
result, and it is the reason to keep the thread alive.

It is not evidence that the feature will beat stay-out **0.276** and
G1.5 **0.322** on the combined 2024+2025 walk, or improve chained MAE
vs G1.1 **1.861 / 2.444 / 2.790**. G4 already taught that a prettier
covariate is not a better `recommend()`. Also:

1. **η² 0.887** — this is mostly a *better circuit descriptor*, not a
   lap-varying tyre-energy tracker. Within-race CV is ~10%. Treating it
   as “how hard was this tyre asked to work *this lap*” oversells the
   within-race part.
2. **2024 cache is 58%.** The design-doc validation block needs 2024+2025.
   Britain / Hungary / Netherlands / Italy 2024 are missing car data.
   Downloading those is a day; ingesting a calendar of raw 100 Hz into
   Postgres is the expensive part the design doc already flagged.
3. **2026 cache is empty** of race car data. Live Strategy cannot see
   this feature from cache today. The design doc said cache-only is
   enough to *fit*; ingest is only for live. Do not invert that.

**What is worth doing next (about 2–4 days, still in this worktree):**

- Keep the feature opt-in and offline.
- On cache-complete data (full 2025; plus 2018–2024 events that already
  have `car_data`), fit **one** G4 pooled GBT with `n_corners` replaced
  or augmented by this load (race-mean and/or per-lap). Same LORO
  discipline: knobs on pre-2024 only, never 2024/2025.
- Score the G4.4 three numbers. If it does not beat stay-out **and**
  G1.5, stop. If it does, *then* spend the ingest / full-walk week.

**What is not worth doing now:** calendar telemetry ingest, wiring
`load_track_config`, a new booster family, or a fifth DegSlope on
`LapTimeS`.

G1.5 stays shipped. This branch stays unmerged.

---

## Pytest

Aimed: full suite green after the code change.

Actual: **268 passed**, **6 skipped** (Postgres integration; `ARIS_DB_URL`
unset, expected). 18 new tests in `tests/test_cornering_load.py`.

---

## Isolation

| Tree | Branch | HEAD | Dirty |
|---|---|---|---|
| `ARIS-cornering-load` | `research/cornering-load` | `a908e79` | this phase's files only |
| `ARIS` (demo lock) | `main` | `a908e79` | `?? .cursor/` only; G.6 files not touched |
| `ARIS-grounded-rag` | `feature/grounded-rag` | `3fddb9b` | not used |

Stop. No merge.
