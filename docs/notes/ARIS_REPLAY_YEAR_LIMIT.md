# ARIS — Replay limited to 2024–2026

Replay FastF1 session packs are restricted to **2024, 2025, and 2026** so the UI does not cold-download older seasons. Live OpenF1, standings, and non-replay calendars for other years are unchanged.

## What changed

**Backend**

- `ALLOWED_REPLAY_YEARS = {2024, 2025, 2026}` in `backend/calendar.py`.
- `POST /api/replay/init` and `POST /api/prewarm` return **400** for any other year with:  
  `Replay is only available for 2024, 2025, and 2026 to improve loading speed.`  
  FastF1 is not called.
- `GET /api/calendar/{year}?replay=1` uses the same check. Without `replay=1`, 2018–2026 calendars still work (live / standings).
- `sessions.load_session` and `build_ff1_replay_assets` raise before FastF1 if the year is outside the window.
- Boot calendar prewarm already only warms 2024–2026; round-session pack prewarm skips other years.

Logs:

- `Replay request for year X — allowed`
- `Replay request for year X — blocked (not in 2024–2026)`

**Frontend**

- Replay setup uses a compact **[2024] [2025] [2026]** season control instead of a full-year dropdown.
- Hover (and native `title`) tooltip: `Replay limited to 2024–2026 for faster loading.`
- Default season is the most recent **completed** year in the window (2025 until December 2026).
- `?year=2023` (old bookmarks) shows: `Replay is only available for 2024, 2025, and 2026.` and stays on a valid year.

## How to verify

1. Restart the API process so it loads the new guards (`scripts/run-backend.ps1`).
2. `POST http://127.0.0.1:8765/api/replay/init` with `{"year":2023,"round_number":1,"session_type":"R"}` → **400**, and logs contain `blocked (not in 2024–2026)`. No `[ARIS] Loading replay session 2023 … via FastF1`.
3. Same endpoint for **2024 / 2025 / 2026** → 200 and `Replay request for year X — allowed`.
4. Open `/replay` → only three season buttons. Hover one → tooltip.
5. Open `/replay?year=2023` → red notice; 2025 (or latest completed) remains selected.
6. Pick a **2025** completed race and start replay → existing pack / FastF1 path as before.

Automated: `pytest tests/test_replay_year_limit.py` and `npx vitest run lib/liveMap.test.ts` from `frontend-next`.

## Load-time impact

Blocked years no longer pay a FastF1 session download (often **10–60+ seconds** cold, plus cache disk). Measured on this machine with TestClient (lifespan off):

| Request | Result | Time |
|---|---|---|
| `POST /api/replay/init` year **2023** | 400, no FastF1 | **89 ms** |
| `GET /api/calendar/2023?replay=1` | 400, no FastF1 | **4 ms** |
| `POST /api/replay/init` year **2025** R1 | 200, normal FastF1 path | **7.4 s** (cached metadata; pack job continues in background) |

The win is avoiding the 2023 (and older) FastF1 download entirely. 2024–2026 load times are unchanged.
