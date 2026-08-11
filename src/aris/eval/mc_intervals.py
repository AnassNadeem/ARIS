"""Monte Carlo percentile bands for recommendations.

Not calibrated conformal prediction. Real split-conformal (e.g. via mapie
on the XGBoost residual) is deferred — these helpers only re-express MC
p10/p90 bands from ``aris.montecarlo``.
"""

from __future__ import annotations

from aris.montecarlo import MCDistribution


def mc_percentile_interval(mc: MCDistribution, *, alpha: float = 0.1) -> tuple[float, float]:
    """Widen/narrow the MC p10–p90 band by a simple alpha fudge factor."""
    low = mc.p10_time_s
    high = mc.p90_time_s
    width = high - low
    margin = width * (alpha / 0.2)
    return low - margin, high + margin


def mc_delta_interval(mc: MCDistribution) -> tuple[float, float]:
    """P10/P90 delta vs stay-out from MC draws (not conformal-calibrated)."""
    baseline = mc.mean_time_s - mc.mean_delta_vs_stay_out_s
    return mc.p10_time_s - baseline, mc.p90_time_s - baseline
