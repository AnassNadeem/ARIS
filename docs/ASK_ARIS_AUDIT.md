# Ask ARIS / Copilot / Comms audit

Read-only audit of the three systems as they exist in the repo on 2026-09-02.
No code was changed for this pass except this document.

Evidence is from the files named below, not from older summaries. `docs/ASK_ARIS.md`
is stale in several places and should not be trusted over this file.

---

## 1. What each system is

### Ask ARIS (production default Q&A)

A chat tab inside ARIS Comms. The recruiter types a question. The UI either
answers from the live timing store, or POSTs to `/api/ask`.

It runs when the Copilot feature flag is **off**. That is the production
Cloudflare Pages default unless `NEXT_PUBLIC_ARIS_COPILOT=1` was set at **build**
time (`copilotFeatureEnabled()` in `frontend-next/lib/api.ts`).

It needs: a running replay or live session so `cars` is populated (for live
facts), and a reachable Heroku/local API (for everything else). It does **not**
need an LLM for the questions it actually answers well.

### Copilot (tool-calling Q&A, hidden in production)

The same chat tab, swapped in when `copilotFeatureEnabled()` is true. Local
`next dev` shows Copilot by default. Production builds show Ask ARIS.

It can call ARIS tools (`recommend()`, `simulate()`, `get_gap`, …) and retrieve
FIA/prior/docs chunks. LLM wrapping is a second, separate flag:
`ARIS_COPILOT_LLM=1` on the backend. Default on Heroku is **off**. Without it,
Copilot still answers from tool JSON via templates. It does not silently die.

It needs: `POST /api/copilot/chat` reachable, and a Postgres-ingested
`RaceState` for tools that call `require_state()` (recommend / simulate / undercut
/ SC / wet). Gap and session-result tools still call `require_state()` today,
so a missing ingest makes the backend Copilot path fail those tools even when
the timing field is present. The frontend factual short-circuit saves some of
that.

### Main Comms (radio narration, not Q&A)

The other tab in ARIS Comms. It is a scrolling radio log, not a question box.
It fires automatically while ARIS is on and the console is racing.

It is **template-based on the frontend**. It does not call Ollama. Backend
`src/aris/narrate.py` exists for Streamlit / backend radio wrapping and is not
the Next.js Main Comms path.

It needs: ARIS toggled on, replay/live ticking, and (for strategy calls)
`POST /api/aris/recommend` succeeding.

---

## 2. Question-type table

| Question type | Which system handles it in production | Works in prod | What would make it work |
|---|---|---|---|
| Who is leading? | Ask ARIS, **frontend** `answerFactualLive` | **yes** (if the tower has cars) | Already works from the timing store. |
| Gap to leader | Ask ARIS, **frontend** `answerFactualLive` | **yes** (if focus driver is in `cars`) | Already works. Empty store → "unavailable", not a fake number. |
| What tyres is VER / Verstappen on? | Ask ARIS, **backend** template (frontend classifier misses this) | **partial** | Widen `LIVE_FACT_RE` so compound questions stay on the store. Backend already answers this if `/api/ask` returns in 1.5s and field timing loaded. |
| Should I pit now? | Ask ARIS, **backend** keyword template | **no** | Stop returning the "use the recommend button" string. Call `recommend()` or read `lastRecommendation`. Copilot's `simulate` tool already does this in local Copilot. |
| Why did ARIS recommend lap N? | Ask ARIS, **backend** greedy `"lap"` matcher | **no** | Do not treat "lap" as "how many laps remaining". Answer from `lastRecommendation` / `pendingRecommendation`. |
| Explain the undercut (concept) | Ask ARIS → RAG `answer_question` + optional LLM wrap | **partial** | Raise `/api/ask` timeout above 1.5s so RAG/LLM is not aborted. Concept file `data/ask/concepts/undercut.md` is real. |
| FIA / two-compound rules | Copilot retrieval (not shown in prod) | **no in prod** (Copilot off) | Set `NEXT_PUBLIC_ARIS_COPILOT=1` at Pages build, or port retrieval into Ask ARIS. |
| Best strategy / top-3 | Copilot `recommend` tool (not shown in prod). Ask ARIS does not call `recommend()`. | **no in prod** | Same: enable Copilot, or wire Ask ARIS "pit now" to `recommend()`. |
| Who won last year? | Ask ARIS **frontend** history lookup via `/api/session/.../results` | **partial** | Works when that results endpoint is up. Else falls through to RAG/API. |
| SC / rain / current lap | Ask ARIS, **frontend** `answerFactualLive` | **yes** | Already works from store phase/rainfall/lap. |

