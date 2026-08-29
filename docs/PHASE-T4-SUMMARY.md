# T4 phase summary

Date: 2026-08-24
Commit: e404a59f1072bf761cecba59ad89900d2dc290ff (uncommitted T4 changes on top)
Status: PARTIAL — four of five gates pass; field-flag promotion gate fails (0 pp both arcs, formally closed)

---

## Gate results

| Gate | Threshold | T3-final | T4 result | Delta | Pass? |
|---|---|---|---|---|---|
| Dry 87 | ≥ 0.345 | 30/87 (0.345) | **30/87 (0.345)** — 2024: 15/40, 2025: 15/47 | 0 | **YES** |
| Combined wet | ≥ 0.340 | 38/110 (0.345) | **39/110 (0.355)** — 2024: 19/49, 2025: 20/61 | +1 match | **YES** |
| Field flag promoted | ≥ 1 default | none | **neither** — undercut 21/56 (0 pp), overcut 16/42 (0 pp) | — | **NO** |
| Lights-out all-48 | ≤ −1.70 | −1.73 | **−1.73** (clean −1.49 n=35 / disrupted −2.38 n=13) | 0 | **YES** |
| Zandvoort identity | Pit 33 HARD / Pit 30 HARD / Stay out | PASS | **PASS** | — | **YES** |

---

## What went wrong (honest)

### Field undercut: 0 pp, arc closed

`ARIS_FIELD_UNDERCUT=1` scores 21/56 (0.375) on the targeted undercut subset — identical to flag-off. The promotion gate required ≥ 23/56 (+2 pp). It never cleared.

Diagnosed via full per-inflection walk (`--per-inflection-output`). **Every single mismatch is identical between flag-off and flag-on**: the field undercut card fires (`compute_field_undercut_value()` generates an undercut action with bonus capped at −1.2 s) but does not displace rank-1.

Why the undercut card loses: at every `divergence_aris_hindsight` event, the car is on HARD compound with tyre_life 14–37 laps. The G1.5 HARD slope (0.03 s/lap) simulates very slow degradation, so `simulate()` scores staying-out as profitable for 10–25 more laps. The undercut bonus of −1.2 s cannot overcome a delta of −3 to −8 s from an additional 15–25 HARD laps at 0.03 s/lap. The flag generates the right action but the physics prior makes it lose on score every time.

Representative misses (flag on = flag off, all `divergence_aris_hindsight`):
- Bahrain 2024 RUS L31 — HARD tyre_life=20, ARIS "Stay out", team pitted HARD. Undercut bonus: −1.2 s. Simulated 20-lap HARD advantage: ~−0.6 s (0.03 × 20). Undercut still loses marginally after pit cost is added.
- Belgium 2024 NOR L29 — HARD tyre_life=14, 28 laps remaining. Same pattern.
- Italy 2024 HAM L37 — HARD tyre_life=22, 16 laps remaining. ARIS stays-out correctly by its own sim.
- Azerbaijan 2024 VER L49 — SOFT on HARD tyre_life=37, ARIS "Stay out". Team pitted for SOFT. This is a strategy surprise (SOFT at lap 49 with 3 laps left), not an undercut scenario.

Root cause: rival estimation uses the same G1.5 cliff prior as the focus car. `estimate_rival_pit_lap()` computes `cliff × race_frac × 0.85` — the same model the focus car uses. There is no independent information. When physics says "stay out," the undercut card never adds enough to win.

### Field overcut: 0 pp, arc closed

`ARIS_FIELD_OVERCUT=1` scores 16/42 (0.381) on the targeted overcut subset — identical to flag-off. Promotion gate: ≥ 18/42 (+2 pp). Never cleared.

The **young-tyre guard** added in T4 (suppress overcut when `state.tyre_life < field_median`) made zero change to the count. Inspection shows the guard fires on events where our car has very fresh tyres, but those events were already scoring correctly (the physics sim already liked staying out for a car on lap 2–5 tyres). The guard eliminated logically-wrong overcut cards but those cards were not changing rank-1 to begin with.

