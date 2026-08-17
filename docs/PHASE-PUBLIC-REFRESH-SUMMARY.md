# Phase Public-Facing Refresh — T−4

Executed 2026-08-17 in the **main** tree
`C:\Users\anass\OneDrive\Desktop\ARIS`. Four days before the 21–23
August 2026 Dutch GP. Scope: Blocks PF.1–PF.5. Docs and deployment
only. `simulate()` / `recommend()` / `tires.py` were not edited.
Overlay remains unset. G1.5 stays locked.

Every numeric result states aimed vs actual.

---

## Verdict (read this first)

Ask ARIS on a fresh clone (Streamlit Cloud's git tree) does **not**
error. It rebuilds an in-memory FAISS index from the committed 14-event
G1.5 fixture plus classified `session_results` and cited concepts. The
gitignored live JSONL and on-disk FAISS index are absent there. That
worked, unlabeled — a silent corpus shrink, not a crash. PF.2 ships
visible **snapshot, not live** labeling on the Ask panel (option a:
genuine committed seed, already present since H.2). README headline
numbers now match `docs/model-status.md`. Both name wet races as out of
scope. Neon was missing migrations 002 and 003; both are now applied
and 2024 weather/results rows are populated. Zandvoort smoke is
**SMOKE OK** on the E4.1 / G1.5 identity.

| Block | Aimed | Actual | Result |
|---|---|---|---|
| PF.1 Ask on fresh clone | report real behaviour | works via 14-event fixture; no crash | **found** |
| PF.2 graceful fix | (a) labeled genuine snapshot or (b) honest unavailable | **(a)** — seed already committed; Ask panel now labels it | **PASS** |
| PF.3 README = model-status | calendar 0.583 vs 0.783, match 0.322 vs 0.276, Δ −1.73 / −1.49, G1.5 locked, physics-offset closed, wet caveat | same numbers in both; Phase C 0.549 no longer the headline | **PASS** |
| Full pytest | green | **269 passed**, 0 failed (aimed 266 + 3 new) | **PASS** |
| PF.4 Neon 002 / 003 | both applied | before: missing; after: weather **24**, results **479**, `'S'` in CHECK | **PASS** |
| PF.5 Zandvoort smoke | G1.5 identity | **SMOKE OK**; same recommend / clock / L25 | **PASS** |

---

## PF.1 — What a fresh clone actually has

Confirmed against git, not assumed.

| Path | Aimed (suspected) | Actual | In a Streamlit Cloud clone? |
|---|---|---|---|
| `results/decisions/*.jsonl` | gitignored | `.gitignore:25` `results/*`; `git ls-files` has no decision JSONL; live dir empty here | **no** |
| `data/ask/index/` FAISS | gitignored | `.gitignore:32` `data/ask/index/*` except `.gitkeep`; local `meta.json` **n_docs=17601** (decision **16630** / race **959** / concept **12**) is local-only | **no** |
| `data/ask/fixtures/decisions.jsonl` | — | **committed**, 14 genuine G1.5 proposes from the corpus (SAI NL L21 delta **−72.72805747985858**) | **yes** |
| `data/ask/fixtures/races.json` | — | **committed** classified rows | **yes** |
| `data/ask/concepts/*.md` | — | **committed**, 12 cited concept docs | **yes** |

Runtime (`aris.ask.grounded._default_index`): if `data/ask/index/meta.json`
exists, load the on-disk index; else `build_index()` from fixtures +
concepts + whatever is in `results/decisions/`. Streamlit Cloud takes
the else branch.

Fresh-clone probe (no `meta.json`, no live JSONL, `ARIS_ASK_DECISION_DIRS`
unset):

| Check | Aimed | Actual |
|---|---|---|
| Documents collected | fixture + races + concepts | **decision 14 / race 959 / concept 12** = **985** in **0.134 s** |
| In-memory index | builds, does not crash | **985** docs in **0.039 s** |
| SAI 2024 NL L21 | exact JSONL delta | **−72.72805747985858** in **0.003 s** |
| Ungroundable ("capital of France") | `ABSTAIN` | exact abstain string |
| Example prompt "should we pit this lap?" (no session) | not a traceback | answers from a fixture propose (Belgium NOR L2) — unlabeled, looks live |

**Behaviour: it works, quietly, on a 14-record seed.** It does not fail
loudly. It does not fail silently (answers are grounded). It also does
not say the corpus is a snapshot. That unlabeled shrink is the
misbehaviour PF.2 fixes.

`faiss-cpu>=1.8` is already in `apps/requirements.txt`, so Streamlit
Cloud can build the in-memory index. The Ask panel has no try/except;
an import failure would be loud. That path was not the bug.

---

## PF.2 — Snapshot, not live

Chose **(a)**: the 14 records are already genuine dumps from
`2024_r15_SAI_15.jsonl` and siblings, not fabricated. Shipping a
288 MB FAISS file is not reasonable. Hiding Ask behind "not available"
would throw away a working, cited seed.

Fix (Ask UI only; not simulate/recommend/tires):

- `ask_panel_notice()` in `src/aris/ask/sources.py`
- rendered as `.aris-caveat` at the top of `render_ask_mode`
- public / fresh-clone copy starts **Snapshot, not live.** and names the
  14-record G1.5 seed
- local machine with `meta.json` or live JSONL gets a companion line that
  the public deployment still uses the snapshot

No new decision records were invented. The existing fixture is the seed.

---

## PF.3 — README and model-status

README headline table now quotes `docs/model-status.md` exactly:

| Question | Aimed | Actual |
|---|---|---|
| Calendar blend MAE | ≤ **0.783** (1.5× MA(2) **0.522**) | **0.583 s** |
| Match-rate vs stay-out | > **0.276** (24/87) | **0.322** (28/87) |
| Position-delta | ≤ 0 | **−1.73** all 48 / **−1.49** clean (n=35) |
| Tyre | physical C1<…<C5 | **G1.5 locked** |
| Physics offset | a stable intercept | mean **+989 s**, std **544** — **closed** |

The five-race Phase C row (blend **0.549 s** vs MA(2) **0.469**) remains
only as the superseded short held-out, labeled as such. It is not the
headline. Roadmap Phase 3 row updated to E3.

**Wet / rain-affected races** are named in both files, same class of
limit as G1.5 and the physics-offset close:

| Slice | Aimed | Actual |
|---|---|---|
| 2024 inflections excluded | ~1/3 | **0.344** (21/61) |
| 2025 | report | **0.365** (27/74) |
| Combined | ~1/3 | **0.356** (48/135) |

No wet-strategy logic exists. The 87-event match-rate is what remains
after that cut. The cut is the missing model, not an evaluation
convenience.

---

## PF.4 — Deployment and Neon schema

PF.2 is a code change, so the public app needs this commit on `main`
(Streamlit Cloud tracks `origin/main`). Live homepage at
[aris-f1.streamlit.app](https://aris-f1.streamlit.app) already showed
the E3 calendar MAE (**0.583 s** vs aimed ≤ **0.783 s**) from current
`main` before this phase.

Neon schema **before** this phase (probed, not assumed):

| Check | Aimed | Actual |
|---|---|---|
| Migration 002 tables | `session_weather`, `session_results`, `strategy_feedback` | **missing** — only `sessions` + `laps` |
| Migration 003 `'S'` in `sessions_session_type_check` | present | **absent** (FP1/FP2/FP3/Q/SQ/SS/R/SR only) |
| `sessions` | 2024 races | **24** |

`scripts/deploy_to_neon.py` applied `schema.sql` + 002 but **not** 003,
and the live project had never received 002 either (Phase 2 schema
only). `schema.sql` is DROP-and-recreate — it was **not** re-run.

Applied 002 and 003 in place (no DROP). Re-ingest of 2024 R was
idempotent on laps (**+0**) and filled the new tables.

| Check | Aimed | Actual |
|---|---|---|
| 002 tables | present | `session_weather`, `session_results`, `strategy_feedback` |
| 003 `'S'` in CHECK | True | **True** |
| `session_weather` rows | 24 races | **24** |
| `session_results` rows | classified 2024 grid/finish | **479** |
| `strategy_feedback` | empty OK | **0** |

`scripts/deploy_to_neon.py` now lists `003_sprint_session_type.sql`
after 002 so a future fresh deploy does not skip it. Do not run that
script against the live DB: `schema.sql` still DROPs.

Without 002, `fetch_session_weather` / `fetch_session_results` on
Strategy would raise `UndefinedTable`. Empty tables after CREATE would
have returned None / empty frames; the re-ingest fills weather and
classified results for the 24 2024 races.

---

## PF.5 — Zandvoort smoke

`scripts/_e1_smoke_strategy_zandvoort.py` against local Postgres.
Overlay unset. Identity vs E4.1 / G1.5 lock:

| Check | Aimed (E4.1 / G1.5) | Actual | Result |
|---|---|---|---|
| Setup | session_id 123, VER | **123**, VER, driver_id **2448** | **PASS** |
| Track | 72 laps, pit_loss **18.5**, slopes **0.08 / 0.05 / 0.03** | **72 / 18.5 / 0.08, 0.05, 0.03** | **PASS** |
| Prewrite windows | A:[18] B:[29] C:[18, 40] | **same** | **PASS** |
| Weekend form | n=20 | **20** | **PASS** |
| Clock | 287 ticks → lap 72 complete | **287** ticks, lap **72**, complete | **PASS** |
| Live state L25 | MEDIUM, tyre_life=2 | **MEDIUM / 2** | **PASS** |
| Recommend | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **Pit lap 33 for HARD; Pit lap 30 for HARD; Stay out on current tyres** | **PASS** |
| What-if | G1.4 physics-delta (not a lock) | **−11.92 s** | report only |
| Smoke exit | SMOKE OK | **SMOKE OK** | **PASS** |

---

## Tests

Aimed: full suite green after the Ask-label and docs edits.
Actual: **269 passed**, 0 failed, in **12.77 s** (266 from Final
Pre-Event + 3: snapshot notice, default-index-without-FAISS, Ask panel
renders caveat).

---

## Stop

Public-Facing Refresh is complete. Print
`docs/zandvoort-day-of-checklist.md`. Keep `ARIS_FAST_CLOCK` and
`ARIS_TRUE_COMPOUND_SLOPES` unset; leave `ARIS_DECISION_LOG` default-on.
No further model-accuracy work before the event.
