"""Compound-identity mapping (Phase G2)."""

import pandas as pd
import pytest

from aris.physics.compounds import (
    TRUE_COMPOUND_SLOPES_ENV,
    compound_era,
    compound_identity,
    event_relative_slopes,
    join_compound_identity,
    lookup_nomination,
    parse_true_compound_mode,
)
from aris.physics.tires import DEFAULT_COMPOUND_SLOPE
from aris.tracks import clear_track_config_cache, load_track_config


class TestSeedNetherlands:
    """Verified seed table from the phase brief / Pirelli."""

    def test_2022_c1_c2_c3_pre_reclass(self):
        nom = lookup_nomination(2022, "Netherlands")
        assert nom is not None
        assert (nom.hard, nom.medium, nom.soft) == ("C1", "C2", "C3")
        assert nom.era == "2022"

    def test_2023_c1_c2_c3_new_generation(self):
        nom = lookup_nomination(2023, "Zandvoort")
        assert nom is not None
        assert (nom.hard, nom.medium, nom.soft) == ("C1", "C2", "C3")
        assert nom.era == "2023-2025"
        # Same C-codes as 2022 must NOT share an era.
        assert lookup_nomination(2022, "Netherlands").era != nom.era

    def test_2024_c1_c2_c3(self):
        nom = lookup_nomination(2024, "Netherlands", round_no=15)
        assert nom is not None
        assert (nom.hard, nom.medium, nom.soft) == ("C1", "C2", "C3")

    def test_2025_c2_c3_c4(self):
        nom = lookup_nomination(2025, "Dutch Grand Prix")
        assert nom is not None
        assert (nom.hard, nom.medium, nom.soft) == ("C2", "C3", "C4")

    def test_2021_c1_c2_c3(self):
        nom = lookup_nomination(2021, "Netherlands")
        assert nom is not None
        assert (nom.hard, nom.medium, nom.soft) == ("C1", "C2", "C3")
        assert nom.era == "2019-2021"

    def test_2026_announced_c2_c3_c4(self):
        nom = lookup_nomination(2026, "Netherlands")
        assert nom is not None
        assert (nom.hard, nom.medium, nom.soft) == ("C2", "C3", "C4")
        assert nom.era == "2026"


def test_2025_spa_nonconsecutive():
    nom = lookup_nomination(2025, "Belgium")
    assert nom is not None
    assert (nom.hard, nom.medium, nom.soft) == ("C1", "C3", "C4")


def test_2018_unmapped():
    assert lookup_nomination(2018, "Australia") is None
    assert compound_identity("SOFT", 2018, "Australia") == "SOFT"


def test_wet_stays_relative():
    assert compound_identity("INTERMEDIATE", 2024, "Netherlands") == "INTERMEDIATE"
    assert compound_identity("WET", 2023, "Netherlands") == "WET"


