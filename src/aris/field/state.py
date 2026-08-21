"""FieldState — all drivers at current replay index."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from aris.field.sectors import (
    SectorColor,
    color_sector_time,
    driver_personal_bests,
    session_sector_bests,
)
from aris.field.standings import StandingRow, compute_standings
from aris.physics.tires import normalize_compound


def stint_lap_times(
    all_laps: pd.DataFrame,
    driver_id: int,
    current_lap: int,
    compound: str | None,
    *,
    n: int = 5,
) -> list[float]:
    """Last ``n`` completed lap times on ``compound`` up to ``current_lap``, oldest first."""
    if all_laps is None or all_laps.empty or "lap_time_s" not in all_laps.columns:
        return []
    drv = all_laps[all_laps["driver_id"] == int(driver_id)].sort_values("lap_number")
    drv = drv[drv["lap_number"] <= int(current_lap)]
    if drv.empty:
        return []
    want = normalize_compound(compound) if compound else None
    times: list[float] = []
    for row in reversed(list(drv.to_dict("records"))):
        if want and "compound" in row:
            got = normalize_compound(row.get("compound"))
            if got != want:
                break
        lt = row.get("lap_time_s")
        if lt is None or pd.isna(lt):
            continue
        times.append(float(lt))
        if len(times) >= n:
            break
    times.reverse()
    return times


@dataclass(frozen=True)
class ReplayIndex:
    lap_number: int
    sector_idx: int  # 0 = start of lap, 1-3 = after S1/S2/S3

    def advance(self, total_laps: int) -> ReplayIndex:
        if self.sector_idx < 3:
            return ReplayIndex(self.lap_number, self.sector_idx + 1)
        if self.lap_number < total_laps:
            return ReplayIndex(self.lap_number + 1, 0)
        return self

    @property
    def is_race_complete(self) -> bool:
        return False

    def is_done(self, total_laps: int) -> bool:
        return self.lap_number >= total_laps and self.sector_idx >= 3


@dataclass
class DriverSectorView:
    standing: StandingRow
    s1_color: SectorColor = SectorColor.NONE
    s2_color: SectorColor = SectorColor.NONE
    s3_color: SectorColor = SectorColor.NONE


@dataclass
class FieldState:
    session_id: int
    index: ReplayIndex
    total_laps: int
    standings: list[StandingRow] = field(default_factory=list)
    driver_views: list[DriverSectorView] = field(default_factory=list)
    session_bests: dict[int, float] = field(default_factory=dict)
    fastest_sectors: dict[int, str] = field(default_factory=dict)
    # Last 5 current-compound lap times per driver code, oldest first.
    lap_times_by_code: dict[str, list[float]] = field(default_factory=dict)

    @classmethod
    def from_laps(
        cls,
        all_laps: pd.DataFrame,
        *,
        session_id: int,
        index: ReplayIndex,
        total_laps: int,
    ) -> FieldState:
        lap = max(1, index.lap_number)
        sector = max(0, min(3, index.sector_idx))
        if sector == 0 and lap > 1:
            display_lap = lap - 1
            display_sector = 3
        else:
            display_lap = lap
            display_sector = max(1, sector) if sector > 0 else 1

        standings = compute_standings(all_laps, lap_number=display_lap, sector_idx=display_sector)
        session_bests = session_sector_bests(all_laps, through_lap=display_lap)
        views: list[DriverSectorView] = []
        fastest: dict[int, tuple[str, float]] = {}

        for row in standings:
            drv_laps = all_laps[all_laps["driver_id"] == row.driver_id]
            personal = driver_personal_bests(drv_laps, through_lap=display_lap)
            s1c = color_sector_time(
                row.sector_1_s, sector_idx=1,
                session_bests=session_bests, personal_bests=personal,
            )
            s2c = color_sector_time(
                row.sector_2_s, sector_idx=2,
                session_bests=session_bests, personal_bests=personal,
            )
            s3c = color_sector_time(
                row.sector_3_s, sector_idx=3,
                session_bests=session_bests, personal_bests=personal,
            )
            views.append(DriverSectorView(standing=row, s1_color=s1c, s2_color=s2c, s3_color=s3c))
            for sec, val, code in (
                (1, row.sector_1_s, row.code),
                (2, row.sector_2_s, row.code),
                (3, row.sector_3_s, row.code),
            ):
                if val is not None and not pd.isna(val):
                    prev = fastest.get(sec)
                    if prev is None or float(val) < prev[1]:
                        fastest[sec] = (code, float(val))

        fastest_sectors = {k: v[0] for k, v in fastest.items()}
        lap_times_by_code = {
            str(row.code).upper(): stint_lap_times(
                all_laps, row.driver_id, display_lap, row.compound
            )
            for row in standings
        }
        return cls(
            session_id=session_id,
            index=index,
            total_laps=total_laps,
            standings=standings,
            driver_views=views,
            session_bests=session_bests,
            fastest_sectors=fastest_sectors,
            lap_times_by_code=lap_times_by_code,
        )

    def standing_for(self, driver_id: int) -> StandingRow | None:
        for row in self.standings:
            if row.driver_id == driver_id:
                return row
        return None
