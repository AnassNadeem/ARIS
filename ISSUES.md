# Phase 0 — triage (investigation only)

Baseline recorded before instrumentation. TEMP-DEBUG-PHASE0 prints remain in source for Phase 1 strip-out.

> **Status update (2026-08-31, full-spec pass):** Bugs 1–5 below are now fixed.
> Bug 1 fixed in `src/aris/ghost.py::score_parallel_ghost` by anchoring the
> ghost's ranked cumulative time to the focus driver's actual telemetry
> cumulative time (`field_cum_by_lap`) offset by the model's cumulative
> *delta*, instead of ranking a raw cold-start absolute model prediction
> against measured field times. Bugs 2 (extra pit stops / wet oscillation)
> and 4–5 (Copilot/Ask gap-to-X and citation leaks) were already fixed in a
> later phase without this file being updated — verified against current
> `src/aris/recommend.py` (`_one_stop_covers_remaining`, `_inter_rain_confirmed`),
> `src/aris/copilot/agent.py`, and `src/aris/ask/grounded.py`
> (`_lookup_classified_result` / `_compose_results`). Bug 3 (tower tyre age)
> needs a fresh repro against current `backend/live.py` before it can be
> closed — not re-verified in this pass.
>
> Also found and fixed in this pass (not part of the original Bug 1–5 list):
> a frontend regression where `useArisRecommendLoop`'s `force` flag (set on
> every `arisDriver` change, including the initial pre-race selection) bypassed
> the "ghost already follows the selected pre-race plan" guard, firing an
> independent lights-out `recommend()` at lap 1 that could immediately
> contradict — and, once Auto-mode auto-adopt was added, silently overwrite —
> the strategy the user just picked. Fixed in `frontend-next/lib/useArisRecommendLoop.ts`.

---

## Bug 1: Ghost car doesn't start at the same position as the chosen driver
**Symptom:** At lap 1, the ghost’s timing-tower slot (and therefore map rank) does not match the real driver’s grid / lap-1 classified position.
**Repro steps:** (exact driver / race / query used)
1. Load the committed Zandvoort 2025 VER explain fixture (`tests/fixtures/explain_zandvoort.py`).
2. Call `get_ghost_vs_real("VER", "2025-15-R")`.
3. Compare lap-1 `real["position"]` vs `ghost["position"]` / tick `ghost_position`.
**Files/functions involved:**
- `src/aris/explain/ghost.py` (`_compute_ghost_vs_real`, `_rank_and_gap`)
- `src/aris/ghost.py` (`create_ghost_from_plan`, `score_parallel_ghost`, `_rank_ghost_in_field`)
- `backend/live.py` (`_ghost_on_track`) — map path uses delta, not this rank
**Root cause:** Ghost rank at lap 1 is **not** the seeded grid/classified position. `create_ghost_from_plan` correctly seeds `ghost_position` from `race_state.position` (P1 for VER in this fixture). `score_parallel_ghost` then ranks the ghost by **simulated** cumulative lap time against the **classified FastF1/fixture field times**. `simulate(STAY_OUT)` on lap 1 produced 97.504s vs the field’s ~74.0–74.35s, so the ghost is inserted as P3 while the real car is P1. `ghost_cumulative_delta` stayed 0.0 (same-compound vs real sim), so the map offset path would still sit on the real car; the tower uses the ranked P3.
**Evidence:** TEMP-DEBUG-PHASE0 on 2025-15-R VER:
```
create_ghost_from_plan driver VER seed_position 1 seed_or_1 1 pit_laps [9]
ghost lap 1 real_pos 1 ghost_pos 3 ghost_lap_s 97.504 ghost_cum 97.504 delta 0.0
field_lead_times [(74.18, 'NOR'), (74.35, 'PIA')]
ghost_vs_real L1 real_pos 1 L1 ghost_pos 3 L1 real_time 74.0 L1 ghost_time 97.504
```
**Confidence:** High
**Notes for fix phase:** Rank the ghost in the same time base as the field (classified or all-simulated), or apply the known simulate intercept before `_rank_ghost_in_field`. Do not treat the `or 10` fallback as the lap-1 bug unless position is actually missing from the row.

