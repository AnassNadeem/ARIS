# Frontend performance & UX notes

Date: 2026-08-27  
Scope: `frontend-next` only. Does **not** change `src/aris` `recommend()` / `simulate()`.

## What changed

### Track map
- Car dots interpolate **distance along the racing line** (`PathCarAnimator`, ~900 ms ease to match ~1 Hz GPS). Cartesian dead-reckoning is not used for on-track dots.
- A `requestAnimationFrame` loop reads the Zustand store and writes SVG `transform`s. React only re-renders when the on-track car set changes (pit / DNF / new driver), not on every GPS tick.
- Sector polylines (S1 teal, S2 blue, S3 purple) come from FastF1 marshal markers projected onto the outline. Missing or unordered markers fall back to equal-distance thirds and log a console warning. Legend stays top-right.

### Lights-out
- `StartLightsOut` overlays the console until session + circuit outline + at least one timing/GPS frame are loaded.
- **Start** is disabled until then. Click plays five red lights (on… on… on… on… on → off), then replay/live clock starts at 1×.

### Add dropdown
- Header no longer clips with `overflow-x-auto`. The catalogue menu is portaled to `document.body` and positioned from the button’s `getBoundingClientRect`.

### Auto-scroll
- Removed `scrollIntoView()` from Main Comms / Ask / Copilot (it was scrolling the whole console). Chat panels only move their own `scrollTop`. Analytics tab bodies use `overflow-anchor: none` and stable `h-full` / `min-h-0` so arriving lap data does not yank the page.

### Main Comms
- With ARIS strategy on and the console in `racing`, the client calls `POST /api/aris/recommend` at lights-out, typical pit windows, and SC/VSC. Results land in `pendingRecommendation` + a narration line: `ARIS recommends: Pit lap 33 for HARD, Δ -2.4 s vs stay`.

### HTTP cache
- In-memory cache + inflight dedup in `lib/httpCache.ts`, used by `lib/api.ts`.
- TTLs: calendar/drivers 1 h (also `localStorage`); completed session summary 1 d; circuit outlines stay on the existing 7-day `localStorage` circuit cache. Concurrent identical GETs share one promise.

### SSE / store
- `mergeCars` keeps previous row object identity when a driver is unchanged. Timing tower rows are `memo`’d and ignore GPS fields. Store setters no-op when lap / phase / connection status did not change.

## How to verify

```powershell
cd C:\Users\anass\ARIS\frontend-next
npx tsc --noEmit
npx vitest run
```

Manual (broker on `:8765`, `npm run dev` in `frontend-next`):

1. **Replay** → pick a completed race → console. Start is grey until the map and first frame load; then five lights, then cars move on the racing line at 1×. S1/S2/S3 colours + legend. Dots should not jump off the asphalt.
2. DevTools **Performance**: map interaction should stay near 60 fps; React profiler should not flash every GPS tick for the whole tower (only changed rows).
3. Header **+ Add** → dropdown appears over the layout (not clipped).
4. Scroll the analytics row, wait for lap data: the viewport should not jump. Click a map dot to focus a driver (that *is* allowed).
5. Enable ARIS in the selector before start. After lights-out, Main Comms should show a recommendation/narration (or a stay-out fallback if the engine has no state). Network: `POST /api/aris/recommend`.
6. Leave Replay, come back to the same year: calendar/drivers should be instant (Network: from disk/memory, no duplicate in-flight). Application tab → `localStorage` keys `aris.http.v1.*` and `aris.circuit.v2.*`.

## Expected UX gains

- Smoother map (path-constrained 60 fps, no off-line teleport).
- Faster second navigations (calendar/drivers/circuits cached).
- Less jank: no full-console re-render on 1 Hz GPS, no scroll stealing when analytics fill in.
