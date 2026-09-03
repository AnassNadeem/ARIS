# ARIS — How to Run & Test (T12)

Step-by-step local runbook for the T12 Explainability Dashboard (Degradation Curves, Ghost vs Real, Race Debrief) on the Next.js pit-wall (`frontend-next`). Postgres is **not** required for this pass.

T12 is read-only over existing search internals. `recommend()` and `simulate()` are unchanged.

---

## 1. Prerequisites

### Python

- **Python 3.11** (repo pin: `3.11.9` in `.python-version`). CI uses `uv python install 3.11`.
- Repo venv at `.venv/` with the project installed (`uv sync --extra dev` or `pip install -r requirements.txt`).
- Key packages: **FastF1**, **FastAPI**, **uvicorn**, **pandas**, **NumPy**, **Pydantic**, **diskcache**.
- Optional: **pyarrow** — debrief export prefers Parquet; without it the API falls back to CSV.



### Node

- **Node 20+** (Next.js 16).
- Package manager: **npm** (`frontend-next/package-lock.json`).
- Key deps: **Next.js 16.3**, **React 19**, **Recharts**, **flexlayout-react**, **Zustand**.



### FastF1 cache

The backend prefers `fastf1_cache/` if that directory exists; otherwise it uses `cache/fastf1/`. Both are gitignored. First load of a session downloads from FastF1 (can take minutes). Later loads are ~seconds.

### Env vars (T12)


| Variable                    | Where         | Default                 | What it does                                                                    |
| --------------------------- | ------------- | ----------------------- | ------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_API_BASE`      | frontend-next | `http://localhost:8000` | HTTP API origin. **Must match the backend port.** Canonical broker is **8765**. |
| `NEXT_PUBLIC_WS_BASE`       | frontend-next | `ws://localhost:8000`   | WebSocket origin. Same port as the API.                                         |
| `NEXT_PUBLIC_ARIS_EXPLAIN`  | frontend-next | on in non-prod          | `0` hides Explain; `1` forces it on (needed in production builds).              |
| `NEXT_PUBLIC_ARIS_COPILOT`  | frontend-next | on in non-prod          | `0` hides Copilot; `1` forces it on.                                            |
| `ARIS_COPILOT_LLM`          | backend       | off (`0`)               | `1` enables Ollama/HF narration. Leave unset for template Copilot.              |
| `ARIS_TRUE_COMPOUND_SLOPES` | backend       | unset                   | Leave **unset** so G1.5 / Zandvoort identity stay intact.                       |
| `ARIS_USE_MC`               | backend       | unset                   | Leave **unset** for identity-safe recommend deltas.                             |


Do **not** set `ARIS_TRUE_COMPOUND_SLOPES` or `ARIS_USE_MC` for this runbook.

---



## 2. Start the Backend

Canonical broker port is **8765** (`scripts/run-backend.ps1`). `frontend-next` defaults to **8000**, so you must either run uvicorn on 8000 **or** point the frontend at 8765. Use 8765 — port 8000 is often taken on this machine.

### PowerShell (Windows)

```powershell
cd C:\Users\anass\ARIS
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src;.;.deps"
# Leave ARIS_COPILOT_LLM unset unless you want LLM narration (section 8).
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

Or:

```powershell
.\scripts\run-backend.ps1
```

Do **not** use `--reload` on Windows. Concurrent FastF1 loads have crashed uvicorn here.

### macOS / Linux

```bash
cd /path/to/ARIS
source .venv/bin/activate
export PYTHONPATH="src:.:.deps"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
```



### Confirm it is up

```powershell
curl http://127.0.0.1:8765/health
# {"ok":true}

curl http://127.0.0.1:8765/api/health
# {"ok":true,"service":"aris-v3-broker"}
```

Browser: [http://127.0.0.1:8765/health](http://127.0.0.1:8765/health). Leave this terminal open.

---



## 3. Start the Frontend

T12 lives in **`frontend-next`**. Do **not** run `npm run dev` from the repo
root — there is no root `package.json` for the app (Cloudflare Worker scripts
live under `deploy/cloudflare-worker/`). The Vite app in `frontend/` (port 5173)
also has no Explain tab.

New terminal:

```powershell
cd C:\Users\anass\ARIS\frontend-next
npm install   # first time only
$env:NEXT_PUBLIC_API_BASE = "http://localhost:8765"
$env:NEXT_PUBLIC_WS_BASE = "ws://localhost:8765"
# Explain + Copilot are already on in `next dev` (NODE_ENV !== production).
# Optional: $env:NEXT_PUBLIC_ARIS_EXPLAIN = "1"
# Optional: $env:NEXT_PUBLIC_ARIS_COPILOT = "1"
npm run dev
```

macOS / Linux: `export NEXT_PUBLIC_API_BASE=http://localhost:8765` and `export NEXT_PUBLIC_WS_BASE=ws://localhost:8765`.

