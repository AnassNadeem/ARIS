# Ghost Car — Remediation Plan

**Status:** Ship-it MVP in progress (2026-09-01). Historical audit below is kept as-is.
**Author:** Automated audit (read-only), extending the previous ghost-playback audit.
**Date:** 2026-08-31 (audit) / 2026-09-01 (current scope)
**Primary evidence race:** Miami International Autodrome 2026 = **year 2026, round 6**
(`data/replay_r2/replay/2026/6/`). Verified via `meta.circuit_name = "Miami International Autodrome"`,
`total_laps = 57`, 22 drivers. (The previous audit accidentally read round 5 = Shanghai.)

---

## Current scope (ship-it MVP, 2026-09-01)

What is in the product now, and what is explicitly out:

- **Timing tower ARIS row stays.** Ranking uses `rank_ghost_by_gap`; strategy panel / tower stay in sync (ghost-recompute rollback). This is the visible ARIS demo in replay.
- **Map ghost dot is hidden by default.** `ghostMapFeatureEnabled()` in `frontend-next/lib/api.ts` is off unless `NEXT_PUBLIC_ARIS_GHOST_MAP=1`. Root cause is a backend GPS-projection bug in `backend/sessions.py` (`stabilize_path_fracs` / `project_points_along_path` wrap heuristic); confirmed on real cars (e.g. LEC Miami), not ghost-specific. Re-enable the dot after that data is re-derived.
- **Live ARIS is "coming soon."** The live hub (`LiveSessionPicker`) disables the ARIS On control with that message; unused `NoLiveSession` is gated the same way; `ARISConsole` forces `isARISOn` off on live entry. Base live timing (watch a session without ARIS) is unchanged. Advisory-only live `recommend()` is deferred.
- **Tower start order uses qualifying `grid_position`** when `lapFrac < 0.02` (lights-out), not FastF1's lap-1 classified position. Ghost is pinned to the same grid slot at start. Map-dot start alignment is still limited by the GPS-projection bug above and is not claimed as fixed.
- **DNF/DNS cars are hidden from the track map** (still listed at the bottom of the tower).
- **Known limitation — map cars can still appear off the start/finish line** because `pos_samples.path_frac` is not grid-snapped. That is a data-generation issue, not a tower issue.

**Deploy target (unconfirmed from the repo):** repo-root `wrangler.jsonc` still serves `./frontend/dist` (Vite). `frontend-next` is wired for Cloudflare Pages static export (`CF_PAGES`). There is no Pages deploy workflow in this repo. **Confirm in the Cloudflare dashboard which URL is actually live before submitting/demoing** — if the Worker/Vite app is production, none of the `frontend-next` work is visible until Pages is the live target.

---

## 0. Evidence gathered this round

### Ghost vs real position (Miami 2026, driver ANT)

| Lap | Ghost `position` (file) | Ghost `cumulative_delta_s` (file) | ANT real classified `position` |
|-----|--------------------------|-----------------------------------|--------------------------------|
| 1 | 23 | 0.0 | 2 |
| 2 | 23 | 0.0 | 2 |
| 3 | 23 | 0.0 | 2 |
| 4 | 23 | 0.0 | 1 |
| 5 | 23 | 0.0 | 2 |
| 6 | 23 | 0.0 | 3 |
| 7 | 23 | 0.0 | 3 |
| 8 | 23 | 0.0 | 3 |
| 9 | 23 | -7.035 | 3 |
| 10 | 23 | -9.185 | 3 |

- **P23 is impossible** — the field is only 22 cars, so 23 = "ranked behind every real car."
- `gap_to_leader_s` in the ghost file grows without bound: 31 → 64 → 96 → 127 → 238 → 364 → … → **6742s** by lap 57.
- For laps 1–8 `cumulative_delta_s = 0.0`, meaning the ghost strategy is identical to what ANT
  actually did. So the ghost position **should equal ANT's real position (P2/P1/P3)** on those laps.

### Where `position` comes from (backend)

- `src/aris/ghost.py` → `score_parallel_ghost()` → `_rank_ghost_in_field(ghost_cum_anchored, field_now, fallback)`.
- `position = 1 + (number of real drivers whose cumulative time is lower than the ghost's)`.
- The ghost's absolute time is *anchored*: `ghost_cum_anchored = anchor - cumulative_delta_s`, where
  `anchor = field_now.get(focus_code, real_cum_actual)` and `field_now` comes from
  `field_cumulative_by_lap()`.

### Two independent defects proven

