# Standings page (2024–2026)

## What changed

ARIS has a **Standings** page next to Home / Live / Replay. The Circuits catalogue page was removed; live/replay track maps are unchanged.

- **Standings** (`/standings`, `/standings/{year}`) — driver and constructor championship tables for 2024, 2025, and 2026.
- Header nav: `Home | Live | Replay | Standings`.

### Backend

- `GET /api/standings/drivers/{year}` and `GET /api/standings/constructors/{year}` reject any year outside `{2024, 2025, 2026}` with HTTP 400:
  - `"Standings only available for 2024, 2025, and 2026."`
- 2024 / 2025 use Jolpica (cached; completed seasons use a longer TTL).
- 2026 uses the same Jolpica path. If the table is empty or Jolpica is down, the payload includes `"message": "2026 standings not yet available."`
- Existing `GET /api/circuits/{circuit_id}/layout` (map layout for live/replay) is unchanged. There is no Circuits catalogue API.

`src/aris` recommend / simulate logic was not touched.

### Frontend

- Year buttons `[2024] [2025] [2026]`.
- Tabs: Drivers | Constructors.
- Invalid URL years such as `/standings/2023` show the 3-year error copy (no request is made).

## How to verify

1. Start the broker and Next app:
   - Backend: `uvicorn backend.main:app --host 127.0.0.1 --port 8765`
   - Frontend: `npm run dev` in `frontend-next`.
2. Click **Standings** in the header.
   - Year buttons 2024 / 2025 / 2026.
   - Drivers table: pos, name, team, points, wins, podiums, FL, DNFs, gap.
   - Switch to Constructors.
3. Open `/standings/2023` — empty state: standings only for 2024–2026.
4. Confirm there is no Circuits nav link and `/circuits` is not a page.
5. Curl:
   - `GET /api/standings/drivers/2023` → 400.
   - `GET /api/standings/drivers/2024` (and 2025, 2026) → 200 table or 2026 `message`.

Unit tests: `pytest tests/test_standings_circuits_pages.py -q`

## Known limitations

- **2026 standings** depend on Jolpica publishing a driver/constructor table. Early-season or API outages surface as the not-available message rather than a guessed grid.
- The older Streamlit / Vite standings views still call `/api/standings/...`; years before 2024 now get 400 from the broker.