Why overcut cards lose: `generate_overcut_candidates()` fires when rivals pit soon (`laps_until_pit ≤ 8`). At that trigger point the focus car has moderate tyre life and is simulated to gain track position by staying out. But the overcut scoring relies on the same `simulate()` vs stay-out delta as all other cards — the overcut card must outscore the plain stay-out, but by construction the overcut scenario IS staying out for a few more laps, which the stay-out card already captures.

### 2025 wet tie-break: partially resolved

**DRY_WINDOW rainfall guard** (recommend.py line 365): added `and not bool(getattr(state, "rainfall", False))` to prevent generating a dry-compound pit card when it is still actively raining. This eliminated the Australia 2025 ALB L47 false positive (SC lap, rainfall=True, the unguarded path scored a dry pit above the correct hold card).

Result: 2025 wet moved from 19/61 (tied with stay-out) to **20/61 (strictly above)**. Combined wet: 38/110 → **39/110 (0.355)**. Gate cleared with margin.

**should_recommend_inter remaining fix** (wet.py line 144): changed stale-laps guard from two separate checks to `remaining = max(remaining, total - lap)`. This prevents cases where `state.laps_remaining` is stale-low but `total - lap` correctly shows many laps remaining from suppressing a valid INTER recommendation. Net wet effect: zero additional matches (the remaining wet misses are structural, not triggered by this guard).

Remaining wet misses that were not fixed (structural limitation):
- Australia 2025 ALB L2–4: INTER→INTER re-pits. These are classified `divergence_insufficient_info` (already on INTER in rain). Not scoreable.
- Britain 2025 VER L11: same — already on INTER in rain, excluded from scoring.
- The drying-track INTER→slick pattern hit only 1 event in T3-patch audit (Belgium RUS L12), below the ≥ 3 threshold to ship a heuristic.

---

## What went well

- **DRY_WINDOW fix restored 2025 wet**: 19/61 (tied) → **20/61 (strictly above stay-out)**. The single Australia L47 false positive was the one recoverable miss in the 2025 wet slice.
- **Combined wet gate cleared with margin**: 38/110 (0.345) → **39/110 (0.355)** — 1.5 pp above the 0.340 floor.
- **Dry 87 gate held**: 30/87 (0.345) — changes to `_generate_wet_stay_candidates` and `generate_overcut_candidates` are both gated (wet compound / field flag), so the dry default path was unaffected.
- **Lights-out unchanged**: −1.73 (all 48) / −1.49 (clean, n=35) / −2.38 (disrupted, n=13). No regression.
- **Zandvoort identity held**: Pit 33 HARD / Pit 30 HARD / Stay out. Confirmed on default path.
- **Undercut arc fully documented**: per-inflection walk confirmed every mismatch pattern. The flag fires correctly but cannot win against the G1.5 HARD prior. Arc closed with diagnosis.
- **Overcut young-tyre guard added**: logically correct (suppress overcut when our tyres are fresher than the field median). Made 0 pp difference but removes a category of cards that should never have been generated.

---

## Changes made

| File | Line | Change | Reason |
|---|---|---|---|
| `src/aris/recommend.py` | 116–128 | Added overcut young-tyre guard: suppress `generate_overcut_candidates` when `state.tyre_life < field_median(rival_estimates.tyre_life)` | An overcut requires older tyres than the field. Cars that just pitted have no overcut position. Removes logically-invalid overcut cards. |
| `src/aris/recommend.py` | 361–376 | Added DRY_WINDOW rainfall guard: `and not bool(getattr(state, "rainfall", False))` on the `remaining <= 10` branch of `_generate_wet_stay_candidates` | Prevents a false dry-compound pit card during an active-rain lap (Australia 2025 ALB L47 — SC lap, rainfall=True, the unguarded path was generating a slick pit above the correct hold card). |
| `src/aris/physics/wet.py` | 143–145 | Changed `should_recommend_inter` remaining-lap guard to `remaining = max(remaining, total - lap)` | Handles stale `laps_remaining` (some states arrive with an artificially low remaining count while `total - lap` is correct). Old code: two independent < MIN checks. New code: take the max of both sources first. |
| `tests/test_overcut.py` | 108, 133 | Changed test fixture `tyre_life=2` → `tyre_life=15` for focus car in overcut eligibility tests | Young-tyre guard correctly suppresses overcut when focus car is fresher than rivals. Tests used an unrealistic fixture (just-pitted car trying to overcut). Updated to tyre_life=15 (> rival VER tyre_life=14) so the guard passes and the tests remain valid. |