---

## 3. System 1 — Ask ARIS, full path

### 3.1 Where the message enters

`frontend-next/components/aris/ARISComms.tsx`, inner function `AskARIS`,
`send()` at line 144.

The input at line 236 (`onKeyDown` Enter) and the send button at line 243 both
call `send(input)`. Suggestion chips at line 214 call `send(c)` with the chip
text.

`ARISComms` (line 251) only mounts `<AskARIS />` when
`copilotFeatureEnabled()` is false (line 299).

### 3.2 What happens before the backend

There **is** frontend intent classification. `docs/ASK_ARIS.md` is wrong on this.

Order in `send()` (`ARISComms.tsx` 149–203):

1. `answerFactualLive(question, { cars, currentLap, totalLaps, racePhase, rainfall, focusDriver, session })`
   (`frontend-next/lib/copilotIntent.ts`).
   If this returns a string, that string is pushed as `ARIS_ANALYSIS` and **the
   API is never called**.
2. If `classifyIntent(question) === "factual_history"`, `historyLookupHint` +
   `getSessionResults(year, round)` looks up the classified winner.
3. Otherwise `askARIS(...)` → `POST /api/ask`.

`classifyIntent` (`copilotIntent.ts` 42–48):

- `STRATEGIC_RE` (should we / pit now / undercut window / …) → `"strategic"`
- `HISTORY_RE` (who won / last year / podium) → `"factual_history"`
- `LIVE_FACT_RE` (who is leading / gap to / tyre **life** / SC / VSC / current lap / …) → `"factual_live"`
- else → `"strategic"`

Not every question goes to the API. Live leader/gap/phase/lap questions stay
on the client. Compound questions that do not contain `"tyre life"` are
classified strategic and **do** go to the API.

`race_state` is always passed as `undefined` (`ARISComms.tsx` 188). The cars
snapshot is **not** sent to the backend.

### 3.3 `POST /api/ask`

`backend/main.py` 1817–1828: `api_ask` forwards to `aris_api.chat(...)`.
`AskRequest.race_state` is accepted by the Pydantic model
(`backend/models.py` 1097–1103) and **never read**.

`aris_api.chat()` (`backend/aris_api.py` 1145–1218):

1. Resolve year/round (or next race / 2024 R15 fallback).
2. Resolve focus driver (or HAM / NOR fallbacks).
3. Load a `RadioField` from replay timing, or FastF1 laps if timing is empty.
4. `generate_template_response(question, field, focus, lap, total_laps)`
   (`src/aris/narrate.py` 46–110). If that is not the default abstain string,
   **return it immediately**. No RAG. No LLM. No `recommend()`.
5. Else `answer_question(None, question)` — grounded RAG in
   `src/aris/ask/grounded.py`. Session is `None`, so there are no live-session
   documents. This searches the Ask FAISS/hash index (logged decisions, classified
   results, concept markdown).
6. Build a one-line `field_ctx` (`"{leader} leads. We are P{n} at +Xs on {compound}."`).
7. `call_llm_with_fallback(question, context=field_ctx+RAG, fallback=template)`.

**Intent on the backend:** keyword `in` checks in `generate_template_response`,
not a classifier. Dead function `_direct_chat_answer` (`aris_api.py` 994–1033)
has a better pit/leader/tyre router and is **never called**.

**Deterministic vs LLM:**

| Match in `generate_template_response` | Source | LLM? |
|---|---|---|
| gap / behind / ahead / **leader** / front | field snapshot | no |
| position / where / place / running | field snapshot | no |
| tyre / tire / compound / rubber | field snapshot (named driver or focus) | no |
| lap / remaining / left / to go | current_lap vs total_laps | no |
| pit / box / stop | canned "use the recommend button" | no |
| nothing matched | RAG then optional LLM wrap | LLM only if Ollama/HF answers |

**LLM prompt (Ask ARIS wrap)** — `src/aris/narrate.py` `CHAT_SYSTEM_PROMPT`:

```
You are ARIS, a Formula 1 race engineer assistant speaking on the
radio. Answer in plain English. Be direct and concise. Lead with
the number or answer, then the context.

Rules:
- Never show field names like "grid_pos=" or "finish_pos="
- Never show database keys, IDs, or session numbers
- Never reproduce raw query results
- If citing a race, say "the 2025 Abu Dhabi race" not
  "session_results year=2025 round=24"
- Maximum 3 sentences
- If you don't know, say "No data available for that"

Format context given to you as natural background information,
not as database rows. Extract the relevant numbers and present
them naturally.
```

Model: Ollama `llama3.1:8b-instruct-q5_K_M` at `http://127.0.0.1:11434`
(`ARIS_LLM_MODEL` / `ARIS_OLLAMA_URL` override). Fallback: Hugging Face
`mistralai/Mistral-7B-Instruct-v0.2` if `HF_TOKEN` or
`HUGGINGFACEHUB_API_TOKEN` is set. If both fail, return the template/RAG
string. Failures are swallowed (`call_llm_with_fallback` 231–240).

**When the LLM is unavailable:** template or RAG text is returned. The
frontend never sees an LLM error. If the handler is slower than **1.5s**,
the frontend never sees the backend at all (see timeout below).

**Critical timeout:** `askARIS` calls `tryFetch` with the default
`timeoutMs = 1500` (`api.ts` 117, 665). `call_llm_with_fallback` waits up to
5s on Ollama. Locally, with Ollama up, unmatched questions will often abort
and show the mock. On Heroku, Ollama is not running, so the connect-refused
is usually fast and RAG may still return in time.

### 3.4 `mockAskAnswer`

Activates only when both `/api/ask` and `/api/aris/chat` return nothing
(`tryFetch` null: network error, non-OK, or abort). Then
`{ answer: mockAskAnswer(question), offline: true }`.

Exact returns (`api.ts` 899–911):

| Question | Mock string |
|---|---|
| `"who is leading"` | `"Based on the current race state: physics-default scoring has HARD at lap 33 ranked #1, delta −3.4s vs stay-out, confidence std 1.1s. Ask a more specific question (gap, undercut, tyre) for detail."` |
| `"what tyres is VER on"` | same default string (no tyre/gap/undercut keyword hit as written) |
| `"should I pit now"` | same default string |
| `"explain the undercut"` | `"Undercut window open: gap ahead 1.8s, cliff estimate for the car ahead is lap 31 ± 2. Dynamic undercut bonus currently −0.5s."` |
| `"gap to leader"` | `"Gap to the driver ahead: +1.8s and closing at ~0.1s/lap over the last 3 laps. Inside the 22s undercut window."` |

Those numbers (1.8s, lap 33, −3.4s) are **fixtures**, not the live race.

### 3.5 OFFLINE badge

`ARISComms.tsx` 226–230, only when `m.offlineAnswer` is true:

> ⚠ OFFLINE — backend unreachable, showing a cached local answer

Amber 9px mono pill under the answer. Live-store answers do **not** get this
badge (they are real). A recruiter who reads the canned "HARD at lap 33"
paragraph can easily miss a 9px tag. Distinct if you look; easy to miss if
you only read the sentence.

Copilot has the same pill (`CopilotPanel.tsx` 175–178).

### 3.6 Race context Ask ARIS actually has

| Signal | Frontend short-circuit | Backend `/api/ask` |
|---|---|---|
| Current lap | yes | yes (`current_lap`) |
| Positions | yes (`cars`, ghosts filtered) | yes (replay timing / FastF1) |
| Compound per driver | yes if classified `factual_live` **and** question has tyre life or a named code + tyre | yes if question contains tyre/tire/compound/rubber |
| Gaps | yes | yes (focus + leader + P2) |
| Tyre life | yes (same caveat as compound) | yes |
| ARIS recommendation | **no** — not in `FactualRaceSnapshot` | **no** — never calls `recommend()`, never reads `pendingRecommendation` |
| Ghost position | **no** — `is_ghost` / `A_*` filtered out | **no** |

Ask ARIS is not fully context-blind. It can see the field. It **cannot** see
why ARIS just recommended a pit.

---

## 4. System 2 — Copilot

### 4.1 Environment variables

| Var | Where | Default in code |
|---|---|---|
| `NEXT_PUBLIC_ARIS_COPILOT` | frontend build | unset → **on** in non-production, **off** in production (`api.ts` 47–50) |
| `ARIS_COPILOT_LLM` | backend process | unset / `"0"` → LLM **off** (`aris_api.py` 1278–1279) |

