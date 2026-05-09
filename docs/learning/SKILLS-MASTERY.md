# ARIS — Skills Mastery Checklist

**Purpose:** the *real* test of this project. Not "did I ship ARIS" — anyone
with enough Claude credits can ship ARIS. The test is: **could I rebuild
ARIS from scratch, on a plane, with no internet and no AI?**

Every skill below has a **self-test question**. The rule:

> If I can answer the question on a whiteboard / blank page, **without looking
> it up and without an AI**, I know it. If I can't, I don't, no matter how
> many times Claude has explained it to me.

Re-test yourself end of every phase. Tick boxes only when the test passes
**cold** — not "I remember Claude saying...".

Sections progress foundation → applied. Earlier sections are prerequisites
for later ones.

---

## How to use this document

1. End of each week, pick one section you've touched.
2. Read the test question. Answer on paper, not in code.
3. If wrong or stuck, the *gap* is the lesson. Don't move on.
4. Tick the box only when the answer is fluent (~30s).
5. Re-test old sections monthly — knowledge decays.

The CV claim *"I built ARIS"* is meaningless if you can't pass these cold.
The interviewer **will** test these. They have time, you have one shot.

---

# Part 1 — Python

The default language for everything in ARIS. Skills are listed in roughly
the order you'll need them.

## 1.1 Syntax & Control Flow

- Variables, types (`int`, `float`, `str`, `bool`, `None`).
- Truthy / falsy values (`0`, `""`, `[]`, `None`, `False` are falsy).
- `if / elif / else`, `for`, `while`, `break`, `continue`.
- `range`, `enumerate`, `zip`.
- Identity (`is`) vs equality (`==`) — `is` checks the same object,
  `==` checks equal values.

**Test 1.1:** Without running it, what does this print?
```python
xs = [1, 2, 3]
ys = xs
ys.append(4)
print(xs, ys, xs is ys, xs == ys)
```

> Answer: `[1,2,3,4] [1,2,3,4] True True` — list is mutable, both names
> point to the same object. Get this wrong and you'll write bugs forever.

- [ ] Mastered

## 1.2 Functions & Scope

- `def`, default args, `*args`, `**kwargs`.
- Positional vs keyword arguments.
- Local vs enclosing vs global vs built-in scope (LEGB rule).
- Mutable default arguments are a trap (`def f(x=[])` shares the same list).
- Pure functions vs functions with side effects.

**Test 1.2:** Why is this a bug, and how do you fix it?
```python
def append_item(item, bucket=[]):
    bucket.append(item)
    return bucket
```

> Answer: the default list is created **once** at function-definition time,
> then shared across all calls. Fix: `bucket=None` then `if bucket is None:
> bucket = []`.

- [ ] Mastered

## 1.3 Data Structures

- `list` (ordered, mutable, duplicates allowed).
- `tuple` (ordered, **immutable**, hashable if elements are).
- `dict` (key→value, ordered since 3.7, keys must be hashable).
- `set` (unordered, unique elements, O(1) membership test).
- When to pick each — set for membership tests, dict for lookups, tuple
  for fixed records, list for everything else.
- List/dict/set comprehensions.

**Test 1.3:** You have 1 million numbers and need to check whether each
of 1000 queries is in the collection. List, set, or dict? Why?

> Answer: `set` — O(1) lookup vs O(n) for list. 1000 × 1M lookups in a
> list = 1 billion ops; in a set = 1000 ops.

- [ ] Mastered

## 1.4 Object-Oriented Programming

- `class`, `__init__`, `self`.
- Attributes (instance vs class-level).
- Methods, `@classmethod`, `@staticmethod`.
- **Encapsulation** — `_protected` (convention) and `__name_mangled` (real,
  rarely used). Python has no enforced private; convention is the rule.
- **Inheritance** — `class Subclass(Parent):`, `super().__init__()`.
- **Polymorphism** — different classes, same method name, called by interface.
- **Composition over inheritance** — prefer "has-a" over "is-a".
- **Dunder methods**: `__repr__`, `__str__`, `__eq__`, `__hash__`, `__len__`,
  `__iter__`, `__getitem__`, `__enter__`/`__exit__`.
- `@property` — turns a method into an attribute access.
- `@dataclass` — auto-generates `__init__`, `__repr__`, `__eq__`.

**Test 1.4:** Write a `Lap` class with:
- attributes `driver`, `lap_number`, `lap_time_s` (float)
- a property `lap_time_minutes` that returns the time in minutes
- `__repr__` that prints `Lap(VER, lap=23, 1:32.451)`
- `__lt__` so `sorted([laps])` orders by `lap_time_s`

Write it on paper. No imports allowed.

> If you can do this in 3 minutes, you have OOP. If you can't, redo §1.4.

- [ ] Mastered

## 1.5 Exceptions

