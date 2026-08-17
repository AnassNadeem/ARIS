# Phase Final Pre-Event Consolidation — T−4

Executed 2026-08-17 in the **main** tree
`C:\Users\anass\OneDrive\Desktop\ARIS`. Four days before the 21–23
August 2026 Dutch GP. Scope: Blocks P1–P5. No default-path change.
Overlay remains off. G1.5 stays locked.

Every numeric result states aimed vs actual.

---

## Verdict (read this first)

The three-phase dirty tree (H.2 / R.2.1 / R.2.2) is on `origin/main`.
The G.6-style rehearsal re-cleared on current code. Zandvoort recommend
identity is still exactly the E4.1 / G1.5 lock. Readiness doc is dated
T−4. Model-accuracy research is closed until after the event.

**If the race started tonight, this is ready to demo.**

| Block | Aimed | Actual | Result |
|---|---|---|---|
| P1 commit + push | clean `origin/main` | four commits `47500b2`…`eed1a25` pushed; working tree clean except local `.cursor/` | **PASS** |
| P2 G.6-style rehearsal | all G.6 rows still pass | all pass; see table below | **PASS** |
| P3 Zandvoort smoke | G1.5 identity | **SMOKE OK**; same recommend / clock / L25 | **PASS** |
| P4 readiness refresh | T−4, link model-status, locked identity, caveats | `docs/ZANDVOORT-2026-READINESS.md` rewritten | **PASS** |
| P5 research window | explicit close, queued not abandoned | statement in `docs/model-status.md` | **PASS** |
| Full pytest | green | **266 passed**, 0 failed, 266 collected | **PASS** |

---

## P1 — Commit confirmation

Working tree had carried uncommitted H.2 / R.2.1 / R.2.2 work since
Phase H.2 (stashed and restored at R21.1). Cross-check vs
`docs/PHASE-H2-SUMMARY.md` onward: every load-bearing file those
summaries name was present and matched. Nothing was missing or
altered.

Pushed `a908e79..eed1a25` to `origin/main`.

| Hash | Message | Covers |
|---|---|---|
| `47500b2` | fix(eval): score position-delta on the time-rank field, not official P5 | R.2 (was local-only; now on origin) |
| `8bb71a8` | fix(ask): isolate tests from live JSONL and prefer G1.5 over overlay duplicates | H.2 |
| `5604c5d` | docs(eval): land R.2.1 offset diagnosis and R.1 cheap-check summary on main | R.2.1 scripts + R.1 summary |
| `eed1a25` | fix(eval): report lights-out position-delta clean vs disrupted, not one number | R.2.2 |

### Cross-check notes (not mismatches in the shipped code)

1. **`.cursor/`** left untracked. Local IDE plugin settings. H.2 also
   left it untracked. Not load-bearing.
2. **`docs/PHASE-R1-CORNERING-LOAD-SUMMARY.md`** is now on `main` as
   the evidence trail. H.2 explicitly did **not** commit it because
   R.1 was not merged. The R.1 **code** is still unmerged
   (`research/cornering-load`). Only the summary landed. Intentional.
3. **`47500b2`** (R.2 merge) was already on local `main` but **not**
   on `origin/main` before this block. It went out with the push.

`git status` after P1: `main` up to date with `origin/main`; only
`?? .cursor/`. Last 10 commits at that point:

```
eed1a25 fix(eval): report lights-out position-delta clean vs disrupted, not one number
5604c5d docs(eval): land R.2.1 offset diagnosis and R.1 cheap-check summary on main
8bb71a8 fix(ask): isolate tests from live JSONL and prefer G1.5 over overlay duplicates
47500b2 fix(eval): score position-delta on the time-rank field, not official P5
a908e79 docs: add Phase G.6 pre-event rehearsal and day-of overlay/log checklist
82c8192 fix(decisions): fail loudly when the JSONL decision log cannot be written
429a284 chore(scripts): let G1 diagnosis and walk-forward backtests write to a chosen directory
0e857a0 docs: lock G1.5 as the shipped tyre model and close the degradation thread
126482a feat(models): add pooled context-aware tyre degradation behind an opt-in flag
03fd7ff feat(physics): add traffic-gap construction and isotonic C-code slope constraint
```