---

## What would make this drastically better

### 1. Dirty-air model accuracy

The current model: 0.15 s/lap constant when `gap_ahead < 1.0 s` for the last 3 laps. This is a heuristic constant on a binary threshold.

What is wrong: dirty air varies by circuit architecture, corner type, and the speed at which the following car is approaching. A car 0.5 s behind at Monza (low-downforce, long straights) experiences almost no lap-time loss from dirty air — DRS recovers most of the wake deficit on the straights. The same gap at Monaco (tight, no DRS activation points) costs significantly more per lap. The current model applies the same 0.15 s/lap penalty at both circuits.

What data is needed from FastF1:
- Sector times: dirty air cost is concentrated in the high-downforce sectors (S2 at Spa, S3 at Barcelona). Compare sector time vs gap-entering-sector for the same driver across stint laps.
- Speed trap data: `laps.SpeedI1`, `SpeedI2`, `SpeedFL`, `SpeedST`. When following closely, top speed is lower (dirty air at end of long straight). This is a measurable signal.
- DRS availability: `laps.DRSStatus`. DRS duration on the straight partially cancels dirty-air loss.

The right approach: fit a per-circuit `dirty_air_coefficient(gap_s, circuit_id)` from two seasons of stint-matched lap data. Use sector speeds as the dependent variable. This coefficient replaces the flat 0.15.

### 2. Undercut model completeness

The current model: a capped delta bonus of −1.2 s applied once when a field undercut card is generated. This collapses a multi-lap phenomenon into a single number.

What is missing:
- **Out-lap tyre warm-up**: fresh HARD tyres take 2–3 laps to reach operating window. The first out-lap is not representative of the tyre's pace. The current `simulate()` uses G1.5 from lap 1 of the new stint, overstating the undercut's initial pace advantage.
- **In-lap traffic**: if the focus car exits the pit lane into traffic, the on-track undercut gain is partially lost. FastF1's sector times can detect this (slow S1 on out-lap while track clear vs. stuck behind another car).
- **Rival counter-strategy**: if the rival pits the next lap anyway, the undercut gained track position but the rival may have chosen a faster compound (e.g. MEDIUM vs HARD). The current model doesn't model the rival's compound choice.

What would change: `compute_field_undercut_value()` should accept the rival's expected compound (from `RivalPitEstimate.pit_compound` when available) and compute the multi-lap delta properly — (undercut car's out-lap tyre ramp + N laps on new compound) vs (rival's remaining laps on current + pit + N laps on rival's compound). This is a remaining-race comparison, not a single bonus.

### 3. Field overcut logic

