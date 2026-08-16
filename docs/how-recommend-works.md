# How ARIS decides

This is the plain-language account of `recommend()` — the function behind the
Strategy page’s top-three cards. It is written for someone who will sit in on
an interview about this project, not for someone who will patch the code.

The shipped path (August 2026, before Zandvoort) uses **global tyre slopes**
(SOFT 0.08 / MEDIUM 0.05 / HARD 0.03 s per lap of tyre age) and a
**physics-delta rollout** inside the simulator. Fitted C-code overlays exist
in the repo but are **off unless you opt in**. That choice is deliberate: a
fitted overlay that ignored compound hardness order made the 2024+2025
walk-forward *worse* than always staying out.

---

## What it can see at a decision point

Every call is a snapshot of one driver, on one lap, with no future laps
visible. The snapshot (`RaceState`) carries:

| Input | What it is | Why it matters |
|---|---|---|
| **Position** | Field rank at this lap | Context for the engineer; not a hard constraint on the scorer |
| **Gap ahead / behind** | Seconds to the car in front and behind | A gap under ~22 s slightly favours pitting (undercut window, −0.3 s bonus). A gap under 1 s can also *trigger* a tactical prompt |
| **Compound + tyre life** | What is on the car, and how many laps it has done | The physics term: older tyres are slower, and SOFT is assumed to fall off faster than HARD |
| **Laps remaining** | Race distance left, including this lap | A pit with few laps left rarely pays back the ~18 s pit loss. SOFT stop candidates are dropped when fewer than 15 laps remain |
| **Recent pace** | Last two lap times, plus a 3-lap stint roll | Anchors the first simulated lap to what the car is actually doing right now |
| **Fuel** | Estimated from lap number / race distance | The car gets lighter; that is in the physics, not a separate “strategy lever” |
| **Track status** | Green / SC / VSC | SC-affected recent pace adds a confidence caveat; an SC lap also *triggers* a prompt |
| **Track** | Lap count, pit-loss, corners | Pit loss is a measured circuit constant. Tyre slopes are the global 0.08/0.05/0.03 unless an overlay is opted in |

It does **not** see: the other nine teams’ hidden strategies, tyre
temperatures, fuel in the tank as weighed, or a true C1–C6 label from the
timing feed (FastF1 only has SOFT/MEDIUM/HARD).

---

## When it speaks

`recommend()` is not on a timer. The live engine asks it when a **trigger**
fires:

- lap 1 (confirm the pre-race plan)
- tyre life crossing 25% / 50% / 75% of race distance
- the car ahead is inside the undercut window
- the gap ahead is under 1 s (tactical / line)
- safety car / VSC

The walk-forward scores a subset of those moments: pit / SC / compound
**inflections** in the real race, not every trigger.

---

## How candidates are built

It does not search every legal strategy. It scores a **fixed shortlist**:

1. **Stay out** on the current tyres.
2. **Pit now** for the default next compound (usually HARD).
3. **Pit in 1, 2, 3, 5, or 8 laps** for SOFT, MEDIUM, or HARD (SOFT skipped
   late in the race).
4. Two **two-stop sketches** (MEDIUM then HARD; SOFT then HARD) if those laps
   are still ahead.
5. **Lift** or **brake** earlier into turns 1, 7, and 10 — physics-backed
   line actions, not made-up DRS bonuses.

That is the whole menu. There is no tree search, no opponent model, and no
“what if they cover.”

---

## How a candidate is scored

Each candidate is run through `simulate()`:

1. **First remaining lap:** physics (bicycle + fuel + tyre slope) plus a
   damped residual that uses the *real* last lap times sitting on the
   snapshot.
2. **Every later lap:** only the **physics delta** — tyre degradation and
   fuel burn. The residual is not chained forward on fake laps. (That chained
   path used to invent tens of seconds of “SOFT is faster”; it was the reason
   the first walk lost to always-stay-out.)
3. **A pit** adds the circuit pit-loss once and resets tyre life to 1 on the
   new compound.
4. If the simulated stint runs past typical observed lengths (SOFT ~16 laps,
   MEDIUM ~32, HARD ~50), the ranking delta is **discounted** and a caveat is
   shown. That is not a claim of calibration out there; it is a warning.

The score is **seconds vs stay-out** (negative = faster). A tiny undercut
bonus can apply. Monte Carlo bands are for the live What-if card; the
walk-forward ranks on the deterministic number (`mc_draws=0`).

The top three cards are the three lowest scores, with **stay-out always
kept on the list** even when every pit looks better — so the engineer can
reject a pit push.

---

## What currently limits reliability

The honest bottleneck is **tyre degradation inferred from lap times alone**.

Lap time is not a tyre sensor. It mixes:

- real compound wear
- fuel burn (a car on HARD late in a stint is also lighter)
- traffic and dirty air
- **deliberate pace management** (drivers on HARD are systematically in
  cleaner air than drivers on SOFT — larger gaps, more free-air laps)
- Safety Car compressions, out-laps, traffic after a pit

When we re-keyed the fitter onto true Pirelli C-codes (C1–C6 within each
tyre generation), the fitted slopes were **still not ordered** C1 < C2 < …
C5. Constraining them to be ordered (isotonic / PAVA) forced the entire
2023–2025 generation onto **one number** — the data could not tell the
compounds apart. That is a data-quality result, not a tuning result.

So today the shipped model uses the **physical prior** (softer degrades
faster: 0.08 > 0.05 > 0.03) rather than pretending the lap-time fit has
identified C1 vs C5. `recommend()` will still prefer the compound the
simulator thinks is kindest. If those slopes are wrong, the cards are
rationally wrong.

What would actually change the ceiling: a degradation signal that is not
just stint-slope of dirty lap times — for example, a wear proxy that
conditions on traffic, or an order constraint that does not collapse every
compound to the same value. That work is gated and is **not** the Zandvoort
demo path.