---

## P2 — Full G.6-style rehearsal vs G.6 original numbers

Docker `aris-postgres` healthy (Up 6 days). Overlay / fast-clock unset.
Logs under `results/final-pre-event/`.

### Sprint-sequence (2024 Austria stand-in)

Aimed: ≤ 120 s per session, ≤ 300 s weekend, and no real slowdown vs
G.6 actuals.

| Session | Aimed (s) | E4.1 | G.6 | T−4 actual (s) | vs G.6 | Result |
|---|---:|---:|---:|---:|---:|---|
| FP1 | ≤ 120 | 11.1 | **7.1** | **12.1** (10.2 + 1.9) | **+5.0** | **PASS** (ceiling; first cached load) |
| SQ | ≤ 120 | 6.7 | **3.9** | **3.5** (2.1 + 1.4) | **−0.4** | **PASS** |
| Sprint (S) | ≤ 120 | 10.2 | **5.1** | **7.4** (6.1 + 1.3) | **+2.3** | **PASS** |
| Q | ≤ 120 | 9.1 | **5.4** | **5.7** (4.3 + 1.3) | **+0.3** | **PASS** |
| Race (R) | ≤ 120 | 11.0 | **5.5** | **5.8** (4.5 + 1.3) | **+0.3** | **PASS** |
| `--sprint` weekend | ≤ 300 | 11.7 | **4.2** | **3.7** | **−0.5** | **PASS** |

All sessions `+0` rows (idempotent). Weekend types
`['FP1','SQ','S','Q','R']`, form n=20. Cold FastF1 can still take
minutes; these are cached.

### JSONL write safety (full Watch-mode, 2025 NL VER)

First run appended to G.6's leftover `2025_r15_VER_123.jsonl` and
failed the 107/107 order check (215/214). Clean-file re-run:

| Check | Aimed | G.6 | T−4 actual | Result |
|---|---|---|---|---|
| Clock | ~287 ticks → lap 72 | 287 / 26.28 s | **287** / **23.66 s** | **PASS** |
| Propose / resolve | every trigger, in order | **107 / 107**, order_ok | **107 / 107**, order_ok=True | **PASS** |
| JSONL write | << 50 ms (live tick 25 s) | max **1.609 ms** | mean **0.950 ms**, max **1.858 ms** | **PASS** |
| vs live-default propose | negligible | 4.880 s / 0.862 ms | **4.056 s** / **0.847 ms** (0.0209%) | **PASS** |
| Unwritable dir | loud `RuntimeError` | same | same (`decision log write failed for 'propose'`) | **PASS** |

### Live-write gating vs real Aug 21–23 window

Aimed window `(2026-08-21, 2026-08-23)`; actual **same**. Overlay
independence: fit script does not read `ARIS_TRUE_COMPOUND_SLOPES`.

| Date | Aimed inside? | Actual | Result |
|---|---|---|---|
| 2026-08-17 (T−4) | no | no | **PASS** |
| 2026-08-20 (Thu) | no | no | **PASS** |
| 2026-08-21 (Fri) | yes | yes | **PASS** |
| 2026-08-22 (Sat) | yes | yes | **PASS** |
| 2026-08-23 (Sun) | yes | yes | **PASS** |
| 2026-08-24 (Mon) | no | no | **PASS** |

Five E4.1 flag paths: all match (outside `--write` allow; inside
`--write` alone refuse; inside `--write --allow-live-write` allow).

### Failure-mode drills

| Scenario | Aimed | G.6 | T−4 actual | Result |
|---|---|---|---|---|
| FastF1 rate limit | loud, no hang | **0.00 s** | **0.00 s** `RateLimitExceededError` | **PASS** |
| Empty/missing laps | refuse before DB | **0.00 s** | **0.00 s** `RuntimeError: … session.laps is None` | **PASS** |
| Bad session type | exit 1, no hang | **1.49 s** | **1.58 s** exit 1 | **PASS** |

