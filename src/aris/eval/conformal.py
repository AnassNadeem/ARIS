"""Conformal prediction intervals for recommendations."""

from __future__ import annotations

from aris.montecarlo import MCDistribution


def conformal_interval(mc: MCDistribution, *, alpha: float = 0.1) -> tuple[float, float]:
    """Simple split-conformal style interval from MC percentiles."""
    low = mc.p10_time_s
    high = mc.p90_time_s
    width = high - low
    margin = width * (alpha / 0.2)
    return low - margin, high + margin


def calibrated_delta_interval(mc: MCDistribution) -> tuple[float, float]:
    """P10/P90 delta vs stay-out from MC draws."""
    baseline = mc.mean_time_s - mc.mean_delta_vs_stay_out_s
    return mc.p10_time_s - baseline, mc.p90_time_s - baseline
