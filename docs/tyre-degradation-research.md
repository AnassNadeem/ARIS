# Tyre degradation research — G1 through G4

This is the interview account of four evidenced attempts to replace ARIS's
global tyre slopes with something fitted from public data. The conclusion
is already shipped: **G1.5 stays**. The rest of this note is why that is
a considered choice, not a placeholder.

Phases: G1 2026-08-13, G2–G4 2026-08-14. Every number below is aimed vs
actual from those phase summaries. Opt-in overlays remain in the repo;
none of them is the default.

---

## The conclusion, first

The shipped path is:

- **Global compound slopes** SOFT **0.08** / MEDIUM **0.05** / HARD **0.03**
  seconds per lap of tyre age (the physical prior: softer degrades faster).
- **Physics-delta rollout** inside `simulate()`: the residual is applied
  once, on the first remaining lap, with the real last-lap times sitting on
  the snapshot. Every later lap adds only tyre slope + fuel.

That combination (G1.4 + G1.5) is the **permanent default** as of Phase G.5.
It is not waiting for a better lap-time fit. Four attempts at a better fit,
each evaluated on the same walk-forward gate, did not beat it.

The gate was explicit from G3.5.11 onward: a fitted overlay becomes the
default only if it beats **both** always-stay-out **and** G1.5 on combined
2024+2025 decision match-rate. Stay-out is **0.276** (24/87). G1.5 is
**0.322** (28/87). G2, G3, and G4 all missed that bar.

---

## Why lap time is not a tyre sensor

A real race-engineering group does not infer degradation from the timing
screen. The car carries **onboard tyre sensors** — surface and carcass
temperature, TPMS pressure, and (on the team side) the load path through
the wheel. From those they compute **tyre energy**: the work going into
the rubber through lateral and longitudinal load. Wear tracks that energy
much more closely than it tracks a clocked lap.

AWS F1 Insights' public "Tyre Performance" graphics sit on the same side
of that split: they are visualising a sensor-backed remaining-life story,
not a slope fitted to `LapTime`. Pirelli's own compound briefings are
built from those channels plus indoor characterisation. None of that feed
is in FastF1.

What ARIS actually has:

