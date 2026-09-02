"""Circuit history from 2018 (Jolpica), not 2024-only."""

from backend.analytics import (
    HISTORY_FROM_YEAR,
    _circuit_history_compute,
    _ergast_circuit_id,
    _history_analysis,
)
from backend.models import CircuitHistoryYear


def test_history_from_year_is_2018():
    assert HISTORY_FROM_YEAR == 2018


def test_ergast_id_maps_zandvoort():
    assert _ergast_circuit_id("netherlands") == "zandvoort"
    assert _ergast_circuit_id("zandvoort") == "zandvoort"


def test_history_analysis_mentions_2018_sample():
    years = [
        CircuitHistoryYear(year=2018, winner="HAM", winner_team="Mercedes", winner_grid=1),
        CircuitHistoryYear(year=2021, winner="VER", winner_team="Red Bull", winner_grid=1),
        CircuitHistoryYear(year=2024, winner="NOR", winner_team="McLaren", winner_grid=2),
    ]
    text = _history_analysis(years, typical_stops=1.0, median_first=20, most_common="HAM")
    assert "2018" in text
    assert "3 races" in text
    assert "HAM" in text
    assert "one-stop" in text


def test_circuit_history_uses_jolpica_2018(monkeypatch):
    from backend import analytics

    def fake_circuit(cid: str):
        if cid != "zandvoort":
            return []
        return [
            CircuitHistoryYear(year=2018, winner="HAM", pole="HAM", race_name="Dutch Grand Prix"),
            CircuitHistoryYear(year=2021, winner="VER", pole="VER", race_name="Dutch Grand Prix"),
            CircuitHistoryYear(year=2024, winner="NOR", pole="NOR", race_name="Dutch Grand Prix"),
        ]

    monkeypatch.setattr(analytics, "_history_from_jolpica_circuit", fake_circuit)
    monkeypatch.setattr(analytics, "_jolpica_hist", lambda _p: {})
    monkeypatch.setattr(analytics, "_calendar_notes_overlay", lambda _k: {})
    monkeypatch.setattr(analytics, "_fastf1_history_overlay", lambda _k: [])
    monkeypatch.setattr(analytics, "_field_pit_meta", lambda *_a, **_k: (None, None))
    monkeypatch.setattr(analytics, "_winner_pit_meta", lambda *_a, **_k: (1, 18))

    out = _circuit_history_compute("netherlands")
    years = {y.year for y in out.years}
    assert 2018 in years
    assert 2024 in years
    assert out.from_year == 2018
    assert min(years) == 2018
    poles = {y.year: y.pole for y in out.years}
    assert poles[2018] == "HAM"
    assert poles[2024] == "NOR"


def test_pole_from_results_uses_grid_one():
    from backend.analytics import _pole_from_results

    assert (
        _pole_from_results(
            [
                {"grid": "3", "Driver": {"code": "VER"}},
                {"grid": "1", "Driver": {"code": "NOR"}},
            ]
        )
        == "NOR"
    )


def test_zandvoort_analysis_names_modern_races():
    years = [
        CircuitHistoryYear(year=2021, winner="VER", winner_team="Red Bull", winner_grid=1),
        CircuitHistoryYear(year=2024, winner="NOR", winner_team="McLaren", winner_grid=2),
        CircuitHistoryYear(year=2025, winner="PIA", winner_team="McLaren", winner_grid=1),
    ]
    text = _history_analysis(years, typical_stops=1.2, median_first=23, most_common="VER", circuit_key="netherlands")
    assert "2021–2025" in text or "2021-2025" in text
    assert "one-stop" in text


def test_weekend_excludes_hadjar_dutch_2026():
    from backend.calendar import weekend_excluded_codes

    assert "HAD" in weekend_excluded_codes(2026, 12)
    assert weekend_excluded_codes(2026, 14) == set()
