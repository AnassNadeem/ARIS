# Future research — estimated cornering load (design only)

**Status:** design doc. Not scheduled, not built. After Zandvoort 2026.

G1–G4 showed that lap-time-only degradation inference has a mapped
ceiling (`docs/tyre-degradation-research.md`). This note is the one
remaining idea that is *not* another fit of the same clocked lap: a
**lateral-load proxy per corner**, computed from speed and geometry, used
as a degradation covariate independent of lap time.

It is a new research thread — data plumbing, a new feature, a new
validation — not a weekend patch. Seven days out is the wrong time to
start it. G4's pooled overlay stays off; G1.5 stays shipped.

---

## Why this is different

Real teams (and sensor-backed public graphics) track **tyre energy**:
work into the rubber from lateral and longitudinal load. ARIS cannot
see temperature, pressure, or strain. It *can* see, for most circuits:

- a list of corners with `radius_m` and `arc_length_m`
- a speed trace vs distance on a lap (FastF1 car telemetry)

Lateral acceleration in a corner is \(a_\mathrm{lat} \approx v^2 / R\).
That is a load, not a lap time. Two cars can clock the same lap with
different speed profiles (lift-and-coast vs committed mid-corner), and
two compounds can take the same corner at different \(v\) for the same
geometry. Summing load over the lap is a wear proxy that does not
require the fitter to swallow fuel, SC, and pace management the way a
DegSlope on `LapTimeS` does.

G4 already put **corner count** into a GBT (gain share **10.5%**, behind
compound and tyre_life, ahead of gap). Count is a circuit constant. Load
varies by lap, driver, and how much speed is actually carried. That is
the increment.

This is still not onboard tyre energy. It is the best public-data
stand-in that is not "fit the timing screen again."

---

## How it would be computed

### Per corner, one sample of speed

For corner \(i\) with radius \(R_i\) and arc \(s_i\), take a speed
sample \(v_i\) from telemetry in a window around that corner's distance
marker (the same ±40 m / ±90 m windows `scripts/build_track_config.py`
already uses for the circle fit).

\[
a_{\mathrm{lat},i} = \frac{v_i^2}{R_i}
\qquad
L_i = m \cdot a_{\mathrm{lat},i}
\qquad
E_i = L_i \cdot s_i = m \cdot \frac{v_i^2}{R_i} \cdot s_i
\]

Mass \(m\) can be the current fuel-estimated mass (car min + remaining
fuel) so a heavy first stint is not treated as a light last stint. For
ranking compounds inside one race, a constant \(m\) cancels and
\(\sum v_i^2 s_i / R_i\) is enough.

Practical \(v_i\): median Speed in the window, not a single GPS point.
Drop windows with no samples (out-lap, SC, missing telemetry) rather
than inventing a speed.

### Per lap

`cornering_load` = \(\sum_i E_i\) (or the unit-mass sum). Optional
splits that are still independent of lap time:

- **tight-corner load**: sum over \(R_i\) below some threshold (Zandvoort
  T3 / T11-ish vs Monza T1)
- **peak \(a_\mathrm{lat}\)** vs integrated energy (wear vs a single
  spike)

### Fallback when telemetry is missing

The bicycle already has a grip-limited corner speed
`corner_speed = min(sqrt(μ g R), v_max)` (`src/aris/physics/bicycle.py`).
That is a *circuit* number, not a lap number — it would collapse back
toward G4's `n_corners` / geometry-only feature. Use it only as a
circuit prior, never as a silent stand-in for a missing speed trace on
a lap that is supposed to carry a load covariate.

Do not substitute Bahrain's 15-corner profile for another circuit
(G4.1 rule; `n_corners_for_event` already returns `None` on empty YAML).

---

## How it would be used

**As a covariate, not as a new slope table.** The G4 lesson: restoring
C1 < … < C6 inside a model is not the same as a better `recommend()`
constant. The load feature should go into a degradation model the way
gap and weather did — predict a fuel-corrected early-stint residual (or
a per-lap pace loss), then derive a slope by finite difference at fixed
*load*, not at fixed lap time.

Independence from lap time is the point:

- Target can still be fuel-corrected `LapTimeS` minus a fresh-tyre
  baseline (E3.2 / G4.2 construction). That target is lap time; the
  *inputs* must not be.
- Do not put `LapTimeS`, lags, or `physics_pred` into the load
  calculation. Speed in a corner window is allowed; the sector clock is
  not.
- Gap-to-nearest (G3.3 construction in `src/aris/physics/traffic.py`)
  can stay as a separate traffic covariate. Load answers "how hard was
  this tyre asked to work"; gap answers "was the driver managing in
  space." G3.3 says those are confounded today. Splitting them is the
  experiment.

