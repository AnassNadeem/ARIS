# Phase H summary — grounded RAG for Ask ARIS

Executed 2026-08-15–16 in worktree `C:\Users\anass\OneDrive\Desktop\ARIS-grounded-rag` on branch `feature/grounded-rag` (HEAD `86db68f`, separate from the dirty G.6/R.1/R.2 main tree). Scope: Blocks H.1–H.6. Additive only.

`simulate.py`, `recommend.py`, `tires.py`, `tracks.py`, and `physics/` were not modified (`git diff` against those paths is empty).

---

## Verdict (read this first)

**Ask ARIS now retrieves and cites. It does not keyword-match, and it does not guess.** Headline: **14 / 14** logged-decision questions returned the exact JSONL numbers; **3 / 3** ungroundable questions abstained. Zandvoort smoke still **SMOKE OK** with the G1.5 recommend identity.

| Metric | Aimed | Actual | Result |
|---|---|---|---|
| Retrieval infra | decide pgvector vs local FAISS/Chroma from real probes | local **FAISS IndexFlatIP** (see H.1) | **decided** |
| Three sources indexed | decision JSONL + session_results + small cited KB | **16630** decisions + **959** race docs + **12** concepts = **17601** | **PASS** |
| Grounding (logged decisions) | **≥ 10** questions, cited numbers match the record exactly | **14 / 14**, 0 mismatches | **PASS** |
| Abstain when nothing retrieved | say so, do not guess | **3 / 3** → exact `ABSTAIN` string | **PASS** |
| In-session memory | multi-turn, no cross-session store | `ConversationMemory`; new instance empty | **PASS** |
| Zandvoort smoke | unaffected demo path | **SMOKE OK**; recommend identity matches G1.5 | **PASS** |
| Full pytest | green | **207 passed**, 0 failed | **PASS** |

---

## H.1 — Retrieval infrastructure decision

Probed, not assumed.

| Probe | Aimed | Actual |
|---|---|---|
| Local Docker image | whatever `docker-compose.yml` runs | `postgres:16-alpine`, container `aris-postgres` healthy, **PostgreSQL 16.14** |
| Local `pg_available_extensions` for `vector` / `pgvector` | report whatever exists | **[]** (not packaged) |
| Local `CREATE EXTENSION vector` | succeed or fail loudly | **FAIL** `psycopg.errors.FeatureNotSupported`: extension "vector" is not available |
| Neon host | from `.env.cloud` (password not logged) | `ep-sparkling-cake-ab4ivr0f.eu-west-2.aws.neon.tech`, **PostgreSQL 16.14** |
| Neon available extension | report | `vector` default version **0.8.0**, `installed_version` **None** |
| Neon `CREATE EXTENSION vector` (transaction rolled back) | succeed or fail | **OK**, `extversion=0.8.0`; after rollback still **not** installed |
| `faiss-cpu` on this Windows venv | installable? | **yes**, `faiss-cpu==1.15.0`, `IndexFlatIP` smoke OK |

**Choice: local FAISS IndexFlatIP**, file-backed under `data/ask/index/` (gitignored; rebuild with `python scripts/build_ask_index.py`). Embeddings: `sklearn.HashingVectorizer` (`n_features=4096`, English stop words, L2-normalised) so queries do not need a model download or pickle.

**Why not Neon pgvector even though CREATE worked:** enabling it needs a new table on the locked Zandvoort Neon schema (Phase G already refused that and kept JSONL). Local `postgres:16-alpine` cannot load the same extension without swapping the demo image. That is a split-brain, not a shared retrieval store. Neon free-tier friction is the schema change plus the local/cloud mismatch, not “pgvector missing on Neon.”

**Why not Chroma:** FAISS installed cleanly here; Chroma would pull onnxruntime into Streamlit Cloud for no extra capability we need.

---

## H.2 — Three retrieval sources

### 1. Decision-record log (Phase G JSONL, real)

Indexed propose events from `results/decisions/*.jsonl` on the main tree (`ARIS_ASK_DECISION_DIRS`). Tests use a 14-event fixture dumped from those same files (`data/ask/fixtures/decisions.jsonl`) so CI does not need the gitignored logs.

