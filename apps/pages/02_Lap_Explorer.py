"""ARIS — F1 lap-time explorer."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

try:
    if "ARIS_DB_URL" in st.secrets:
        os.environ.setdefault("ARIS_DB_URL", st.secrets["ARIS_DB_URL"])
except (FileNotFoundError, KeyError):
    pass

from apps.theme import empty_state, inject_theme, render_disclaimer, show_technical  # noqa: E402
from aris.io import db  # noqa: E402

inject_theme()

st.markdown('<div class="aris-kicker">Telemetry</div>', unsafe_allow_html=True)
st.title("Lap-time explorer")
st.caption("Pick a season, race, and driver. This is the historical trace — strategy lives on the Strategy page.")

seasons = db.fetch_seasons()
if not seasons:
    empty_state(
        "No sessions ingested yet",
        "Run <code>python scripts/ingest_season.py 2024</code> against Postgres, then refresh.",
    )
    render_disclaimer()
    st.stop()

col_season, col_race, col_driver = st.columns(3)

with col_season:
    season = st.selectbox("Season", seasons)

races = db.fetch_races(season).set_index("session_id")
if races.empty:
    empty_state(
        f"No races ingested for {season}",
        f"Run <code>python scripts/ingest_season.py {season}</code>.",
    )
    render_disclaimer()
    st.stop()

with col_race:
    session_id = st.selectbox(
        "Race",
        races.index.tolist(),
        format_func=lambda sid: f"R{races.at[sid, 'round_no']} — {races.at[sid, 'country']}",
    )

drivers = db.fetch_drivers(session_id).set_index("driver_id")
if drivers.empty:
    empty_state(
        "No laps ingested for this race",
        "Try another round, or re-run the ingest.",
    )
    render_disclaimer()
    st.stop()


def _driver_label(did: int) -> str:
    code = drivers.at[did, "code"]
    full_name = drivers.at[did, "full_name"]
    team = drivers.at[did, "team"]
    base = f"{code} — {full_name}"
    return f"{base} ({team})" if pd.notna(team) and team else base


with col_driver:
    driver_id = st.selectbox("Driver", drivers.index.tolist(), format_func=_driver_label)

laps = db.fetch_laps(session_id, driver_id)
timed = laps.dropna(subset=["lap_time_s"]).copy()
timed["lap_time_s"] = timed["lap_time_s"].astype(float)

if timed.empty:
    empty_state("No timed laps", "This driver has no timed laps in this race.")
    render_disclaimer()
    st.stop()

chart_df = timed.rename(columns={"lap_number": "Lap", "lap_time_s": "Lap time (s)"})
lap_chart = (
    alt.Chart(chart_df)
    .mark_line(color="#E10600", strokeWidth=2)
    .encode(
        x=alt.X("Lap:Q", title="Lap"),
        y=alt.Y("Lap time (s):Q", title="Lap time (s)"),
        tooltip=["Lap", alt.Tooltip("Lap time (s):Q", format=".3f")],
    )
    .properties(height=280)
)
st.altair_chart(lap_chart, use_container_width=True)

st.subheader("Sector breakdown")
sectors = db.fetch_lap_sectors(session_id, driver_id)
sectors_long = sectors.melt(
    id_vars="lap_number",
    value_vars=["sector_1_s", "sector_2_s", "sector_3_s"],
    var_name="sector",
    value_name="seconds",
).dropna(subset=["seconds"])

if sectors_long.empty:
    empty_state("No sector times", "No sector times recorded for this driver in this race.")
else:
    area = (
        alt.Chart(sectors_long)
        .mark_area()
        .encode(
            x=alt.X("lap_number:Q", title="Lap"),
            y=alt.Y("seconds:Q", stack="zero", title="Sector time (s)"),
            color=alt.Color(
                "sector:N",
                title="Sector",
                scale=alt.Scale(
                    domain=["sector_1_s", "sector_2_s", "sector_3_s"],
                    range=["#4C78A8", "#F58518", "#54A24B"],
                ),
                legend=alt.Legend(labelExpr="'S' + replace(datum.label, /sector_(\\d)_s/, '$1')"),
            ),
            tooltip=["lap_number", "sector", alt.Tooltip("seconds:Q", format=".3f")],
        )
    )
    median_total = alt.Chart(
        pd.DataFrame({"y": [timed["lap_time_s"].median()]})
    ).mark_rule(strokeDash=[4, 4], color="#8B93A1").encode(y="y:Q")
    st.altair_chart(area + median_total, use_container_width=True)
    st.caption(
        "S1 + S2 + S3 = lap time. The dashed line is this driver's median lap time."
    )

mae_s, n_scored = db.fetch_driver_ma2_mae(session_id, driver_id)
if show_technical():
    if mae_s is not None:
        st.caption(
            f"MA(2) baseline MAE for this driver/race: **{mae_s:.3f} s** "
            f"across {n_scored} scored laps — the moving-average floor a model must beat."
        )
    else:
        st.caption("Not enough clean laps to compute an MA(2) baseline for this driver.")

render_disclaimer()
