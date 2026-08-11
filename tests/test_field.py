"""Tests for field standings and sector colors."""

import pandas as pd

from aris.field.sectors import SectorColor, color_sector_time, session_sector_bests
from aris.field.standings import compute_standings
from aris.field.state import FieldState, ReplayIndex


def _sample_all_laps() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "driver_id": 1, "code": "VER", "full_name": "Max", "team": "RBR",
                "lap_number": 1, "lap_time_s": 95.0,
                "sector_1_s": 30.0, "sector_2_s": 36.0, "sector_3_s": 29.0,
                "compound": "SOFT", "tyre_life": 1, "stint": 1,
                "track_status": "1", "pit_in": False, "pit_out": False,
            },
            {
                "driver_id": 2, "code": "HAM", "full_name": "Lewis", "team": "FER",
                "lap_number": 1, "lap_time_s": 96.0,
                "sector_1_s": 31.0, "sector_2_s": 36.5, "sector_3_s": 28.5,
                "compound": "SOFT", "tyre_life": 1, "stint": 1,
                "track_status": "1", "pit_in": False, "pit_out": False,
            },
        ]
    )


class TestStandings:
    def test_leader_is_ver(self):
        standings = compute_standings(_sample_all_laps(), lap_number=1, sector_idx=3)
        assert standings[0].code == "VER"
        assert standings[0].position == 1
        assert standings[1].gap_to_leader_s > 0

    def test_mid_lap_hides_later_sectors_and_full_lap_time(self):
        standings = compute_standings(_sample_all_laps(), lap_number=1, sector_idx=1)
        assert standings[0].sector_1_s == 30.0
        assert standings[0].sector_2_s is None
        assert standings[0].sector_3_s is None
        assert standings[0].last_lap_s is None
        assert standings[0].pit_in is False


class TestSectors:
    def test_purple_for_session_best(self):
        bests = session_sector_bests(_sample_all_laps(), through_lap=1)
        color = color_sector_time(30.0, sector_idx=1, session_bests=bests, personal_bests={})
        assert color == SectorColor.PURPLE


class TestFieldState:
    def test_from_laps(self):
        field = FieldState.from_laps(
            _sample_all_laps(), session_id=1, index=ReplayIndex(1, 3), total_laps=57
        )
        assert len(field.standings) == 2
        assert field.fastest_sectors[1] == "VER"
