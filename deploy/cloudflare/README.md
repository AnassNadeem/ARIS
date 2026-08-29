# Publish the localhost ARIS app on Cloudflare

This is the Vite React UI plus the FastAPI broker. Not a Streamlit remake.

## What Cloudflare can host

- The React app: Workers static assets. `npm run deploy`
- The FastAPI broker: a Container running the same `uvicorn backend.main:app`. That needs the **Workers Paid** plan.

This account is on the free Workers plan, so `npm run deploy` publishes the UI. `/api` stays dark until you either:

1. Upgrade at https://dash.cloudflare.com/?to=/:account/workers/plans then run `npm run deploy:container` and  
   `npx wrangler secret put OPENF1_USERNAME` / `OPENF1_PASSWORD`
2. Or leave this PC on and run `powershell -File scripts/aris-home-tunnel.ps1`
   (free Cloudflare quick tunnel → Worker `API_ORIGIN`)

Local is unchanged: uvicorn on 8765, `npm run dev` in `frontend/`. The UI calls `/api` on the same origin; Vite proxies to 8765.
