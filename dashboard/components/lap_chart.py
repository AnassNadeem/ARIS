"""Matplotlib lap time charts with dark ARIS theme."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np


def _style_ax(ax: plt.Axes, fig: plt.Figure) -> None:
    fig.patch.set_facecolor("#0D0D0D")
    ax.set_facecolor("#111111")
    ax.tick_params(colors="#888884", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#1e1e1e")
    ax.xaxis.label.set_color("#888884")
    ax.yaxis.label.set_color("#888884")


def plot_lap_trace(
    laps: list[int],
    times: list[float],
    pit_laps: list[int] | None = None,
    *,
    title: str = "",
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 3))
    _style_ax(ax, fig)
    ax.plot(laps, times, color="#E8002D", linewidth=1.5, label="Predicted pace")
    if pit_laps:
        for pit in pit_laps:
            ax.axvline(pit, color="#F5A623", linestyle="--", linewidth=1, alpha=0.8)
            ax.text(pit, ax.get_ylim()[1], f"PIT L{pit}", color="#F5A623", fontsize=7, ha="center")
    ax.set_xlabel("Lap")
    ax.set_ylabel("Lap time (s)")
    if title:
        ax.set_title(title, color="#888884", fontsize=9)
    ax.grid(False)
    fig.tight_layout()
    return fig


def plot_stint_bars(
    actual_laps: list[int],
    actual_times: list[float],
    forecast_laps: list[int] | None = None,
    forecast_times: list[float] | None = None,
    *,
    title: str = "LAP HISTORY — STINT",
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 2.5))
    _style_ax(ax, fig)
    width = 0.8
    if actual_laps:
        ax.bar(actual_laps, actual_times, width=width, color="#333333", label="Actual", alpha=0.9)
    if forecast_laps and forecast_times:
        ax.bar(
            forecast_laps, forecast_times, width=width,
            color="#E8002D", alpha=0.5, label="ARIS forecast",
        )
    ax.set_xlabel("Lap")
    ax.set_ylabel("s")
    ax.set_title(title, color="#888884", fontsize=8)
    ax.legend(fontsize=7, facecolor="#111", edgecolor="#1e1e1e", labelcolor="#888884")
    ax.grid(False)
    fig.tight_layout()
    return fig


def plot_temp_forecast(temps: list[float], total_laps: int = 57) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 1.2))
    _style_ax(ax, fig)
    if not temps:
        temps = np.linspace(36, 42, total_laps).tolist()
    else:
        temps = temps[:total_laps] if len(temps) >= total_laps else list(temps) + [temps[-1]] * (total_laps - len(temps))
    colors = ["#F5A623" if t < 40 else "#E8002D" for t in temps]
    ax.bar(range(1, len(temps) + 1), [1] * len(temps), color=colors, width=1.0)
    ax.set_xlim(0.5, len(temps) + 0.5)
    ax.set_yticks([])
    ax.set_xlabel("Lap", fontsize=7)
    ax.set_title("Track temp forecast", color="#888884", fontsize=8)
    fig.tight_layout()
    return fig


def plot_gap_chart(gaps: list[tuple[str, float, str]]) -> plt.Figure:
    """Horizontal bar chart: (code, gap_s, team_color)."""
    fig, ax = plt.subplots(figsize=(3, 3))
    _style_ax(ax, fig)
    codes = [g[0] for g in gaps]
    values = [g[1] for g in gaps]
    colors = [g[2] for g in gaps]
    y_pos = range(len(codes))
    ax.barh(list(y_pos), values, color=colors, height=0.6)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(codes, fontsize=8)
    ax.set_xlabel("Gap (s)", fontsize=7)
    ax.set_title("GAP CHART — TOP 5", color="#888884", fontsize=8)
    ax.invert_yaxis()
    fig.tight_layout()
    return fig