### SC/VSC caveat in the actual UI

| Layer | Aimed | T−4 actual | Result |
|---|---|---|---|
| 2025 Zandvoort VER L25 state | `based on Safety Car-affected recent pace — lower confidence` | same | **PASS** |
| Callout + live strip | `Note: …` via `.aris-caveat` (amber, not `display:none`) | same | **PASS** |
| Recommend identity | Pit 33 HARD / Pit 30 HARD / Stay out | **same** | **PASS** |
| Engine HIT | 2024 Austria RIC L66 TrackStatus=71 | **same**; caveat in narrate | **PASS** |

### Day-of checklist vs current code

`docs/zandvoort-day-of-checklist.md` matches ingest CLI, sprint
session tuple, YAML 72 / 18.5 / 0.08,0.05,0.03, prewrite
A:[18] B:[29] C:[18,40], and the three env defaults (fast-clock off,
overlay off, decision log on). Live-write window 21–23 Aug.

---

## P3 — Zandvoort smoke

`python scripts/_e1_smoke_strategy_zandvoort.py` against local
Postgres. Overlay unset.

| Check | Aimed (E4.1 / G1.5) | Actual | Result |
|---|---|---|---|
| Setup | session 123, VER | **123**, VER, driver_id **2448** | **PASS** |
| Track | 72 / 18.5 / 0.08, 0.05, 0.03 | **same** | **PASS** |
| Prewrite | A:[18] B:[29] C:[18, 40] | **same** | **PASS** |
| Weekend form | n=20 | **20** | **PASS** |
| Clock | 287 → lap 72 complete | **287 / 72 / True** | **PASS** |
| L25 | MEDIUM, tyre_life=2 | **MEDIUM / 2** | **PASS** |
| Recommend | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **Pit lap 33 for HARD; Pit lap 30 for HARD; Stay out on current tyres** | **PASS** |
| Smoke exit | SMOKE OK | **SMOKE OK** | **PASS** |

What-if MC is unseeded: delta **−11.92 s**, P10/P90 **−147.55 /
+29.33** (same printed delta as G.6 / H.2 / R21.2 / R22.5). Log:
`results/final-pre-event/zandvoort-smoke.log`.

---

## P4 — Readiness doc refresh

`docs/ZANDVOORT-2026-READINESS.md` rewritten for T−4. It now links
`docs/model-status.md`, restates the locked identity, restates the
caveat list (tyre globals, China 0.033 s, uncalibrated +989 s
offset, position-delta not FIA points, SC/VSC pits, cold FastF1,
Ask G1.5 default), and records this rehearsal vs G.6.

---

## P5 — Research window closed

Added to `docs/model-status.md`: no further model-accuracy research
before the event, including the cornering-load bounded next step in
`docs/PHASE-R1-CORNERING-LOAD-SUMMARY.md`. Queued, not abandoned.
Resumes after the Dutch GP on `research/cornering-load` from R1.4
and `docs/future-research-cornering-load.md`. G1.5 stays shipped.

---

## Tests

Docker Postgres up, `ARIS_DB_URL` from `.env`, overlay / fast-clock
unset. No production-code change in this phase (docs + rehearsal
only).

| Suite | Aimed | Actual | Result |
|---|---|---|---|
| Full pytest | green | **266 passed**, 0 failed, 266 collected | **PASS** |

266 = R.2.2's count (R.2 isolated 258 + H.2 five Ask-model-version
tests + three R22 tests). Log: `results/final-pre-event/pytest.log`.

---

## What this does and does not claim

Does: put H.2 / R.2.1 / R.2.2 on `origin/main`; re-run the full
pre-event rehearsal against G.6's numbers; re-confirm the locked
Zandvoort identity; refresh the readiness page; close the research
window until after the event.

Does not: change `simulate()` / `recommend()` / tyre slopes; ship a
physics intercept; merge cornering-load; restore E4.1 What-if
−13.00 s.

**STOP.**
