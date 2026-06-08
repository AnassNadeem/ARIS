# Single-track (bicycle) model — Rajamani Ch. 2 notes

Notes taken before writing `src/aris/physics/bicycle.py`. The point of these is to
be honest about *which* assumptions ARIS knowingly makes, so the predicted-vs-actual
residual in `notebooks/06-bicycle-vs-actual.ipynb` is interpretable, not mysterious.

## What the bicycle model is

Collapse the four-wheel car onto its centreline: one front tyre, one rear tyre, a
rigid body of mass `m` with yaw inertia about the CoG. State is lateral velocity and
yaw rate; inputs are steer angle and speed. Rajamani Ch. 2 derives the lateral
dynamics from the tyre **cornering stiffness** `C_α` (lateral force ≈ `C_α · α` for
small slip angle `α`) and the geometry (distances `a`, `b` from CoG to front/rear axles).

## The two results ARIS actually uses

1. **Steady-state cornering speed (the friction circle).** At the limit, a tyre can
   produce lateral force up to `μ · F_z`. Setting required centripetal force equal to
   available grip: `m v² / R = μ m g` ⟹ **`v_corner = √(μ g R)`**. This is the speed
   cap per corner. Mass cancels — a heavier car corners at the same grip-limited speed
   (it just needs more force, and has proportionally more weight to generate it). That
   cancellation is *in the model on purpose* and is why Day-2 lap time is invariant to
   fuel mass; the fuel-burn term is a Day-3 add.

2. **Longitudinal load transfer.** Under longitudinal accel `a_x`, load shifts between
   axles by `ΔF_z = m a_x h / L` (`h` = CoG height, `L` = wheelbase). Rajamani uses this
   for per-axle grip; ARIS computes it for sanity-checking (monotonic in `a_x`,
   symmetric for accel vs braking) but does **not** yet feed it back into per-axle grip —
   another deliberate Day-2 simplification.

## Steady-state assumptions ARIS knowingly makes (all of these make it *wrong*, on purpose)

- **No aerodynamic downforce.** Real F1 lateral grip is 4–5 g because downforce scales
  `F_z` with `v²`; pure mechanical `μ ≈ 1.5` gives ~1.5 g. So our cornering speeds are
  far too low and the predicted lap time is far too slow. This is the single biggest
  residual the Wk-6 ML will learn.
- **Linear tyre, no thermal model.** `C_α` constant; no cold-tyre out-lap, no
  degradation over a stint. The first lap of a stint (cold tyres) will be the worst-fit
  point.
- **No fuel-burn effect** (Day 3 adds a linear term: car gets lighter → faster).
- **Lumped straights.** All straights summed into one length, traversed with a single
  trapezoidal accelerate-cruise-brake profile between a representative corner speed and
  `v_max`. Longitudinal grip limit `a_x = μ g`; no engine-power or drag ceiling beyond a
  fixed `v_max`.
- **Geometry is approximate.** Bahrain corner radii / arc lengths are eyeballed off the
  circuit map, not surveyed. Good enough for an order-right number; wrong in detail.

## Why ship it visibly wrong

The bicycle model is the interpretable backbone. The residual `actual − bicycle`,
plotted against lap-in-stint / tyre age / fuel proxy, *is* the signal the Wk-6 residual
ML is trained to predict — through the leakage-safe feature builder the Day-1 tripwire
guards. Over-fitting the physics by hand now is wasted effort the residual would redo.
