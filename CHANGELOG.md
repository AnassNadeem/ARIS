# Changelog

All notable changes to ARIS are recorded here. Versions are the phase tags from
the [roadmap](./README.md#roadmap); dates are the tag dates. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [v0.2-pipeline] — 2026-05-28 — Phase 2: Postgres ingest + live dashboard

### Added
- Idempotent FastF1 → Postgres ingest (`aris.io.ingest`) with natural-key
  `ON CONFLICT` upserts and per-session all-or-nothing transactions; CLIs
  `scripts/ingest_session.py` and `scripts/ingest_season.py`.
- Raw-SQL read layer `aris.io.db` (`fetch_seasons/races/drivers/laps/lap_sectors`,
  `fetch_driver_ma2_mae`) backing a public Streamlit dashboard at
  **[aris-f1.streamlit.app](https://aris-f1.streamlit.app)** (Neon Postgres).
- Sector-breakdown chart + race/driver-selector polish on the dashboard.
- `aris.eval.run_baseline_all_races` with a `python -m` entry point (promoted from
  the Wk 2 dry-run script).
- `db/queries/baseline_ma2.sql` + `scripts/baseline_crosscheck.py` — the SQL-vs-pandas
  MA(2) canary proving the ingest is lossless.
- Telemetry gear-clean rule (`gear` outside `1..8` → NULL) at the ingest boundary.

### Changed
- Baseline now filters to green-flag laps (`TrackStatus='1'`) in both the pandas and
  SQL paths: overall **MA(2) MAE floor 1.088 s → 0.460 s** (6383 laps), the number
  the Phase 3 predictor must beat.
- README reframed around the live demo; root `requirements.txt` populated as a
  no-uv pip fallback.

### Verified
- SQL and pandas baselines match to **machine epsilon** — 6.66e-16 s across 8 local
  races, 8.33e-16 s across the 5 ingested 2024 races on live Neon.
- 46 unit tests green; 6 DB-integration tests skip without `ARIS_DB_URL` (CI's state).

## [v0.1-foundation] — 2026-05-16 — Phase 1: Python + FastF1 + statistical baseline

### Added
- Project scaffold (uv, ruff, pytest, CI on push/PR to `main`).
- FastF1 cache prewarm + first telemetry pull (`notebooks/01-fastf1-first-pull.ipynb`).
- Stint detection + degradation slopes (`aris.physics.stint`).
- Moving-average lap-time baseline + scoring helpers (`aris.eval.baseline`,
  `aris.eval.scoring`) with leakage-free per-stint shift.
- First reference baseline: MA(2), 1.088 s MAE across 8 races / 6734 laps.

[v0.2-pipeline]: https://github.com/AnassNadeem/ARIS/releases/tag/v0.2-pipeline
[v0.1-foundation]: https://github.com/AnassNadeem/ARIS/releases/tag/v0.1-foundation
