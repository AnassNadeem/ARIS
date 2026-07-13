"""FastF1 session loading with Streamlit caching."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CACHE_DIR = _REPO_ROOT / "fastf1_cache"

# 2025 F1 grid — hardcoded for driver selector
DRIVERS_2025: list[dict] = [
    {"number": 1, "code": "VER", "name": "Max Verstappen", "team": "Red Bull Racing", "color": "#3671C6", "badge": "WDC x4"},
    {"number": 11, "code": "PER", "name": "Sergio Pérez", "team": "Red Bull Racing", "color": "#3671C6", "badge": ""},
    {"number": 16, "code": "LEC", "name": "Charles Leclerc", "team": "Ferrari", "color": "#E8002D", "badge": ""},
    {"number": 55, "code": "SAI", "name": "Carlos Sainz", "team": "Ferrari", "color": "#E8002D", "badge": ""},
    {"number": 44, "code": "HAM", "name": "Lewis Hamilton", "team": "Mercedes", "color": "#27F4D2", "badge": "WDC x7"},
    {"number": 63, "code": "RUS", "name": "George Russell", "team": "Mercedes", "color": "#27F4D2", "badge": ""},
    {"number": 4, "code": "NOR", "name": "Lando Norris", "team": "McLaren", "color": "#FF8000", "badge": ""},
    {"number": 81, "code": "PIA", "name": "Oscar Piastri", "team": "McLaren", "color": "#FF8000", "badge": ""},
    {"number": 14, "code": "ALO", "name": "Fernando Alonso", "team": "Aston Martin", "color": "#229971", "badge": "WDC x2"},
    {"number": 18, "code": "STR", "name": "Lance Stroll", "team": "Aston Martin", "color": "#229971", "badge": ""},
    {"number": 10, "code": "GAS", "name": "Pierre Gasly", "team": "Alpine", "color": "#FF87BC", "badge": ""},
    {"number": 31, "code": "OCO", "name": "Esteban Ocon", "team": "Alpine", "color": "#FF87BC", "badge": ""},
    {"number": 23, "code": "ALB", "name": "Alexander Albon", "team": "Williams", "color": "#64C4FF", "badge": ""},
    {"number": 2, "code": "SAR", "name": "Logan Sargeant", "team": "Williams", "color": "#64C4FF", "badge": ""},
    {"number": 22, "code": "TSU", "name": "Yuki Tsunoda", "team": "RB", "color": "#6692FF", "badge": ""},
    {"number": 3, "code": "RIC", "name": "Daniel Ricciardo", "team": "RB", "color": "#6692FF", "badge": ""},
    {"number": 77, "code": "BOT", "name": "Valtteri Bottas", "team": "Kick Sauber", "color": "#52E252", "badge": ""},
    {"number": 24, "code": "ZHO", "name": "Zhou Guanyu", "team": "Kick Sauber", "color": "#52E252", "badge": ""},
    {"number": 20, "code": "MAG", "name": "Kevin Magnussen", "team": "Haas", "color": "#B6BABD", "badge": ""},
    {"number": 27, "code": "HUL", "name": "Nico Hülkenberg", "team": "Haas", "color": "#B6BABD", "badge": ""},
]

# Weather tags per race (round -> condition)
WEATHER_LOOKUP: dict[int, str] = {
    1: "Dry", 2: "Dry", 3: "Mixed", 4: "Dry", 5: "Dry",
    6: "Wet", 7: "Dry", 8: "Dry", 9: "Dry", 10: "Mixed",
    11: "Dry", 12: "Dry", 13: "Dry", 14: "Wet", 15: "Dry",
    16: "Dry", 17: "Dry", 18: "Dry", 19: "Dry", 20: "Dry",
    21: "Dry", 22: "Dry", 23: "Dry", 24: "Dry",
}

FLAG_EMOJI: dict[str, str] = {
    "bahrain": "🇧🇭", "saudi": "🇸🇦", "australia": "🇦🇺", "japan": "🇯🇵",
    "china": "🇨🇳", "miami": "🇺🇸", "imola": "🇮🇹", "monaco": "🇲🇨",
    "canada": "🇨🇦", "spain": "🇪🇸", "austria": "🇦🇹", "britain": "🇬🇧",
    "hungary": "🇭🇺", "belgium": "🇧🇪", "netherlands": "🇳🇱", "italy": "🇮🇹",
    "azerbaijan": "🇦🇿", "singapore": "🇸🇬", "united states": "🇺🇸",
    "mexico": "🇲🇽", "brazil": "🇧🇷", "las vegas": "🇺🇸", "qatar": "🇶🇦",
    "abu dhabi": "🇦🇪",
}


def _enable_cache() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    import fastf1

    fastf1.Cache.enable_cache(str(_CACHE_DIR))


@st.cache_data(show_spinner=False, ttl=3600)
def get_event_schedule(year: int) -> pd.DataFrame:
    _enable_cache()
    import fastf1

    schedule = fastf1.get_event_schedule(year)
    rows = []
    for _, ev in schedule.iterrows():
        rnd = int(ev["RoundNumber"])
        country = str(ev.get("Country", ev.get("Location", "")))
        name = str(ev.get("EventName", ev.get("OfficialEventName", country)))
        date = str(ev.get("EventDate", ""))[:10]
        weather = WEATHER_LOOKUP.get(rnd, "Dry")
        flag = FLAG_EMOJI.get(country.lower(), "🏁")
        rows.append({
            "round": rnd,
            "country": country,
            "name": name,
            "date": date,
            "weather": weather,
            "flag": flag,
            "event_name": str(ev.get("EventName", "")),
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner="Loading FastF1 session…", ttl=3600)
def load_race_session(year: int, event: int | str) -> dict:
    """Load race session and return serialisable summary + laps DataFrame."""
    _enable_cache()
    import fastf1

    session = fastf1.get_session(year, event, "R")
    session.load(laps=True, telemetry=False, weather=True, messages=False)

    laps_df = session.laps
    if laps_df is None or laps_df.empty:
        return {"ok": False, "error": "No lap data", "session": None, "laps": pd.DataFrame()}

    records = []
    for _, lap in laps_df.iterrows():
        drv = lap.get("Driver")
        if drv is None:
            continue
        records.append({
            "driver": str(drv),
            "lap_number": int(lap["LapNumber"]),
            "lap_time_s": float(lap["LapTime"].total_seconds()) if pd.notna(lap.get("LapTime")) else None,
            "compound": str(lap.get("Compound", "MEDIUM")).upper() if pd.notna(lap.get("Compound")) else "MEDIUM",
            "tyre_life": int(lap["TyreLife"]) if pd.notna(lap.get("TyreLife")) else 1,
            "sector_1_s": float(lap["Sector1Time"].total_seconds()) if pd.notna(lap.get("Sector1Time")) else None,
            "sector_2_s": float(lap["Sector2Time"].total_seconds()) if pd.notna(lap.get("Sector2Time")) else None,
            "sector_3_s": float(lap["Sector3Time"].total_seconds()) if pd.notna(lap.get("Sector3Time")) else None,
            "pit_in": bool(lap.get("PitInTime") is not None and pd.notna(lap.get("PitInTime"))),
            "pit_out": bool(lap.get("PitOutTime") is not None and pd.notna(lap.get("PitOutTime"))),
            "track_status": str(lap.get("TrackStatus", "")),
        })

    laps_out = pd.DataFrame(records)

    weather_data = getattr(session, "weather_data", None)
    weather_summary: dict = {}
    if weather_data is not None and not weather_data.empty:
        last = weather_data.iloc[-1]
        weather_summary = {
            "track_temp_c": float(last.get("TrackTemp", 38)),
            "air_temp_c": float(last.get("AirTemp", 28)),
            "humidity_pct": float(last.get("Humidity", 22)),
            "wind_speed": float(last.get("WindSpeed", 8)),
            "rainfall": bool(last.get("Rainfall", False)),
        }
        weather_summary["track_temps"] = weather_data["TrackTemp"].tolist() if "TrackTemp" in weather_data.columns else []

    results = session.results
    driver_info: dict[str, dict] = {}
    if results is not None and not results.empty:
        for _, r in results.iterrows():
            code = str(r.get("Abbreviation", r.get("DriverNumber", "")))
            driver_info[code] = {
                "code": code,
                "full_name": str(r.get("FullName", r.get("BroadcastName", code))),
                "team": str(r.get("TeamName", "")),
                "position": int(r["Position"]) if pd.notna(r.get("Position")) else None,
            }

    total_laps = int(laps_df["LapNumber"].max()) if not laps_df.empty else 57

    return {
        "ok": True,
        "error": None,
        "year": year,
        "event": event,
        "total_laps": total_laps,
        "weather": weather_summary,
        "drivers": driver_info,
        "laps": laps_out,
        "event_name": str(session.event.get("EventName", "")),
        "country": str(session.event.get("Country", "")),
    }


def check_session_available(year: int, event: int | str) -> tuple[bool, str]:
    try:
        result = load_race_session(year, event)
        if result["ok"]:
            return True, "ready"
        return False, result.get("error", "unavailable")
    except Exception as exc:
        return False, str(exc)[:60]


def get_driver_laps(laps_df: pd.DataFrame, driver_code: str) -> pd.DataFrame:
    return laps_df[laps_df["driver"] == driver_code].sort_values("lap_number").copy()


def format_lap_time(seconds: float | None) -> str:
    if seconds is None or pd.isna(seconds):
        return "—"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:06.3f}" if m > 0 else f"{s:.3f}"