| Check | Aimed | Actual |
|---|---|---|
| Full-index propose events | the persisted Phase G JSONL | **16630** |
| Fixture proposes (tests) | ≥ 14 real records | **14** |
| SAI 2024 NL L21 `delta_vs_stay_out_s` | exact JSONL **−72.72805747985858** | **−72.72805747985858** |

### 2. Historical race summaries (not narratives)

Derived from local Postgres `session_results` + `laps.pit_in` counts (2024+2025 races), dumped to `data/ask/fixtures/races.json`, plus the documented 2024 walk-forward row from `docs/strategy-backtest.md`. Grid / finish / points / pit-in count only.

| Check | Aimed | Actual |
|---|---|---|
| Race docs | ≥ 24 classified rows | **959** (958 results + 1 backtest summary) |
| SAI 2024 R15 Netherlands | `finish_pos=5`, `grid_pos=10`, `pit_in_count=1` | **5 / 10 / 1** |
| 2024 walk-forward (from `docs/strategy-backtest.md`) | match-rate **0.125** (5/40); always-stay-out **0.250** (10/40); mean pos-delta **+2.58** | same numbers in the backtest doc |

### 3. Strategy-concept KB (small, cited)

12 short markdown files under `data/ask/concepts/`. Regulatory claims cite **FIA 2025 Formula 1 Sporting Regulations, Issue 5, 2025-04-30** (Articles 34, 55, 56, 30.1). ARIS model facts cite `docs/how-recommend-works.md` and `data/tracks/netherlands.yaml`. No invented FIA articles.

| Check | Aimed | Actual |
|---|---|---|
| Concept count | small (8–40), not thousands | **12** |

---

## H.3 — Embedding + retrieval pipeline

New modules:

| File | Role |
|---|---|
| `src/aris/ask/retrieve.py` | Hashing embed + FAISS `IndexFlatIP` + light metadata boost |
| `src/aris/ask/sources.py` | Load the three sources |
| `src/aris/ask/grounded.py` | Extractive `answer_question` (copy facts, cite, abstain) |
| `src/aris/ask/memory.py` | In-session turns only |
| `src/aris/ask/keyword_qa.py` | Re-export; **no keyword `if "pit" in q` matcher** |
| `scripts/build_ask_index.py` | Build/persist the index |
| `apps/components/aris_chat.py` | Wires grounded Q&A + session memory |

Full build: aimed IndexFlatIP `n_features=4096`; actual **n_docs=17601**, `by_source={decision: 16630, race: 959, concept: 12}`, elapsed **7.096 s**.

Runtime loads `data/ask/index/` when `meta.json` exists; otherwise builds from packaged fixtures + concepts.

---

## H.4 — Grounding contract (headline)

Same rule as `narrate.py`: numbers in the answer are `json.dumps` of the retrieved record’s fields. Tests construct one question per fixture propose (**aimed ≥ 10, actual 14**) and check `delta_vs_stay_out_s`, `mean_race_time_s`, and `label` against that record, plus a `Cited:` block.

| # | Question key | Aimed `delta_vs_stay_out_s` | Actual in answer | Result |
|---|---|---|---|---|
| 1 | 2024 Netherlands SAI L21 Pit now HARD | **−72.72805747985858** | same | **PASS** |
| 2 | 2024 Netherlands SAI L2 Pit lap 10 HARD | **−45.83318244933962** | same | **PASS** |
| 3 | 2024 Netherlands SAI L32 Stay out | **0.0** | same | **PASS** |
| 4 | 2024 Belgium NOR L11 Pit now HARD | **−11.188644561767251** | same | **PASS** |
| 5 | 2024 Belgium NOR L2 Pit lap 7 HARD | **−16.64143821716316** | same | **PASS** |
| 6 | 2024 Belgium NOR L18 Stay out | **0.0** | same | **PASS** |
| 7 | 2024 Azerbaijan VER L12 Pit now HARD | **−89.89449531555128** | same | **PASS** |
| 8 | 2024 Azerbaijan VER L51 Stay out | **0.0** | same | **PASS** |
| 9 | 2024 Azerbaijan VER L23 Pit lap 24 SOFT | **−50.833354838709724** | same | **PASS** |
| 10 | 2024 Australia PER L2 Pit lap 10 MEDIUM | **−15.203754425048647** | same | **PASS** |
| 11 | 2024 Australia PER L46 Pit now HARD | **−10.998999999999956** | same | **PASS** |
| 12 | 2024 Bahrain RUS L25 Pit lap 26 MEDIUM | **−91.52004661560049** | same | **PASS** |
| 13 | 2024 Italy R16 HAM L34 Pit now HARD | **−16.81289999999949** | same | **PASS** |
| 14 | 2024 United States R6 SAI L21 Pit now HARD | **−27.349999999999728** | same | **PASS** |