**Cloudflare Pages default (from code, not the dashboard):** production
`NODE_ENV=production` + unset flag → Copilot tab is **Ask ARIS**. Actual Pages
project env is not in this repo (`docs/GHOST_CAR_REMEDIATION_PLAN.md` already
flags that as unconfirmable).

**Heroku default (from code + `Procfile`):** `web: uvicorn backend.main:app …`.
No `ARIS_COPILOT_LLM` in `Procfile` or `.env.example` → **off**. Ollama is not
on the dyno.

### 4.2 LLM

Same stack as Ask ARIS wrap: Ollama `llama3.1:8b-instruct-q5_K_M` on
`127.0.0.1:11434`, then Hugging Face if a token exists
(`src/aris/narrate.py`).

If `ARIS_COPILOT_LLM` is unset, `run_copilot(..., use_llm=False)` never calls
Ollama. Template over tool JSON. **Visible, useful answers**, not a silent
failure.

If the flag is on and Ollama is down: `call_llm_with_fallback` returns the
template. Still not silent.

If `POST /api/copilot/chat` 503/timeout: frontend `mockCopilotAnswer` + OFFLINE
badge. `chatCopilot` timeout is **30s** (`api.ts` 871), unlike Ask ARIS's 1.5s.

### 4.3 Tools

All dispatch through `src/aris/copilot/tools.py` `execute_tool`. None of them
HTTP-call the Next frontend. They call in-process ARIS functions. RaceState
is injected; the LLM cannot send it.

| Tool | What it does | Returns | Live ARIS vs static |
|---|---|---|---|
| `get_gap` | Position, gaps, compound, tyre life, order | JSON field snapshot | Live/replay **field** + `RaceState` (`require_state`) |
| `get_undercut_window` | `simulate_undercut` vs rival pit estimate | window laps, delta, gap | Live ARIS physics |
| `get_deg_slope` | Compound slope at circuit | s/lap | ARIS tyre model (FP2/G1.5), not a live stint |
| `simulate` | `simulate(state, action)` | remaining time, delta vs stay | Live ARIS |
| `recommend` | `recommend(state, top_k=3)` | top-3 labels + deltas | Live ARIS |
| `get_sc_risk` | `predict_sc_risk` | P(SC) 5/10 laps | Live ARIS (circuit prior is the useful part) |
| `get_wet_state` | T10-C rule classifier | DRY/DAMP/… + confidence | Live ARIS / RaceState flags |
| `run_mc_comparison` | `compare_actions_mc` | E[time], P(best) | Live ARIS |
| `get_driver_style` | priors JSON | tyre style text | **Static** `data/priors/drivers.json` |
| `get_circuit_info` | priors + track YAML | deg, SC rate, pit loss | **Static** priors + YAML |
| `get_session_result` | classified race docs | winner / podium | **Static/indexed** race-result documents |

`require_state()` raises `"Copilot has no RaceState for this session"` when
Postgres ingest is missing (`context.py` 60–64). `copilot_chat` only sets
state via `try_load_from_postgres` (`aris_api.py` 1260–1261). No Postgres row
→ recommend/simulate/get_gap all error inside the tool, and the template
falls back to "I need an ARIS tool result…".

### 4.4 Copilot system prompt

`src/aris/copilot/prompts.py` `SYSTEM_PROMPT`, used for LLM **tool planning**
and (indirectly) wrap. Template mode does not send this to a model.

```
You are ARIS Copilot, a race strategy assistant for Formula 1. You can:
- See the current race state (live or replayed).
- Call ARIS tools to get gaps, undercut windows, degradation slopes, simulate strategies, and recommendations.
- Retrieve FIA regulations, driver/track priors, and ARIS internal docs.
You must:
- Never compute lap times, deltas, or pit windows yourself; always call ARIS tools.
- Be concise and honest about uncertainty.
- When answering strategy questions, show the top-3 actions with deltas and P(best) if available.
- When answering regulation/prior questions, cite the retrieved document(s).
- Stay within 150 words unless the user asks for more detail.
```

Ask ARIS does **not** use this prompt. Ask ARIS uses `CHAT_SYSTEM_PROMPT`
(section 3.3).

### 4.5 Approve / Deny / Alter

Appears on a Copilot reply when `needs_approval` is true and there is a
`recommendations[0]` (`CopilotPanel.tsx` 183–185). Backend sets
`needs_approval` when the question looks like best strategy / recommend /
should we / cover / pit now, or when a rec label contains "pit"
(`agent.py` 518–526).

