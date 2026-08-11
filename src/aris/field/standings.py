"""Derive positions and gaps from cumulative lap times."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class StandingRow:
    position: int
    driver_id: int
    code: str
    full_name: str
    team: str | None
    lap_number: int
    sector_idx: int
    cumulative_time_s: float
    gap_to_leader_s: float
    gap_ahead_s: float | None
    gap_behind_s: float | None
    last_lap_s: float | None
    sector_1_s: float | None
    sector_2_s: float | None
    sector_3_s: float | None
    compound: str | None
    tyre_life: int | None
    pit_in: bool
    pit_out: bool
    track_status: str | None


def _sector_columns(sector_idx: int) -> list[str]:
    if sector_idx <= 0:
        return []
    return [f"sector_{i}_s" for i in range(1, sector_idx + 1)]


def _partial_lap_time(row: pd.Series, sector_idx: int) -> float | None:
    cols = _sector_columns(sector_idx)
    if not cols:
        return 0.0
    values = [row.get(c) for c in cols]
    if any(pd.isna(v) for v in values):
        return None
    return float(sum(values))


def _visible_sector(row: pd.Series, sector_num: int, sector_idx: int) -> float | None:
    """Sector time only if that sector has been completed at this replay point."""
    if sector_num > sector_idx:
        return None
    val = row.get(f"sector_{sector_num}_s")
    return float(val) if pd.notna(val) else None


def _completed_lap_time(grp: pd.DataFrame, lap_number: int, sector_idx: int) -> float | None:
    """Last fully completed lap time visible at this point (None mid-lap)."""
    if sector_idx >= 3:
        current = grp[grp["lap_number"] == lap_number]
        if not current.empty and pd.notna(current.iloc[0].get("lap_time_s")):
            return float(current.iloc[0]["lap_time_s"])
    prior = grp[grp["lap_number"] < lap_number]
    if prior.empty:
        return None
    last = prior.iloc[-1]
    return float(last["lap_time_s"]) if pd.notna(last.get("lap_time_s")) else None


def compute_standings(
    all_laps: pd.DataFrame,
    *,
    lap_number: int,
    sector_idx: int,
) -> list[StandingRow]:
    """Positions at end of sector `sector_idx` on `lap_number` (1-3).

    Mid-lap rows hide later-sector times and the unfinished lap's full
    ``lap_time_s`` so a replay cannot see timing that has not happened yet.
    """
    if all_laps.empty:
        return []

    rows: list[StandingRow] = []
    for driver_id, grp in all_laps.groupby("driver_id"):
        grp = grp.sort_values("lap_number")
        prior = grp[grp["lap_number"] < lap_number]
        cum = float(prior["lap_time_s"].dropna().sum()) if not prior.empty else 0.0

        current = grp[grp["lap_number"] == lap_number]
        if current.empty:
            if lap_number > 1:
                last = grp[grp["lap_number"] == lap_number - 1]
                if not last.empty:
                    lr = last.iloc[0]
                    rows.append(
                        StandingRow(
                            position=0,
                            driver_id=int(driver_id),
                            code=str(lr["code"]),
                            full_name=str(lr["full_name"]),
                            team=str(lr["team"]) if pd.notna(lr.get("team")) else None,
                            lap_number=lap_number - 1,
                            sector_idx=3,
                            cumulative_time_s=cum,
                            gap_to_leader_s=0.0,
                            gap_ahead_s=None,
                            gap_behind_s=None,
                            last_lap_s=float(lr["lap_time_s"])
                            if pd.notna(lr.get("lap_time_s"))
                            else None,
                            sector_1_s=_visible_sector(lr, 1, 3),
                            sector_2_s=_visible_sector(lr, 2, 3),
                            sector_3_s=_visible_sector(lr, 3, 3),
                            compound=str(lr["compound"]) if pd.notna(lr.get("compound")) else None,
                            tyre_life=(
                                int(lr["tyre_life"]) if pd.notna(lr.get("tyre_life")) else None
                            ),
                            pit_in=bool(lr.get("pit_in")),
                            pit_out=bool(lr.get("pit_out")),
                            track_status=str(lr["track_status"])
                            if pd.notna(lr.get("track_status"))
                            else None,
                        )
                    )
            continue

        lap_row = current.iloc[0]
        partial = _partial_lap_time(lap_row, sector_idx)
        if partial is None:
            continue
        total = cum + partial
        rows.append(
            StandingRow(
                position=0,
                driver_id=int(driver_id),
                code=str(lap_row["code"]),
                full_name=str(lap_row["full_name"]),
                team=str(lap_row["team"]) if pd.notna(lap_row.get("team")) else None,
                lap_number=lap_number,
                sector_idx=sector_idx,
                cumulative_time_s=total,
                gap_to_leader_s=0.0,
                gap_ahead_s=None,
                gap_behind_s=None,
                last_lap_s=_completed_lap_time(grp, lap_number, sector_idx),
                sector_1_s=_visible_sector(lap_row, 1, sector_idx),
                sector_2_s=_visible_sector(lap_row, 2, sector_idx),
                sector_3_s=_visible_sector(lap_row, 3, sector_idx),
                compound=str(lap_row["compound"]) if pd.notna(lap_row.get("compound")) else None,
                tyre_life=int(lap_row["tyre_life"])
                if pd.notna(lap_row.get("tyre_life"))
                else None,
                pit_in=bool(lap_row.get("pit_in")) if sector_idx >= 3 else False,
                pit_out=bool(lap_row.get("pit_out")),
                track_status=str(lap_row["track_status"])
                if pd.notna(lap_row.get("track_status"))
                else None,
            )
        )

    rows.sort(key=lambda r: r.cumulative_time_s)
    leader_time = rows[0].cumulative_time_s if rows else 0.0
    enriched: list[StandingRow] = []
    for i, row in enumerate(rows):
        gap_leader = row.cumulative_time_s - leader_time
        gap_ahead = None
        gap_behind = None
        if i > 0:
            gap_ahead = row.cumulative_time_s - rows[i - 1].cumulative_time_s
        if i < len(rows) - 1:
            gap_behind = rows[i + 1].cumulative_time_s - row.cumulative_time_s
        enriched.append(
            StandingRow(
                **{
                    **row.__dict__,
                    "position": i + 1,
                    "gap_to_leader_s": gap_leader,
                    "gap_ahead_s": gap_ahead,
                    "gap_behind_s": gap_behind,
                }
            )
        )
    return enriched
