# T11 phase summary — Copilot (LLM Narrator + Tool‑Caller + Hybrid Retrieval)

Date: 2026-08-26
Commit: e404a59 (working tree; T11 not committed)
Status: **COMPLETE**

Copilot is a narrator and tool-caller only. `recommend()` and `simulate()` are unchanged. Race math always goes through existing ARIS functions.

## Changes

- Defined JSON tool schemas and `execute_tool()` in `src/aris/copilot/` (gap, undercut window, deg slope, simulate, recommend, SC risk, wet state, MC compare, driver style, circuit info). RaceState is injected; the LLM never sends it.
- Hybrid retrieval over FIA paraphrases (`data/regs/`), driver/track priors (`data/priors/`), and ARIS docs (T9–T10, model-status, how-recommend-works): hashing dense vectors + BM25, RRF fusion, heuristic re-rank, query rewrite. `sentence-transformers` MiniLM / cross-encoder are opt-in (`ARIS_COPILOT_ST=1`, `ARIS_COPILOT_CE=1`), not required for the gate.
- Agent loop: rewrite → retrieve → plan tools (heuristic, optional LLM JSON) → execute → ≤150-word answer with citations and top-3 when `recommend()` ran.
- Pit-wall **Copilot** tab in ARIS Comms (`frontend-next/components/aris/CopilotPanel.tsx`) with Approve / Deny / Alter / Explain. Dev toggle: on unless `NODE_ENV=production`; force with `NEXT_PUBLIC_ARIS_COPILOT=1`, disable with `=0`.
- FastAPI `POST /api/copilot/chat`. LLM wrapping is off unless `ARIS_COPILOT_LLM=1` (Ollama/HF via existing `call_llm_with_fallback`).

## Metrics

| Gate | Threshold | Result | Pass? |
|---|---|---|---|
| Retrieval Recall@5 | ≥ 0.7 | **1.00** (25/25) | YES |
| Retrieval MRR | ≥ 0.6 | **0.867** | YES |
| End-to-end Copilot | 10/10 standard questions | **10/10** | YES |
| Core tools callable | all 10 | **10/10** pytest | YES |
| Zandvoort identity / lights-out | no strategy edits | not re-walked; `recommend()` / `simulate()` untouched | — |

Tests: `tests/test_copilot_tools.py`, `tests/test_copilot_retrieval.py`, `tests/test_copilot_agent.py` (**22 passed**). Eval: `python scripts/eval_retrieval.py`.

## Example interactions

- “What’s the undercut window for VER vs NOR?” → calls `get_undercut_window`; window open laps 25–32 (gap 1.8 s on the Zandvoort identity fixture). Deltas come from `simulate_undercut`, not the LLM.
- “Do drivers have to use two compounds in a dry race?” → retrieves FIA Art. 30.5 paraphrase: unless the race is declared wet, each driver must use at least two different specifications of dry-weather tyres. Cite: `fia_reg:two-compounds-dry`.
- “What’s the best strategy from here?” → calls `recommend()`; identity labels Pit lap 33 for HARD / Pit lap 30 for HARD / Stay out, with deltas vs stay-out. UI shows a top-3 table and Approve/Deny/Alter.

## Honest limits

- Default dense encoder is sklearn `HashingVectorizer` (384-d), not MiniLM, so retrieval is lexical-heavy. The 25-question set is small and in-domain; Recall@5 = 1.0 is not a claim about open-ended FIA PDFs.
- FIA corpus is short cited paraphrases (same pattern as `data/ask/concepts/`), not the full sporting-regulations PDF.
- Without `ARIS_COPILOT_LLM=1` the narrator is extractive templates over tool JSON + chunks.
- Driver “style” stats are priors in `data/priors/drivers.json`, not fitted FastF1 variances.

## Readiness for T12 (Explainability Dashboard)

- [x] Copilot stable enough for console use (tool path is the existing engine; retrieval is in-process and small).
- [ ] Live LLM latency not measured (flag off by default).
- [x] No changes to `recommend()` or strategy logic; existing gates are not invalidated by this phase.

## Files

- `src/aris/copilot/tools.py` — tool execution
- `src/aris/copilot/retrieval.py` — hybrid search + re-rank + rewrite
- `src/aris/copilot/agent.py` — Copilot loop
- `data/regs/`, `data/priors/`, `data/eval/retrieval_qa.jsonl`
- `backend/main.py` — `POST /api/copilot/chat`
- `frontend-next/components/aris/CopilotPanel.tsx`