- `try / except / else / finally`.
- Catching specific exceptions vs bare `except:` (don't use bare).
- `raise`, custom exception classes.
- EAFP ("easier to ask forgiveness") vs LBYL ("look before you leap").

**Test 1.5:** When should you catch `Exception` and when should you let
the program crash?

> Answer: catch when you can recover meaningfully (retry network, fall
> back to default). Let crash when state is corrupted or the bug is
> programmer-error (`KeyError`, `IndexError` from logic bugs). Bare
> `except:` swallows `KeyboardInterrupt` — never use it.

- [ ] Mastered

## 1.6 Modules, Packages, Imports

- `import x` vs `from x import y` vs `from x import *` (don't use star).
- A *module* is one `.py` file. A *package* is a folder with `__init__.py`.
- Absolute (`from aris.physics import bicycle`) vs relative
  (`from ..physics import bicycle`) imports — prefer absolute.
- `if __name__ == "__main__":` guard.
- Circular imports — solve by restructuring, not by lazy importing.

**Test 1.6:** Where does Python look for `import fastf1`? What's `sys.path`?

> Answer: built-in modules → `sys.path` directories in order
> (current dir, PYTHONPATH, installed packages in venv `site-packages`).
> Editing `sys.path` at runtime is a code smell; use proper packaging.

- [ ] Mastered

## 1.7 Comprehensions, Generators, Iterators

- List/dict/set comprehensions: `[x*2 for x in xs if x > 0]`.
- Generator expressions: `(x*2 for x in xs)` — lazy, memory-efficient.
- `yield` — function becomes a generator, pauses + resumes.
- Iterator protocol: `__iter__` returns self, `__next__` returns next or
  raises `StopIteration`.

**Test 1.7:** What's the difference between these?
```python
a = [x**2 for x in range(10**8)]
b = (x**2 for x in range(10**8))
```

> Answer: `a` allocates 100M ints in RAM (will OOM on 8GB).
> `b` is a generator — produces values one at a time, constant memory.
> Use generators for huge sequences you only iterate once.

- [ ] Mastered

## 1.8 Decorators

- A decorator is a function that takes a function and returns a function.
- `@dec` is sugar for `f = dec(f)`.
- `functools.wraps` to preserve metadata.
- Common ones: `@staticmethod`, `@classmethod`, `@property`, `@cached_property`.

**Test 1.8:** Write a `@timeit` decorator that prints how long the
decorated function took.

> Skeleton:
> ```python
> import functools, time
> def timeit(fn):
>     @functools.wraps(fn)
>     def wrapper(*args, **kwargs):
>         t0 = time.perf_counter()
>         result = fn(*args, **kwargs)
>         print(f"{fn.__name__} took {time.perf_counter()-t0:.3f}s")
>         return result
>     return wrapper
> ```

- [ ] Mastered

## 1.9 Context Managers

- `with open(...) as f:` — guarantees cleanup.
- Implement via `__enter__` / `__exit__`, or via `@contextlib.contextmanager`.
- Used for files, DB connections, locks, suppressing warnings.

**Test 1.9:** Why is `with open("f")` better than `f = open("f")`?

> Answer: `with` guarantees `f.close()` even if an exception is raised
> inside the block. Forgetting `f.close()` on exception leaks file
> descriptors.

- [ ] Mastered

## 1.10 Type Hints & Pydantic

- `def f(x: int, y: list[str]) -> dict[str, float]:`
- `Optional[X]` = `X | None`.
- `Union[A, B]` = `A | B` (3.10+).
- `Callable[[int, str], bool]` for function signatures.
- Type hints are not enforced at runtime — they're for IDE / mypy / pyright.
- **Pydantic v2:** `BaseModel`, validation at construction, `.model_dump()`.
- Used in ARIS for `RaceState`, `Action` vocabulary.

**Test 1.10:** Why use Pydantic for `RaceState` instead of `@dataclass`?

> Answer: pydantic *validates* — wrong types raise at construction. Plus
> JSON serialization, schema generation, and field constraints
> (`Field(ge=0, le=100)`). Dataclass is just a struct with no validation.

- [ ] Mastered

## 1.11 Async & Concurrency (Phase 4)

- `async def`, `await`, event loop.
- `asyncio.run()`, `asyncio.gather()`.
- Async is for **I/O-bound** work (network, disk), not CPU-bound.
- For CPU-bound: `multiprocessing` or NumPy vectorization.
- GIL — one thread executes Python bytecode at a time.

**Test 1.11:** ARIS Phase 4 ticks every 5s, fetches the next state,
runs ~50 simulations, picks top 3, narrates with the LLM. Where does
async help and where doesn't it?

> Answer: async helps for the LLM call (network I/O) and DB writes.
> The 50 simulations are CPU-bound — async won't speed them up; use
> NumPy vectorization or `multiprocessing.Pool`.

- [ ] Mastered

## 1.12 File I/O & Serialization

- Text vs binary mode.
- `json.dump` / `json.load`.
- `pickle` — Python-only, **never unpickle untrusted data** (arbitrary
  code execution).
- `parquet` (via pandas) — columnar, fast, smaller than CSV.

**Test 1.12:** Why parquet over CSV for `data/laps.parquet` (5M rows)?

> Answer: columnar layout → reads only the columns you need, ~10× smaller,
> preserves dtypes (no string-parsing every read), supports compression.

- [ ] Mastered

---

# Part 2 — Numerical Computing

## 2.1 NumPy

- `ndarray` — fixed-size, homogeneous-dtype, contiguous memory.
- Why fast: vectorized operations in C, SIMD, no Python overhead per element.
- Broadcasting — operations between arrays of different but compatible shapes.
- Slicing returns a *view* (shares memory); fancy indexing returns a *copy*.
- `np.where`, `np.argmin`, `np.argmax`, `np.linalg.solve`, `np.linalg.inv`.
- Random: `np.random.default_rng(seed)` — never use `np.random.seed()` in new code.

**Test 2.1a:** Why is `np.array(xs) * 2` ~100× faster than `[x*2 for x in xs]`?

> Answer: NumPy's multiply runs in compiled C with one Python-level call.
> List comp does N Python-level multiplies plus interpreter overhead.

**Test 2.1b:** What does broadcasting do here?
```python
a = np.array([[1,2,3],[4,5,6]])     # shape (2,3)
b = np.array([10, 20, 30])           # shape (3,)
a + b
```

> Answer: `b` is broadcast across rows of `a`. Result `[[11,22,33],[14,25,36]]`.
> Broadcasting rule: align trailing dims; size-1 or missing dims stretch.

- [ ] Mastered

## 2.2 Pandas

- `Series` (1D, with index) and `DataFrame` (2D, named columns).
- `.loc[label]` (label-based) vs `.iloc[pos]` (integer-position).
- Boolean indexing: `df[df.col > 5]`.
- `groupby().agg()` — split-apply-combine.
- `merge` (= SQL JOIN), `concat` (= UNION).
- `pd.to_datetime`, `pd.Timedelta`, `.dt` accessor.
- `pivot_table`, `melt`.
- `.copy()` to avoid `SettingWithCopyWarning`.

**Test 2.2:** From `session.laps`, get the median lap time per (driver,
compound), excluding in/out laps. Write the pandas line(s).

> Answer:
> ```python
> clean = session.laps[session.laps.IsAccurate]
> clean.groupby(["Driver","Compound"])["LapTime"].median()
> ```

- [ ] Mastered

## 2.3 Matplotlib

- `plt.subplots()` returns `(fig, ax)`. Use `ax`, not `plt` (state machine).
- `ax.plot`, `ax.scatter`, `ax.hist`, `ax.bar`.
- Always label: `ax.set_xlabel`, `ax.set_ylabel`, `ax.set_title`, `ax.legend`.
- `plt.savefig("path.png", dpi=150, bbox_inches="tight")`.

**Test 2.3:** Why `fig, ax = plt.subplots()` instead of `plt.plot(...)`?

> Answer: explicit Axes object lets you control layout, multiple subplots,
> reuse axis. `plt.*` uses the global state and breaks when you have
> 2+ figures.

- [ ] Mastered

---

# Part 3 — Software Engineering

## 3.1 Git

- `clone, add, commit, push, pull, branch, checkout, merge, rebase, stash, log, diff`.
- A commit is a snapshot, not a diff (despite what diff views show).
- Branches are pointers to commits.
- `merge` preserves history; `rebase` rewrites it.
- **Never force-push to `main`.** Force-push only your own feature branches.
- `.gitignore` excludes paths from tracking.
- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

**Test 3.1:** You committed an API key to a feature branch but haven't
pushed yet. How do you remove it?

> Answer: `git reset --soft HEAD~1` (uncommit, keep changes staged), edit
> file, recommit. If pushed, also rotate the key — git history is
> append-only forever once distributed.

- [ ] Mastered

## 3.2 Testing with pytest

- `assert` statements — pytest rewrites them with rich error messages.
- Test discovery: files `test_*.py`, functions `test_*`.
- Fixtures: `@pytest.fixture` for setup/teardown.
- `@pytest.mark.parametrize` for table-driven tests.
- `pytest -k name` to run specific tests.
- Mocking: `unittest.mock.patch`, `monkeypatch` fixture.

**Test 3.2:** What does `tests/test_no_leakage.py` test for ARIS, and why
is it the most important test in the project?

> Answer: it asserts no race in the test fold appears in the training fold.
> Train/test leakage produces fake-good MAE that collapses on real
> held-out data — the #1 risk for the residual model.

- [ ] Mastered

## 3.3 Project Structure

- `src/` layout — code in `src/aris/`, tests in `tests/`. Forces you to
  install your own package (avoids accidentally importing local `.py`
  shadows).
- `pyproject.toml` — modern config (replaces `setup.py`).
- Editable install: `uv pip install -e .`.

**Test 3.3:** Why `src/aris/` instead of `aris/` in repo root?

> Answer: src layout makes `import aris` only work if the package is
> installed. Without it, you can `import aris` from the repo root by
> accident, and tests pass against unpackaged code that breaks for
> end users.

- [ ] Mastered

## 3.4 Linting & Type Checking

- **Ruff** — fast linter + formatter, replaces flake8/black/isort.
- **mypy** or **pyright** — static type checker.
- Run on every commit (pre-commit hook).

**Test 3.4:** What's the difference between a linter and a type checker?

> Answer: linter catches style + simple bugs (unused vars, complexity).
> Type checker catches type mismatches that the runtime would miss until
> the code path executes. Both, not either.

- [ ] Mastered

## 3.5 Logging & Debugging

- `logging` module: `DEBUG, INFO, WARNING, ERROR, CRITICAL`.
- Never `print` in production code; use logger.
- `pdb` / `breakpoint()` for interactive debugging.
- Read tracebacks bottom-up — the deepest frame is usually your bug.

**Test 3.5:** When should you log at WARNING vs ERROR?

> Answer: WARNING = something unusual but the program continues
> meaningfully. ERROR = a specific operation failed. CRITICAL = the
> program can't continue. Get this wrong and on-call gets paged for
> nothing.

- [ ] Mastered

---

# Part 4 — Databases

## 4.1 SQL

- `SELECT cols FROM t WHERE cond GROUP BY g HAVING agg ORDER BY o LIMIT n`.
- `JOIN` types: `INNER`, `LEFT`, `RIGHT`, `FULL OUTER`.
- Aggregates: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`.
- Window functions: `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)`.
- Indexes — speed up reads, slow down writes.
- `EXPLAIN` to read query plans.

**Test 4.1:** Get the fastest lap of each driver in 2024 Bahrain GP.
Pure SQL.

> Answer:
> ```sql
> SELECT DISTINCT ON (driver) driver, lap_number, lap_time_s
> FROM laps
> WHERE event = 'Bahrain' AND year = 2024 AND session = 'R'
> ORDER BY driver, lap_time_s ASC;
> ```
> (Postgres-specific `DISTINCT ON`. Generic version uses a window function.)

- [ ] Mastered

## 4.2 SQLAlchemy 2.0

- Engine, Session, Connection.
- ORM models inherit from `DeclarativeBase`.
- `select(Model).where(...)`. New unified API replaces 1.x.
- Migrations via Alembic.

**Test 4.2:** When to use ORM vs raw SQL?

> Answer: ORM for CRUD with stable schemas; raw SQL for analytics
> queries where the SQL is the design. ARIS Phase 1 uses ORM for ingest,
> raw SQL inside Streamlit pages for charts.

- [ ] Mastered

## 4.3 Postgres Specifics

- Types: `TIMESTAMP WITH TIME ZONE`, `JSONB`, `NUMERIC`, `UUID`.
- Constraints: `NOT NULL`, `UNIQUE`, `FOREIGN KEY`, `CHECK`.
- Idempotency via `INSERT ... ON CONFLICT DO NOTHING`.
- `psql` basics: `\dt`, `\d table`, `\timing`.

**Test 4.3:** How do you make a FastF1 ingest script idempotent (rerunnable
without duplicates)?

> Answer: `INSERT ... ON CONFLICT (year, round, session, driver, lap_number)
> DO NOTHING`. Requires a UNIQUE constraint on those columns first.

- [ ] Mastered

## 4.4 Docker

- Container = isolated process + filesystem; image = container template.
- `Dockerfile` builds an image. `docker run` instantiates it.
- `docker compose` for multi-service (Postgres + app).
- Volumes persist data outside the container's lifecycle.

**Test 4.4:** Why does `docker compose up` need a volume for Postgres?

> Answer: containers are ephemeral. Without a volume, dropping the
> container loses your DB. Volume = on-host directory mounted into
> container, survives `down/up`.

- [ ] Mastered

---

# Part 5 — Maths

The minimum maths to actually understand what your code is doing. If you
can't pass the tests here, the ML and physics sections are vibes.

## 5.1 Calculus

- Derivative = instantaneous rate of change. Geometrically, slope of the
  tangent.
- Chain rule: `(f∘g)' = f'(g) · g'`.
- Partial derivative — derivative w.r.t. one variable, others held constant.
- Integral = signed area under the curve. Antiderivative reverses
  differentiation (FTC).
- Gradient `∇f = [∂f/∂x₁, ∂f/∂x₂, ...]` — vector of partials, points uphill.
- ODE = equation involving derivatives. Solve numerically with Euler /
  Runge-Kutta.

**Test 5.1a:** Differentiate `f(x) = (3x² + 1)·sin(x)`.

> Answer (product rule): `6x·sin(x) + (3x² + 1)·cos(x)`.

**Test 5.1b:** Why is the **gradient** the direction of steepest ascent?

> Answer: by Cauchy-Schwarz, the directional derivative `∇f·u` is
> maximised when `u` is parallel to `∇f`. Gradient descent goes in `-∇f`.

- [ ] Mastered

## 5.2 Linear Algebra

- Vector — ordered tuple. Magnitude `‖v‖ = √(Σvᵢ²)`.
- Dot product `u·v = Σuᵢvᵢ = ‖u‖‖v‖cos θ`. Zero ⇔ perpendicular.
- Matrix — 2D array. Multiply: `(AB)ᵢⱼ = Σₖ Aᵢₖ Bₖⱼ`.
- Identity `I`, inverse `A⁻¹` such that `AA⁻¹ = I`.
- Determinant — scaling factor of the transformation. 0 ⇒ singular.
- Eigenvector `v`, eigenvalue `λ`: `Av = λv`. Direction unchanged by `A`.
- Linear regression closed form: `β = (XᵀX)⁻¹Xᵀy`.

**Test 5.2:** Given `X` is `(n, p)` and `y` is `(n,)`, derive the OLS
solution. State the assumption that makes it unique.

> Answer: minimise `‖Xβ − y‖²`. Set `∇β = 0` → `XᵀXβ = Xᵀy` → `β = (XᵀX)⁻¹Xᵀy`.
> Unique iff `X` has full column rank (no perfectly collinear features).

- [ ] Mastered

## 5.3 Probability

- Sample space, event, probability axioms (P ≥ 0, P(Ω)=1, σ-additivity).
- Conditional probability: `P(A|B) = P(A∩B)/P(B)`.
- Bayes' theorem: `P(A|B) = P(B|A)P(A)/P(B)`.
- Independence: `P(A∩B) = P(A)P(B)`.
- Distributions:
  - **Bernoulli(p)** — single coin flip.
  - **Binomial(n, p)** — # successes in n flips.
  - **Normal(μ, σ²)** — bell curve. Central limit theorem.
  - **Exponential(λ)** — memoryless waiting time. Pit-stop arrival.
  - **Poisson(λ)** — # events in fixed window. Safety cars per race.
- Expected value `E[X] = Σ x·p(x)` (or integral for continuous).
- Variance `Var(X) = E[(X − E[X])²]`. Std dev `σ = √Var`.

**Test 5.3:** A driver's lap-time is N(μ=92.0, σ=0.4). What's the
probability of a sub-91.5 lap?

> Answer: `Z = (91.5 − 92)/0.4 = −1.25`. `P(Z < −1.25) ≈ 0.106`. ~10.6%.

- [ ] Mastered

## 5.4 Statistics

- Sample mean / std vs population.
- Bias / variance tradeoff — total error = bias² + variance + irreducible noise.
- Confidence interval — frequentist. 95% CI ≈ `mean ± 1.96·σ/√n`.
- Hypothesis testing — null, p-value, type I/II errors.
- Bootstrap — resample with replacement to estimate uncertainty.
- Conformal prediction — distribution-free prediction intervals with
  guaranteed coverage. Phase 6 of ARIS.

**Test 5.4:** What's the precise interpretation of "95% confidence
interval"? (Hint: it's not "95% chance the parameter is in here.")

> Answer: if you repeat the experiment many times, 95% of the constructed
> intervals will contain the true parameter. Any single interval either
> contains it or doesn't (deterministic, unknown). The 95% is about the
> *procedure*, not this interval.

- [ ] Mastered

## 5.5 Optimization

- Convex function: line between any two points lies above the function.
- Convex optimisation has a unique global minimum.
- Gradient descent: `θ ← θ − η·∇L(θ)`.
- Stochastic GD — gradient on a mini-batch.
- Adam — adaptive learning rate per parameter.
- Local minima are an issue for non-convex (NN training).

**Test 5.5:** Why does setting learning rate too high fail?

> Answer: each step overshoots the minimum, loss diverges (or oscillates).
> Too low: slow convergence, gets stuck in plateaus. Pick via learning-rate
> sweep / schedule.

- [ ] Mastered

---

# Part 6 — Machine Learning

## 6.1 Train/Test/Validation

- Three splits: train (fit), val (tune hyperparams), test (final eval).
- **Never** touch the test set during development.
- k-fold CV — train k models on k different splits.
- For ARIS: **race-by-race CV** — fold = whole race. Lap-level random
  split leaks info between folds.

**Test 6.1:** You split FastF1 laps 80/20 randomly and get MAE 0.3s.
You split race-by-race and get MAE 0.9s. Which is real, why the gap?

> Answer: 0.9s is real. Random lap split has many laps from the same
> race in both folds — model memorises race-specific noise (track grip,
> weather). Race-by-race forces generalisation to unseen race conditions.

- [ ] Mastered

## 6.2 Metrics

- **MAE** = mean absolute error = `(1/n)Σ|yᵢ − ŷᵢ|`. Same units as `y`.
- **MSE** = mean squared error = `(1/n)Σ(yᵢ − ŷᵢ)²`. Penalises large errors.
- **RMSE** = √MSE. Same units as `y`.
- **R²** = `1 − SS_res/SS_tot`. Fraction of variance explained. 1 is perfect, 0 is mean baseline, can be negative.
- **MAPE** = mean absolute *percentage* error. Use when scale varies.

**Test 6.2:** ARIS predicts lap times. Why pick MAE over RMSE as the
headline metric?

> Answer: MAE is in seconds — interpretable to a strategy engineer.
> RMSE penalises outliers more (one bad lap dominates), which is the
> wrong incentive for ARIS — we want consistent prediction across
> normal racing laps, not heroics on safety-car laps.

- [ ] Mastered

## 6.3 Bias / Variance / Overfitting

- **Bias** — systematic error from too-simple model.
- **Variance** — model fits noise, varies across training sets.
- **Overfitting** — low train error, high test error. High variance.
- **Underfitting** — high train error. High bias.
- Counter overfitting: regularization (L1/L2), early stopping, more data,
  simpler model.

**Test 6.3:** Train MAE 0.1s, test MAE 1.2s. Diagnose and prescribe.

> Answer: severe overfit (10× gap). Prescribe: smaller model
> (max_depth/n_estimators down for XGBoost), L2 reg, more training races,
> verify no leakage. Don't add features.

- [ ] Mastered

## 6.4 Linear Regression

- Model `y = Xβ + ε`. Closed form: `β = (XᵀX)⁻¹Xᵀy`.
- Assumptions: linearity, independence, homoscedasticity, normal errors
  (for inference, not prediction).
- L1 (Lasso) → sparse coefficients. L2 (Ridge) → small coefficients.

**Test 6.4:** What does Ridge actually do, geometrically?

> Answer: minimise `‖y − Xβ‖² + λ‖β‖²` — adds a sphere constraint that
> shrinks all coefficients toward 0 proportional to their size. Reduces
> variance at the cost of some bias.

- [ ] Mastered

## 6.5 Decision Trees → Random Forests → Gradient Boosting

- Tree: recursive binary split that minimises a loss (Gini, entropy, MSE).
- Forest: bagging — many trees on bootstrapped data, average predictions.
- Boosting: train tree to fit residuals of previous ensemble. Iterative.
- **XGBoost** — fast, regularised gradient boosting. Default for tabular ML.
- Hyperparameters that matter: `max_depth`, `eta` (learning rate),
  `n_estimators`, `subsample`, `min_child_weight`.

**Test 6.5:** Why is XGBoost the default for ARIS residual prediction
instead of a neural net?

> Answer: tabular data, ~10⁴ rows, no spatial/temporal locality the
> features capture explicitly. Trees naturally handle interactions,
> need no scaling, train in seconds, fewer hyperparams to tune. NNs
> shine on raw signals (image, text, audio); not here.

- [ ] Mastered

## 6.6 Neural Networks (Phase 2 PyTorch experiment + Phase 6 LLM)

- Neuron: `output = activation(Σ wᵢxᵢ + b)`.
- Activations: ReLU (default hidden), sigmoid (binary out), softmax (multi-class).
- Forward pass — compute outputs.
- Loss — MSE for regression, cross-entropy for classification.
- Backprop — chain rule applied to the computational graph.
- Optimiser updates weights using `∂L/∂w`.

**Test 6.6:** Walk through one step of training a 1-hidden-layer MLP:
input → loss → updated weight. Whiteboard.

> Skeleton: forward (`h = ReLU(W₁x+b₁); ŷ = W₂h+b₂`), loss `(y−ŷ)²`,
> grads via chain rule, weight update `W ← W − η·∂L/∂W`. If you can't
> sketch this, redo §6.6.

- [ ] Mastered

## 6.7 PyTorch Basics

- `Tensor` — like ndarray, with autograd.
- `nn.Module` — subclass to define a model.
- Training loop: zero grads → forward → loss → backward → step.
- `model.train()` vs `model.eval()`.
- `torch.no_grad()` for inference.
- Move to GPU: `tensor.to('cuda')`.

**Test 6.7:** Why call `optimizer.zero_grad()` every iteration?

> Answer: PyTorch *accumulates* gradients into `.grad` by default
> (useful for RNNs). If you don't zero, this batch's gradients add to
> last batch's, and training is wrong.

- [ ] Mastered

## 6.8 Conformal Prediction (Phase 6)

- Wrap any predictor in a procedure that gives valid prediction intervals
  with target coverage (e.g. 90%) — no distribution assumption.
- Split-conformal: compute residuals on a calibration set. The 90th
  percentile of |residuals| is the half-width of the 90% interval.
- Coverage guarantee holds in expectation over fresh test points,
  assuming exchangeability.

**Test 6.8:** Your XGBoost predicts lap-time, residuals on calibration
set have 90th percentile 0.42s. What's the 90% prediction interval
for a new prediction `ŷ`?

> Answer: `[ŷ − 0.42, ŷ + 0.42]`. Empirical coverage on held-out should
> be ≥ 90% if exchangeability holds.

- [ ] Mastered

## 6.9 Monte Carlo (Phase 4.5)

- Estimate something by random sampling.
- Law of large numbers — sample mean → expectation as N grows.
- Variance of estimator scales `1/√N` — to halve error, 4× samples.
- Common-random-numbers trick — same seeds across scenarios for variance reduction.

**Test 6.9:** Why does ARIS run Monte Carlo over remaining-race
trajectories instead of computing the optimum analytically?

> Answer: stochastic events (SC, weather, traffic, pit variance) make
> the joint distribution intractable analytically. MC samples
> trajectories, ranks actions by expected outcome under uncertainty.

- [ ] Mastered

---

# Part 7 — Vehicle Dynamics & Physics

## 7.1 Newton's Laws

- N1: object in motion stays in motion absent net force.
- N2: `F = ma`.
- N3: equal and opposite reactions.
- For a car: `Σ F = m · a` in each axis (longitudinal, lateral, vertical).

**Test 7.1:** Brake force = 12kN, car mass = 800 kg, drag = 1kN. What's
the deceleration?

> Answer: `a = (12000 + 1000)/800 = 16.25 m/s²` (≈ 1.66g). Brake + drag
> both decelerate.

- [ ] Mastered

## 7.2 Kinematic Bicycle Model

- Two-wheel simplification (front + rear).
- State: `[x, y, ψ, v]` (position, heading, speed).
- Inputs: steering angle `δ`, acceleration `a`.
- Equations (with wheelbase `L`):
  ```
  ẋ = v · cos(ψ)
  ẏ = v · sin(ψ)
  ψ̇ = (v / L) · tan(δ)
  v̇ = a
  ```
- Valid at low/moderate speed. No tire forces.

**Test 7.2:** What's the kinematic model's turning radius given speed `v`
and steering `δ`?

> Answer: `R = L / tan(δ)` (independent of v in the kinematic case).

- [ ] Mastered

## 7.3 Dynamic Bicycle Model

- Adds tire side forces, slip angles.
- Lateral force ≈ `Cα · α` (linear tire), where `α` is slip angle and
  `Cα` is cornering stiffness.
- State adds lateral velocity `vy` and yaw rate `r`.
- Equations of motion (small-angle, constant `vx`):
  ```
  m · v̇y = Fyf + Fyr − m · vx · r
  Iz · ṙ = a · Fyf − b · Fyr
  ```
  where `a, b` = distances from CG to front/rear axle.

**Test 7.3:** Why does the dynamic model matter at high speed where
kinematic fails?

> Answer: at speed, lateral acceleration requires real tire forces; cars
> drift inside/outside their kinematic path due to slip angles. ARIS
> needs this for braking/turn-in lap-time predictions.

- [ ] Mastered

## 7.4 Tire Forces

- **Slip ratio** (longitudinal): `s = (ωr − v)/v`. 0 = pure rolling,
  +ve = traction, −ve = braking.
- **Slip angle** (lateral): angle between wheel heading and velocity vector.
- **Friction circle** — total horizontal tire force `√(Fx² + Fy²) ≤ μ·Fz`.
  Trade longitudinal vs lateral grip.
- **Load sensitivity** — peak `μ` decreases with vertical load (non-linear).

**Test 7.4:** Why can't a tire deliver max braking and max cornering
simultaneously?

> Answer: friction-circle constraint. Total grip is bounded; using it
> longitudinally leaves nothing lateral. Trail-braking is exactly playing
> the boundary of this circle.

- [ ] Mastered

## 7.5 Pacejka Magic Formula (Simplified)

- Empirical tire model:
  `Fy(α) = D · sin(C · arctan(B·α − E·(B·α − arctan(B·α))))`
- Coefficients B, C, D, E: stiffness, shape, peak, curvature.
- For ARIS, simplified linear-then-saturating form is enough.

**Test 7.5:** Why an empirical formula instead of from-first-principles?

> Answer: tire mechanics are too complex (rubber + thermal + carcass).
> Pacejka fits real data with few coefficients and reproduces measured
> behaviour. Industry standard since the 1980s.

- [ ] Mastered

## 7.6 Tire Degradation Model

- Two effects: **fuel-based** (car gets lighter, lap-time drops linearly)
  and **wear-based** (rubber chunking, thermal, falls off increasingly).
- Linear-with-fuel: `Δt_fuel ≈ k · m_fuel`. ~0.03 s/lap per kg.
- Exponential wear: `Δt_wear ≈ a · (lap_in_stint)^b` or
  `Δt_wear ≈ a · (exp(c·lap) − 1)`.
- Compound differences: soft starts faster, falls off harder.
- Track temp accelerates wear non-linearly.

**Test 7.6:** Why does fuel correction matter for ARIS lap-time prediction?

> Answer: a 100 kg fuel start vs near-empty changes lap-time by ~3s. Without
> fuel correction, your residual model fits "lap number" as a proxy and
> the physics layer's claim ("interpretable") is a lie.

- [ ] Mastered

## 7.7 Pit Loss

- `pit_loss = pit_lane_time + tire_change_time − optimal_lap_segment_time`.
- ARIS uses `PIT_LOSS_BASE = 22.0s` as a starting constant; track-specific
  in real strategy.
- Undercut window opens when tire-fresher car beats traffic-bound out-laps.

**Test 7.7:** Why is pit loss circuit-dependent?

> Answer: pit-lane length, speed limit, time-from-line-to-line all vary.
> Bahrain ~22s, Monaco ~17s, Spa ~20s. ARIS treats it as a constant for
> v1 and refits per-track in v2.

- [ ] Mastered

## 7.8 Aerodynamics (Brief)

- Downforce `F_d = ½ ρ v² CL A`. Scales with v². Pushes car onto track,
  increases tire `Fz`, which increases grip.
- Drag `F_D = ½ ρ v² CD A`. Limits top speed.
- Drag-reduction system (DRS) opens flap, cuts drag ~10-12% on straights.
- Slipstream — leading car creates low-pressure wake; following car has
  less drag and gains ~0.3-0.5s/lap on a long straight.

**Test 7.8:** Why does cornering grip degrade behind another car in F1?

> Answer: dirty air — turbulent wake disrupts the leader's wing pressure
> distribution. Effective `CL` drops, downforce falls, tire load drops,
> grip drops. The 2022 ground-effect rules tried to mitigate this.

- [ ] Mastered

---

# Part 8 — F1 Strategy Domain

These come up directly in interviews. The five canonical strategy
questions per the master plan §0 Tier C.

## 8.1 Undercut vs Overcut

- **Undercut**: pit *earlier* than the car ahead. Out-lap on fresh tires
  beats their in-lap. You jump them.
- **Overcut**: pit *later* than the car ahead. Stay out, push on
  degrading tires while they sit in traffic. Works when fresh-tire delta
  is small or out-lap is compromised.
- Undercut works when: tire delta is big, out-lap pace is good, pit
  loss is short.

**Test 8.1:** Driver A is 1.5s behind. Driver B pits, A stays out one
lap. A pushes on old tires — what does A need to do for the overcut to work?

> Answer: A's old-tire push lap must be faster than B's (out-lap on cold
> tires + pit-loss − ~1 lap). A needs old tires to still be viable AND
> B's out-lap to be slow (cold tires, traffic). If A's pace drops below
> B's out-lap pace + pit-loss, undercut wins.

- [ ] Mastered

## 8.2 Gap to Leader vs Gap Ahead

- Gap-to-leader: cumulative time to race leader.
- Gap-ahead: time to car immediately in front. Different number, different
  decision.
- Pit decisions look at gap-ahead and gap-to-rivals-behind, not gap-to-leader
  (unless you're leading).

**Test 8.2:** You're P5, 8s ahead of P6. P6 pits. Should you cover?

> Answer: depends on pit-loss vs 8s margin and tire delta. If pit-loss
> is 22s and fresh tires give you 1s/lap, you'd lose track position
> for 14 laps — only worth it if P6 will catch you within those 14 laps
> at a higher pace. If their tire delta yields 1.2s/lap, they catch in
> ~11 laps → cover. Lower delta → stay out.

- [ ] Mastered

## 8.3 1-Stop vs 2-Stop in Mixed Weather

- 1-stop: lower pit-loss exposure, requires tire to last.
- 2-stop: faster average pace via fresher tires, double pit-loss.
- Mixed weather adds option-value — flexibility to react to changing conditions.

**Test 8.3:** Rain forecast 60% in 10 laps, race has 30 laps left, you're
on mediums lap 20-of-30. Plan?

> Answer: stay out, monitor. If rain hits in 10 laps, pit lap 31 for
> inters — ~9 laps on slicks past optimum is the cost of optionality.
> If rain misses, you're committed to the 1-stop on aging mediums; pit
> only if drop-off > 1s/lap. Don't pre-emptively pit for inters — that
> commits to a stop you might not need.

- [ ] Mastered

## 8.4 Pit-Stop Walkthrough

- Driver entry → speed limit → box → 4-tire change (~2.0s peak, ~2.5s
  realistic) → release → exit.
- Total stop ~22-25s. Tire change is tiny fraction; the time is in the
  pit-lane.
- Failure modes: cross-threaded wheel, unsafe release, jack drops.

**Test 8.4:** Why does a 0.3s slow tire change cost ~0.3s on track and
not 22s?

> Answer: pit-lane time is fixed. The 0.3s extra at the box adds 0.3s
> to elapsed time, not 22s. Track-position cost depends on traffic.

- [ ] Mastered

## 8.5 Defending a Decision Under Pressure

- Frame: data, alternatives, tradeoffs, decision, monitoring.
- Strategy decisions are reversible until the box is committed; design
  for the data you'll have at decision-point, not perfect hindsight.

**Test 8.5:** "Why didn't you pit your car under SC?"

> Answer template: *"At the SC trigger we had 12 laps tire delta worth
> ~5s; behind us were two cars on different strategies. Pitting drops
> us to P9 in traffic; staying out costs ~0.3s/lap to fresh-tire cars
> behind for the next 12 laps = 3.6s. Net we judged track position
> worth more than tire delta. If the SC had extended past lap N, we'd
> have re-evaluated."* Show: data, options, tradeoff, reversibility.

- [ ] Mastered

---

# Part 9 — LLMs & Inference (Phase 6)

## 9.1 What an LLM Actually Is

- Transformer NN trained to predict the next token.
- Token = subword unit (BPE / SentencePiece). "Lift" might be 1 token,
  "Verstappen" might be 3.
- Pretraining on internet-scale text → general language model.
- Instruction-tuning + RLHF → chat-style following.
- Inference cost ≈ O(seq_len² · d_model · n_layers).

**Test 9.1:** Why does generating 1000 tokens cost more than 1 prompt of
1000 tokens?

> Answer: per-token autoregressive generation requires N forward passes
> (one per output token), each over the *full* growing context. Prompt
> ingestion is one parallel forward pass. Generation is the bottleneck.

- [ ] Mastered

## 9.2 Prompt Engineering

- System prompt (role/constraints) + user message (task).
- Few-shot — show examples, then ask.
- Chain-of-thought — ask model to reason step-by-step.
- Structured output — ask for JSON, validate at the boundary.

**Test 9.2:** ARIS narrator gets a structured recommendation
`{action: "pit", lap: 23, reason: "undercut"}`. Sketch the system prompt.

> Skeleton: *"You are a Formula 1 race engineer. Given a structured
> recommendation, produce a one-sentence radio call. Use precise F1
> language. Examples: ..."* + 2-3 examples + the JSON.

- [ ] Mastered

## 9.3 Retrieval-Augmented Generation

- Retrieval: pull relevant facts from a structured store (ARIS state).
- Generation: feed those facts + user query to LLM.
- Avoids hallucination because the LLM is grounded in fresh data.
- ARIS Q&A pane is RAG over structured state, not a vector DB.

**Test 9.3:** Why does ARIS's Q&A pane not use a vector DB?

> Answer: the relevant data is structured (laps, telemetry, residuals),
> already indexed in Postgres. Vector DB is for *unstructured* text
> retrieval. Use SQL retrieval where the data is structured.

- [ ] Mastered

## 9.4 Local Inference + Quantization

- Quantization — reduce weight precision (FP16 → INT8 → INT4) to fit
  bigger models in less VRAM.
- Llama 3.1 8B q5_K_M ≈ 5.5 GB on disk, fits 8 GB VRAM with headroom.
- Throughput trade: q5 ~10% slower than fp16 on same hardware but allows
  larger model.

**Test 9.4:** When does Llama 3.2 3B beat Llama 3.1 8B for ARIS's narrator?

> Answer: when 8B q5 doesn't fit (other GPU memory pressure) or latency
> matters. 3B is faster but less coherent on multi-clause F1 phrasing.
> 8B is the default; 3B is the fallback per the master plan §0.

- [ ] Mastered

---

# Part 10 — MATLAB/Simulink (Phase 4.7)

## 10.1 MATLAB Syntax

- Matrix-first thinking — everything is a matrix.
- 1-indexed arrays.
- `;` suppresses output.
- Function files: one function per `.m` file with matching name.
- Element-wise ops via `.*`, `./`, `.^`. Matrix ops via `*`, `/`, `^`.

**Test 10.1:** What's the difference between `A * B` and `A .* B`?

> Answer: `*` is matrix multiply (requires inner dim match). `.*` is
> element-wise (requires same shape or broadcasting). NumPy uses `@` for
> matrix and `*` for element-wise — opposite naming convention.

- [ ] Mastered

## 10.2 Simulink

- Block-diagram dataflow programming.
- Each block has inputs, outputs, internal state.
- Solver integrates ODEs over time.
- Used for control + plant simulation; F1 teams ship Simulink models
  to ECUs.

**Test 10.2:** Why port the bicycle model from Python to Simulink for
ARIS-Validation?

> Answer: not for performance (Python is fine). For *signal*: Mercedes
> HPP, Red Bull Powertrains, Williams Vehicle Dynamics list MATLAB/
> Simulink as "good to have" → expected on placement CV. Cheap to do
> (it's already debugged in Python).

- [ ] Mastered

---

# Part 11 — Communication & Placement Skills

## 11.1 Technical README

- Pitch (1 line) → screenshot → install → quickstart → architecture →
  results → tests → license.
- Treat reader as time-poor recruiter, not maintainer.
- README sells the project before they read code.

**Test 11.1:** What's the first thing in the ARIS README and why?

> Answer: the one-line pitch from §0 of the final plan. Recruiters read
> top-down; if the first 50 chars don't sell it, they leave.

- [ ] Mastered

## 11.2 90-Second Demo Video

- 3-act structure: hook (problem) → demo (artifact in action) → claim
  (validation + scope).
- Voiceover, screen recording, no music to distract.
- One artifact per video. Don't try to demo two features.

**Test 11.2:** What three beats should the ARIS demo video hit?

> Answer (from §7 of execution plan):
> 1. "Real lap from [race]. ARIS is watching live."
> 2. "Lap 23: ARIS recommends X with predicted +0.2 ± 0.15s. Driver did Y, lost 0.3s."
> 3. "Trained on 5 seasons of FastF1, validated on held-out races
>    with conformal intervals, runs locally on a laptop."

- [ ] Mastered

## 11.3 The 30-Second Pitch

- Memorise word-for-word from §1d:
> *"ARIS is a hybrid AI race strategist. The core is a physics simulator
> — bicycle model with tire degradation — corrected by a machine-learning
> residual trained on FastF1 data. An action-search engine evaluates
> dozens of candidate driver and strategy actions per tick, scores them
> with Monte Carlo confidence intervals, and an LLM turns the top
> recommendation into a sentence. It runs always-on against a live race
> replay. It is not a world model and not reinforcement learning — it
> is classical decision support stitched together with modern ML and LLMs."*

**Test 11.3:** Recite the pitch from memory in 30 seconds. Time yourself.

- [ ] Mastered

## 11.4 What ARIS is NOT

- NOT a world model (no learned latent dynamics).
- NOT reinforcement learning (no policy / reward signal).
- NOT a LangChain agent (LLM narrates, doesn't decide).
- NOT physics-grounded (it's "lightweight, interpretable, LLM-narrated").
- NOT UDX (single plugin, not a platform).

**Test 11.4:** Interviewer asks "is this a world model?" — answer in 15s.

> Answer: *"No. World models learn latent dynamics from data — RSSM,
> Dreamer. ARIS uses a hand-coded physics simulator with an ML residual
> correction. The LLM only narrates. I made the choice deliberately:
> world models need a research team and 8+ A100s. ARIS works on a laptop
> in 17 weeks."*

- [ ] Mastered

---

# Part 12 — Self-Assessment Rubric

End of each phase, score each section 0-3:

- 0 = haven't touched this yet
- 1 = read about it, can't do it cold
- 2 = can do simple cases, struggles with edge cases
- 3 = fluent, can teach it

Phase gates:

| End of phase | Required score for section… |
|---|---|
| Phase 0 | Python (1.1-1.7) ≥2, NumPy/Pandas/Matplotlib ≥2, Git ≥2 |
| Phase 1 | + SQL ≥2, Postgres ≥2, Docker ≥2, Streamlit ≥2 |
| Phase 2 | + Calc/LinAlg/Prob/Stats ≥2, ML §6.1-6.5 ≥2, Vehicle Dyn 7.1-7.3 ≥2, Tires 7.4-7.6 ≥2 |
| Phase 3 | + Pydantic ≥3, type hints ≥3 |
| Phase 4 | + async ≥2, Monte Carlo 6.9 ≥2 |
| Phase 4.7 | + MATLAB ≥2 |
| Phase 6 | + Conformal 6.8 ≥3, LLM ≥2 |
| Phase 7 | + Communication 11.1-11.4 ≥3 |

**Honest scoring.** A 2 you mark as 3 is just a 2 you'll fail on cold
in an interview.

---

# Part 13 — Why this exists

The project is the artifact. The skills are the asset. ARIS will be
deprecated, replaced, or surpassed before your placement starts. What
remains is *what you can build, alone, on a blank machine, with no
internet*.

If on August 31 you can answer every test in this document on paper,
you don't need to "look like" you can build ARIS — you actually can,
again, anywhere. That is the only thing that gets you the placement,
the grad scheme, and the strategy specialisation after that.

Re-read this file every Sunday. Mark what's true. Be honest about what
isn't. The honest answer is the only one that compounds.
