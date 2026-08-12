# Phase E.1b summary — Zandvoort tyre-deg fuel patch

Executed 2026-08-12. Scope was **only** Zandvoort / Netherlands (Blocks E1b.1–E1b.6).
No Phase E.2 circuit regression work was started.

---

## Verdict (read this first)

**If the race started tonight, is this ready to demo?**

**Yes — with eyes open, and slightly more honest about tyres than E.1.**
Strategy pipeline, sprint ingest, pit_loss 18.5 s, and runbook still stand.
Fuel correction confirmed E.1’s SOFT/MEDIUM slopes were confounded, but the
corrected fit still failed the SOFT > MEDIUM > HARD sanity check, so Zandvoort
now ships **global compound slopes** (0.08 / 0.05 / 0.03) rather than a second
wrong track override. Held-out blended MAE returns to the pre-E.1-tyre numbers
(**0.634 s / 0.673 s**) — worse than E.1’s empirical 0.558 / 0.591, but those
gains came from understated SOFT/MEDIUM deg that failed physical ordering.

Live tyre YAML writes are **log-only by default**; SC/VSC recent-pace caveats
are wired into recommendations/narration.

---

## Block E1b.1 — Fuel-burn confound diagnosis

**Finding (no code changes):** `DegSlope` is fit on **raw** lap time vs tyre life.

`compute_stint_metrics` does:

```python
slope, _ = np.polyfit(fit["TyreLife"], fit["LapTimeS"], 1)
```

There is **no** pre-fit correction for fuel burn. The fuel-burn pace effect used
elsewhere lives in `aris.physics.bicycle.FUEL_PENALTY_S_PER_KG` (0.03 s/kg) with
burn schedule `estimate_fuel_kg` (110 kg start, 1.7 kg/lap) in
`aris.models.features` — i.e. ~0.051 s/lap of lightening that masquerades as
“negative degradation” when left in the raw slope.

**Why E.1 SOFT/MEDIUM looked absurdly soft:** raw DegSlope ≈ true_deg − fuel_benefit.
SOFT (0.0128) and MEDIUM (0.0029) sat far below globals (0.08 / 0.05) while HARD
(0.0322) stayed near its global 0.03 — consistent with a fuel confound that
partially cancels true deg, especially on earlier / fuller-tank stints, while
late HARD stints can hit the empty-tank floor and look “steeper.”

**Checkpoint:** full suite green (exit 0; ~134 tests at E.1 baseline).

---

## Block E1b.2 — Fuel-corrected refit

Race sessions only: before `compute_stint_metrics`,

`LapTimeS -= FUEL_PENALTY_S_PER_KG * estimate_fuel_kg(LapNumber, total_laps)`.

Practice / sprint left raw (no race fuel schedule).

### Slopes

| Compound | E.1 shipped (uncorrected) | E1b fuel-corrected fit | Shipped after sanity |
|---|---:|---:|---:|
| SOFT | 0.0128 | **0.0601** | **0.08** (global fallback) |
| MEDIUM | 0.0029 | **0.0563** | **0.05** (global fallback) |
| HARD | 0.0322 | **0.0765** | **0.03** (global fallback) |

Fuel correction moved SOFT/MEDIUM near the globals (strong evidence the confound
was real). Ordering after correction: SOFT (0.0601) ≳ MEDIUM (0.0563) but HARD
(0.0765) is **highest** — still wrong vs real F1. Per phase rule: **did not force
ordering**; fell back to `DEFAULT_COMPOUND_SLOPE` in `netherlands.yaml`.

Fitted-pre-sanity values are recorded under
`source.compound_slopes_fitted_pre_sanity` for audit.

**Checkpoint:** suite green.

---

## Block E1b.3 — Re-validate (2024 + 2025)

Same scorer as E1.1/E1.2 (`scripts/_e1_score_zandvoort.py`).

