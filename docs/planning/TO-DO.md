# ARIS — Notebook TO-DO

**Scope:** the only notebooks ARIS needs across Phases 0–2 (Weeks 1–7).
Cap at 5. Don't pad the count. Production logic goes in `src/aris/`,
not in `.ipynb` files.

---

## The 5 notebooks

### `notebooks/00-pandas-basics.ipynb` — Week 1, Saturday
**Purpose:** prove pandas fluency. Evidence of the Phase 0 deliverable
*"you can do a pandas groupby + agg + merge without looking it up."*

**Contents:**
- DataFrame / Series creation
- Slicing, boolean indexing, `.loc` vs `.iloc`
- `groupby` + `.agg` (multiple aggregations)
- `merge` across two small DataFrames
- One datetime / Timedelta exercise (warmup for FastF1's `LapTime`)

**Done when:** kernel restart + run-all works top-to-bottom, no errors.

---

### `notebooks/01-fastf1-first-pull.ipynb` — Week 1, Sunday
**Purpose:** first real FastF1 contact. Produces the
`docs/screenshots/01-verstappen-bahrain-2024.png` embedded in the README.

**Contents:**
- Enable cache, load 2024 Bahrain GP race session
- Inspect `session.laps` columns, `.head()`, `.dtypes`
- `pick_driver('VER').pick_quicklaps()`
- Convert `LapTime` Timedelta → seconds
- Plot lap times vs lap number, save PNG

**Done when:** PNG saved, embedded in README, notebook runs clean.

---

### `notebooks/02-stint-analysis.ipynb` — Week 2
**Purpose:** real pandas joins on real data. Tyre-stint timeline plot.

**Contents:**
- Load 2024 Bahrain GP race
- Group laps by `(Driver, Stint)`, compute stint length + mean pace
- Pull weather data, merge by approximate timestamp
- Plot: per-driver tyre stint timeline (compound colour-coded)
- Plot: pace degradation across one stint for one driver

**Done when:** plot is readable on a phone screen, committed as PNG.

---

### `notebooks/03-bicycle-validation.ipynb` — Week 5
**Purpose:** sanity-check the hand-coded `aris.physics.bicycle` module
against one real FastF1 stint. Validates Phase 2 Day 1's physics work.

**Contents:**
- Import `from aris.physics.bicycle import predict_lap_time`
- Load one stint of telemetry (Verstappen, Bahrain 2024, stint 1)
- Run physics predictor against actual lap times
- Plot predicted vs actual; residual histogram
- Document the gap honestly — physics-only will be off by 3–10s

**Done when:** plot saved to `docs/screenshots/`, residual MAE recorded
in notebook markdown for later comparison after tyre + ML layers land.

---

### `notebooks/04-residual-eda.ipynb` — Week 7
**Purpose:** feature exploration before fitting XGBoost on residuals.
Phase 2 Day 1–2.

**Contents:**
- Load assembled feature parquet (track temp, lap, fuel est., compound,
  stint age, sector grip, weather)
- Correlation matrix vs the residual target
- Distribution of residuals (any heavy tails? skew?)
- Per-compound, per-track-temp residual slices
- Decide which features earn their place in the XGBoost feature set

**Done when:** feature shortlist documented at the bottom of the
notebook, ready to feed into `src/aris/models/residual.py`.

---

## Notebooks NOT to write

- Anything for Phase 3+ (counterfactuals, simulator, recommender,
  always-on loop, LLM narration). That code lives in modules.
- Per-race FastF1 dumps. One stint-analysis notebook is enough.
- "Tutorial" notebooks. Learn in the actual deliverable notebooks above.
- Refactor / cleanup notebooks. Refactor in the source tree.

---

## Hygiene rules — apply to every notebook before commit

1. **Restart kernel + run all** — if it doesn't work top-to-bottom on a
   fresh kernel, fix it before commit.
2. **Clear outputs** before commit:
   `jupyter nbconvert --clear-output --inplace notebooks\<name>.ipynb`
   (Or VS Code: `...` menu → Clear All Outputs.)
3. **Save plots as PNGs** to `docs/screenshots/` and embed in README.
   Don't rely on the cell output for repo display — GitHub diffs of
   `.ipynb` outputs are unreadable.
4. **No secrets, no API keys, no DB passwords** in any cell.
5. **Markdown headers in every notebook** — title, purpose, what reader
   should take away. So future-you (and an interviewer) can skim.

---

## Mid-plan check

If you've written more than 5 `.ipynb` files by end of Phase 2, ask why.
Likely you're avoiding the harder work of putting logic into
`src/aris/` modules. Notebooks are exploration scaffolding, not product.
