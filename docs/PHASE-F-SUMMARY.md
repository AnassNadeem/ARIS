# Phase F summary — Dashboard UX and structure

Executed 2026-08-13. Scope: Blocks F.1–F.8. The Zandvoort demo path
(`apps/pages/01_Strategy.py` + `scripts/_e1_smoke_strategy_zandvoort.py`)
was treated as phase-blocking: restyle is a failure if that path regresses.

**Aimed vs actual** here is checklist pass/fail against the criteria below,
not a numeric MAE table. Same rigor, different unit.

---

## Verdict (read this first)

**Would you send this link to a stranger with no explanation attached?**

**Yes — to a technical or motorsport-literate stranger.** The new Home
page states what ARIS is, the unofficial/not-affiliated disclaimer, the
real held-out numbers (calendar 0.583 s, Zandvoort pass, China miss of
0.033 s), and two doors (Strategy vs lap explorer). A first visit no
longer lands on a snake_case chart with a sidebar named `streamlit app`.

I would **not** claim this is a consumer product site. Streamlit’s
Deploy button, collapsed-sidebar-on-phone, and a ~20 s What-if score
are still the framework. Those are acceptable constraints, not hidden.

The rehearsed Zandvoort smoke path **did not regress**.

---

## Block F.1 — Before-state critique

Screenshots: `results/f1_before/`. No production code was changed before
this audit. Postrace was **not reachable** in four minutes: the sector
clock waits 25 s / speed per tick (287 ticks). The before `07_*.png` is
still LIVE at lap 2, not POST_RACE. That is an audit gap, not a fake
postrace shot.

### Navigation

- Sidebar page title was **`streamlit app`**. A stranger has no idea
  that is the product home.
- Two competing paths to Strategy: Streamlit’s page list **and** a
  markdown `[Race Strategy](Strategy)` link. Same for “← Lap explorer”
  on the Strategy page — a blue markdown link next to a page button,
  two visual languages.
- No landing page. First URL was the lap explorer. The actual product
  (recommend a pit call) was a second click away, unlabeled as such.
- Strategy **Start / Reset session** lived in the sidebar; season /
  race / team / driver lived in the main pane. The CTA and the inputs
  were on opposite sides of the screen (`01_strategy_initial_setup.png`).

### Visual consistency

- Streamlit dark theme (F1 red primary) vs the timing tower’s neon
  `#b400ff` / `#00ff00` / `#ffff00` sector chips. The tower looked
  like a different app glued in (`03_strategy_live_watch.png`).
- Axis labels on the explorer were raw columns: `lap_time_s`,
  `lap_number`.
- Strat cards were three naked `st.metric` + text inputs. Recommended
  plan was a ⭐ prefix, not a card. Estimated race time was **5575s**
  — a raw second count, not a clock (`02b` before).
- Default Strategy team was **Alpine / COL** (alphabetical), not a
  driver anyone opening a Dutch GP link would expect.

### Information hierarchy

- The decision — the only reason this exists — was a chat bubble and
  an expander. What-if put `st.metric` and `MC P10/P90` above buried
  `#1/#2/#3` expanders. The SC/VSC caveat string from Phase E lived
  inside `evidence` inside those expanders. A stranger would never
  see it.
- Watch mode at lap 2: timing tower on the left, **empty black** on
  the right. No “ARIS is watching” copy. Looked broken
  (`03_strategy_live_watch.png`).
- Ask: Streamlit `chat_input` floated over the tower
  (`04_strategy_ask.png`).
- Replay scrubber overlapped S2/S3/Last of the tower
  (`06_strategy_replay.png`).

### Blank / confusing states (E1.4 and others)

- `weekend_form()` empty → the whole “Weekend form” block was skipped.
  2024 Bahrain (race-only ingest) showed strat cards and **no
  explanation** that FP/Q was missing (`02b` before). That is the
  E1.4 weekend-form-blank case.
- “No sessions ingested.” / “No races for {year}.” — engineer-speak,
  no next step.
- Leaderboard already had “Waiting for race data…” — the one empty
  state that was already honest.

---

## Blocks F.2–F.7 — checklist