| Channel | In the public feed? | Used for degradation? |
|---|---|---|
| Lap time, `TyreLife`, event-relative SOFT/MEDIUM/HARD | yes | yes — this is the whole signal |
| True C1–C6 identity | **no** (FastF1 issue #332). Sourced by hand from Pirelli (G2) | tried; did not produce physical order |
| Fuel | estimated (110 kg start, 1.7 kg/lap), not weighed | subtracted as a linear detrend |
| Weather (air / track / humidity) | yes, nearest timestamp | G4 covariate; real coverage, small gain share |
| Gap to nearest car | derived from cumulative lap times | G3/G4; selection effect, not a tyre sensor |
| Corner count / geometry | YAML from `get_circuit_info` + telemetry circle fit | G4 used *count*; load is unscored (see the cornering-load design doc) |
| Car telemetry (speed, GPS) | optional ingest; not on every race in Postgres | unused for degradation |
| Tyre temp / pressure / energy | **not in FastF1** | unavailable |

Lap time mixes real wear with fuel burn, dirty air, Safety Car, out-laps,
and **deliberate pace management**. G3.3 measured the last of those:
HARD stints sit in freer air than SOFT (median min-gap **1.82 s** vs
**1.40 s**; free-air fraction **0.464** vs **0.376**). Observed "HARD
degrades slowly" is partly drivers managing a long stint in space, not
pure compound physics. Any fitter that only sees lap time will swallow
that confound.

That is the information ceiling. G1–G4 mapped it. They did not break it.

---

## What was tried

### G1 — the walk lost to stay-out for a measurable reason

Phase G's first walk was **5/40 = 0.125** against always-stay-out
**10/40 = 0.250**. Diagnosis, then one fix tied to the evidence.

- **G1.1.** `simulate()` was chaining its own predictions back as lag
  inputs. Teacher-forced MAE stays ~0.76–0.86 s at every horizon (the
  same world as held-out MAE). Chained MAE compounds: **0.861 → 1.861 →
  2.444 → 2.790 s** at +1/+5/+10/+20. By +20 that is ~3.5× the one-step
  number. Singapore PIA MEDIUM: teacher-forced inside 0.5 s; chained
  already **+7 s** at five laps.
- **G1.2.** Single-step with *real* lags is not "old HARD looks too
  slow." HARD at tyre_life ≥ 25: bias **−0.003 s** (n=2995). The Phase G
  hindsight pattern is not missing long HARD runs.
- **G1.3.** Divergence audits: physics often *punished* ARIS's later
  SOFT/MEDIUM stop; the chained residual then awarded it tens to hundreds
  of seconds. Hungary VER L21: tyre **+15.5 s** against ARIS, residual
  **−157.4 s** for ARIS.
- **G1.4.** Physics-delta rollout (residual once, then slope + fuel) plus
  a mild extrapolation caveat past typical stint lengths. Not extra
  residual features; G1.2 already showed those were not the hole.
- **G1.5.** Same walker, `mc_draws=0`, classified P5. **2024 0.325**
  (13/40), **2025 0.319** (15/47), combined **0.322** (28/87). Beats
  stay-out on match-rate. Mean position-delta stayed positive
  (**+2.96** combined) — a different question, still a miss.

G1.5 is the first (and so far only) degradation-related change that
cleared the strategy floor. The slopes it uses are the same global prior
E3.2 already fell back to after a fuel-corrected DegSlope fit failed
SOFT > MEDIUM > HARD sanity (Netherlands fitted 0.0609 / 0.0346 / 0.0491
and was not shipped).

### G2 — the labels were wrong; the physical claim still failed

Hypothesis: three prior ordering failures were an artifact of
event-relative SOFT/MEDIUM/HARD hiding different C-codes.

- FastF1 `Compound` is never C1–C6. Mapping is a sourced
  `(year, round) → C-code` file (`data/compounds/nominations.json`, 98
  rows, every row a `source_url`). Unmapped races were left unmapped.
- E3.2 fitter re-keyed onto `CompoundIdentity` within era. Aimed:
  monotonic C1 < C2 < … < C5/C6 in every era. Actual: **no in all four
  eras**. Walk-forward era 2023–2025 (n=4597 stints): C5 **−0.1892**,
  C4 slower-degrading than C1–C3.
- Zandvoort event-relative SOFT > MEDIUM > HARD: **no every year
  2021–2026**. 2025 (C2/C3/C4) made SOFT the *kindest* tyre in the
  simulator (0.0283 vs HARD 0.0359).
- Shipping that overlay: combined match-rate **0.195** (17/87) — below
  stay-out, below G1.5. Chained MAE did not shrink. Recommend identity at
  Zandvoort moved to Plan L31→SOFT, L46→HARD because the simulator
  believed SOFT degraded slowest.

The labels were the wrong diagnosis. Correctly labelled C-codes, same
fitter, still not a physical series.

### G3 — constrain the fit; protect the demo first

G2 had applied the overlay whenever `year` was passed — that is the
`simulate()` / `recommend()` / Strategy UI path. G3.1 reverted the
default to G1.5 **before** any new fit. Zandvoort recommend identity
returned to the E4.1 lock: **Pit lap 33 HARD / Pit lap 30 HARD / Stay
out**. What-if/MC stayed on G1.4 numbers (−11.92 s, P10/P90 −147.55 /
+29.33), not E4.1's −13.00 s and not G2's −2.34 s. Restoring −13.00 s
would mean dropping physics-delta.

Then three findings, not a fifth unconstrained guess:

- **`recommend()` is rationally biased by the slope table.** On G2's
  overlay it picked the flattest fitted compound on **80.7%** of pit/plan
  proposes (2143/2657). On G1.5 globals it picked HARD. The apparent
  SOFT bias was not a candidate-generation bug.
- **Pace-management confound holds** (numbers above). HARD/C1 stints run
  in lower traffic pressure. Unconstrained lap-time fits will not emit
  C1 < … < C5.
- **Isotonic (PAVA) C1 ≤ … ≤ C6** is a different method. It made the
  stack monotone by construction. In 2023–2025 it compressed **every**
  C-code to **0.0216 s/lap** — C5's −0.1892 inversion dragged the whole
  era to one number. That is data quality, not a shipping table.
  Zandvoort SOFT > MED > HARD: still **no every year**. Combined
  match-rate **0.299** (26/87): beats stay-out, **loses to G1.5**. Not a
  default candidate.

### G4 — one pooled model with real context; order returns, strategy does not

Last variation on the same signal, this time with covariates that
actually exist (coverage measured, not assumed): weather **1.000**,
gap **0.983**, n_corners **0.950**, fuel **1.000**, tyre_life **0.994**,
C-code identity **0.329** overall / **1.000** on mapped laps.

One XGBoost across mapped C-codes, LORO knobs on pre-2024 only
(depth=4, η=0.05, rounds≤120; CV MAE **4.233 ± 2.400 s** on 36 events).
Slopes are finite differences tyre_life 2→12 at fixed context.

**Headline:** at global median context, C1 **0.1286** < C2 **0.1538** <
C3 **0.1658** < C4 **0.1707** < C5 **0.2867** < C6 **0.3028**. G2's
inversion is partly confounding. Two caveats sit next to that sentence:
C1–C4 are a tight cluster; order is **not** universal (free-air C5>C6;
cool-track C3>C4; some hot events go negative). Feature gain: compound
18.4%, tyre_life 16.8%, n_corners 10.5%, gap 8.9%. Temperature together
~14%. Gap matters as *selection*, not as the top splitter of a
fuel-corrected residual.

The overlay slopes (~0.13–0.17 on C1–C4) are several times G1.5's
0.08/0.05/0.03. Chained MAE **worse** at all three horizons (1.976 /
2.790 / 4.079 vs G1.1 1.861 / 2.444 / 2.790). Combined match-rate
**0.264** (23/87): loses to stay-out **and** to G1.5. 2025 alone is
below a never-box policy. **Not a default candidate.** Flag stays off.

---

## Scoreboard (same 87 scored inflections)

Always-stay-out is **0.276** (24/87). G1.5 is **0.322** (28/87).
Default-candidate rule: beat both.

| Attempt | 2024 | 2025 | Combined | vs stay-out | vs G1.5 | Chained MAE +5 / +10 / +20 |
|---|---|---|---|---|---|---|
| Stay-out | 0.250 (10/40) | 0.298 (14/47) | **0.276** (24/87) | — | — | — |
| **G1.5 (shipped)** | **0.325** (13/40) | **0.319** (15/47) | **0.322** (28/87) | beat | — | 1.861 / 2.444 / 2.790 (G1.1 path) |
| G2 unconstrained C-code | 0.225 (9/40) | 0.170 (8/47) | 0.195 (17/87) | lose | lose | 1.911 / 2.442 / 2.820 |
| G3 isotonic PAVA | 0.300 (12/40) | 0.298 (14/47) | 0.299 (26/87) | beat | lose | 1.913 / 2.383 / 2.957 |
| G4 pooled GBT | 0.300 (12/40) | 0.234 (11/47) | 0.264 (23/87) | lose | lose | 1.976 / 2.790 / 4.079 |

Position-delta (classified P5 after bias-cancel) was **never ≤ 0**. G1.5
**+2.96**; G3 **+2.88**; G4 **+3.48**. That metric is the lights-out
prewrite vs the team's actual pit schedule, not the mid-race inflection
ranking match-rate uses. Tyre-slope work is not a substitute for
diagnosing it (`docs/research-backlog.md`).

Zandvoort recommend identity is the E4.1 lock under G1.5 (Pit lap 33
HARD / Pit lap 30 HARD / Stay out) and moved under G2. What-if delta is
G1.4's **−11.92 s**, not E4.1's −13.00 s, because physics-delta stays.

---

## What this rules out

1. **"Just stop chaining residuals."** Done (G1.4). Necessary; not
   sufficient to make a fitted slope table beat the prior.
2. **"The C-codes were mislabelled."** Mapping is real (G2). Fitted
   C-code slopes are still not ordered. Shipping them made strategy
   worse.
3. **"Force the physical order."** PAVA does (G3). In the walk-forward
   era it erases compound identity. Beats stay-out; loses to G1.5.
4. **"Condition on weather, traffic, and corners."** Coverage is real
   (G4). Order returns at typical context. The finite-difference slopes
   are too steep and lose the walk. Not a candidate.
5. **"A fifth unconstrained variation on lap time."** The ceiling is
   mapped. Do not spend the week before Zandvoort on another one.

The one genuinely different idea that is still standing — **estimated
cornering load from speed + corner geometry**, a wear proxy that is not
the clocked lap — is scoped in
[`docs/future-research-cornering-load.md`](./future-research-cornering-load.md)
and is **not** being built before the event.

---

## Honest close

G1.5's globals are a physical prior that E3 already had to fall back to,
plus a rollout change that stopped the simulator inventing tens of
seconds of "SOFT is faster." Every more sophisticated attempt, evaluated
on the same races with the same gate, either lost to a never-box policy
or won against stay-out by less than G1.5 already does.

That is why the shipped default is locked, not left provisional.
Overlays stay behind `ARIS_TRUE_COMPOUND_SLOPES` (`1` / `isotonic` /
`pooled`) for research replay. Unset / `off` / unknown → G1.5.

Further reading: `docs/PHASE-G1-SUMMARY.md` … `docs/PHASE-G4-SUMMARY.md`,
`docs/how-recommend-works.md`, `docs/research-backlog.md`.
