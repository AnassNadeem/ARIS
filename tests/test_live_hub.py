"""Live hub, cancelled 2026 rounds, replayable calendar — no live network."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.calendar import country_flag, replay_years, replayable_rounds
from backend.live_hub import classify_hub_mode
from backend.models import LiveStatus, SessionInfo


def test_live_hub_routes_registered():
    from backend.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/live/hub" in paths
    assert "/api/live/next" in paths
    assert "/api/live/status" in paths
    assert "/api/telemetry/cars" in paths
    assert "/api/circuits/{circuit_id}/layout" in paths
    assert "/api/circuit/{year}/{round_number}/map" in paths


def test_classify_live_session_wins():
    weekend = [
        SessionInfo(session_type="Q", session_name="Qualifying", status="COMPLETED"),
        SessionInfo(session_type="R", session_name="Race", status="LIVE"),
    ]
    mode, reason = classify_hub_mode(
        is_live=True, session_ended=False, weekend_sessions=weekend, is_this_weekend=True
    )
    assert mode == "live_session"
    assert reason is None


def test_classify_waiting_for_race():
    weekend = [
        SessionInfo(session_type="FP1", session_name="Free Practice 1", status="COMPLETED"),
        SessionInfo(session_type="Q", session_name="Qualifying", status="COMPLETED"),
        SessionInfo(session_type="R", session_name="Race", status="UPCOMING"),
    ]
    mode, reason = classify_hub_mode(
        is_live=False, session_ended=False, weekend_sessions=weekend, is_this_weekend=True
    )
    assert mode == "waiting_for_session"
    assert reason is not None
    assert "hasn't started" in reason.lower()
    assert "waiting for race data" in reason.lower()


def test_classify_waiting_for_qualifying():
    weekend = [
        SessionInfo(session_type="FP3", session_name="Free Practice 3", status="COMPLETED"),
        SessionInfo(session_type="Q", session_name="Qualifying", status="UPCOMING"),
        SessionInfo(session_type="R", session_name="Race", status="UPCOMING"),
    ]
    mode, reason = classify_hub_mode(
        is_live=False, session_ended=False, weekend_sessions=weekend, is_this_weekend=True
    )
    assert mode == "waiting_for_session"
    assert reason is not None
    assert "qualifying" in reason.lower()


def test_classify_next_weekend():
    weekend = [
        SessionInfo(session_type="FP1", session_name="Free Practice 1", status="UPCOMING"),
        SessionInfo(session_type="R", session_name="Race", status="UPCOMING"),
    ]
    mode, reason = classify_hub_mode(
        is_live=False, session_ended=False, weekend_sessions=weekend, is_this_weekend=False
    )
    assert mode == "next_weekend"
    assert reason is None


def test_classify_session_ended():
    weekend = [
        SessionInfo(session_type="R", session_name="Race", status="COMPLETED"),
    ]
    mode, _reason = classify_hub_mode(
        is_live=False, session_ended=True, weekend_sessions=weekend, is_this_weekend=False
    )
    assert mode == "session_ended"


def test_2026_bahrain_saudi_cancelled():
    from backend.calendar import get_calendar

    cal = get_calendar(2026, as_of=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc))
    by = {r.round_number: r for r in cal.rounds}
    assert by[2].status == "CANCELLED"
    assert "bahrain" in (by[2].cancelled_reason or "").lower()
    assert by[3].status == "CANCELLED"
    assert "saudi" in (by[3].cancelled_reason or "").lower()


def test_next_race_skips_cancelled_bahrain_saudi():
    from backend.calendar import next_race

    nxt = next_race(as_of=datetime(2026, 3, 16, 16, 0, tzinfo=timezone.utc))
    assert nxt.round_number == 4
    blob = f"{nxt.name} {nxt.circuit_name}".lower()
    assert "japan" in blob or "suzuka" in blob
    assert nxt.status != "CANCELLED"


def test_replayable_2026_excludes_cancelled_and_upcoming():
    as_of = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    rows = replayable_rounds(2026, as_of=as_of)
    nums = {r.round_number for r in rows}
    assert 2 not in nums
    assert 3 not in nums
    assert 15 in nums
    assert 16 not in nums
    assert all(r.status not in {"CANCELLED", "UPCOMING"} for r in rows)


def test_replay_years_include_2026():
    years = replay_years(as_of=datetime(2026, 8, 26, tzinfo=timezone.utc))
    assert years[0] == 2026
    assert 2018 in years
    assert 2025 in years


def test_country_flag_netherlands():
    assert country_flag("Netherlands", "netherlands") == "🇳🇱"
    assert country_flag("Italy", "monza") == "🇮🇹"


def test_resolve_layout_netherlands_2025():
    from backend.live_hub import resolve_layout_round

    year, rnd = resolve_layout_round("netherlands", year=2025)
    assert year == 2025
    assert rnd == 15


def test_hub_sessions_replayable_flag():
    from backend.live_hub import _hub_sessions

    rows = _hub_sessions(
        [
            SessionInfo(session_type="FP1", session_name="FP1", status="COMPLETED"),
            SessionInfo(session_type="R", session_name="Race", status="UPCOMING"),
        ]
    )
    assert rows[0].replayable is True
    assert rows[0].live is False
    assert rows[1].replayable is False


def test_build_live_hub_waiting_zandvoort_race_morning(monkeypatch):
    from backend.live_hub import build_live_hub

    as_of = datetime(2026, 8, 23, 11, 0, tzinfo=timezone.utc)

    async def fake_status(*_a, **_k):
        return LiveStatus(is_live=False, year=2026, round_number=15, session_name="Race")

    monkeypatch.setattr("backend.live.live_status", fake_status)
    monkeypatch.setattr("backend.analytics.peek_circuit_history", lambda *_a, **_k: None)

    hub = asyncio.run(build_live_hub(as_of))
    assert hub.next.round_number == 15
    assert hub.mode == "waiting_for_session"
    assert hub.waiting_reason is not None
    assert "hasn't started" in hub.waiting_reason.lower()
    assert hub.countdown_target is not None
    assert any(s.session_type == "R" and s.status == "UPCOMING" for s in hub.weekend_sessions)
    assert any(s.replayable for s in hub.weekend_sessions)


def test_build_live_hub_fast_does_not_need_openf1():
    from backend.live_hub import build_live_hub_fast

    hub = build_live_hub_fast(datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc))
    assert hub.next.round_number >= 1
    assert hub.circuit.circuit_name
    assert hub.weekend_sessions


def test_sse_payload_includes_positions_key():
    import inspect

    from backend.live import sse_generator

    src = inspect.getsource(sse_generator)
    assert '"positions"' in src
    assert '"timing"' in src