| # | Criterion | Result | Evidence |
|---|---|---|---|
| F.2 | A first-time visitor understands what ARIS is within a few seconds, unaided | **MET** | `results/f1_after/00_home.png` vs `results/f1_before/00_lap_explorer.png` |
| F.2 | Honesty framing: unofficial disclaimer linked | **MET** | Home + every page footer → `https://github.com/AnassNadeem/ARIS#readme` |
| F.2 | Real headline numbers (not marketing): calendar blend **0.583 s** aimed ≤ **0.783 s**, 23/24; NL 2024 **0.502** / 2025 **0.566**; China **0.596** vs **0.563**, miss **0.033 s** | **MET** | Home stat cards; China card is amber “still a miss” |
| F.2 | Clear navigation into lap explorer vs Strategy | **MET** | Sidebar Home / Strategy / Lap explorer + two `st.page_link` CTAs on Home |
| F.3 | Limited palette, type scale, spacing applied across explorer, Strategy, and `apps/components/` | **MET** | `apps/theme.py` + `.streamlit/config.toml`; IBM Plex Sans/Mono |
| F.3 | Timing tower does not clash with native widgets | **MET** | Toned sector chips (`#7C3AED` / `#22C55E` / `#CA8A04`), shared surface/border, `aris-tower` CSS vs neon before (`03` after vs before) |
| F.4 | Recommendation / decision is visually the product | **MET** | Gold `aris-callout` on What-if (`05` after: “Pit lap 10 for HARD”, Δ vs stay out) and mid-race Watch (`03b`: “ARIS RECOMMENDS”) |
| F.4 | Phase E SC/VSC caveat is prominent, not buried | **MET** | Yellow caveat strip on the callout: “based on Safety Car-affected recent pace — lower confidence” (`03b`) |
| F.5 | Weekend-form-blank-until-FP/Q (E1.4) is a message, not a hole | **MET** | `02b` after: “Waiting for FP1 data… Race-only ingest is not enough.” (2024 NL race-only; same case as Bahrain) |
| F.5 | Other blank-until-data states from F.1 | **MET** | Setup: “No session started” + sidebar CTA (`01` after). Watch: “ARIS is watching…” (`03` after). Ask: example prompt (`04` after). Postrace empty decision log (`07` after) |
| F.6 | Simple/technical toggle; dense numbers off by default | **MET** | Sidebar “Show technical detail” default off. Explorer MAE hidden until on. What-if MC P10/P90 and σ only when on (`05` after shows deltas, not σ/P10) |
| F.7 | Nothing seriously broken at phone width | **MET** (Streamlit limits accepted) | `08_mobile_home.png`: stats stack, readable. `08_mobile_strategy.png`: empty-state + disclaimer; sidebar behind `»` (framework, not fought) |

### F.2 before / after

- **Before:** `/` was the lap explorer. Caption: “Phase 2 dashboard — lap-time traces…”. Sidebar “About ARIS” was hybrid-physics jargon.
- **After:** `/` is Home. One sentence value prop, three honest MAE cards, two doors.

### F.3 before / after

- **Before:** neon tower, 5575s, Alpine/COL default, `streamlit app` nav.
- **After:** shared tokens, race time as `1:53:57`, default **Red Bull / VER** when present, nav labels Home / Strategy / Lap explorer.

### F.4 before / after

- **Before:** recommend inside expanders / chat; caveat inside `evidence`.
- **After:** gold callout + caveat strip. What-if still shows the slider experiment as a secondary metric (“This what-if vs stay out”).

### F.5 before / after

- **Before:** race-only weekend form = missing section.
- **After:** dashed empty-state with the FP1 sentence. Setup / Watch / Ask / postrace log have the same pattern.

---

## Block F.8 — Zandvoort demo path re-verification

Command: `python scripts/_e1_smoke_strategy_zandvoort.py`  
Log: `results/f8_zandvoort_smoke.log`  
Against the restyled UI code (same engine path the Strategy page calls).

| Check | Aimed / expected | Actual | Result |
|---|---|---|---|
| Track config | 72 laps, pit 18.5, globals 0.08/0.05/0.03 | `total_laps=72` `pit_loss=18.5` slopes SOFT/MED/HARD **0.08/0.05/0.03** | **PASS** |
| Prewrite windows | A≈18 / B≈29 / C≈18+40 | **A:[18] B:[29] C:[18,40]** | **PASS** |
| Weekend form | sessions ingested | **n=20** | **PASS** |
| Live clock | complete to lap 72 | **287 ticks → lap 72 complete=True** | **PASS** |
| Mid-race state | L25 usable | L25 MEDIUM tyre_life=2 | **PASS** |
| What-if | finite delta + MC band | delta **−13.00 s**, MC P10/P90 **−32.62 / −13.35** | **PASS** |
| Ask/recommend | ≥1 rec | Pit lap 33 HARD; Pit lap 30 HARD; Stay out | **PASS** |
| Postrace | export written | `123_VER_postrace.json`, finish=2 | **PASS** |

**SMOKE OK.** Numbers match the E4.1 lock-in table in
`docs/ZANDVOORT-2026-READINESS.md` exactly (same deltas, same rec
labels, same finish). No functional regression.

Button labels the demo uses are unchanged: **Start / Reset session**,
**Lock strategy & start race**, modes Watch / Ask / What-if / Replay.