1. **Stale R2 files.** The anchor logic is committed at `c2e157c` ("Phase 5/6: ghost timing tower
   anchor fix…", 2026-08-31 19:30). But `ghost_ANT.json` on disk was built **2026-08-30 18:19** —
   *before* the fix. Reproducing the ranking with the **current committed code** yields
   pos ≈ 3/3/3/2/5/7/8/8/13/15 for laps 1–10 — **not** the file's frozen 23. Therefore the on-disk
   (and almost certainly the R2-bucket) files predate the fix.
   - `.github/workflows/prebuild_race.yml` only triggers on pushes touching
     `scripts/prebuild_race_r2.py`, `deploy/r2_upload.py`, or the workflow file — **not**
     `src/aris/ghost.py`. So the anchor-fix commit did not retrigger a rebuild.
   - The workflow runs `--all-completed --skip-existing`, so even a scheduled/manual run **skips**
     the already-present Miami files. They will never be overwritten without a force.

2. **Ranking algorithm still wrong for non-clean races.** Even with the anchor fix, the reproduced
   positions drift (P5/P7/P13 over laps 5–10) because `field_cumulative_by_lap()` sums only the laps
   for which a driver has a `lap_time_s` and **never accounts for laps completed**. A car that retires
   early (Miami had one around lap 4) freezes at a tiny cumulative and is treated as the "leader"
   forever (observed `leader_cum` frozen at 390.7s from lap 5 on). `_rank_ghost_in_field` then ranks
   against a meaningless cumulative. Also, when `cumulative_delta_s ≈ 0` the code does **not** simply
   inherit the real driver's classified `position`; it re-derives from cumulative time and can land
   off by one or more even in a clean lap.

---

## 1. Confirmed bugs (ranked; each backed by evidence above)

### BUG-1 — Ghost timing-tower position is garbage (frozen P23) due to STALE R2 files
- **What:** Every Miami-2026 ANT tick has `position = 23` for all 57 laps; `gap_to_leader_s` diverges to thousands of seconds.
- **Why:** R2 `ghost_*.json` were generated before the committed anchor fix, and the prebuild pipeline neither retriggers on `src/aris/ghost.py` changes nor overwrites existing files (`--skip-existing`).
- **Files:** `data/replay_r2/replay/**/ghost_*.json` (artifacts); `.github/workflows/prebuild_race.yml` (trigger paths + `--skip-existing`); regeneration entrypoint `scripts/prebuild_race_r2.py`.
- **Severity:** **HIGH — recruiter sees this instantly.** A car that started P2 shown as P23/last is the single most damaging visible defect.

### BUG-2 — Ranking algorithm is incorrect for races with retirements / SC / lapping
- **What:** Even after regeneration, ghost position will be visibly wrong whenever a car retires early, the field gets lapped, or an SC/red-flag inflates lap times unevenly.
- **Why:** `field_cumulative_by_lap()` ignores laps-completed and freezes retired cars as artificial leaders; `_rank_ghost_in_field()` ranks by that broken cumulative. When `cumulative_delta_s ≈ 0`, position is not anchored to the real driver's classified `position`.
- **Files:** `src/aris/ghost.py` (`field_cumulative_by_lap`, `_rank_ghost_in_field`, `score_parallel_ghost`, and `_estimate_ghost_position` which is also gap-based/approximate).
- **Severity:** **MEDIUM-HIGH.** Regenerating without this fix produces "less wrong" but still-off numbers during incidents (Miami is exactly such a race).

### BUG-3 — Ask ARIS / Copilot silently falls back to a canned mock with no user indication
- **What:** When the backend is unreachable, every question returns a canned scoring string; the "every question returns the same output" symptom.
- **Why:** `askARIS`/`chatCopilot` (`frontend-next/lib/api.ts`) call `tryFetch`, which returns `null` on any failure, then silently return `mockAskAnswer`/`mockCopilotAnswer`. In a static Cloudflare Pages export, `next.config.ts` **skips all rewrites** (`staticExport = Boolean(process.env.CF_PAGES)`), so unless `NEXT_PUBLIC_API_BASE` is set to the Heroku origin at build time, `/api/ask` and `/api/copilot/chat` resolve same-origin and 404 → silent mock. There is no UI signal that this happened.
- **Files:** `frontend-next/lib/api.ts` (`askARIS`, `chatCopilot`, `mockAskAnswer`, `mockCopilotAnswer`, `tryFetch`), `frontend-next/next.config.ts`.
- **Severity:** **HIGH** if a recruiter asks any question.

### BUG-4 — No intent classification (factual vs strategic)
- **What:** No deterministic race-state lookup path; `mockAskAnswer` is three keyword branches plus a catch-all that returns identical text.
- **Files:** `frontend-next/lib/api.ts`, `frontend-next/components/aris/ARISComms.tsx`, `frontend-next/components/aris/CopilotPanel.tsx`.
- **Severity:** **MEDIUM.**

### BUG-5 — Hardcoded driver name in sample chips
- **What:** `ARISComms.tsx:13` chip reads `"Gap to Lando?"`; `CopilotPanel` chips hardcode `NOR`/`VER`.
- **Files:** `frontend-next/components/aris/ARISComms.tsx`, `frontend-next/components/aris/CopilotPanel.tsx`.
- **Severity:** **LOW** (cosmetic, but recruiter-visible; brief asked for generic wording).

### BUG-6 — Pre-race analytics leak (sector/speed visible before "Start Race")
- **What:** Sector times and speeds appear before the user clicks Start.
- **Why:** `ReplayFrameFeed.tryR2()` calls `this.tick()` immediately on connect and every 250 ms; `tickR2()` computes `r2FrameAt(field, elapsedS = 0)` and calls `applyPayload`, which populates the store's `cars` (including lap-1 sectors/speed) regardless of play state. `consolePlayState === "racing"` only gates *elapsed advancement* (`liveFeed.ts:898`), not data population. No analytics panel gates on `consolePlayState` (only `PlaybackControls`, `ARISConsole`, `RaceFinishedDebrief`, the recommend loop, and comms narration do).
- **Files:** `frontend-next/lib/liveFeed.ts` (`tryR2`, `tickR2`), analytics panels under `frontend-next/components/panels/`.
- **Severity:** **MEDIUM** (visible before Start).

### BUG-7 — Deploy ambiguity: repo pipeline ships the Vite `frontend/`, not `frontend-next/`
- **What:** The audited UI (`frontend-next/`) may not be what production actually serves.
- **Why:** `package.json` `build:ui` = `npm --prefix frontend ci && npm --prefix frontend run build`; `wrangler.jsonc` serves `./frontend/dist` (the older Vite app) via a Worker + `ArisApi` Durable Object. `frontend-next/` is wired for Cloudflare **Pages** static export (`CF_PAGES`), but there is **no Pages deploy workflow in the repo**. So there are two candidate frontends and the repo only automates the Vite one.
- **Files:** `package.json`, `wrangler.jsonc`, `frontend-next/next.config.ts`.
- **Severity:** **HIGH if unresolved** — a frontend fix could target a UI that isn't live. **UNVERIFIED** (see §4).

### BUG-8 — (carried from prior audit) `deriveGhostSlice` not reactive to driver change
- **What:** Switching driver mid-session doesn't re-derive `ghostLapS`/`ghostCumulativeS`.
- **Why:** `deriveGhostSlice` runs only in `setR2RaceField`/`setGhostTicks`/`mergeGhostTicksFrom`, not in `setSelectedDriver`/`setARISDriver`.
- **Files:** `frontend-next/store/raceStore.ts`.
- **Severity:** **MEDIUM** — stale ghost after driver swap until ticks reload.

### BUG-9 — (carried, UNVERIFIED) high-speed backward jump
- **What:** Possible backward animation at 25×/50× when a tick advances > 0.5 lap.
- **Files:** `frontend-next/lib/deadReckoning.ts` (`wrappedDelta`, `PathCarAnimator`).
- **Severity:** **LOW-MEDIUM**, and **UNVERIFIED** — needs a live browser to reproduce.

---

## 2. Proposed fix sequence (and why this order)

1. **Fix the backend ranking first (BUG-2).** Regenerating artifacts on top of a wrong algorithm just
   bakes wrong numbers again. Correct `field_cumulative_by_lap`/`_rank_ghost_in_field` (or replace the
   cumulative-time ranking with real classified `position` when `|delta|` is small, and only adjust by
   places-gained/lost from `delta` vs rival gaps). Validate the reproduction reproduces ANT ≈ P2/P1/P3
   on laps 1–8 for Miami.
2. **Regenerate R2 artifacts (BUG-1).** After the algorithm is correct, force a rebuild (drop
   `--skip-existing` or delete the affected `ghost_*.json`), re-upload to R2, and fix the workflow
   trigger so `src/aris/ghost.py` changes also retrigger a (forced) prebuild. Do this *after* step 1 so
   the regenerated files are correct.
3. **Verify the frontend display (no expected change).** The prior audit confirmed the tower reads the
   tick `position` correctly; once the data is right, confirm the tower shows P2 and the map dot is
   independent. Only touch frontend here if a mismatch appears.
4. **Ask ARIS (BUG-3, BUG-4, BUG-5).** Decide the canonical wiring (Copilot vs simple Ask), surface a
   visible "offline / using cached answer" state instead of silent mock, add intent classification
   (factual → deterministic race-state lookup; strategic → LLM), and de-hardcode the sample chips.
5. **Pre-race gate (BUG-6).** Hold analytics population/rendering until `consolePlayState === "racing"`
   (or clear/skeleton the panels while `"ready"`).
6. **Reactivity + animation (BUG-8, BUG-9).** Re-derive the ghost slice on driver change; then
   reproduce and, if confirmed, fix the high-speed wrap. BUG-9 must be reproduced in a browser first.
7. **Resolve deploy ambiguity (BUG-7).** Confirm which frontend Cloudflare Pages builds, then set the
   correct build-time env (`NEXT_PUBLIC_API_BASE` → Heroku origin, `NEXT_PUBLIC_ARIS_COPILOT` as
   desired). This underpins whether any of the frontend fixes are even user-visible.

---

## 3. Layer per fix (backend / frontend / both / ops)

| Bug | Backend | Frontend | Data/CI | Ops/Config |
|-----|:------:|:--------:|:-------:|:----------:|
| BUG-1 stale files | — | — | ✅ regenerate + fix workflow trigger/force | — |
| BUG-2 ranking algorithm | ✅ `src/aris/ghost.py` (+ tests) | — | ✅ regen after | — |
| BUG-3 silent mock fallback | possibly (endpoint reachability) | ✅ `api.ts` UI signal | — | ✅ set `NEXT_PUBLIC_API_BASE` |
| BUG-4 intent classification | ✅ or frontend deterministic lookup | ✅ routing | — | — |
| BUG-5 hardcoded chips | — | ✅ | — | — |
| BUG-6 pre-race leak | — | ✅ `liveFeed.ts` + panels | — | — |
| BUG-7 deploy ambiguity | — | — | — | ✅ confirm Pages target + env |
| BUG-8 driver-change reactivity | — | ✅ `store/raceStore.ts` | — | — |
| BUG-9 high-speed wrap | — | ✅ `deadReckoning.ts` | — | — |

---

## 4. Still unverified / unresolved after this round

- **Actual Cloudflare Pages / Worker env values** (`NEXT_PUBLIC_ARIS_COPILOT`, `NEXT_PUBLIC_API_BASE`)
  — set outside the repo (Cloudflare dashboard). Code default in a production build is
  `copilotFeatureEnabled() = false` (so **Ask ARIS**, not Copilot, unless `=1` at build). Not confirmable from the repo.
- **Which frontend is actually live** (Vite `frontend/` via Worker vs `frontend-next/` via Pages). The
  repo automates only the Vite build; the brief assumes Pages serves `frontend-next`. Must be confirmed
  before trusting any frontend-side conclusion (BUG-3/4/5/6/8/9).
- **Reachability of `/api/ask` and `/api/copilot/chat` in production** — depends on the two items above
  plus whether the Heroku backend is up. Not tested (no network access to prod from here).
- **Correct ghost position target during SC / red flag / lapped cars** — needs a design decision
  (inherit classified `position` + delta-adjust, vs a corrected cumulative that counts laps-completed
  and excludes retired cars) and cross-validation on several races, not just Miami.
- **BUG-9 high-speed backward jump** — no dev server / browser available this session (terminal shows
  the last command was `git push`, not a running server). Every runtime claim in AUDIT TASK 4 is
  therefore **unverified**.

### AUDIT TASK 4 status
No live browser or running dev server was available, so none of the runtime reproductions (Miami lap-10
tower/map screenshot, 25×/50× backward-jump on Monaco vs Spa, mid-replay driver swap) were performed.
These remain **unverified** and should be run before fixing BUG-9 and validating BUG-1/BUG-2 end-to-end
in the browser.

---

## 5. Effort estimate (small/contained vs multi-file)

**Small / contained**
- BUG-5 (de-hardcode chips): 1–2 files, trivial.
- BUG-6 (pre-race gate): 1 guard in the feed and/or a shared panel gate; contained.
- BUG-8 (driver-change reactivity): one store action wiring change.
- BUG-1 (regenerate artifacts): a data/CI operation (force rebuild + re-upload), plus a small workflow
  edit; low code risk but must follow BUG-2.

**Multi-file / larger**
- BUG-2 (ranking rewrite): `src/aris/ghost.py` + `tests/test_ghost.py` + regeneration + cross-race
  validation. This is the core correctness work.
- BUG-3 + BUG-4 (Ask ARIS reachability signal + intent routing + deterministic lookups): frontend
  `api.ts`/components and possibly a backend endpoint; touches several files.
- BUG-7 (deploy ambiguity): investigation + ops/config; may reshape which frontend is canonical and
  therefore how much of the frontend work matters.
- BUG-9 (high-speed wrap): small code change *if* confirmed, but blocked on runtime reproduction.

---

## 6. One-line summary for the reviewer

The recruiter-visible "P23" is **stale pre-fix R2 data** (BUG-1), sitting on top of a **ranking
algorithm that is still wrong for races with retirements/SC** (BUG-2); fix the algorithm, then
force-regenerate, then confirm which frontend is actually deployed (BUG-7) before spending effort on
the Ask-ARIS/pre-race/animation frontend fixes (BUG-3–6, 8–9).