### Confirm it is up

Open **[http://localhost:3000](http://localhost:3000)** (use `localhost`, not `127.0.0.1` — CORS allowlist is `http://localhost:3000`).

You should see the ARIS home page (wordmark + Live / Replay cards).

If you skipped the env vars, Next will call `http://localhost:8000` and charts will **silently fall back to mock data**.

---



## 4. Open the App and Select a Session

There is no `/aris` route and no deep-link like `/aris/2025-15-R`. Session id `2025-15-R` is an **API** identifier.

1. Open [http://localhost:3000](http://localhost:3000).
2. Click **See all races →** (or go to [http://localhost:3000/replay](http://localhost:3000/replay)).
3. Session selector:
  - **Year:** `2025` (the dropdown defaults to **2024** — change it).
  - **Round:** Netherlands / Dutch GP (round **15**). The selector prefers Netherlands when the calendar loads.
  - **Session:** **R** (Race). ARIS scoring is Race / Sprint only.
  - **Driver:** **VER**.
  - Leave the **ARIS** toggle on.
4. Click **Load Session**. You should land on `/replay/console`.

First FastF1 load of Zandvoort 2025 Race can take a few minutes (cache miss). Backend logs will show session load. Later T12 calls reuse that cache.

**Explain tab location:** it is in the **analytics row below** the main dock (Track Map / Timing / ARIS Comms). Scroll the console down. Tab label: **Explain**.

If Explain is missing: `NEXT_PUBLIC_ARIS_EXPLAIN=0` is set, or you are on a production build without `=1`. Restart `npm run dev` after changing `NEXT_PUBLIC_*` vars.

---



## 5. Test T12: Degradation Curves

1. Open the **Explain** tab.
2. Sub-tab **Degradation Curves** (default).
3. Driver **VER**, Stint **1** (or “Current stint”).



### What to check

- Chart renders two lines: **Predicted** (red) and **Actual** (amber).
- X-axis: **Tyre age (laps)**. Y-axis: **Deg (s)**.
- Header shows compound + circuit, e.g. `MEDIUM · Netherlands` (Zandvoort 2025 VER stint 1 is MEDIUM in the T12 fixture).



### Optional — Network / curl

DevTools → Network. Expect:

`GET /api/explain/degradation?session_id=2025-15-R&driver=VER&stint_id=1`

JSON must include `tyre_age`, `predicted_deg_s`, `actual_deg_s` (same length), plus `compound`, `circuit`, `available_stints`.

```powershell
curl "http://127.0.0.1:8765/api/explain/degradation?session_id=2025-15-R&driver=VER&stint_id=1"
```

First call can take **up to ~60 s** (frontend timeout). If it fails, the UI still draws a **mock** curve (MEDIUM, ~18 laps, Netherlands). A live response has real FastF1 lengths and a matching `session_id`.

---



## 6. Test T12: Ghost vs Real

1. Explain tab → **Ghost vs Real**.
2. Driver **VER**.



### What to check

- Chart: **Ghost P** (red, ARIS strategy) and **Real P** (white dashed, classified run).
- Right axis: **Ghost gap** / **Real gap** (seconds to leader).
- Position axis is inverted (P1 at the top).
- Pit laps are in the header, not as chart markers: `Ghost pits … · Real pits …`.
- Optional caption under the chart (`explanation`).

Ghost remaining-race times are the bicycle/`simulate()` path, not a full-field Monte Carlo. Position is cumulative-time rank vs the classified field.

### Optional — Network / curl

`GET /api/explain/ghost?session_id=2025-15-R&driver=VER`

JSON: `ghost` and `real` each with `laps`, `position`, `gap_to_leader`, `compound`, `pit_laps`; plus `delta`.

```powershell
curl "http://127.0.0.1:8765/api/explain/ghost?session_id=2025-15-R&driver=VER"
```

---



## 7. Test T12: Race Debrief

1. Explain tab → **Race Debrief**.
2. Driver **VER**. The UI always sends a focus driver (no “all” option).



### What to check

**Timeline** (scatter + shaded bands):

- Pit stops as compound-coloured dots (tooltip: `L{n} {in}→{out}`).
- SC/VSC as orange `ReferenceArea` bands.
- Rain as blue bands (from FastF1 weather `Rainfall`).

**Key decisions** (cards below):

- Lap + type, **Team** chosen action, **ARIS** action.
- `recommend()` top-3 table: label, Δ vs stay-out, P(best).
- Explanation line (template narration unless Copilot LLM is on).

**Export:** click **Export**. File is `debrief.parquet` (or `debrief.csv` if pyarrow is missing).

### Optional — Network / curl

`GET /api/explain/debrief?session_id=2025-15-R&focus_driver=VER`

JSON: `timeline`, `decisions`, `metadata`.

```powershell
curl "http://127.0.0.1:8765/api/explain/debrief?session_id=2025-15-R&focus_driver=VER"
curl -OJ "http://127.0.0.1:8765/api/explain/debrief?session_id=2025-15-R&focus_driver=VER&format=parquet"
```

Mock fallback (API down) looks like: SC laps 8–10, rain 12–16, team boxed lap 20. If you see exactly that, you are **not** on live FastF1.

---



## 8. Optional: Test Copilot on the Same Session

Copilot is a sub-tab of **ARIS Comms** (right side of the main dock), not a top-level console tab.

1. Confirm ARIS is on (session selector toggle).
2. In **ARIS Comms**, open **Copilot**. Leave the in-panel **Dev toggle** checked.
3. LLM narration is optional. Template answers are enough for T12.

To enable LLM (Ollama default `llama3.1:8b-instruct-q5_K_M` on `http://127.0.0.1:11434`):

```powershell
# backend terminal, then restart uvicorn
$env:ARIS_COPILOT_LLM = "1"
```



### Example queries

- “What’s the undercut window for VER vs NOR?”
- “What’s the best strategy from here?”
- “Do drivers have to use two compounds in a dry race?”



### What to check

- Status line: `Copilot calling ARIS tools…`
- Answer is short; **Cite:** chunk ids when retrieval ran.
- Strategy questions show a top-3 table and Approve / Deny / Alter when `needs_approval` is set.
- Network: `POST /api/copilot/chat`. Response includes `tool_calls`, `retrieved_chunks`, `recommendations`.

```powershell
curl -X POST http://127.0.0.1:8765/api/copilot/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"What's the undercut window for VER vs NOR?\",\"session_id\":\"2025-15-R\",\"year\":2025,\"round_number\":15,\"driver_code\":\"VER\",\"current_lap\":25}"
```

Without `ARIS_COPILOT_LLM=1` the narrator is extractive templates over tool JSON + chunks. Race math still goes through `get_undercut_window` / `recommend()` / `simulate()`.

---



## 9. Sanity Checks for Core Gates



### Zandvoort identity (Python `recommend()`, not HTTP labels)

At lap 25, MEDIUM life 2, default flags off, top-3 must be:

**Pit 33 HARD / Pit 30 HARD / Stay out**

```powershell
cd C:\Users\anass\ARIS
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src;."
python scripts\check_zandvoort_pace.py
```

Expect: `Zandvoort pace check PASS`.

Or:

```powershell
python -m pytest tests/test_circuit_deg.py::test_zandvoort_identity_flag_off -q
```



### HTTP recommend / simulate (no crash)

These hit FastF1/Postgres fallbacks. Success is **200 + no traceback**, not the identity label strings (HTTP uses a different response shape).

```powershell
curl -X POST http://127.0.0.1:8765/api/aris/recommend `
  -H "Content-Type: application/json" `
  -d "{\"year\":2025,\"round_number\":15,\"session_type\":\"R\",\"driver_code\":\"VER\",\"current_lap\":25,\"mode\":\"replay\"}"

curl -X POST http://127.0.0.1:8765/api/aris/simulate `
  -H "Content-Type: application/json" `
  -d "{\"year\":2025,\"round_number\":15,\"session_type\":\"R\",\"driver_code\":\"VER\",\"current_lap\":25,\"pit_lap\":33,\"compound\":\"HARD\"}"
```

Backend log should stay clean for `/api/explain/*`, `/api/aris/recommend`, `/api/aris/simulate`, `/api/copilot/chat`.

### T12 pytest (8/8, fixture — no FastF1 download)

```powershell
cd C:\Users\anass\ARIS
$env:PYTHONPATH = "src;."
python -m pytest tests/test_degradation_curve.py tests/test_ghost_vs_real.py tests/test_race_debrief.py tests/test_explain_api.py -q
```

Expect **8 passed**.

Copilot tool smoke:

```powershell
python -m pytest tests/test_copilot_tools.py::test_each_tool_returns_without_error -q
```

Frontend typecheck:

```powershell
cd frontend-next
npx tsc --noEmit
```

---



## 10. Troubleshooting



### Backend won’t start

- Missing `.venv` → `uv sync --extra dev` or `python -m venv .venv` then install.
- `No module named backend` / `aris` → set `PYTHONPATH=src;.;.deps` (Unix: `src:.:.deps`) and run from repo root.
- Port in use → `netstat -ano | findstr :8765` then pick a free port and set `NEXT_PUBLIC_API_BASE` / `NEXT_PUBLIC_WS_BASE` to match.
- FastF1 cache: create `fastf1_cache/` (or `cache/fastf1/`). FastF1 errors if the cache dir is missing.
- Do not enable uvicorn `--reload` on Windows.



### Frontend won’t start / talks to the wrong API

- `Missing script: "dev"` → you are in the repo root. `cd frontend-next` first.
- Node too old → use Node 20+.
- `npm install` in `frontend-next`, then `npm run dev`.
- Charts look “fine” but Network never hits 8765 → `NEXT_PUBLIC_API_BASE` still `http://localhost:8000`. Restart `npm run dev` after setting env vars (`NEXT_PUBLIC_*` is inlined at boot).
- CORS: open **[http://localhost:3000](http://localhost:3000)**, not [http://127.0.0.1:3000](http://127.0.0.1:3000).



### Charts don’t render / look fake

- First explain call is slow (FastF1). Wait; timeout is 60 s.
- After timeout the UI **mocks** data. Confirm a **200** on `/api/explain/...` in Network.
- Mock tells: debrief SC 8–10 + rain 12–16 + pit lap 20; deg curve ~18 even laps.
- Wrong driver/stint → empty or short series. Use VER stint 1 on `2025-15-R`.
- Session selector still on **2024** → change year to **2025**.
- Explain tab below the fold — scroll the analytics row.



### Copilot not responding

- Tab missing → `NEXT_PUBLIC_ARIS_COPILOT=0`, or ARIS toggle off (no Comms panel).
- In-panel **Dev toggle** off.
- `POST /api/copilot/chat` 503 → backend exception; check uvicorn stderr.
- LLM path: `ARIS_COPILOT_LLM=1` but Ollama down → falls back to template (or empty if the route errors). Template mode does not need Ollama.



### Identity failed

- `ARIS_TRUE_COMPOUND_SLOPES` or `ARIS_USE_MC` set → unset, restart backend, re-run `scripts/check_zandvoort_pace.py`.
- Do not treat HTTP `/api/aris/recommend` `action` enums as the identity labels. Identity is `aris.recommend.recommend()` labels.

---



## Live hub, circuit maps, 2026 replay

Design: `[docs/ARIS_LIVE_AND_MAP_DESIGN.md](./ARIS_LIVE_AND_MAP_DESIGN.md)`.

Backend must be on **8765** (or match `NEXT_PUBLIC_API_BASE`). The pit-wall talks to:

| Path | Role |
|---|---|
| `GET /api/live/hub` | Current vs next weekend, countdown, session chips |
| `GET /api/live/status` | OpenF1/FastF1 live window |
| `GET /api/live/stream` | **SSE** (1 s live / 2 s idle) — timing + weather + GPS |
| `GET /api/live/positions` / `/api/telemetry/cars` | Car GPS |
| `GET /api/circuit/{year}/{round}/map` | Track outline + **S/F** marker |
| `GET /api/calendar/2026` | Includes `CANCELLED` Bahrain (R2) and Saudi (R3) |

### Backend tests

```powershell
cd C:\Users\anass\ARIS
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src;.;.deps"
python -m pytest tests/test_live_hub.py -q
```

Expect **15 passed**. Re-run T12 explain tests if you touched `backend/main.py` imports:

```powershell
python -m pytest tests/test_explain_api.py tests/test_degradation_curve.py tests/test_ghost_vs_real.py tests/test_race_debrief.py -q
```

### Frontend

```powershell
cd C:\Users\anass\ARIS\frontend-next
$env:NEXT_PUBLIC_API_BASE = "http://localhost:8765"
$env:NEXT_PUBLIC_WS_BASE = "http://localhost:8765"
npm install
npx tsc --noEmit
npx vitest run
npm run dev
```

Open **[http://localhost:3000/live](http://localhost:3000/live)** (not 127.0.0.1).

Checklist:

1. **Live hub** — countdown to the next session (Monza after Zandvoort 2026). If a session is live, the console opens on timing + map. If the race has not started, the amber banner says the race is waiting for data; FP/Q chips that are `COMPLETED` are replayable.
2. **Demo fallback** — `http://localhost:3000/live?demo=1` or the “Enter demo console” button (mock oval only when the API is down / demo is explicit).
3. **Circuit map** — outline from `/api/circuit/{year}/{round}/map`, **S/F** label at the start/finish line, car dots from GPS (`positions` on the SSE). Not a synthetic oval when the map endpoint returns `x[]`.
4. **Replay year** — selector includes **2026**. Cancelled Bahrain/Saudi are hidden. Upcoming rounds (Italy onward, as of 26 Aug 2026) are hidden. Session pills that are still `UPCOMING` are disabled.
5. **Timing / strategy panels** — driven by SSE timing + polled `/api/live/laps` and `/api/live/stints` once a pack exists; they fall back to mock only if those arrays are empty.

---

## How to Run & Test — UX / Perf

Design: `[docs/ARIS_UX_AND_PERF_DESIGN.md](./ARIS_UX_AND_PERF_DESIGN.md)`.

Same-origin: `frontend-next` rewrites `/api/*` to `http://127.0.0.1:8765`. You can leave `NEXT_PUBLIC_API_BASE` unset, or set it to `http://localhost:8765`.

### Backend

```powershell
cd C:\Users\anass\ARIS
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src;.;.deps"
python -m pytest tests/test_ux_perf.py tests/test_live_hub.py -q
```

Expect both files green. `test_ux_perf.py` covers sector polylines, DNF/DNS annotation, parallel SSE `gather`, `/api/aris/quick-analysis`, and scheduled laps from track YAML.

### Frontend

```powershell
cd C:\Users\anass\ARIS\frontend-next
npx tsc --noEmit
npx vitest run
```

### Manual checklist

1. **Map** — racing line only (no pit lane). Exact FastF1 outline for the circuit being replayed (not the 20-point preview or mock oval). S1/S2/S3 colours + legend. Cars ease along the line. Click a dot → that driver highlights in the timing tower and analytics.
2. **Timing tower** — last/best lap, FL, purple/green/yellow sectors, laps completed. VSC/SC banner. DNF/DNS rows greyed and missing from the map.
3. **Header laps** — `Lap X / N` matches the circuit YAML (Monza 53, Zandvoort 72, etc.), not a hardcoded 72.
4. **Replay flow** — year → race → **Replay** or **ARIS**. ARIS → **Assisted / Auto** → pick driver → top-3 with **Recommended** → **Start replay**. Replay starts at lights-out, **1×** (up to **50×**). Header `Lap 1 / N`, not a leftover mid-race lap.
5. **Comms** — two tabs (Main Comms + Copilot). **New chat** keeps the same backend. Mid-race: strategy ARIS cannot be turned on; **Add Copilot** still works.
6. **Analytics** — empty “Waiting for lap data…” until FastF1/OpenF1 laps arrive; no mock 72-lap series on a loaded session.
7. **Lights-out** — Start stays disabled until circuit + first frame; five red lights, then 1×. See [`FRONTEND_PERF_UX_NOTES.md`](./FRONTEND_PERF_UX_NOTES.md).
8. **Add menu** — header **+ Add** opens a portaled dropdown. Repeat Replay navigations should not refetch calendar/drivers (1 h cache).

---

## Next Steps After T12

T12 is the final polish layer (deg curves, ghost vs real, debrief with `recommend()` top-3) on an unchanged strategy core.

Evidence: `[docs/PHASE-T12-SUMMARY.md](./PHASE-T12-SUMMARY.md)`. Interview numbers: `[docs/model-status.md](./model-status.md)`.

The placement pack can now reference **T9–T12** as the core story (calibrated deg + Copilot + explainability) without claiming `recommend()` was retuned.