Additive (not on the rehearsed path): **Skip to chequered flag** on
the live tower, so postrace UI can be reached without 287×25 s ticks.
Used only for after-screenshots and as a replay convenience.

### After screenshots

Same names as F.1, plus Home and mobile, under `results/f1_after/`:

| File | State |
|---|---|
| `00_home.png` | Landing (new) |
| `00_lap_explorer.png` | Explorer (was home) |
| `01_strategy_initial_setup.png` | Strategy, no session |
| `02_strategy_prerace.png` | 2025 NL, weekend form + strat cards |
| `02b_strategy_prerace_bahrain_blank_form.png` | 2024 race-only, FP1 waiting copy |
| `03_strategy_live_watch.png` | Watch, early laps, watching empty-state |
| `03b_strategy_live_recommend.png` | Watch + gold rec + SC caveat |
| `04_strategy_ask.png` | Ask empty prompt |
| `05_strategy_whatif.png` | Rec callout + what-if delta |
| `06_strategy_replay.png` | Replay scrubber |
| `07_strategy_postrace.png` | POST_RACE, export, finish=2 |
| `08_mobile_home.png` | 390×844 Home |
| `08_mobile_strategy.png` | 390×844 Strategy setup |

---

## Deferred, and why

1. **Before-state POST_RACE screenshot.** The 25 s sector clock cannot
   finish 72 laps in a reasonable screenshot budget. After-state used
   Skip to flag. Honest gap in F.1, not a faked before shot.
2. **What-if `recommend()` latency (~15–30 s).** Pre-existing MC cost.
   Spinner added (“Scoring pit options…”) so it does not look blank.
   Not a model change.
3. **Streamlit Deploy / `»` sidebar on phone.** Framework chrome.
   F.7 accepted this.
4. **SC What-if deltas still look extreme (−160 s).** Known E4 caveat.
   F.4 makes the caveat *visible*; it does not scrub lags. Correct.
5. **`st.navigation` built-in sidebar list** did not render with
   `showSidebarNavigation = false`. Worked around with explicit
   `st.page_link` on the Page objects. Same three destinations.

---

## Test suite

Docker Postgres up; `ARIS_DB_URL` set.

| Checkpoint | Result |
|---|---|
| After F.2–F.6 code | **159 passed**, 0 failed (`results/f_pytest.log`) |
| `tests/test_ui_text.py` (new) | 9 passed (clock format, empty-form copy, `ARIS_FAST_CLOCK`) |
| Zandvoort smoke (F.8) | **SMOKE OK** (`results/f8_zandvoort_smoke.log`) |

New tests are Streamlit-free on purpose (CI has no browser). UI
helpers live in `src/aris/ui_text.py`. `ARIS_FAST_CLOCK=1` is
screenshot-only; default `should_tick` still uses the 25 s interval
(unit-tested).

---

## Files created / modified (high level)

### Created
| File | Reason |
|---|---|
| `apps/theme.py` | Palette, CSS, technical toggle |
| `apps/pages/00_Home.py` | Landing |
| `apps/pages/02_Lap_Explorer.py` | Explorer moved off `/` |
| `apps/components/recommend_panel.py` | Gold rec + caveat callout |
| `src/aris/ui_text.py` | Disclaimer, locked MAE constants, empty-form copy, race clock |
| `tests/test_ui_text.py` | Helpers + fast-clock |
| `docs/PHASE-F-SUMMARY.md` | This summary |
| `scripts/_f1_*.py` | Screenshot / fast-clock harness (not the demo path) |

### Modified
| File | Reason |
|---|---|
| `apps/streamlit_app.py` | `st.navigation` entry + page links |
| `apps/pages/01_Strategy.py` | Layout, callouts, empty states, skip-to-flag; **engine calls unchanged** |
| `apps/components/session_setup.py` | NL/VER defaults, empty copy |
| `apps/components/strat_cards.py` | Card chrome, `h:mm:ss` |
| `apps/components/leaderboard.py` | Shared tower CSS |
| `apps/components/aris_chat.py` | Ask empty prompt |
| `.streamlit/config.toml` | Palette; hide auto `pages/` nav |
| `src/aris/engine/clock.py` | Optional `ARIS_FAST_CLOCK` |
| `src/aris/plan/weekend_form.py` | `weekend_session_types()` for the empty message |

`01_Strategy.py` still: `generate_strat_plans` → `weekend_form` →
`SectorClock` → `check_triggers` / `propose` → `simulate` / `recommend`
/ `run_mc` → `compare_post_race` / `export_postrace`. That is the
rehearsed path.

---

## Stop

Phase F is complete pending review of this summary. **No later phase
work starts until you say so.**
