# LinkedIn post #1 — final (ready; held one week on the screenshot gate)

**Status (updated 2026-05-31):** **READY TO PUBLISH — all four gate criteria pass.**
(1) URL live (`aris-f1.streamlit.app`), (2) CI green on `main`, (3) the README hero is
now a real deployed-dashboard screenshot — `assets/screenshots/wk4-streamlit-hero.png`,
Bahrain 2024 R → VER, captured after fixing the wedged venv (see BUILD-LOG 2026-05-30
addendum), (4) body below is final. The only remaining step is the literal publish,
which is an account action — paste the body, attach the two screenshots, click post,
then drop the post URL into BUILD-LOG.

---

## When to publish

All four must be true at the moment of clicking Publish (carried from the Wk 2/3
gate):

1. The public URL is live and renders cleanly in incognito *and* on mobile.
2. CI is green on `main` right now.
3. The README hero is the deployed dashboard (Wk 4 Day 4 swap), looks proud-to-send.
4. You feel in flow, not catching up.

If any is no on Wk 4 Sat, defer with one paragraph of why in BUILD-LOG.

## Attachments

- `assets/screenshots/wk4-streamlit-hero.png` — full deployed app, Bahrain 2024 R →
  VER selected (captured Wk 4 Day 1 Block 4, refined Wk 4 Day 4 Block 1).
- `assets/screenshots/wk2-bahrain-stints.png` — stint timeline from Wk 2,
  as the "what's already validated" supporting image.

## The post

---

3 weeks into ARIS — an always-on race-strategy AI for Formula 1 — and the
first public artefact is live.

What's running behind that URL:

→ Idempotent FastF1 → Postgres ingest of 24 races (one full F1 season +
  3 carry-over 2023 races, ~30 000 laps). Re-running the ingest is a no-op,
  not a duplicate — `INSERT ... ON CONFLICT (natural_key) DO NOTHING` for every
  table, all-or-nothing transaction per session.

→ A statistical baseline (MA(2) moving average per stint) computed two ways:
  once in pandas, once as a Postgres window query. They match below 1e-15 s —
  machine epsilon — across all 8 reference races. That's the canary that
  proves the ingest is lossless before any model goes near it.

→ A Streamlit dashboard you can open right now: pick a season, race, driver,
  see the lap-time trace + the MA(2) baseline floor that any model will have
  to beat. 0.460 s overall MAE across 6 383 green-flag laps (SC, VSC and
  red-flag laps filtered out so the floor is honest) — the number ARIS Phase 3
  (residual ML + conformal intervals, starting June) is going to be measured
  against.

The hard call this week was *cloud deploy in week 3, not week 4* — the plan
moved it earlier because "URL someone outside the laptop can open" is the
deliverable that turns a notebook project into a real one. Telemetry schema
landed and validated on Bahrain 2024 (840k samples for one race); full
population is Phase 3 work.

Tag: `v0.2-pipeline`. Live demo: https://aris-f1.streamlit.app
Repo: github.com/AnassNadeem/ARIS

Up next (Phase 3, Jun 1–21): hand-coded bicycle model + tire degradation
curve + XGBoost residual, with conformal prediction intervals. Target
MAE: < 0.7 s on 5 held-out races. The baseline above is the floor I have
to beat — and the cross-check above is what catches me if I beat it the
wrong way (data leakage rather than real signal).

#Formula1 #MachineLearning #DataEngineering #Postgres #Python #SoftwareEngineering

---

## Notes on tone

- Concrete numbers, not adjectives. The 4.4e-15 s cross-check is the most
  defensible single sentence in the post — it's specific, it's verifiable
  in the repo, and it's the engineering judgement that separates "did the
  ingest work" from "I think the ingest worked."
- The plan-vs-reality move (cloud deploy moved earlier) signals that the
  schedule is real and the constraints are understood. Don't soften it.
- No emojis except `→` for the bullet arrows. The audience is hiring
  managers in motorsport / vehicle dynamics, not the general LinkedIn feed.
- The "#Formula1" hashtag matters; the F1 audience on LinkedIn skews toward
  the people you want to be in front of.

## Things to update at publish time

1. Replace `<URL goes here>` with the actual deployed URL.
2. Verify the screenshot is the latest (post-Wk 4 sector chart, not the
   pre-polish Wk 3 skeleton).
3. Confirm the `v0.2-pipeline` tag is on a commit that's actually on `main`
   (`gh release list` and the live URL must match the tagged code).
4. Paste the published post URL into BUILD-LOG immediately after publishing.