def test_join_keeps_relative_and_adds_identity():
    laps = pd.DataFrame({"Compound": ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE"]})
    out = join_compound_identity(laps, year=2025, event="Netherlands")
    assert list(out["Compound"]) == ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE"]
    assert list(out["CompoundIdentity"]) == ["C4", "C3", "C2", "INTERMEDIATE"]


def test_unmapped_event_relative_slopes_are_none():
    slopes, meta = event_relative_slopes(2019, "Bahrain", round_no=1)
    assert slopes is None
    assert meta["mapped"] is False
    assert meta["source"] == "global_fallback"


def test_mapped_without_fit_does_not_overlay_yaml():
    # No true_compound_slopes.json in a fresh checkout / before the fit.
    # Overlay must be None so YAML/global defaults remain.
    slopes, meta = event_relative_slopes(2024, "Bahrain", round_no=1)
    assert meta["mapped"] is True
    if slopes is None:
        assert meta.get("reason") == "mapped_but_no_fit"
    else:
        for k in ("SOFT", "MEDIUM", "HARD"):
            assert k in slopes


def test_era_helper():
    assert compound_era(2021) == "2019-2021"
    assert compound_era(2022) == "2022"
    assert compound_era(2025) == "2023-2025"
    assert compound_era(2026) == "2026"


def test_pava_pools_an_inversion():
    from aris.physics.compounds import constrain_slopes_isotonic

    unconstrained = {"C1": 0.10, "C2": 0.04, "C3": 0.12}
    constrained, notes = constrain_slopes_isotonic(
        unconstrained, {"C1": 1.0, "C2": 1.0, "C3": 1.0}
    )
    assert constrained["C1"] <= constrained["C2"] <= constrained["C3"]
    # Equal-weight pool of the C1>C2 inversion → 0.07, 0.07, 0.12
    assert constrained["C1"] == pytest.approx(0.07, abs=1e-4)
    assert constrained["C2"] == pytest.approx(0.07, abs=1e-4)
    assert constrained["C3"] == pytest.approx(0.12, abs=1e-4)
    kinds = {n["pair"]: n["kind"] for n in notes}
    assert kinds["C1<=C2"] == "inverted_compressed_to_equal"


def test_pava_leaves_already_ordered_untouched():
    from aris.physics.compounds import constrain_slopes_isotonic

    unconstrained = {"C1": 0.02, "C2": 0.04, "C3": 0.08}
    constrained, notes = constrain_slopes_isotonic(unconstrained)
    assert constrained == {"C1": 0.02, "C2": 0.04, "C3": 0.08}
    assert all(n["kind"] == "unchanged" for n in notes)


def test_load_track_config_without_year_keeps_yaml():
    clear_track_config_cache()
    cfg = load_track_config("Bahrain")
    if cfg.compound_slopes is not None:
        for k in ("SOFT", "MEDIUM", "HARD"):
            assert cfg.compound_slopes[k] == pytest.approx(DEFAULT_COMPOUND_SLOPE[k])
    clear_track_config_cache()


def test_parse_true_compound_mode_defaults_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(TRUE_COMPOUND_SLOPES_ENV, raising=False)
    assert parse_true_compound_mode() == "off"
    assert parse_true_compound_mode("1") == "unconstrained"
    assert parse_true_compound_mode("isotonic") == "isotonic"
    assert parse_true_compound_mode("pooled") == "pooled"
    assert parse_true_compound_mode("maybe") == "off"


def test_load_track_config_year_does_not_overlay_by_default(monkeypatch: pytest.MonkeyPatch):
    """G3.1: year-keyed load is the simulate()/recommend() path; must stay G1.5."""
    monkeypatch.delenv(TRUE_COMPOUND_SLOPES_ENV, raising=False)
    clear_track_config_cache()
    cfg = load_track_config("Netherlands", year=2025, round_no=15)
    assert cfg.compound_slopes is not None
    assert cfg.compound_slopes["SOFT"] == pytest.approx(0.08)
    assert cfg.compound_slopes["MEDIUM"] == pytest.approx(0.05)
    assert cfg.compound_slopes["HARD"] == pytest.approx(0.03)
    clear_track_config_cache()


def test_true_compound_overlay_requires_opt_in(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(TRUE_COMPOUND_SLOPES_ENV, "1")
    clear_track_config_cache()
    cfg = load_track_config("Netherlands", year=2025, round_no=15)
    # 2025 NL is C2/C3/C4 in era 2023-2025 — not the YAML 0.08/0.05/0.03 triple.
    assert cfg.compound_slopes is not None
    assert cfg.compound_slopes["SOFT"] == pytest.approx(0.0283, abs=1e-4)
    assert cfg.compound_slopes["MEDIUM"] == pytest.approx(0.0461, abs=1e-4)
    assert cfg.compound_slopes["HARD"] == pytest.approx(0.0359, abs=1e-4)
    # Explicit kwarg still works if env is off.
    monkeypatch.delenv(TRUE_COMPOUND_SLOPES_ENV, raising=False)
    clear_track_config_cache()
    off = load_track_config("Netherlands", year=2025, round_no=15)
    assert off.compound_slopes["SOFT"] == pytest.approx(0.08)
    on = load_track_config(
        "Netherlands", year=2025, round_no=15, use_true_compound=True
    )
    assert on.compound_slopes["SOFT"] == pytest.approx(0.0283, abs=1e-4)
    clear_track_config_cache()


def test_isotonic_overlay_opt_in(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(TRUE_COMPOUND_SLOPES_ENV, "isotonic")
    from aris.physics.compounds import clear_compound_caches

    clear_compound_caches()
    clear_track_config_cache()
    cfg = load_track_config("Netherlands", year=2025, round_no=15)
    # 2023-2025 PAVA collapsed every C-code to 0.0216, so H/M/S are equal.
    assert cfg.compound_slopes is not None
    assert cfg.compound_slopes["SOFT"] == pytest.approx(0.0216, abs=1e-4)
    assert cfg.compound_slopes["MEDIUM"] == pytest.approx(0.0216, abs=1e-4)
    assert cfg.compound_slopes["HARD"] == pytest.approx(0.0216, abs=1e-4)
    monkeypatch.delenv(TRUE_COMPOUND_SLOPES_ENV, raising=False)
    clear_track_config_cache()
