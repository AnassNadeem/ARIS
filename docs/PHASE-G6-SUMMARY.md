# Phase G.6 summary — full pre-event rehearsal (T−6)

Executed 2026-08-15, six days before the 21–23 August 2026 Dutch GP.
Scope: Blocks G6.1–G6.6. Everything since E4.1 (Phases F, F.1, G, G.1–G.5)
had only been checked against the narrow recommend-identity smoke. This
phase re-runs the full E4.1 rehearsal against current code, plus the
JSONL decision log added in Phase G.

No default-path change. Overlay remains off. G1.5 stays locked.

---

## Verdict (read this first)

**If the race started tonight, this is ready to demo.** Same GO as E4,
re-cleared on the post-G.5 stack: sprint ingest is faster than E4.1 (not
merely under the 120 s / 300 s ceiling), JSONL logging is safe under the
live clock, the live-write gate matches the actual 21–23 Aug window and
is independent of `ARIS_TRUE_COMPOUND_SLOPES`, failure modes are still
loud, and the SC/VSC caveat still renders on the F1.1 stint.

Known accepted gaps from E4 are unchanged (Zandvoort globals, China
0.033 s miss, physics bias, SC-dirty What-if deltas, cold FastF1). None
of F–G.5 moved those.

| Metric | Aimed | Actual | vs E4.1 | Result |
|---|---|---|---|---|
| FP1 ingest→UI-ready | ≤ 120 s | **7.1 s** | E4.1 **11.1 s** (−4.0 s) | **PASS** |
| SQ | ≤ 120 s | **3.9 s** | E4.1 **6.7 s** (−2.8 s) | **PASS** |
| Sprint (S) | ≤ 120 s | **5.1 s** | E4.1 **10.2 s** (−5.1 s) | **PASS** |
| Q | ≤ 120 s | **5.4 s** | E4.1 **9.1 s** (−3.7 s) | **PASS** |
| Race (R) | ≤ 120 s | **5.5 s** | E4.1 **11.0 s** (−5.5 s) | **PASS** |
| Full `--sprint` weekend | ≤ 300 s | **4.2 s** | E4.1 **11.7 s** (−7.5 s) | **PASS** |
| JSONL under Watch (2025 NL VER) | every propose/resolve in order; write << 25 s tick | **107 / 107**, max write **1.609 ms** | n/a (new since E4.1) | **PASS** |
| Unwritable `results/decisions/` | loud fail, no silent drop | `RuntimeError` (not swallowed) | n/a | **PASS** |
| Live-write window | 2026-08-21 … 2026-08-23 | same; five E4.1 flag paths match | same | **PASS** |
| Overlay vs write gate | independent | fit script does not read `ARIS_TRUE_COMPOUND_SLOPES` | n/a | **PASS** |
| Rate limit | loud, no hang; E4.1 **0.01 s** | **0.00 s** | −0.01 s | **PASS** |
| Empty/missing laps | refuse before DB; E4.1 **0.00 s** | **0.00 s** | 0.00 s | **PASS** |
| Bad session type | exit 1, no hang; E4.1 **2.23 s** | **1.49 s** | −0.74 s | **PASS** |
| SC caveat on F1.1 stint (rendered) | `Note: based on Safety Car-affected recent pace — lower confidence` | same string on callout + live strip | same HIT | **PASS** |
| Day-of checklist vs code | commands + env match | matched; added overlay + decision-log lines | stale env vars fixed | **PASS** |
| Full pytest | green | **243 passed**, 0 failed | G5 was 230 | **PASS** |

---

## G6.1 — Full sprint-sequence rehearsal (2024 Austria stand-in)

Runbook verbatim: per-session `ingest_session.py 2024 Austria {FP1,SQ,S,Q,R}`
then `ingest_weekend.py 2024 Austria --sprint`. Cached FastF1, same as
E4.1 / E2.9. UI-ready probe = `fetch_weekend_sessions` + `fetch_drivers`
+ `weekend_form` (what Strategy setup reads).

Aimed: **≤ 120 s** per session, **≤ 300 s** weekend — **and** no real
slowdown vs E4.1's actuals (11.1 / 6.7 / 10.2 / 9.1 / 11.0 s, weekend
11.7 s). A JSONL-era regression would show up against those numbers, not
against the loose ceiling.

| Session | Aimed (s) | E4.1 actual (s) | G6.1 actual (s) | vs E4.1 | Ceiling |
|---|---:|---:|---:|---:|---|
| FP1 | ≤ 120 | 11.1 | **7.1** (ingest 5.4 + ui-ready 1.7) | **−4.0** | **PASS** |
| SQ | ≤ 120 | 6.7 | **3.9** (2.2 + 1.6) | **−2.8** | **PASS** |
| Sprint (S) | ≤ 120 | 10.2 | **5.1** (3.6 + 1.5) | **−5.1** | **PASS** |
| Q | ≤ 120 | 9.1 | **5.4** (3.8 + 1.6) | **−3.7** | **PASS** |
| Race (R) | ≤ 120 | 11.0 | **5.5** (3.9 + 1.6) | **−5.5** | **PASS** |
| Full `--sprint` weekend | ≤ 300 | 11.7 | **4.2** | **−7.5** | **PASS** |

