"""Circuit history from 2018 (Jolpica), not 2024-only."""

from backend.analytics import HISTORY_FROM_YEAR, _ergast_circuit_id, _history_analysis, circuit_history
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

    def fake_year(cid: str, year: int):
        if cid != "zandvoort" or year not in {2018, 2021, 2024}:
            return None
        return CircuitHistoryYear(year=year, winner="VER" if year > 2018 else "HAM", race_name="Dutch Grand Prix")

    monkeypatch.setattr(analytics, "_history_year_from_jolpica", fake_year)
    monkeypatch.setattr(analytics, "_jolpica_hist", lambda _p: {})
    monkeypatch.setattr(analytics, "_calendar_notes_overlay", lambda _k: {})
    monkeypatch.setattr(analytics, "_fastf1_history_overlay", lambda _k: [])
    monkeypatch.setattr(analytics, "_winner_pit_meta", lambda *_a, **_k: (1, 18))

    out = circuit_history("netherlands")
    years = {y.year for y in out.years}
    assert 2018 in years
    assert 2024 in years
    assert out.from_year == 2018
    assert min(years) == 2018
