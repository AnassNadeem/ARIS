# Research backlog (post-event)

These items are documented, not scheduled. They came out of Phases G.1–G.4
and are separate from the Zandvoort demo path (G1.5 globals + G1.4
physics-delta). Do not treat this file as a commitment to change defaults.

---

## Position-delta root cause (separate from tyre degradation)

Walk-forward **match-rate** and **classified-P5 position-delta** answer different
questions. G1.5 beat always-stay-out on match-rate (aimed > 0.276 combined,
actual **0.322** = 28/87) while mean position-delta stayed positive (aimed ≤ 0,
actual **+2.96**). G3's isotonic overlay moved the combined delta only from
+2.96 to **+2.88** and still missed ≤ 0. Position-delta is scored from the
lights-out prewrite plan vs the team's actual pit schedule after bias-cancel,
not from the mid-race inflection ranking that match-rate uses. Physics-delta
changed which compound `recommend()` preferred at inflections; it did not
repair the opening-plan vs reality gap. Tyre-slope work (G2/G3/G4) is not a
substitute for diagnosing that lights-out / bias-cancel path.

---

## Wet-race strategy (currently unhandled)

`recommend()`'s candidate menu is dry (stay / pit SOFT-MEDIUM-HARD / two-stop
sketches / lift-brake). Walk-forward already excludes rainfall, wet compounds,
and red-flag inflections as `divergence_insufficient_info`. FastF1 C-code
mapping leaves INTERMEDIATE/WET as relative labels. There is no wet pit-loss
model, no intermediate cliff, and no “box for slicks as the track dries”
search. Shipping a dry slope table into a wet race would be a new error, not a
fix. This needs its own data path and a decision to score wet races at all.

---

## `physics_pred` absolute calibration debt

The bicycle + fuel + tyre term is a **shape** model. G1.2 measured
physics-only MAE ≈ **17.6–18.0 s** on 2024 held-out clean laps, with bias of
the same size — a near-constant offset, not a tyre-age slope. One-step
residual + real lags cancel it (HARD ≥25 bias **−0.003 s**). G1.4's
physics-delta rollout never re-uses the absolute `physics_pred` after the
first anchored lap, which is why chained residual compounding stopped
dominating strategy rank. Any future use of the raw bicycle number as an
absolute lap time (telemetry overlays, “predicted race time” clocks, new
residual features) still inherits that ~18 s offset. Calibrating the intercept
is unfinished on purpose; do not confuse “delta is usable” with “absolute
physics_pred is calibrated.”

---

## Monte Carlo interval calibration

Live What-if bands come from `aris.montecarlo` residual draws, re-expressed by
`mc_percentile_interval` / `mc_delta_interval`. Those helpers are **not**
split-conformal (the module says so). Locked E4.1 Zandvoort P10/P90 was
**−32.62 / −13.35 s**. After G1.4 physics-delta they moved to **−147.55 /
+29.33 s** and G2/G3 did not restore the lock. Walk-forward ranks on
`mc_draws=0` (deterministic), so the uncalibrated bands are a display-path
debt, not the match-rate number. Interval coverage vs held-out remaining-race
error has not been measured. Do not quote P10/P90 as a calibrated confidence
interval until that check exists.
