# ARIS V3 UI

Vite + React + TypeScript client for the FastAPI broker in `backend/`.
The browser never calls FastF1 or OpenF1; Vite proxies `/api` to `http://127.0.0.1:8765`.

Streamlit remains the public demo. This app is the parallel V3 surface.

## Run locally

```bash
# repo root — port 8000 is often taken on this machine
PYTHONPATH=.deps;src;. python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765

# frontend
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. First visit shows the ARIS wordmark; home then follows the computed calendar state (today that is race weekend for Zandvoort, not LIVE).

Dev-only: `?asOf=2026-08-19T12:00:00Z` exercises home states. `?replay_session_key=` serves historical OpenF1 through the live shapes.
