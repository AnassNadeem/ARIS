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
        return cls(
            session_id=session_id,
            index=index,
            total_laps=total_laps,
            standings=standings,
            driver_views=views,
            session_bests=session_bests,
            fastest_sectors=fastest_sectors,
        )

    def standing_for(self, driver_id: int) -> StandingRow | None:
        for row in self.standings:
            if row.driver_id == driver_id:
                return row
        return None