| Race | Mode | E.1 shipped (empirical slopes) | After E1b (global fallback) |
|---|---|---:|---:|
| 2024 NL | Physics-only | 18.119 | **18.363** |
| 2024 NL | Physics+residual | 0.833 | **0.975** |
| 2024 NL | Blended | 0.558 | **0.634** |
| 2025 NL | Physics-only | 18.605 | **18.930** |
| 2025 NL | Physics+residual | 0.861 | **0.996** |
| 2025 NL | Blended | 0.591 | **0.673** |

**Worse than E.1’s empirical overrides** — expected, and useful: those MAE gains
came with physically inverted compound ordering. Falling back to globals restores
the Phase D / pre-override baseline that the residual was trained against.

**Checkpoint:** suite green.

---

## Block E1b.4 — Residual refresh

**Skipped.** After the ordering fallback, Zandvoort slopes are again the same
globals the residual artefact was trained with, so rebuilding
`physics_pred` for NL races would be a no-op for the tyre term. A full corpus
rebuild/refit is Phase E.2 work and was not worth the deadline risk here.
Current residual artefact kept unchanged.

---

## Block E1b.5 — Live-write policy

Confirmed default is **observe/log only**:

- `scripts/fit_zandvoort_tire_slopes.py`: YAML write requires `--write`.
- During event window **2026-08-21 … 2026-08-23**, `--write` alone is refused;
  `--allow-live-write` is also required.
- `docs/zandvoort-weekend-runbook.md` states this policy plainly and no longer
  suggests mid-weekend YAML overwrites under normal ops.

---

## Block E1b.6 — SC/VSC caveat

**Reached (lightweight).**

- `RaceState.recent_sc_pace` / `confidence_caveat` set when the current lap or
  the 1–2 prior laps feeding lag pace have FastF1 TrackStatus containing SC/VSC
  codes (`4` / `6` / `7`, including multi-codes like `24`).
- `recommend()` attaches the caveat to `evidence` and `narration_context`.
- Fallback narration appends:
  `Note: based on Safety Car-affected recent pace — lower confidence.`
- Unit tests in `tests/test_sc_pace_caveat.py`.

This is a flag + string, not a full SC-aware predictor redesign. Deeper
SC-contaminated What-if lag handling remains a Phase E.2 item.

---

## Phase E.2 notes (noticed, not fixed)

- Fuel-corrected Zandvoort HARD still degrades faster than SOFT in the pooled
  fit — needs calendar-wide / hierarchical deg work, not another Zandvoort hack.
- Residual retrain with per-track slopes where they exist (deferred).
- Broader SC/VSC lag scrubbing beyond the caveat string (deferred).
- Calendar-wide MAE problems from Phase D / E.1 summary (Japan, Canada, …).

---

## Test suite

Docker Postgres up; `ARIS_DB_URL` set.

| Checkpoint | Result |
|---|---|
| After E1b.1 | green |
| After E1b.2 | green |
| After E1b.3 | green |
| After E1b.5/E1b.6 | green |
| **End of Phase E.1b** | **136 passed**, 0 failed |

---

## Files created / modified (high level)

### Created
| File | Reason |
|---|---|
| `docs/PHASE-E1b-SUMMARY.md` | This summary |
| `tests/test_sc_pace_caveat.py` | SC/VSC caveat unit tests |

### Modified
| File | Reason |
|---|---|
| `scripts/fit_zandvoort_tire_slopes.py` | Fuel-detrend Race DegSlope; ordering fallback; event-window write gate |
| `data/tracks/netherlands.yaml` | `compound_slopes` → globals; audit fields for failed fuel-corrected fit |
| `docs/zandvoort-weekend-runbook.md` | Log-only live-write policy |
| `src/aris/state.py` | `recent_sc_pace` / `confidence_caveat` |
| `src/aris/recommend.py` | Surface caveat on recommendations |
| `src/aris/narrate.py` | Append caveat in radio fallback / LLM prompt |

---

## Stop

Phase E.1b is complete. **No Phase E.2 (or later) work will start until you say so.**