| Button | What the UI does | Ghost strategy? |
|---|---|---|
| Approve | `sendARISAction({ action: "approve", … })` | **No** |
| Deny | same, `action: "deny"` | **No** |
| Alter | tyre + note, then `action: "alter"` | **No** |
| Explain | another `chatCopilot("Explain the strategy recommendation: …")` | n/a |

`sendARISAction` POSTs `/api/aris/action`. **There is no such route in
`backend/`**. `tryFetch` returns null → `{ result: "ok (mock)" }`. Status
text: `"approve: ok (mock)"`.

Copilot's bar never calls `adoptRecommendation` / `postGhostRecompute`.

The Main Comms `RecommendationCard` Approve path is almost as hollow:
`approveRecommendation()` only appends `"Approved: … Ghost driver executing
strategy."` It does **not** recompute the ghost. Only **Adopt new strategy**
and Auto-mode `adoptRecommendation` actually call `/api/aris/ghost-recompute`.

### 4.6 Copilot race context

Frontend short-circuit: same as Ask ARIS (`answerFactualLive`).

Backend: `RaceState` (postgres) + `FieldCar` list from `_load_chat_field`.
Tools can call `recommend()` so Copilot **can** see a fresh ARIS
recommendation. It still does not receive the console's
`pendingRecommendation` or ghost tick. Ghost is not in `field`.

### 4.7 Flag mismatch: Copilot UI on, `ARIS_COPILOT_LLM` off

Not a silent failure. `use_llm` is false. Heuristic tool plan + template
narration. User sees a real (template) answer if tools succeed, or
"I need an ARIS tool result or a retrieved source…" if they don't.

If the Copilot **route** is missing (static Pages without `NEXT_PUBLIC_API_BASE`),
that is the mock + OFFLINE badge, not the template path.

### 4.8 Has Copilot ever been tested with a real LLM?

No evidence in this repo.

- `tests/test_copilot_agent.py` — `use_llm=False` on every call.
- `tests/test_copilot_tools.py` — fixture `use_llm=False`.
- `tests/test_overcut.py` / `test_strategy.py` / `test_wet.py` —
  `narrate_recommendation(..., use_llm=False)`.
- Zero tests mock or hit `127.0.0.1:11434`. Zero `respx`/`httpx_mock` for Ollama.

There is a solid **template** Copilot test: ten standard questions, leader
plain language, last-year winner, gap-to-NOR interval. Those prove tools, not
Ollama.

---

## 5. System 3 — Main Comms / radio

### 5.1 What triggers a message

Event-based and recommendation-based. Not a wall-clock radio unless the
**mock** feed is running.

| Source | Trigger |
|---|---|
| `detectCommsEvents` (`frontend-next/lib/commsEvents.ts`) via `useCommsNarration` | Phase change, rain toggle, fastest-lap holder change, new DNF, new recommendation id (undercut/overcut only), new lap (sector loss ≥0.15s vs car ahead), every 5th lap gap line |
| `useArisRecommendLoop` | `POST /api/aris/recommend` on lights-out / pit windows / SC-VSC-red / Get strategy. Pushes `recommendNarration` or `autoDecisionStatement` / `annotateVsActivePlan` |
| `maybeAnnounceGhostBoxing` (`liveFeed.ts` 120–145) | Ghost enters pits |
| `MockRaceFeed.maybeEmitComms` | Every 6s, **only mock feed** |

`useCommsNarration` no-ops unless `isARISOn && playState === "racing"`.

### 5.2 Template, not LLM

Frontend string templates. Backend `narrate.py` LLM radio
(`_build_prompt` / `narrate_recommendation`) is **not** used by Next Main Comms.

### 5.3 Three real examples from code

From `commsEvents.ts`:

1. `Lap ${lap}: SC deployed. Pitting now saves ~9 s vs green.`
2. `Lap ${lap}: Undercut opportunity vs ${ahead}. Pit now for ${compound} gains ~${gain} s.`
3. `Lap ${lap}: Gap to leader ${gap} · ahead ${code} ${gapAhead} · behind ${code}.`

From `arisRecommend.ts`:

4. `ARIS recommends: Pit lap ${pitLap} for ${compound}, Δ ${delta} s vs stay`
5. `SC WINDOW — ARIS is pitting now for ${compound}.`

From `liveFeed.ts`:

6. `L${lap} — ARIS is boxing now for ${compound}.`

