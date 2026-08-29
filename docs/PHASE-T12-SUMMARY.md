# T12 phase summary — Explainability Dashboard + Debrief

Date: 2026-08-26
Commit: e404a59 (working tree; T12 not committed)
Status: **COMPLETE**

Explainability is a read-only dashboard over existing search internals. `recommend()` and `simulate()` are unchanged. Charts call those functions; they do not retune them.

## Changes

- Exposed degradation curve, ghost vs real, and race debrief data via `src/aris/explain/` and `GET /api/explain/{degradation,ghost,debrief}`.
- Added **Explain** tab in the pit-wall console (`frontend-next`) with three sub-tabs: Degradation Curves, Ghost vs Real, Race Debrief.
- Reused existing UI (flexlayout catalogue, driver picker, Recharts, Copilot-style top-3 table). Dev toggle: on unless `NODE_ENV=production`; force with `NEXT_PUBLIC_ARIS_EXPLAIN=1`, disable with `=0`.
- Optional debrief export: `GET /api/explain/debrief?format=parquet` (CSV fallback if pyarrow is missing).
- Added backend tests. Frontend typecheck (`tsc --noEmit`) is clean; no Playwright runner in this package.

## Metrics

| Gate | Threshold | Result | Pass? |
|---|---|---|---|
| Backend explain tests | 8/8 | **8/8** pytest | YES |
| Zandvoort identity | Pit 33 HARD / Pit 30 HARD / Stay out | **PASS** (untouched) | YES |
| Copilot tools | no regression | **PASS** (`test_each_tool_returns_without_error`) | YES |
| Frontend typecheck | `tsc --noEmit` | **PASS** | YES |
| Complete race debrief | timeline + deg + ghost + decisions | **YES** (Zandvoort 2025 VER fixture; live FastF1 when session cache is warm) | YES |

Tests: `tests/test_degradation_curve.py`, `tests/test_ghost_vs_real.py`, `tests/test_race_debrief.py`, `tests/test_explain_api.py` (**8 passed**).

## Example views

- Degradation Curves: VER, Zandvoort 2025, stint 1 — predicted (bicycle slope + warmup + out-lap + fuel delta) vs actual (fuel-adjusted FastF1 − fresh baseline).
- Ghost vs Real: VER, Zandvoort 2025 — `recommend()` pit schedule rolled through `simulate(..., lap_times_out=)` vs classified lap times; position and gap to leader.
- Race Debrief: Zandvoort 2025 — pit stops, SC/VSC from TrackStatus, rain from weather `Rainfall`, key decisions with `recommend()` top-3 and `narrate_recommendation(use_llm=False)`.

## Honest limits

- Tests inject a FastF1-shaped Zandvoort 2025 VER bundle so CI does not download a session. Production loads via `backend.sessions` (same FastF1 cache as the rest of the console).
- Ghost remaining-race times are the bicycle/simulate path, not a full field Monte Carlo. Position is cumulative-time rank against the classified field.
- Debrief explanations are template narration unless Copilot LLM is on elsewhere; T12 does not turn `ARIS_COPILOT_LLM` on.
- Pit-wall UI was not browser-walked in this pass (no browser tool in session). Charts typecheck and mock-fallback when the API is down.

## Readiness for Placement Pack

- [x] Explainability Dashboard stable enough for a demo (dev default on; mock fallback if API cold).
- [x] No regressions in Zandvoort identity or Copilot tool smoke.
- [x] Placement pack can reference T12 as the “final polish” layer (deg curves, ghost vs real, debrief with top-3).

## Files

- `src/aris/explain/degradation.py` — predicted vs actual deg curve
- `src/aris/explain/ghost.py` — ghost vs real (calls `recommend()` / `simulate()` as-is)
- `src/aris/explain/debrief.py` — timeline + decisions
- `src/aris/explain/session.py` — session_id parse + FastF1/backend load + test override
- `src/aris/schemas.py` — `DegradationCurveResponse`, `GhostVsRealResponse`, `RaceDebriefResponse`
- `backend/main.py` / `backend/aris_api.py` — `/api/explain/*`
- `frontend-next/components/aris/ExplainPanel.tsx` — Explain tab
- `frontend-next/components/aris/DegradationChart.tsx`
- `frontend-next/components/aris/GhostVsRealChart.tsx`
- `frontend-next/components/aris/RaceDebriefView.tsx`
- `docs/PHASE-T11-SUMMARY.md` — T11 context
