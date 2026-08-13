# Phase F.1 summary — skip-to-flag verification

Executed 2026-08-13. Scope: Blocks F1.1–F1.4. Not a UX restyle. Closes the
one real gap Phase F called out: **Skip to chequered flag** was added for
after-screenshots and sits on the live Strategy screen the 21–23 August
demo will use, but F.8 never exercised it.

No Phase G work starts from this document.

---

## Verdict (read this first)

Skip-to-flag and a full tick-by-tick run reach the **same final RaceState,
field tower, weekend form, recommend() output, and postrace export**.

They are **not** the same path. Skip never calls `check_triggers` /
`propose`. A Watch-mode tick-through would have proposed at least once
(first trigger: lap 2 pit); if the engineer kept clearing pending, **107**
trigger kinds fire across 287 ticks. Skip logs none of that.

That is expected, not a corrupted final state. The button stays, moved
behind **Show technical detail** (default off) so it cannot be clicked by
accident during a live demo.

F.8 / E4.1 lock-in numbers are unchanged.

---

## Block F1.1 — skip vs tick (2025 Netherlands, VER)

Session `123`, 72 laps, same start index as Strategy LIVE (`ReplayIndex(1, 0)`).
Script: `scripts/_f1_skip_vs_tick.py`. Log: `results/f1_skip_vs_tick.log`.

Two independent paths to lap 72:

| Path | What it does |
|---|---|
| **(a) Tick-by-tick** | `clock.tick()` 287 times; each tick `check_triggers` then queue side-effect, matching `apps/pages/01_Strategy.py` LIVE |
| **(b) Skip** | Exact button body: set index to `(72, 3)`, `current_field()`, `POST_RACE` |

A third **harvest** run cleared `pending` after each trigger (no
`recommend()` / MC) so the full intermediate trigger list is visible.
UI-faithful Watch does **not** do that: `pending` blocks later
`check_triggers`, so only the first proposal lands unless the engineer
resolves it.

### Final state — identical

| Field | Tick | Skip |
|---|---|---|
| `replay_index` | `(72, 3)` | `(72, 3)` |
| phase | `post_race` | `post_race` |
| RaceState L72 | SOFT, tyre_life=22, pos=2, gap=1.271 s, caveat=None | **same** |
| Field top 5 | PIA / VER / HAD / RUS / ALB | **same** |
| weekend_form | n=20, types FP1–Q–R | path-independent, **same call** |
| recommend() L72 | Lift T1; Brake T1; Stay out (same deltas) | **same** |
| recommend() L25 | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **same** |
| postrace | 0 resolved decisions, finish=2, 5911.1 s | **same** |

Exports: `results/f1_tick_postrace.json`, `results/f1_skip_postrace.json`
(did not overwrite F.8’s `123_VER_postrace.json`).

### Intermediate decision history — not identical

| | Tick (UI-faithful Watch) | Skip |
|---|---|---|
| ticks | 287 | 0 |
| proposed (history) | **1** (L2 S1 `pit`) | **0** |
| pending | `pit` | none |
| resolved `decisions` | 0 (nobody clicked Yes/No) | 0 |
| `triggered_laps` | `[2]` | `[]` |

Harvest (pending cleared each time): **107** trigger kinds skip never
sees — mostly `pit` on successive laps, plus `safety_car` (e.g. L23–L26,
L31–32, L53–57, L65–68) and `tactical` when gap-ahead < 1 s.

`CONFIRM_STRAT` never fires on either path: the clock starts at lap 1
sector 0, and that trigger requires `lap == 1 and is_new_lap`. Pre-existing;
not introduced by skip.

**Reading:** same final state; intermediate Watch history is missing on
skip because fewer ticks occurred and `check_triggers`/`propose` were
never called. That is Branch 1 of the brief (equivalent finals, legitimate
history gap) — not a wrong RaceState.

---

## Block F1.2 — what was done

Left the button available. Gated it:

```python
if clock and show_technical() and st.button("Skip to chequered flag"):
```

Default **Show technical detail** is off, so the control is absent on the
event-facing Watch screen. Screenshot harness
`scripts/_f1_screenshot_supplement.py` now turns that toggle on before
clicking skip.

Did **not** route skip through 287× `propose()`/`recommend()`. The first
real `propose()` at L2 is a full MC recommend and hung the F1.1 probe for
minutes — not something to dump into one Streamlit rerun.

Regression: `tests/test_ui_text.py::TestSkipToFlagGated`.

---

## Block F1.3 — rendered-value spot check

Formatter used by the gold callout is now `format_callout_delta` /
`recommendation_caveat` in `src/aris/ui_text.py`; the panel renders those
strings (label via `html.escape(rec.label)`, no slice). CSS has no
ellipsis on `.headline`. Script: `scripts/_f1_render_spotcheck.py`.
Log: `results/f1_render_spotcheck.log`.

### 2025 Zandvoort (full weekend, n=20)