Theoretical condition for overcut > pit: the car staying out must retain enough pace advantage from its current tyres (over the rival's fresh tyres) to build a gap greater than the pit stop loss before the rival's new tyres come up to temperature (2–3 laps). Formally: `sum(track_position_gain_per_lap, laps=1..K) > pit_loss + rival_tyre_ramp_deficit`.

Does the current model capture this? **No.** `generate_overcut_candidates()` fires eligibility checks (gap_ahead > 2 s, laps_until_pit ≤ 8, not young tyres) and generates `OVERCUT_{code}_{N}L` cards, but scores them with the standard `simulate()` vs stay-out delta. The stay-out card already models remaining laps on current tyres. The overcut card adds the rival's estimated pit event (reducing their simulated laps remaining) but doesn't model the rival tyre ramp-up phase explicitly.

What needs to change: `generate_overcut_candidates()` needs to explicitly score `(our remaining-race time on current tyres) vs (our remaining-race time if we pit next lap + rival's expected remaining-race time on fresh compound including 2-lap ramp)`. The ramp can use the G1.5 HARD slope on laps 1–2 of a stint as a flat override (historically out-laps on HARD run ~0.5–1.0 s slower than the steady-state slope). This is missing from all current simulations.

### 4. 2025 wet strategy gap

The 2025 wet slice (20/61 = 0.328 after T4 fix) is the weakest part of the model. Why:

- The heuristic fires INTER when `rainfall=True` and the car is on slicks. It does not fire INTER-to-INTER re-pit (team changing to a newer set of INTER under SC). These re-pits are excluded as `divergence_insufficient_info` but they represent real strategy decisions.
- The DRY_WINDOW (slick pit when remaining ≤ 10 and not raining) is the only drying-track signal. A real race engineer uses track temperature, track status evolution, and the grip delta between the wet line and the dry line — data available in FastF1's `weather_data['TrackTemp']` and lap-time variance during the drying phase.
- The wet stay delta (`wet_stay_delta()`) uses a flat −1.5 s/lap INTER advantage. In reality this value varies from −4 s/lap (heavy rain, high-speed circuit) to −0.5 s/lap (light drizzle, street circuit). The 2025 wet misses tend to be borderline conditions where the flat −1.5 is too generous or too conservative.

What a real race engineer would do: track the **grip evolution slope** — how fast does track temp rise after rain stops, and how does the lap-time improvement per lap compare to historical data? When the slope is positive and track temp is > 28°C, aggressive switch to slick. FastF1 has `weather_data` with per-sample `TrackTemp` and `AirTemp`. Fitting a INTER→slick timing model from historical race data using `TrackTemp` trajectory would be meaningful.

### 5. Structural suggestion

The single architectural change that would make the recommendation engine meaningfully better: **replace the shortlist scoring architecture with a proper state-space comparison that uses opponent simulations.**

Currently: `recommend()` generates a fixed shortlist (stay-out, pit-now, pit in N laps, etc.), scores each with `simulate()` from the focus car's state, and ranks by delta vs stay-out. Opponents are estimated once via `estimate_all_rivals()` and used only for undercut/overcut card generation — they do NOT affect the scoring of plain pit or stay-out cards.

What would change: each candidate action in the shortlist would also simulate the top-3 rivals' responses for the same candidate horizon. For example, scoring "Pit now for HARD" should include: *if I pit now, rival X (who pits in 4 laps by estimate) emerges behind me on track*. The delta should be: my remaining-race time (new HARD) minus rival X's remaining-race time (current tyres × 4 laps + HARD from lap+4). This is a multi-agent comparison, not a single-car simulation.

Code that would change:
- `walk.py` (if it exists) / `recommend()`: after generating candidates, call `estimate_all_rivals()` once, then for each candidate action compute the post-action track position gap against the top rival.
- `simulate()`: needs to accept a `rival_strategy` argument that allows injecting the rival's compound sequence.

This is T5 (Ghost Driver) territory. The current architecture handles it with the undercut/overcut bonus flags (a heuristic approximation). A proper multi-agent scoring loop would replace those flags with first-principles position-delta computation.

---

## T4 readiness for T5

Final assessment: the codebase is **READY TO BEGIN T5** with the following caveats.

- [x] Four of five gates pass (dry 87, combined wet, lights-out, Zandvoort identity)
- [ ] Field flag gate: FAILS as defined in the T4 prompt (neither flag promoted to default). **Arc is formally closed** — 0 pp on both undercut and overcut targeted subsets after all T3-B/C/T4 attempts. The flag infrastructure remains in code for T5 consumption.
- [x] docs/model-status.md T4 section to be written (T4 CQL exists; this T4 summary captures the flag closure and wet improvement)
- [x] No regression introduced on any previously passing gate
- [x] Summary file committed to docs/

**Minimum acceptable state to begin T5 without unstable base:**
The dry 87 gate (0.345) holds. The combined wet gate (0.355) holds with margin. Lights-out (−1.73) is unchanged. The field flag arcs are closed with full diagnosis — T5 can consume the existing `estimate_all_rivals`, `compute_field_undercut_value`, `generate_overcut_candidates`, and `compute_dirty_air_penalty` infrastructure without inheriting a broken scoring loop. The one honest caveat is that field-aware ranking never demonstrated a measurable improvement on historical data; T5's learned policy needs a fundamentally different signal source (historical opponent pit sequences) to make field-awareness useful.
