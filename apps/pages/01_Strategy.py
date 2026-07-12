"""ARIS Race Engineer — always-on sector-paced strategy game."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

import streamlit as st  # noqa: E402

try:
    if "ARIS_DB_URL" in st.secrets:
        os.environ.setdefault("ARIS_DB_URL", st.secrets["ARIS_DB_URL"])
except (FileNotFoundError, KeyError):
    pass

from apps.components.aris_chat import render_ask_mode, render_chat  # noqa: E402
from apps.components.leaderboard import render_leaderboard  # noqa: E402
from apps.components.session_setup import render_setup  # noqa: E402
from apps.components.strat_cards import render_strat_cards  # noqa: E402
from aris.engine.clock import SectorClock  # noqa: E402
from aris.engine.session import RaceEngineSession, SessionPhase  # noqa: E402
from aris.engine.triggers import check_triggers  # noqa: E402
from aris.eval.conformal import calibrated_delta_interval  # noqa: E402
from aris.eval.postrace import compare_post_race, export_postrace, save_feedback_rows  # noqa: E402
from aris.io import db  # noqa: E402
from aris.montecarlo import run_mc  # noqa: E402
from aris.plan.prewrite import generate_strat_plans  # noqa: E402
from aris.plan.weekend_form import weekend_form  # noqa: E402
from aris.recommend import recommend  # noqa: E402
from aris.simulate import ActionKind, StrategyAction, simulate  # noqa: E402
from aris.tracks import load_track_config  # noqa: E402

st.set_page_config(page_title="ARIS Race Engineer", layout="wide")
st.title("ARIS — Race Engineer")
st.caption("Always-on strategy game. You are the race engineer — ARIS recommends, you decide.")

if "engine_session" not in st.session_state:
    st.session_state.engine_session = None
if "clock" not in st.session_state:
    st.session_state.clock = None
if "ui_mode" not in st.session_state:
    st.session_state.ui_mode = "Watch"

with st.sidebar:
    st.markdown("[← Lap explorer](streamlit_app)")
    ui_mode = st.radio("Mode", ["Watch", "Ask", "What-if", "Replay"], key="mode_radio")
    st.session_state.ui_mode = ui_mode
    use_llm = st.toggle("Use LLM narration", value=False)

try:
    setup = render_setup()
except RuntimeError as exc:
    st.error(f"Database not configured: {exc}")
    st.stop()

if setup is None:
    st.stop()

track = load_track_config(setup["country"])

if st.sidebar.button("Start / Reset session"):
    session = RaceEngineSession(
        session_id=setup["session_id"],
        driver_id=setup["driver_id"],
        driver_code=setup["driver_code"],
        team=setup["team"],
        year=setup["year"],
        round_no=setup["round_no"],
        country=setup["country"],
        total_laps=track.total_laps,
        phase=SessionPhase.PRE_RACE,
    )
    all_laps = db.fetch_all_laps(setup["session_id"])
    st.session_state.engine_session = session
    st.session_state.clock = SectorClock(
        all_laps,
        session_id=setup["session_id"],
        total_laps=track.total_laps,
    )
    st.session_state.strat_plans = generate_strat_plans(
        setup["session_id"],
        setup["driver_id"],
        year=setup["year"],
        round_no=setup["round_no"],
        country=setup["country"],
        driver_code=setup["driver_code"],
    )

session: RaceEngineSession | None = st.session_state.engine_session
clock: SectorClock | None = st.session_state.clock

if session is None:
    st.info("Select team/driver and click **Start / Reset session** in the sidebar.")
    st.stop()

left, right = st.columns([0.35, 0.65])

# --- PRE-RACE ---
if session.phase == SessionPhase.PRE_RACE:
    with right:
        forms = weekend_form(setup["year"], setup["round_no"])
        if forms:
            st.subheader("Weekend form")
            form_rows = [
                {
                    "Driver": f.code,
                    "Team": f.team,
                    "Quali": f"{f.quali_time:.3f}" if f.quali_time else "—",
                    "SOFT": f"{f.best_soft:.3f}" if f.best_soft else "—",
                    "MEDIUM": f"{f.best_medium:.3f}" if f.best_medium else "—",
                    "HARD": f"{f.best_hard:.3f}" if f.best_hard else "—",
                }
                for f in forms[:10]
            ]
            st.dataframe(form_rows, use_container_width=True)

        plans = st.session_state.get("strat_plans")
        if plans:
            selected = render_strat_cards(plans)
            if selected:
                session.active_strat = selected
            if st.button("Lock strategy & start race", type="primary"):
                if session.active_strat is None and plans.plans:
                    session.active_strat = plans.plans[0]
                session.phase = SessionPhase.LIVE
                st.rerun()

# --- LIVE RACE ---
elif session.phase == SessionPhase.LIVE:
    with left:
        st.subheader("Timing Tower")
        speed = st.radio("Speed", ["Pause", "1x", "2x", "4x"], horizontal=True, index=1)
        speed_map = {"Pause": 0.0, "1x": 1.0, "2x": 2.0, "4x": 4.0}
        if clock:
            clock.set_speed(speed_map[speed])
            if speed != "Pause" and clock.should_tick():
                event = clock.tick()
                session.replay_index = event.index
                session.field_state = event.field
                kind = check_triggers(session, event)
                if kind:
                    session.decision_queue.propose(
                        session.build_state(), kind=kind, use_llm=use_llm
                    )
                if event.is_race_complete:
                    session.phase = SessionPhase.POST_RACE
            elif session.field_state is None and clock:
                session.field_state = clock.current_field()
        render_leaderboard(session.field_state)

    with right:
        st.subheader(f"Engineer for {session.driver_code} ({session.team})")
        if session.active_strat:
            st.caption(f"Active: {session.active_strat.name}")

        mode = st.session_state.ui_mode
        if mode == "Watch":
            render_chat(session, session.decision_queue)
            with st.expander("Manual Pit"):
                pit_offset = st.number_input("Pit in N laps", 0, 10, 0)
                compound = st.selectbox("Tyre", ["SOFT", "MEDIUM", "HARD"])
                if st.button("Confirm manual pit"):
                    lap = session.replay_index.lap_number + int(pit_offset)
                    session.commit_pit(lap, compound, source="manual")
                    session.decision_queue.push_engineer(
                        f"Manual pit call — lap {lap}, {compound}"
                    )
                    st.rerun()
        elif mode == "Ask":
            render_ask_mode(session)
        elif mode == "What-if":
            st.subheader("What-if")
            state = session.build_state()
            pit_lap = st.slider("Pit lap", state.lap_number, state.total_laps, state.lap_number + 5)
            compound = st.selectbox("Pit compound", ["SOFT", "MEDIUM", "HARD"], key="wi_compound")
            action = StrategyAction(kind=ActionKind.PIT_LAP, pit_lap=pit_lap, pit_compound=compound)
            outcome = simulate(state, action)
            mc = run_mc(state, action, n_draws=50)
            lo, hi = calibrated_delta_interval(mc)
            st.metric("Delta vs stay out", f"{outcome.delta_vs_stay_out_s:+.2f}s")
            st.write(f"MC P10/P90 delta: {lo:+.2f}s / {hi:+.2f}s")
            rec = recommend(state, top_k=3, mc_draws=30)
            for r in rec.recommendations:
                with st.expander(f"#{r.rank} {r.label}"):
                    st.write(r.evidence)
                    st.write(f"Δ {r.delta_vs_stay_out_s:+.2f}s (σ {r.confidence_std_s:.2f})")
        elif mode == "Replay":
            st.subheader("Replay scrubber")
            scrub_lap = st.slider("Lap", 1, session.total_laps, session.replay_index.lap_number)
            scrub_sector = st.slider("Sector", 0, 3, session.replay_index.sector_idx)
            if clock:
                clock.index = clock.index.__class__(scrub_lap, scrub_sector)
                session.field_state = clock.current_field()
            hist_state = session.build_state(scrub_lap)
            rec = recommend(hist_state, top_k=1, mc_draws=20)
            label = rec.recommendations[0].label if rec.recommendations else "—"
            st.write(f"ARIS at L{scrub_lap}: {label}")

    if speed != "Pause":
        time.sleep(0.3)
        st.rerun()

# --- POST-RACE ---
elif session.phase == SessionPhase.POST_RACE:
    with left:
        render_leaderboard(session.field_state)
    with right:
        st.subheader("Post-race analysis")
        comparison = compare_post_race(session)
        st.write(comparison.summary)
        c1, c2, c3 = st.columns(3)
        c1.metric("Decisions", comparison.decision_count)
        c2.metric("Actual finish", comparison.actual_finish_pos or "—")
        pit_err = f"{comparison.pit_lap_error:.0f}" if comparison.pit_lap_error else "—"
        c3.metric("Pit lap error", pit_err)

        path = export_postrace(session, comparison)
        st.success(f"Exported to {path.name}")
        if st.button("Save feedback to DB"):
            n = save_feedback_rows(session)
            st.success(f"Saved {n} feedback rows")

        st.subheader("Decision log")
        for rec in session.decision_queue.decisions:
            label = rec.recommendation.label if rec.recommendation else rec.kind.value
            st.write(f"L{rec.lap}: {label} — {'accepted' if rec.accepted else 'rejected'}")