---

## Bug 2: Ghost / ARIS takes more pit stops than necessary
**Symptom:** Over a replay, the ghost pits more times (or far earlier) than the real one-stop that the race needed.
**Repro steps:** (exact driver / race / query used)
1. Lights-out `recommend()` on VER, Netherlands, lap 1, 72 total laps, MEDIUM, DRY (typical Zandvoort race length).
2. Contrast with fixture race (`zandvoort_2025_bundle`, 32 laps): real pit lap 20 vs ghost pit lap 9.
3. Wet/damp check: same VER lap-25 state with `track_state=DAMP`, `rainfall=True`, `tyre_life=18`.
**Files/functions involved:**
- `src/aris/recommend.py` (`_candidate_actions` two-stop templates; wet INTER cards when `should_recommend_inter`)
- `src/aris/ghost.py` (`schedule_from_recommendation` copies `action.pit_laps` onto the ghost)
- `src/aris/physics/wet.py` (`should_recommend_inter`) — related, not the dry extra-stop generator
- `src/aris/fsm.py` — **does not choose pits**; only scales pit loss
**Root cause:** Two separate triggers, confirmed not the same code path:
1. **Dry extra stops (main ghost plan):** `_candidate_actions` always injects two hardcoded two-stop plans (`[mid, total-8] MEDIUM/HARD` and `[mid-5, mid+10] SOFT/HARD`). On a 72-lap lights-out call those cards win (`Plan: L31->SOFT, L46->HARD`, delta −112s vs stay-out). The ghost then follows **two** stops. A real Zandvoort-style race is typically one stop. `fsm.py` is not the decision maker.
2. **Wet/damp INTER (oscillation, linked but distinct):** When `rainfall=True` on DAMP, top card becomes `Pit now for INTERMEDIATE` (`wet_heuristic=True`, delta −52s). Same DAMP state with `rainfall=False` stays on a dry `Pit lap 33 for HARD`. A flickering FastF1 rainfall boolean will flip PIT-INTER vs dry pit without needing a second bug.
**Evidence:**
```
# 72-lap lights-out VER
recommend_top label Plan: L31->SOFT, L46->HARD kind stay_out pit_laps [31, 46] delta -112.24
# fixture 32-lap VER vs real
REAL_PITS [20] GHOST_PITS [9]
# DAMP + rain
recommend_top label Pit now for INTERMEDIATE wet_heuristic True rainfall True
# DAMP, no rain
recommend_top label Pit lap 33 for HARD wet_heuristic False rainfall False
```
**Confidence:** High
**Notes for fix phase:** Stop treating two-stop templates as default-scored equals of one-stop physics; gate or penalize extra stops vs remaining laps / compounds used. Separately, debounce INTER on boolean rainfall / DAMP so a damp-not-wet track cannot win `PIT_NOW INTERMEDIATE`. Do not change FSM thresholds for this.

---