Mock-only (`mockRaceFeed.ts`, not production replay):

7. `Gap to car ahead stable at 1.8s. Undercut window remains open.`

### 5.4 Recommendation, ghost, rivals

- **ARIS recommendation:** yes, when `useArisRecommendLoop` or undercut/overcut
  `detectCommsEvents` fires. Text is derived from the same
  `ARISRecommendation` object the card uses.
- **Ghost position:** not as "ghost is P4". Boxing is announced when the ghost
  pit flag flips. Gap lines use the **focus real car** (`arisDriver`), not the
  ghost row.
- **Rival strategies:** undercut/overcut lines name the car ahead. No full
  rival-plan dump.

### 5.5 Comms vs Strategy panel — can they diverge?

**Yes.**

Strategy panel (`StrategyPanel.tsx`) renders `activeStrategy` stints only —
the plan the ghost is actually flying. Comment in that file: it must match
the ghost pit laps.

Main Comms recommend lines come from the latest `recommend()` result, which
may say "Pit lap 28" while `activeStrategy.pit_laps` is still the pre-race
plan (e.g. 33) until Auto adopt or the user clicks **Adopt new strategy**.

Assisted Approve does not adopt. So comms can say the new call and the panel
can still show the old stints.

Auto mode calls `adoptRecommendation`, which recomputes ghost ticks and then
updates `activeStrategy`. After that they should match. If ghost-recompute
fails, comms says it stayed on the current plan and the panel does not change.

`recommendNarration` uses `rec.action.pit_lap ?? rec.lap`. For a BOX mapped as
pit-now, that lap is the **fetch lap**, not a future target. A recommend
fetched at lap 28 becomes "Pit lap 28" in comms. The panel only shows 28 if
that plan was adopted.

### 5.6 SC / VSC / red flag

`detectCommsEvents` on phase change:

- SC → `SC deployed. Pitting now saves ~9 s vs green.`
- VSC → `VSC deployed. Cheap pit window — delta limited.`
- RED_FLAG → `Red flag. Free tyre change. Strategy reset.`
- back to GREEN → `Green flag. Racing resumes.`

`shouldFetchRecommend` also refetches on SC/VSC/RED_FLAG.
`autoDecisionStatement` then says `SC WINDOW — ARIS is pitting now…` or
`staying out`. Phase is referenced. The "~9 s" SC line is a **fixed** template,
not the live pit-loss number.

---

## 6. What a recruiter actually gets

Assume: production UI (Ask ARIS, not Copilot), backend reachable, a race
loaded so `cars` is filling. Copilot is off.

### Q1. "Who is leading?"

- **System:** Ask ARIS frontend (`answerFactualLive`). API not called.
- **Real or canned:** real driver from the tower (`position === 1`).
- **Actual shape:** `{CODE} is leading (P1) on {compound}, tyre life {n}.`
- **Verdict: WORKS**

If `cars` is empty: `"No leader in the current timing frame."` (honest, not mock).

If this somehow hit the mock: the lap-33 HARD paragraph (wrong).

### Q2. "What tyres is Verstappen on?"

- **System:** Ask ARIS **backend** template. Frontend classifier does **not**
  treat this as `factual_live` (`LIVE_FACT_RE` wants `tyre life`, not `tyres`).
- **Real or canned:** real if `_load_chat_field` has Verstappen/VER.
  `generate_template_response` matches substring `"tyre"` in `"tyres"` and
  name/code in the question → `"{CODE} is on {compound}, {tyre_life} laps old."`
- **If API times out (1.5s) or is down:** mock default (lap 33 HARD) + OFFLINE.
- **Verdict: PARTIALLY WORKS** — correct path exists, easy to miss the client
  classifier, depends on field load + timeout.

### Q3. "Should I pit now?"

- **System:** Ask ARIS backend template (`"pit" in question`).
- **Actual answer:** `"Ask ARIS for a strategy recommendation using the recommend button, or type 'should we pit?' for an analysis."`
- **Race state:** none. No lap, compound, tyre life, gap, or `recommend()`.
- **Verdict: BROKEN** as a strategy answer. (Copilot local-dev would `simulate`.)

Note: `"should we pit?"` still contains `"pit"` and hits the **same** canned
string. The "type should we pit?" hint is a lie.

### Q4. "Why did ARIS recommend pitting on lap 28?"

