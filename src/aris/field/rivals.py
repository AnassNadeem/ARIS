"""Rival pit-window estimates from field standings (T3-A).

Used for undercut/overcut scoring and FIELD comms. Does not change the
focus driver's ``simulate()`` lap times.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aris.field.state import FieldState
from aris.physics.tires import circuit_deg_enabled, normalize_compound

CLIFF_LAPS: dict[str, float] = {
    "SOFT": 16.0,
    "MEDIUM": 32.0,
    "HARD": 50.0,
}
PIT_BEFORE_CLIFF = 0.85
REF_RACE_LAPS = 72.0
TOP_N = 6


@dataclass
class RivalState:
    driver_code: str
    position: int
    compound: str
    tyre_life: int
    gap_to_focus: float
    gap_trend: float
    team: str
    last_lap_s: float
    stint_number: int = 1


@dataclass
class RivalPitEstimate:
    driver_code: str
    compound: str
    tyre_life: int
    estimated_pit_lap: int
    laps_until_pit: int
    confidence: str
    reasoning: str
    last_lap_s: float = 0.0
    position: int = 0


def estimate_rival_pit_lap(
    rival: RivalState,
    current_lap: int,
    total_laps: int,
    circuit_key: str,
    use_circuit_deg: bool = False,
) -> RivalPitEstimate:
    """Estimate rival next pit using compound cliff thresholds.

    This is the T3-A method (cliff prior, 0.85 factor). The observed-pace
    method (T3-final) was reverted: OLS slope on 3–5 lap history was too
    noisy at trigger time and dropped the undercut flag-on walk 21/56 → 20/56.
    """
    del circuit_key  # cliff table is global; slopes are not used here
    _ = use_circuit_deg or circuit_deg_enabled()

    life = rival.tyre_life if rival.tyre_life and rival.tyre_life > 0 else 1
    compound = normalize_compound(rival.compound)
    if compound not in CLIFF_LAPS:
        compound = "MEDIUM"
    total = max(int(total_laps), 1)
    current = max(int(current_lap), 1)

    race_frac = total / REF_RACE_LAPS
    cliff_threshold = CLIFF_LAPS[compound] * race_frac
    laps_until_cliff = max(0.0, cliff_threshold - life)
    estimated = current + int(laps_until_cliff * PIT_BEFORE_CLIFF)

    if laps_until_cliff <= 8:
        confidence = "HIGH"
    elif laps_until_cliff <= 18:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    lo = current + 1
    hi = max(lo, total - 2)
    estimated = min(max(estimated, lo), hi)
    laps_until_pit = estimated - current

    already = rival.stint_number >= 2
    two_stop = " likely two-stop — already on a later stint." if already else ""
    cliff = int(cliff_threshold)
    reasoning = (
        f"{rival.driver_code} {compound} {life}L, cliff {cliff}L, "
        f"{int(laps_until_cliff)} remaining, box ~L{estimated} ({confidence}).{two_stop}"
    )
    return RivalPitEstimate(
        driver_code=rival.driver_code,
        compound=compound,
        tyre_life=life,
        estimated_pit_lap=estimated,
        laps_until_pit=laps_until_pit,
        confidence=confidence,
        reasoning=reasoning.strip(),
        last_lap_s=float(rival.last_lap_s or 0.0),
        position=int(rival.position),
    )


def rivals_from_field(
    field: FieldState,
    focus_driver: str,
    *,
    all_laps: pd.DataFrame | None = None,
) -> list[RivalState]:
    """Map standings to RivalState, excluding the focus driver."""
    focus = (focus_driver or "").upper()
    focus_row = next(
        (r for r in field.standings if str(r.code).upper() == focus),
        None,
    )
    focus_gap = float(focus_row.gap_to_leader_s) if focus_row is not None else 0.0
    out: list[RivalState] = []
    for row in field.standings:
        code = str(row.code).upper()
        if code == focus:
            continue
        gap_to_focus = focus_gap - float(row.gap_to_leader_s)
        trend = _gap_trend(all_laps, focus, code, field.index.lap_number)
        out.append(
            RivalState(
                driver_code=code,
                position=int(row.position),
                compound=normalize_compound(row.compound),
                tyre_life=int(row.tyre_life) if row.tyre_life is not None else 1,
                gap_to_focus=float(gap_to_focus),
                gap_trend=trend,
                team=str(row.team or ""),
                last_lap_s=float(row.last_lap_s or 0.0),
                stint_number=int(row.stint_number or 1),
            )
        )
    return out


def estimate_all_rivals(
    field: FieldState,
    focus_driver: str,
    current_lap: int,
    total_laps: int,
    circuit_key: str,
    *,
    all_laps: pd.DataFrame | None = None,
    use_circuit_deg: bool = False,
) -> list[RivalPitEstimate]:
    """Pit estimates for the top 6 cars excluding focus, soonest first."""
    rivals = rivals_from_field(field, focus_driver, all_laps=all_laps)
    rivals = sorted(rivals, key=lambda r: r.position)[:TOP_N]
    estimates = [
        estimate_rival_pit_lap(
            rival,
            current_lap,
            total_laps,
            circuit_key,
            use_circuit_deg=use_circuit_deg,
        )
        for rival in rivals
    ]
    return sorted(estimates, key=lambda e: (e.estimated_pit_lap, e.driver_code))


def _gap_trend(
    all_laps: pd.DataFrame | None,
    focus_code: str,
    rival_code: str,
    current_lap: int,
) -> float:
    """s/lap change in gap_to_focus over the last 3 completed laps.

    Positive = rival pulling away (gap_to_focus becoming more positive if
    they are ahead, or more negative if they are behind and dropping).
    """
    if all_laps is None or all_laps.empty or current_lap < 2:
        return 0.0
    from aris.field.standings import compute_standings

    start = max(1, int(current_lap) - 2)
    gaps: list[float] = []
    for lap in range(start, int(current_lap) + 1):
        rows = compute_standings(all_laps, lap_number=lap, sector_idx=3)
        focus = next((r for r in rows if str(r.code).upper() == focus_code.upper()), None)
        rival = next((r for r in rows if str(r.code).upper() == rival_code.upper()), None)
        if focus is None or rival is None:
            continue
        gaps.append(float(focus.gap_to_leader_s) - float(rival.gap_to_leader_s))
    if len(gaps) < 2:
        return 0.0
    n = len(gaps) - 1
    return (gaps[-1] - gaps[0]) / n