## Bug 3: Tire age on the timing tower is glitched
**Symptom:** Tower Age column does not track laps on the current tyre (stuck / wrong vs FastF1 `TyreLife`).
**Repro steps:** (exact driver / race / query used)
1. Call `backend.live._timing_rows_from_payload` with VER lap 15, lap payload `tyre_life=15`, stint `lap_start=1`, `tyre_age_at_start=1`.
2. Read `LiveTimingRow.tyre_life` (this is what `mapTimingAndPositions` → `TimingTower` renders as Age).
**Files/functions involved:**
- `backend/live.py` (`_timing_rows_from_payload`, `_stints_at`)
- `backend/sessions.py` (stint pack: `tyre_age_at_start` frozen at first stint lap)
- `frontend-next/lib/mapCars.ts` (`tyre_life: row.tyre_life ?? 0`)
- `frontend-next/components/panels/TimingTower.tsx` (`car.tyre_life`)
- `src/aris/state.py` `build_race_state()` / `_build_stints_dict` — **not on this hop**
**Root cause:** Replay/live tower age is `stint["tyre_age_at_start"]` only. It never adds `(current_lap - lap_start)`. The per-lap `tyre_life` already present on the lap row is ignored. The T6 note “stints not populated in `build_race_state()`” is **not** this bug: T7 already fills `RaceState.stints` for rival compound inference; that dict is unused by the tower.
**Evidence:**
```
HOP source_lap.tyre_life=15 stint.tyre_age_at_start=1 tower.tyre_life= 1 lap_number 15
TEMP-DEBUG-PHASE0 timing_tyre_life [{'code': 'VER', 'lap': 15, 'tyre_life': 1, 'stint': 1, 'compound': 'M'}]
stint_of_ages {1: (1, 1)}
```
Postgres `test_stints_populated_in_race_state` failed in the baseline run with SQLAlchemy (no DB), not with empty stints — so that test could not be used as UI evidence.
**Confidence:** High
**Notes for fix phase:** Set tower age from lap `tyre_life` when present, else `tyre_age_at_start + (lap - lap_start)`. Leave `build_race_state().stints` alone unless recommend/undercut still misreads it.

---

## Bug 4: Copilot gives inaccurate "gap to leader" answers
**Symptom:** Ask/Copilot gap numbers do not match what the user means (or go `gap n/a`) compared with the timing tower.
**Repro steps:** (exact driver / race / query used)
1. Zandvoort copilot fixture field: VER P1 +0.0s, NOR P2 +1.8s, PIA P3 +3.1s (tower-equivalent snapshot).
2. As **PIA**, query `What's the gap to NOR?`
3. As VER with **empty field** and `state.gap_to_leader_s=None` (FastF1 `build_race_state_from_fastf1_session` shape), query `What's the gap to the leader?`
**Files/functions involved:**
- `src/aris/copilot/agent.py` (`_heuristic_plan` → `get_gap` on the first driver token)
- `src/aris/copilot/tools.py` (`tool_get_gap`)
- `backend/aris_api.py` (`copilot_chat`, `_load_chat_field`, `_load_chat_field_from_fastf1`, `build_race_state_from_fastf1_session`)
- Tower path: `backend/live.py` `_timing_rows_from_payload` (OpenF1/pack **intervals**); Copilot `_timing_rows` uses `replay_timing` → `gap_history` (summed lap times) when not live
**Root cause:** When the Copilot field **is** the same snapshot as the tower, `get_gap` copies that snapshot faithfully (VER +0.0, NOR +1.8 — matches). The inaccurate answers come from **what it chooses to return**, not from a bad subtract on that fixture:
1. `"What's the gap to NOR?"` binds `get_gap(driver=NOR)` and narrates **NOR’s gap to the leader (1.8s)**. From PIA the tower-relevant interval is **PIA−NOR = 1.3s**. The model logged `asked NOR ... gap_leader 1.8` while `state_driver PIA` / `state_gap 3.1`.
2. FastF1-built `RaceState` leaves `gap_to_leader_s=None` (never computed). Empty field → `VER is P1, gap n/a.`
A live HTTP tower vs Copilot on the same replay clock was **not** run here (no FastF1 cache / no API server in this pass). Interval-sample gaps vs `gap_history` cumulative race time remain a plausible second mismatch when both paths are populated.
**Evidence:**
```
TEMP-DEBUG-PHASE0 get_gap asked NOR state_driver PIA lap 25 pos 2 gap_leader 1.8 state_gap 3.1
PIA->NOR response: NOR is P2, +1.8s to leader. PIA is 1.3s behind on HARD (24 laps).
implied PIA-NOR 1.3
empty field: gap_leader None → "VER is P1, gap n/a."
```
**Confidence:** Medium (High for the named-driver / missing-state cases; Medium for live-interval vs Copilot `gap_history` until a same-clock replay is logged)
**Notes for fix phase:** For “gap to X”, return focus-to-X (difference of gaps or `interval`) and say so. Fill `gap_to_leader_s` on the FastF1 state path. Optionally inject the current replay frame’s timing rows into `CopilotContext.field` so Copilot and the tower share one snapshot.