- **System:** Ask ARIS backend. `"lap"` matches the remaining-laps branch.
- **Actual answer:** `"Lap {currentLap} of {totalLaps}. {n} laps remaining."`
- **Does not** read `lastRecommendation` or `recommend()` output.
- **Verdict: BROKEN**

### Q5. "What's the gap to the leader?"

- **System:** Ask ARIS frontend (`LIVE_FACT_RE` has `gap to` / `what's the gap`).
- **Actual shape (focus driver not P1):** `{CODE} is P{n}, +Xs to the leader.`
- **If focus is P1:** `{CODE} is the leader.`
- **Verdict: WORKS** (needs a focus/ARIS driver in `cars`)

---

## 7. Honest assessment — 5 questions in production

**Two of five get a useful answer reliably: Q1 and Q5.**

Q2 can be useful when `/api/ask` is warm and field timing is loaded. It is
the first question that depends on the 1.5s timeout and Heroku field snapshot.

Q3 and Q4 fail even with a healthy backend. The template matcher is too greedy
and never consults ARIS's own recommendation.

A recruiter who only asks "who's leading?" and "what's the gap?" will think
Ask ARIS is wired. A recruiter who asks "should I pit?" or "why lap 28?" will
think it is a demo script. The OFFLINE badge only appears on the mock path,
not on these wrong-but-online templates.

---

## 8. Minimum changes, smallest first

1. **Widen frontend live facts** (`copilotIntent.ts`): treat `tyre(s)/compound`
   + a driver code or "Verstappen" as `factual_live`. Unlocks Q2 with no
   backend. Same store data Q1 already uses.

2. **Raise `tryFetch` timeout for `/api/ask`** to match Copilot (30s) or at
   least 8s. Stops RAG/concept answers (undercut explain) from looking
   "offline" locally when Ollama is slow, and gives Heroku cold RAG a chance.

3. **Stop matching `"lap"` as remaining-laps** unless the question is actually
   about laps remaining. Unblocks Q4 from being overwritten. Then answer from
   `lastRecommendation` / `pendingRecommendation` already in `raceStore`.

4. **Pass `lastRecommendation` into `answerFactualLive`** (or a sibling) and
   answer "should I pit" / "why did ARIS recommend" from that object: lap,
   compound, delta, evidence. Smallest way to make Q3/Q4 true without Copilot.

5. **If no pending rec yet, call `recommend()`** (Ask ARIS backend or the
   existing `postRecommend` client). Bigger than (4); this is what Copilot
   already does.

6. **Wire Copilot Approve to `adoptRecommendation`** and delete the dead
   `/api/aris/action` mock. Only needed if Copilot is turned on in production.

7. **Enable Copilot in Pages** (`NEXT_PUBLIC_ARIS_COPILOT=1`) only after (6)
   and after confirming Postgres ingest so `require_state()` does not empty
   the tool path. Leave `ARIS_COPILOT_LLM` off; templates are enough.

Do 1–4 and a recruiter asking those five questions gets five useful answers
without Ollama, without Copilot, and without a new model.

---

## 9. File map

| Role | File |
|---|---|
| Chat entry, tab switch, OFFLINE badge | `frontend-next/components/aris/ARISComms.tsx` |
| Copilot UI + approval bar | `frontend-next/components/aris/CopilotPanel.tsx` |
| Intent + live facts | `frontend-next/lib/copilotIntent.ts` |
| `askARIS` / mock / Copilot flag / 1.5s tryFetch | `frontend-next/lib/api.ts` |
| `POST /api/ask`, `POST /api/copilot/chat` | `backend/main.py` |
| `chat()`, `copilot_chat()`, dead `_direct_chat_answer` | `backend/aris_api.py` |
| Ask templates + LLM wrap + radio LLM (unused by Next comms) | `src/aris/narrate.py` |
| Ask RAG | `src/aris/ask/grounded.py` |
| Copilot loop | `src/aris/copilot/agent.py` |
| Copilot prompt | `src/aris/copilot/prompts.py` |
| Copilot tools | `src/aris/copilot/tools.py` |
| Comms event templates | `frontend-next/lib/commsEvents.ts` |
| Recommend → comms text | `frontend-next/lib/arisRecommend.ts`, `useArisRecommendLoop.ts` |
| Strategy panel (ghost plan) | `frontend-next/components/aris/StrategyPanel.tsx` |
| Ghost boxing comms | `frontend-next/lib/liveFeed.ts` |
| Stale prior write-up | `docs/ASK_ARIS.md` |