Cross-lap mix check: SAI NL L21 answer contains **−72.72805747985858** and does **not** contain L2’s **−45.83318244933962**.

Abstain (**aimed: do not guess; actual: exact `ABSTAIN` string**):

| Question | Aimed | Actual |
|---|---|---|
| What is the capital of France? | abstain | abstain |
| SAI 2024 Netherlands lap **9999** | abstain | abstain |
| Who won the 1998 FIFA World Cup? | abstain | abstain |

**Headline: 14 / 14 exact numeric matches, 3 / 3 abstains, 0 invented numbers.**

---

## H.5 — In-session memory

`ConversationMemory` keeps at most 8 turns in process. Follow-up “what was the `delta_vs_stay_out_s` on that call?” after the SAI NL L21 question still returns **−72.72805747985858**. The same follow-up with no memory **abstains**. A new `ConversationMemory()` has empty `turns` and empty `last_decision_docs` (nothing written to disk). Streamlit rebuilds memory from `st.session_state.ask_history` only.

---

## H.6 — Zandvoort smoke (demo path untouched)

`python scripts/_e1_smoke_strategy_zandvoort.py` against local Postgres. Compared to the G1.5 identity in `docs/PHASE-G1-SUMMARY.md` (not the pre-G1 E2.10 recommend line).

| Check | Aimed (G1.5) | Actual (this worktree) | Result |
|---|---|---|---|
| Setup | 2025 Netherlands session_id 123, VER | same, driver_id 2448 | **PASS** |
| Track | 72 laps, pit_loss **18.5**, slopes **0.08 / 0.05 / 0.03** | **72 / 18.5 / 0.08, 0.05, 0.03** | **PASS** |
| Prewrite windows | A:[18] B:[29] C:[18, 40] | **same** | **PASS** |
| Weekend form | n=20 | **20** | **PASS** |
| Clock | 287 ticks → lap 72 complete | **287** ticks, lap **72**, complete | **PASS** |
| Live state L25 | MEDIUM, tyre_life=2 | **MEDIUM / 2** | **PASS** |
| Recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **Pit lap 33 for HARD; Pit lap 30 for HARD; Stay out on current tyres** | **PASS** |
| Smoke exit | SMOKE OK | **SMOKE OK** | **PASS** |

What-if MC P10/P90 is unseeded (`n_draws=20`) and is **not** a locked identity; this run printed delta **−11.92 s**. The lock for this block is smoke OK + G1.5 recommend identity + clock, which held.

`git diff --stat -- src/aris/simulate.py src/aris/recommend.py src/aris/tires.py src/aris/tracks.py src/aris/physics` is empty.

---

## Tests

Docker Postgres up, `ARIS_DB_URL` set to local, `ARIS_ASK_DECISION_DIRS` unset so unit tests use the 14-event fixture rather than the 16630-event corpus.

| Suite | Aimed | Actual |
|---|---|---|
| `tests/test_ask_*.py` | green | **13 passed** |
| Full pytest | green | **207 passed**, 0 failed (194 pre-existing at `86db68f` + 13 Ask) |

New tests: `tests/test_ask_sources.py`, `tests/test_ask_retrieval.py`, `tests/test_ask_grounding.py`, `tests/test_ask_memory.py`.

Dependency added: `faiss-cpu>=1.8` in `pyproject.toml`, `requirements.txt`, and `apps/requirements.txt`.

---

## What this does and does not claim

Does: replace keyword matching with FAISS retrieval over real Phase G decisions, real classified results, and a small cited concept set; copy numbers from those sources; refuse to answer when nothing relevant is retrieved; keep conversation memory inside one Streamlit session.

Does not: change G1.5 slopes or the Zandvoort recommend path; enable pgvector on Neon; use an LLM to invent narration of Ask answers (extractive only, even if `use_llm=True` is passed); persist Ask chat across browser sessions.

**STOP.**