---

## Bug 5: Copilot dumps raw internal doc citations instead of natural language
**Symptom:** Questions like “who is the leader” / “who won here last year” return markdown from internal docs plus `Cite: chunk_id` (or Ask `Cited: concept file | FIA article…`).
**Repro steps:** (exact driver / race / query used)
1. `pytest tests/test_ask_grounding.py` on HEAD (expected-by-brief: 4 citation-format failures).
2. Copilot `use_llm=False`, Zandvoort context: `who is the leader`, `who won here last year`.
3. Ask index (fixture dirs): same two questions plus `Who won the 2024 Netherlands race?`
**Files/functions involved:**
- `src/aris/copilot/agent.py` (`_heuristic_plan`, `generate_response`, `_pick_cite`)
- `src/aris/ask/grounded.py` (`_compose`, `_cited_block`, `_concept_answer`)
**Root cause:** Two related leaks; **not** the four Ask grounding unit tests (those **pass** on HEAD).
1. **Copilot (live symptom):** `_heuristic_plan` does not map “who is the leader” / “who won last year” to `get_gap` or a results tool. `parts` stays empty, so `generate_response` always appends the top retrieved chunk **verbatim** (including `#` headings) plus `Cite: {chunk_id}`. Observed chunks: `aris_doc:how-recommend-works:how-aris-decides`, `aris_doc:model-status:tier-2-2026-08-20`.
2. **Ask (same class of leak):** “who won here last year” retrieves a **concept** FIA tyre doc and returns that markdown plus `Cited: concept dry-tyres-fia.md | …`. “Who won the 2024 Netherlands race?” retrieves **SAR P16**, not the winner, plus a `Cited:` classified-result line. Grounding tests only cover **logged decision** questions and require `Cited:` to be present — they do not fail on citation formatting.
**Evidence:**
- Baseline pytest: `tests/test_ask_grounding.py ...` **3 passed** (not 4 failed).
- Copilot:
```
TEMP-DEBUG-PHASE0 copilot_cite_leak question who is the leader chunk_id aris_doc:how-recommend-works:how-aris-decides parts_before_cite 0
response: # How ARIS decides ... Cite: aris_doc:how-recommend-works:how-aris-decides.
TEMP-DEBUG-PHASE0 copilot_cite_leak question who won here last year chunk_id aris_doc:model-status:tier-2-2026-08-20 parts_before_cite 0
```
- Ask: `who won here last year` → FIA dry-tyre markdown + `Cited: concept dry-tyres-fia.md | FIA 2025 ... Article 30.1a)i)`
**Confidence:** High
**Notes for fix phase:** Plan tools for leader/winner/gap questions; only attach `Cite:` / retrieved markdown for methodology/FIA prompts. Strip heading/table dumps from user-facing text. Do not “fix” Ask grounding tests by relaxing `Cited:` — they are already green; the live leak is untested.

---

## Baseline (pre-instrumentation)

| Suite | Result |
|---|---|
| `pytest tests -v` | **5 failed, 650 passed, 1 xfailed, 3 errors** in 196s |
| `frontend-next` `vitest run` | **55 passed** (7 files) |

Failures/errors were SQLAlchemy/Postgres (`tests/test_db.py` ×2, `tests/test_ingest.py` ×1 fail + 3 errors, `tests/test_integration.py` stints tests ×2). Ask grounding was green. `test_conformal.py::test_coverage_on_2025` xfailed as documented.