**Not** a replacement for G1.5 on day one. Same default-candidate rule
as G3.5.11 / G4.4: beat stay-out **and** G1.5 on the combined 2024+2025
walk before touching `load_track_config` defaults. Offline, opt-in flag
only, until that gate.

---

## What is already available

| Piece | Where | Coverage / caveat |
|---|---|---|
| Corner list `{radius_m, arc_length_m}` | `data/tracks/*.yaml` (32 circuits) | G4.1: `n_corners` present on **0.950** of 161,793 laps. **Mugello** is genuinely empty (`corners: []`). Bahrain uses `physics_profile: bahrain_2024` (15 corners), not YAML. Layout-change flags in `docs/PHASE-D-SUMMARY.md` (Yas Marina, Singapore, Barcelona, Melbourne, Sakhir outer). |
| Corner distance / angle | FastF1 `session.get_circuit_info().corners` | Same source the YAML was built from (`scripts/build_track_config.py`). |
| Speed vs distance | FastF1 `lap.get_telemetry().add_distance()` (`Speed`, `X`/`Y` in 1/10 m) | Cache-backed for historical races; **not** fully populated in Postgres. Ingest `include_telemetry=True` is opt-in (~500k rows/race). Schema already has `telemetry.speed` (`docs/data-sources.md`). |
| Fuel mass proxy | `estimate_fuel_kg` | Coverage **1.000** in G4.1. Linear 110 kg / 1.7 kg/lap — a shape, not a weighed tank. |
| C-code identity | `data/compounds/nominations.json` | Mapped only; G4.1 identity **0.329** overall, **1.000** on mapped laps. Unmapped races stay unmapped. |
| Gap-to-nearest | `gaps_at_completed_laps` | **0.983**; reuse, do not rebuild. |
| Weather | FastF1 `session.weather_data` nearest timestamp | **1.000** present; median \|Δt\| 15 s. Session-level Postgres medians are *not* this join. |

Honest holes: 2020 Tuscan (Mugello) has no geometry; some 2026 races
have no timing yet; telemetry-in-Postgres is a schema check plus a few
races, not a calendar. The FastF1 cache is the real store for a first
pass. Circle-fit radii are themselves an estimate (median circumradius
of XY triples, 8–450 m clip, 70 m fallback when the fit fails) — good
enough for a proxy, not a laser scan of the kerb.

---

## Effort (realistic, after the event)

This is **weeks, not a day**. Rough split:

| Block | What | Time |
|---|---|---|
| 1. Telemetry path | Decide cache-only vs calendar ingest into `telemetry`. Cache-only is enough to *fit*; ingest is needed if Strategy ever sees live load. A full-season ingest is large (hundreds of millions of samples if done naively — probably race-lap + corner-window aggregates, not raw 100 Hz). | 2–4 days |
| 2. Corner matching | Join Speed samples to YAML / `get_circuit_info` distances; define the window; handle missing samples; unit-test against one known lap (Bahrain VER already plotted in Phase 1). | 2–3 days |
| 3. Feature + target | Per-lap `cornering_load` (and maybe tight-corner split). Same E3.2 clean-lap / fuel-detrend / first-lap-drop as G4.2. Leakage: load from *this* lap is contemporaneous with the target — for a slope model that may be acceptable; for a next-lap residual it is not. Decide before fitting. | 1–2 days |
| 4. Fit | One model, LORO on pre-2024 only, never 2024/2025 for knobs. Compare against G4's pooled GBT *with n_corners replaced or augmented by load*. Do not start from a new booster family. | 2–3 days |
| 5. Validate | Same three numbers as G4.4: chained MAE +5/+10/+20 vs G1.1 **1.861 / 2.444 / 2.790**; walk-forward 2024+2025 vs stay-out **0.276** and G1.5 **0.322**; Zandvoort smoke vs E4.1 recommend identity. Opt-in flag only. | 2–3 days (walk is ~15–40 min per year, not a shortcut) |

**Total: about 1.5–3 weeks of focused work**, assuming the FastF1 cache
is already warm and no new C-code mapping is required. Add time if
calendar telemetry ingest is in scope, or if layout-year splits
(Singapore 2019 vs 2023, Yas Marina 2019 vs 2021) have to be first-class.

What would make it *not* worth that time: if a cheap check — circuit-level
mean \( \sum s_i / R_i \) already correlates with G4's `n_corners` at
>0.9 — then lap-varying speed is the only new information, and the
project should prove that variance exists on a handful of races before
building the rest.

---

## What this doc is not

- Not a commitment to change G1.5.
- Not a request to ingest telemetry this week.
- Not a claim that \(v^2/R\) *is* tyre energy. It is a public-data
  proxy for lateral load, which is one input to energy.
- Not a fifth unconstrained DegSlope on `LapTimeS`.

If it is picked up after the event, start with the cheap correlation
check, then Block 1. Do not wire `load_track_config` until the
walk-forward gate is met.