Log: `results/g6/austria_rehearsal.log`. All five sessions already in DB
(`+0` rows, idempotent). Weekend types `['FP1','SQ','S','Q','R']`,
form n=20. **Faster** than E4.1 on every row — no ingest regression from
JSONL writes (those are Watch-path only).

Cold FastF1 (first load of a session) can still take minutes. These
numbers are cached, same caveat as E4.1.

---

## G6.2 — Decision-log I/O under load (new since E4.1)

Full Watch-mode walk of the locked scenario: **2025 Netherlands, VER,
session_id 123**, G1.5 slopes 0.08 / 0.05 / 0.03, 72 laps. Same
`SectorClock` + `check_triggers` + `propose` / `resolve` path as
`01_Strategy.py` Watch. Auto-resolve `"observe"` so pending does not
block the rest of the race (a human click in the UI does the same job).

`mc_draws=0` on the walk (backtest ranking identity); JSONL `append` is
after `recommend()`, so I/O cost is independent of MC. One extra
live-default propose (`DEFAULT_DRAWS=100`) to show write vs scoring.

| Check | Aimed | Actual | Result |
|---|---|---|---|
| Clock | ~287 ticks → lap 72 | **287** ticks, 26.28 s headless | **PASS** |
| Propose / resolve written | every trigger, in order | **107 propose + 107 resolve**, `order_ok=True`, timestamps monotonic | **PASS** |
| JSONL write vs live tick | << 25 s (noticeable bar 50 ms) | mean **0.908 ms**, max **1.609 ms** | **PASS** |
| Write vs live-default propose | negligible | propose **4.880 s**, write **0.862 ms** (0.0177%) | **PASS** |
| Unwritable dir | loud, not silent drop | `RuntimeError: ARIS decision log write failed for 'propose'…` | **PASS** |

Log: `results/g6/watch_jsonl.log`. JSONL:
`results/g6/decisions/2025_r15_VER_123.jsonl`.

**JSONL is safe under the live clock.** Max write is ~0.006% of the 25 s
1x sector interval. It cannot move the cadence.

Unwritable stand-in (a file where `results/decisions/` would be a
directory): `append()` used to raise a raw `OSError`. That was already
not silent, but it was easy to miss in a Streamlit traceback. Production
change: wrap as `RuntimeError` with a clear path + `ARIS_DECISION_LOG=0`
hint, `flush()` after each line, `logger.exception` so it is loud in
logs. Test: `tests/test_decision_queue.py::test_unwritable_log_fails_loudly`.

---

## G6.3 — Live-write gating, actual event window

Today is 2026-08-15 (outside). The gate is `_EVENT_WINDOW =
(date(2026, 8, 21), date(2026, 8, 23))` in
`scripts/fit_zandvoort_tire_slopes.py`. Re-checked with the real dates,
not an abstract “inside/outside”.

| Date | Aimed inside? | Actual | Result |
|---|---|---|---|
| 2026-08-15 (T−6, this rehearsal) | no | no | **PASS** |
| 2026-08-20 (Thu) | no | no | **PASS** |
| 2026-08-21 (Fri) | yes | yes | **PASS** |
| 2026-08-22 (Sat) | yes | yes | **PASS** |
| 2026-08-23 (Sun) | yes | yes | **PASS** |
| 2026-08-24 (Mon) | no | no | **PASS** |

Five E4.1 flag paths (YAML not touched; date mocked):

| Condition | Flags | Aimed REFUSED | Actual | Result |
|---|---|---|---|---|
| Outside window | `--write` alone | False | False | **PASS** |
| Outside window | no `--write` | False | False | **PASS** |
| Inside window | `--write` alone | True | True | **PASS** |
| Inside window | `--write --allow-live-write` | False | False | **PASS** |
| Inside window | log only | False | False | **PASS** |

**Overlay independence:** `fit_zandvoort_tire_slopes.py` does not read
`ARIS_TRUE_COMPOUND_SLOPES`. Setting it to `pooled` does not change
`_in_event_window(2026-08-22)`. Parser still returns `pooled` vs `off`
on its own. Two controls, not coupled.

Log: `results/g6/live_write_gating.log`. Tests:
`tests/test_live_write_gating.py`.

---

## G6.4 — Failure-mode drill (same three as E2.13 / E4.1)

`scripts/_e2_failure_mode_drill.py` against current ingest.

