"""Dashboard copy / formatting helpers (Streamlit-free)."""

from pathlib import Path

import pandas as pd
import pytest

from aris.engine.clock import FAST_CLOCK_WARNING, SectorClock, fast_clock_enabled
from aris.ui_text import (
    format_callout_delta,
    format_race_clock,
    recommendation_caveat,
    weekend_form_empty_message,
)


class TestFormatRaceClock:
    def test_under_an_hour(self):
        assert format_race_clock(95) == "1:35"

    def test_bahrain_style_total(self):
        assert format_race_clock(5575) == "1:32:55"

    def test_rounds(self):
        assert format_race_clock(1.4) == "0:01"


class TestCalloutRendering:
    def test_negative_delta_no_plus(self):
        assert format_callout_delta(-13.00) == "-13.0s vs stay out"

    def test_positive_delta_plus(self):
        assert format_callout_delta(1.24) == "+1.2s vs stay out"

    def test_panel_renders_full_label(self):
        src = Path("apps/components/recommend_panel.py").read_text(encoding="utf-8")
        assert "html.escape(rec.label)" in src
        assert "rec.label[" not in src

    def test_caveat_from_context(self):
        text = "based on Safety Car-affected recent pace — lower confidence"
        assert recommendation_caveat({"confidence_caveat": text}) == text

    def test_caveat_from_evidence_fallback(self):
        ev = "stint ok | caveat: based on Safety Car-affected recent pace — lower confidence"
        assert "lower confidence" in (recommendation_caveat(None, ev) or "")

    def test_caveat_from_extrapolation(self):
        text = (
            "this call extends SOFT to tyre life 30, "
            "beyond typical observed stints — lower confidence"
        )
        assert recommendation_caveat({"confidence_caveat": text}) == text

    def test_no_caveat(self):
        assert recommendation_caveat({}, "") is None


class TestWeekendFormEmptyMessage:
    def test_race_only_mentions_fp1(self):
        msg = weekend_form_empty_message(["R"])
        assert "FP1" in msg
        assert "Race-only" in msg

    def test_no_sessions(self):
        msg = weekend_form_empty_message([])
        assert "No sessions" in msg

    def test_quali_without_practice(self):
        msg = weekend_form_empty_message(["Q"])
        assert "practice" in msg.lower()


class TestFastClockEnv:
    def test_default_absent_is_off(self, monkeypatch):
        monkeypatch.delenv("ARIS_FAST_CLOCK", raising=False)
        assert fast_clock_enabled() is False

    def test_other_values_are_off(self, monkeypatch):
        monkeypatch.setenv("ARIS_FAST_CLOCK", "true")
        assert fast_clock_enabled() is False
        monkeypatch.setenv("ARIS_FAST_CLOCK", "0")
        assert fast_clock_enabled() is False

    def test_default_respects_interval(self, monkeypatch):
        monkeypatch.delenv("ARIS_FAST_CLOCK", raising=False)
        clock = SectorClock(pd.DataFrame(), session_id=1, total_laps=10)
        clock.set_speed(1.0)
        # Fresh clock: 25s sector interval has not elapsed.
        assert clock.should_tick() is False

    def test_fast_clock_ticks_immediately(self, monkeypatch):
        monkeypatch.setenv("ARIS_FAST_CLOCK", "1")
        with pytest.warns(UserWarning, match="ARIS_FAST_CLOCK"):
            clock = SectorClock(pd.DataFrame(), session_id=1, total_laps=10)
        clock.set_speed(4.0)
        assert clock.should_tick() is True

    def test_fast_clock_still_honours_pause(self, monkeypatch):
        monkeypatch.setenv("ARIS_FAST_CLOCK", "1")
        with pytest.warns(UserWarning, match="ARIS_FAST_CLOCK"):
            clock = SectorClock(pd.DataFrame(), session_id=1, total_laps=10)
        clock.set_speed(0.0)
        assert clock.should_tick() is False

    def test_fast_clock_warns_on_construct(self, monkeypatch):
        monkeypatch.setenv("ARIS_FAST_CLOCK", "1")
        with pytest.warns(UserWarning, match="screenshot/harness-only"):
            SectorClock(pd.DataFrame(), session_id=1, total_laps=10)
        assert FAST_CLOCK_WARNING.startswith("ARIS_FAST_CLOCK=1")


class TestSkipToFlagGated:
    def test_button_requires_technical_toggle(self):
        src = Path("apps/pages/01_Strategy.py").read_text(encoding="utf-8")
        needle = 'st.button("Skip to chequered flag")'
        assert needle in src
        idx = src.index(needle)
        window = src[max(0, idx - 80) : idx]
        assert "show_technical()" in window


class TestAskSnapshotLabel:
    def test_ask_panel_renders_snapshot_notice(self):
        src = Path("apps/components/aris_chat.py").read_text(encoding="utf-8")
        assert "ask_panel_notice()" in src
        assert "aris-caveat" in src