`build_race_state` L25 VER: MEDIUM, tyre_life=2, SC caveat set
(matches F.8 live-state compound/life).

| Layer | Value |
|---|---|
| `recommend()` rank 1 | `Pit lap 33 for HARD` |
| engine `delta_vs_stay_out_s` | **−48.3423…** (MC, seed 42, 15 draws) |
| callout headline | `Pit lap 33 for HARD` (full, unescaped change) |
| callout delta | **`-48.3s vs stay out`** (`.1f` of the engine float, not a different number) |
| caveat strip | `Note: based on Safety Car-affected recent pace — lower confidence` |
| others | Pit lap 30 for HARD; Stay out on current tyres |

No truncation, no hardcoded copy, caveat matches `RaceState.confidence_caveat`
and `narration_context`.

The F.8 **−13.00 s** figure is `simulate()` of the What-if slider (pit lap
30 HARD), shown as the secondary metric “This what-if vs stay out”. The
gold callout is `recommend()`’s top row. Different functions; both still
match F.8 labels. Rendering check is the callout path.

### 2024 Bahrain (race-only, weekend-form-blank)

weekend_form n=0, types=`['R']`. Empty copy:

> Waiting for FP1 data… Weekend form needs practice (FP1, or Sprint long
> runs) and preferably qualifying. Race-only ingest is not enough.

`recommend()` L20 VER:

| Layer | Value |
|---|---|
| rank 1 | `Pit lap 22 for MEDIUM` |
| engine delta | **−95.2117…** |
| callout headline | `Pit lap 22 for MEDIUM` |
| callout delta | **`-95.2s vs stay out`** |
| caveat strip | none (state caveat is None; evidence has no `caveat:`) |
| others | Pit lap 23 for MEDIUM; Stay out on current tyres |

**RENDER MATCH** both scenarios.

---

## Block F1.4 — `ARIS_FAST_CLOCK`

Preferred state already held: the flag is **absent by default** and only
`ARIS_FAST_CLOCK=1` opts in (`fast_clock_enabled()`). `"true"` / `"0"` /
unset all keep the 25 s cadence.

Added:

- `UserWarning` when a `SectorClock` is constructed with the flag on
- unit tests for absent/off values, warning, and pause still honoured
- day-of checklist: **must be unset** for the audience; do not put it in
  Streamlit secrets or the demo shell

Not present in `.env` or `.streamlit/`. Screenshot path remains
`scripts/_f1_fast_clock_streamlit.py` (monkeypatch) or an explicit
`ARIS_FAST_CLOCK=1` per run.

Event day: unset. Documented in `docs/zandvoort-day-of-checklist.md`.

---

## Test suite

Docker Postgres up (`aris-postgres` healthy). `ARIS_DB_URL` set. Flag unset.

| Checkpoint | Result |
|---|---|
| Full pytest | **169 passed**, 0 failed (`results/f1_pytest.log`; 100% green, exit 0) |
| `tests/test_ui_text.py` | 19 tests (was 9): callout format, caveat, fast-clock warning, skip gate |
| Zandvoort smoke | **SMOKE OK** (`results/f1_zandvoort_smoke.log`) |

### F.8 / E4.1 lock-in after these changes

| Check | Aimed | Actual | Result |
|---|---|---|---|
| Track | 72 / 18.5 / 0.08·0.05·0.03 | same | **PASS** |
| Prewrite | A:[18] B:[29] C:[18,40] | same | **PASS** |
| Weekend form | n=20 | 20 | **PASS** |
| Clock | 287 ticks → L72 complete | 287, complete=True | **PASS** |
| L25 | MEDIUM tyre_life=2 | same | **PASS** |
| What-if | −13.00 s; MC −32.62 / −13.35 | same | **PASS** |
| Ask/recommend | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | same | **PASS** |
| Postrace | `123_VER_postrace.json`, finish=2 | same | **PASS** |

Exact match to `docs/ZANDVOORT-2026-READINESS.md` E4.1 and
`docs/PHASE-F-SUMMARY.md` F.8.

---

## Files

| File | Change |
|---|---|
| `apps/pages/01_Strategy.py` | Skip button behind `show_technical()` |
| `apps/components/recommend_panel.py` | Callout uses shared formatters |
| `src/aris/ui_text.py` | `format_callout_delta`, `recommendation_caveat` |
| `src/aris/engine/clock.py` | `fast_clock_enabled()`, startup warning |
| `tests/test_ui_text.py` | Format / clock / skip-gate tests |
| `docs/zandvoort-day-of-checklist.md` | Fast-clock + technical-toggle event-day rules |
| `scripts/_f1_skip_vs_tick.py` | F1.1 comparison |
| `scripts/_f1_render_spotcheck.py` | F1.3 traces |
| `scripts/_f1_screenshot_supplement.py` | Enable technical toggle before skip |
| `docs/PHASE-F1-SUMMARY.md` | This summary |

---

## Stop

Phase F.1 is complete pending review of this summary. **Phase G (walk-forward
backtest engine) does not start until you say so.**