| Scenario | Aimed | E4.1 actual | G6.4 actual | Result |
|---|---|---|---|---|
| FastF1 rate limit | raise immediately, no hang | **0.01 s** | **0.00 s** `RateLimitExceededError` | **PASS** |
| Empty/missing laps | refuse before DB write | **0.00 s** | **0.00 s** `RuntimeError: … session.laps is None` | **PASS** |
| Bad session type CLI | loud ValueError, no hang | **2.23 s** exit 1 | **1.49 s** exit 1; `session_type 'NOTASESSION' not one of [...]` | **PASS** |

Log: `results/g6/failure_modes.log`. All three faster or equal vs E4.1;
none hang.

---

## G6.5 — SC/VSC caveat, rendered UI

Same F1.1 rendered-value stint: **2025 Zandvoort, VER, L25** (MEDIUM,
tyre_life=2, SC caveat set). Formatters the gold callout actually
renders (`format_callout_delta`, `recommendation_caveat` →
`recommend_panel.py` `.aris-caveat`). Live strip in `01_Strategy.py`
still prefixes `Note: {live_state.confidence_caveat}`. CSS is visible
(amber border, not `display:none`).

| Layer | Aimed (F1.1 / E4.1) | G6.5 actual | Result |
|---|---|---|---|
| State caveat | `based on Safety Car-affected recent pace — lower confidence` | same | **PASS** |
| Callout strip | `Note: based on Safety Car-affected recent pace — lower confidence` | same | **PASS** |
| Recommend identity | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **same** | **PASS** |
| Headline truncation | none | full label, unescaped change | **PASS** |

Engine HIT unchanged: **2024 Austria, RIC, lap 66, TrackStatus=71**,
`recent_sc_pace=True`, narration still appends the caveat. Logs:
`results/g6/sc_caveat_render.log`, `results/g6/sc_caveat_engine.log`.

Callout delta on this stint is **−49.4 s** vs F1.1 **−48.3 s** (15-draw
MC, not seeded). That is not a caveat-display miss; the lock for this
block is the string on the rendered strip.

---

## G6.6 — Day-of checklist, final accuracy pass

Read `docs/zandvoort-day-of-checklist.md` end to end as if running it
Friday. Cross-checked against current code:

| Item | Checklist | Code | Result |
|---|---|---|---|
| Ingest commands | `ingest_session.py 2026 Netherlands {FP1,SQ,S,Q,R}` | same CLI | **PASS** |
| Weekend catch-up | `ingest_weekend.py 2026 Netherlands --sprint` | `SPRINT_SESSIONS = (FP1, SQ, S, Q, R)` | **PASS** |
| YAML | 72 laps, pit 18.5, compound_slopes | **72 / 18.5 / 0.08, 0.05, 0.03** | **PASS** |
| Prewrite windows | ≈ 18 / 29 / 18+40 | **A:[18] B:[29] C:[18, 40]** | **PASS** |
| `ARIS_FAST_CLOCK` | unset | `fast_clock_enabled()` True only for `"1"` | **PASS** |
| `ARIS_TRUE_COMPOUND_SLOPES` | unset (was missing) | **added**; unset → G1.5 `off` | **fixed** |
| `ARIS_DECISION_LOG` | default on (was missing) | **added**; unset → on; `0` disables | **fixed** |
| Live-write | `--write --allow-live-write` Fri–Sun 21–23 Aug | `_EVENT_WINDOW` 2026-08-21…23 | **PASS** |

Stale bits fixed in the checklist (and commented in `.env.example`):
unset `ARIS_TRUE_COMPOUND_SLOPES` and leave `ARIS_DECISION_LOG` default;
note that the overlay flag does not bypass the YAML write refuse.
Ingest commands and expected 5–20 min FastF1 wait were already correct.

Log: `results/g6/checklist_sanity.log`.

---

## Tests

Docker Postgres up (`aris-postgres` healthy), `ARIS_DB_URL` set,
`ARIS_FAST_CLOCK` / `ARIS_TRUE_COMPOUND_SLOPES` / `ARIS_DECISION_LOG`
unset.

Full pytest after persist + gating tests + checklist edits: **243
passed**, 0 failed (G5 was **230**; +12 live-write gating, +1 unwritable
JSONL). Log: `results/g6/pytest.log`.

Production code touched: `src/aris/decisions/persist.py` (loud write
failure + flush). Docs: `docs/zandvoort-day-of-checklist.md`,
`.env.example`. New tests under `tests/test_live_write_gating.py` and
`tests/test_decision_queue.py`. Rehearsal scripts under `scripts/_g6_*`.

---

## What this does and does not claim

Does: close the rehearsal gap since E4.1; show JSONL logging will not
stall the live clock and will not drop decisions silently; re-confirm
the actual 21–23 Aug write gate; keep the day-of sheet accurate for
Friday.

Does not: change G1.5; turn any overlay on; restore E4.1 What-if
−13.00 s; retrain residual; rewrite `netherlands.yaml`.

**If the race started tonight, is this ready to demo?** **Yes.** Print
`docs/zandvoort-day-of-checklist.md`, keep those three env vars unset
(decision log default-on), and run the runbook after each session.

**STOP.**
