# Ask ARIS — current wiring

**Last updated:** 2026-08-31 (ghost car + Ask ARIS minimal-fix pass).

## Which panel is active

There are two chat panels in `frontend-next/components/aris/`:

- **`CopilotPanel.tsx`** — tool-calling Copilot. Calls `POST /api/copilot/chat`, can return
  ranked strategy recommendations (`Top3Table`) with an approve/deny/alter bar, and cites
  `retrieved_chunks`. This is the **canonical, preferred panel**.
- **`ARISComms.tsx` (`AskARIS`)** — a simpler question box. Calls `POST /api/ask`. No tool
  calls, no citations, no approve/deny.

`ARISComms.tsx` picks between them via `copilotFeatureEnabled()` (`frontend-next/lib/api.ts`):

```ts
export function copilotFeatureEnabled(): boolean {
  if (process.env.NEXT_PUBLIC_ARIS_COPILOT === "0") return false;
  if (process.env.NEXT_PUBLIC_ARIS_COPILOT === "1") return true;
  return process.env.NODE_ENV !== "production";
}
```

- Local dev (`NODE_ENV !== "production"`): Copilot is shown by default.
- A production build: **Ask ARIS is shown unless `NEXT_PUBLIC_ARIS_COPILOT=1` is set at build
  time.** If you want Copilot live in production, set that env var in the build environment
  (Cloudflare Pages project settings, or wherever `frontend-next` is actually built —
  see `docs/GHOST_CAR_REMEDIATION_PLAN.md` BUG-7 for the open question of which frontend is
  deployed).

## Intent classification

There is currently **no intent classifier** in the frontend. Both panels send the raw question
straight to their backend endpoint. When the backend is reachable, whatever server-side logic
lives behind `/api/ask` or `/api/copilot/chat` decides how to answer (this repo pass did not
touch the backend endpoints).

When the backend is **unreachable**, both panels fall back to a local keyword-matched mock
(`mockAskAnswer` / `mockCopilotAnswer` in `frontend-next/lib/api.ts`):

- `"gap" + ("ahead" | "leader" | "rival")` → a canned gap/undercut-window answer.
- `"extend"` → a canned tyre-extension answer.
- `"undercut"` → a canned undercut-window answer.
- Anything else → the same generic "physics-default scoring" string.

This fallback is now **never silent**: both `askARIS()` and `chatCopilot()` return an
`offline: true` flag when the mock was used (backend unreachable), and both `AskARIS` and
`CopilotPanel` render a visible `⚠ OFFLINE` badge on that answer instead of presenting it as a
live response.

## What context is passed to the LLM

`chatCopilot` sends `{ message, session_id, year, round_number, driver_code, current_lap }` to
`/api/copilot/chat`. `askARIS` sends `{ question, race_state }` to `/api/ask`. Neither endpoint's
server-side implementation was modified in this pass — this document describes the frontend
wiring only.

## Known follow-up (not done in this pass)

Real intent classification (factual questions → deterministic race-state lookup, strategic
questions → LLM) was explicitly deferred per plan scope ("Ask ARIS minimal"). Sample chips no
longer hardcode a driver name (previously `"Gap to Lando?"`, `NOR`/`VER`); they now read
generically ("the leader", "the driver ahead", "your nearest rival").
