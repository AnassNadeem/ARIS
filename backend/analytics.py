"""Race analytics, circuit metadata, driver compare, and Open-Meteo forecast."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.cache import TTL_FORECAST, cached
from backend.calendar import circuit_key_for, get_calendar, get_round
from backend.http_client import get_json
from backend.models import (
    ArisCircuitNotes,
    CircuitCharacteristics,
    CircuitHistoryResponse,
    CircuitHistoryYear,
    CompareDriversResponse,
    DriverSeasonRace,
    DriverSeasonResponse,
    FastestLapEvolutionResponse,
    FastestLapPoint,
    ForecastResponse,
    GapHistoryResponse,
    GapLap,
    PitStopRow,
    PitStopsResponse,
    PositionHistoryResponse,
    PositionLap,
    TyreStrategyResponse,
    TyreStrategyStint,
)
from backend.sessions import session_laps, session_results, session_weather


def gap_history(year: int, round_number: int) -> GapHistoryResponse:
    laps = session_laps(year, round_number, "R").laps
    by_lap: dict[int, dict[str, int]] = {}
    for lap in laps:
        if lap.lap_time_ms is None:
            continue
        by_lap.setdefault(lap.lap_number, {})[lap.driver_code] = lap.lap_time_ms
    cum: dict[str, int] = {}
    out: list[GapLap] = []
    for n in sorted(by_lap):
        for code, ms in by_lap[n].items():
            cum[code] = cum.get(code, 0) + ms
        if not cum:
            continue
        leader = min(cum.values())
        gaps = {code: round((ms - leader) / 1000.0, 3) for code, ms in cum.items()}
        out.append(GapLap(lap=n, gaps=gaps))
    return GapHistoryResponse(year=year, round_number=round_number, laps=out)


def position_history(year: int, round_number: int) -> PositionHistoryResponse:
    gaps = gap_history(year, round_number)
    out: list[PositionLap] = []
    for row in gaps.laps:
        ranked = sorted(row.gaps.items(), key=lambda kv: kv[1])
        positions = {code: i + 1 for i, (code, _) in enumerate(ranked)}
        out.append(PositionLap(lap=row.lap, positions=positions))
    return PositionHistoryResponse(year=year, round_number=round_number, laps=out)


def tyre_strategy(year: int, round_number: int) -> TyreStrategyResponse:
    from backend.sessions import session_stints

    stints = session_stints(year, round_number, "R").stints
    rows = [
        TyreStrategyStint(
            driver_code=s.driver_code,
            lap_start=s.lap_start,
            lap_end=s.lap_end,
            compound=s.compound,
            fresh=s.fresh_tyre,
            tyre_life_at_end=s.total_laps,
        )
        for s in stints
    ]
    return TyreStrategyResponse(year=year, round_number=round_number, stints=rows)


def pit_stops(year: int, round_number: int) -> PitStopsResponse:
    laps = session_laps(year, round_number, "R").laps
    by_driver: dict[str, list] = {}
    for lap in sorted(laps, key=lambda r: (r.driver_code, r.lap_number)):
        by_driver.setdefault(lap.driver_code, []).append(lap)
    stops: list[PitStopRow] = []
    for code, rows in by_driver.items():
        for i, lap in enumerate(rows):
            if not lap.pit_in_lap:
                continue
            new_comp = None
            if i + 1 < len(rows):
                new_comp = rows[i + 1].compound
            stops.append(
                PitStopRow(
                    driver_code=code,
                    lap=lap.lap_number,
                    duration_ms=None,
                    new_compound=new_comp,
                )
            )
    return PitStopsResponse(year=year, round_number=round_number, stops=stops)


def fastest_lap_evolution(year: int, round_number: int) -> FastestLapEvolutionResponse:
    laps = session_laps(year, round_number, "R").laps
    best_ms: int | None = None
    points: list[FastestLapPoint] = []
    for lap in sorted(laps, key=lambda r: r.lap_number):
        if lap.lap_time_ms is None or lap.pit_in_lap or lap.pit_out_lap:
            continue
        if best_ms is None or lap.lap_time_ms < best_ms:
            best_ms = lap.lap_time_ms
            points.append(FastestLapPoint(lap=lap.lap_number, driver=lap.driver_code, time_ms=lap.lap_time_ms))
    return FastestLapEvolutionResponse(year=year, round_number=round_number, points=points)


def driver_season(driver_code: str, year: int) -> DriverSeasonResponse:
    cal = get_calendar(year)
    code = driver_code.upper()
    races: list[DriverSeasonRace] = []
    finishes: list[int] = []
    dnf = 0
    wins = 0
    poles = 0
    fl = 0
    tyre_usage: dict[str, int] = {}
    for rnd in cal.rounds:
        if rnd.status == "CANCELLED":
            continue
        if rnd.status == "UPCOMING":
            continue
        try:
            results = session_results(year, rnd.round_number, "R").results
            quali = session_results(year, rnd.round_number, "Q").results
        except Exception:
            continue
        row = next((r for r in results if r.driver_code == code), None)
        qrow = next((r for r in quali if r.driver_code == code), None)
        finish = row.position if row else None
        qpos = qrow.position if qrow else None
        is_dnf = bool(row and row.status and "finish" not in row.status.lower() and row.status not in {"+1 Lap", "+2 Laps"})
        if is_dnf:
            dnf += 1
        if finish:
            finishes.append(finish)
        if finish == 1:
            wins += 1
        if qpos == 1:
            poles += 1
        if row and row.fastest_lap:
            fl += 1
        avg = None
        try:
            laps = session_laps(year, rnd.round_number, "R").laps
            mine = [l.lap_time_ms for l in laps if l.driver_code == code and l.lap_time_ms]
            avg = sum(mine) / len(mine) if mine else None
            for l in laps:
                if l.driver_code == code and l.compound:
                    tyre_usage[l.compound] = tyre_usage.get(l.compound, 0) + 1
        except Exception:
            pass
        races.append(
            DriverSeasonRace(
                round_number=rnd.round_number,
                name=rnd.name,
                finish_position=finish,
                qualifying_position=qpos,
                fastest_lap=bool(row and row.fastest_lap),
                dnf=is_dnf,
                points=row.points if row else None,
                avg_lap_ms=avg,
            )
        )
    avg_finish = sum(finishes) / len(finishes) if finishes else None
    return DriverSeasonResponse(
        driver_code=code,
        year=year,
        races=races,
        average_finish=avg_finish,
        dnf_count=dnf,
        wins=wins,
        poles=poles,
        fastest_laps=fl,
        tyre_usage=tyre_usage,
    )


def _yaml_stem_match(circuit_key: str) -> Any:
    from aris.tracks import load_track_config

    return load_track_config(circuit_key)


def _aris_notes_from_cfg(cfg: Any, circuit_key: str) -> ArisCircuitNotes:
    pit = float(cfg.pit_loss_s or 21.0)
    if pit <= 17:
        undercut = "Strong undercut — pit loss is short, so boxing a lap early usually pays."
    elif pit <= 20:
        undercut = "Average undercut — a clean stop can jump a rival within ~1.5s, not much more."
    else:
        undercut = "Weak undercut — long pit loss means overcut or equal-length stints are usually better."
    slopes = {str(k).upper(): float(v) for k, v in (cfg.compound_slopes or {}).items()}
    soft = slopes.get("SOFT")
    med = slopes.get("MEDIUM")
    hard = slopes.get("HARD")
    if soft and med and hard:
        tyre = (
            f"Deg slopes {soft:.3f}/{med:.3f}/{hard:.3f} s/lap (S/M/H). "
            "Softer compounds fall off sooner; plan the first stop around the cliff, not the window midpoint."
        )
    elif slopes:
        tyre = "Compound deg is track-specific; expect the softer tyre to be the limiter on long stints."
    else:
        tyre = "No fitted deg slopes — treat this as a medium-deg circuit until practice data arrives."
    turns = len(cfg.corners) if cfg.corners else 0
    if turns >= 16:
        overtake = "Overtaking is difficult — high corner count, track position matters more than raw pace."
    elif turns >= 10:
        overtake = "Overtaking is mixed — DRS and a tyre offset can make a pass stick, but not everywhere."
    else:
        overtake = "Overtaking is more open — long straights reward a tyre or DRS offset."
    hist = circuit_history(circuit_key)
    sc_bits = [n for y in hist.years for n in (y.incident_notes or [])]
    if sc_bits:
        sc = f"Safety-car history: {'; '.join(sc_bits[:4])}."
    else:
        sc = "No classified SC notes in recent years — treat SC as a low-probability swing factor."
    summary = f"{undercut} {tyre} {overtake} {sc}"
    return ArisCircuitNotes(
        undercut_effectiveness=undercut,
        tyre_compound_tendencies=tyre,
        overtaking_difficulty=overtake,
        sc_probability_history=sc,
        summary=summary,
    )


def circuit_characteristics(circuit_key: str, year: int | None = None) -> CircuitCharacteristics:
    cfg = _yaml_stem_match(circuit_key)
    turns = len(cfg.corners) if cfg.corners else None
    length_km = (cfg.lap_length_m / 1000.0) if cfg.lap_length_m else None
    deg = {k: float(v) for k, v in (cfg.compound_slopes or {}).items()}
    estimated = cfg.lap_length_m is None and not cfg.corners
    radii = [getattr(c, "radius_m", None) for c in (cfg.corners or [])]
    tight = [r for r in radii if r is not None and r < 60]
    if turns and turns >= 14 and len(tight) >= 6:
        tyre_stress = "HIGH"
    elif turns and turns >= 10:
        tyre_stress = "MEDIUM"
    else:
        tyre_stress = "LOW"
    evo = "HIGH" if (cfg.compound_slopes or {}) else "MEDIUM"
    notes = _aris_notes_from_cfg(cfg, circuit_key)
    sectors: list[str] = []
    if cfg.corners:
        n = len(cfg.corners)
        sectors = [
            f"S1: opening {max(1, n // 3)} corners, set the lap.",
            f"S2: mid-lap {max(1, n // 3)} corners, tyre energy.",
            f"S3: final {max(1, n - 2 * (n // 3))} corners onto the straight.",
        ]
    key = circuit_key.lower().replace(" ", "").replace("_", "").replace("-", "")
    drs_known = {
        "netherlands": 2,
        "zandvoort": 2,
        "dutch": 2,
        "bahrain": 3,
        "monaco": 1,
        "monza": 2,
        "italy": 2,
    }
    drs_zones = getattr(cfg, "drs_zones", None) or drs_known.get(key)
    return CircuitCharacteristics(
        circuit_key=circuit_key,
        name=cfg.name,
        country=cfg.country,
        lap_length_km=round(length_km, 3) if length_km else None,
        turns=turns,
        drs_zones=drs_zones,
        pit_loss_seconds=cfg.pit_loss_s,
        total_laps=cfg.total_laps,
        tyre_stress_rating=tyre_stress,
        track_evolution_rating=evo,
        sector_descriptions=sectors,
        similar_circuits=[],
        corner_types=[],
        known_deg_compounds=deg,
        aris_notes=notes,
        estimated=estimated,
        reg_note_2026=year == 2026 if year else False,
    )


def circuit_history(circuit_key: str) -> CircuitHistoryResponse:
    years_out: list[CircuitHistoryYear] = []
    stems = {circuit_key}
    try:
        from aris.tracks import _match_track_file

        path = _match_track_file(circuit_key)
        if path is not None:
            stems.add(path.stem)
    except Exception:
        pass
    for year in (2024, 2025, 2026):
        cal = get_calendar(year)
        match = next((r for r in cal.rounds if r.circuit_key in stems), None)
        if match is None:
            needle = circuit_key.replace("_", "").replace("-", "").lower()
            match = next(
                (
                    r
                    for r in cal.rounds
                    if needle in (r.circuit_key + r.name + r.city).lower().replace(" ", "").replace("_", "")
                ),
                None,
            )
        if match is None or match.status not in {"COMPLETED", "LIVE"}:
            continue
        winner = pole = fl = team = weather = None
        try:
            results = session_results(year, match.round_number, "R").results
            if results:
                winner = results[0].driver_code
                team = results[0].team
                fl_row = next((r for r in results if r.fastest_lap), None)
                fl = fl_row.driver_code if fl_row else None
            quali = session_results(year, match.round_number, "Q").results
            if quali:
                pole = quali[0].driver_code
        except Exception:
            pass
        try:
            wx = session_weather(year, match.round_number, "R")
            if wx.rainfall and any(wx.rainfall):
                weather = "Wet"
            elif wx.track_temp and any(t is not None for t in wx.track_temp):
                temps = [t for t in wx.track_temp if t is not None]
                weather = f"Dry · {sum(temps) / len(temps):.0f}°C track" if temps else "Dry"
        except Exception:
            weather = None
        years_out.append(
            CircuitHistoryYear(
                year=year,
                winner=winner,
                winner_team=team,
                pole=pole,
                fastest_lap=fl,
                weather=weather,
                incident_notes=match.notes,
            )
        )
    return CircuitHistoryResponse(circuit_key=circuit_key, years=years_out)


def compare_drivers(
    driver_a: str, driver_b: str, year: int, round_number: int | None = None
) -> CompareDriversResponse:
    a, b = driver_a.upper(), driver_b.upper()
    q_a = q_b = r_a = r_b = 0
    lap_deltas: list[float] = []
    s1: list[float] = []
    s2: list[float] = []
    s3: list[float] = []
    rounds = [round_number] if round_number else [r.round_number for r in get_calendar(year).rounds if r.status == "COMPLETED"]
    for rnd in rounds:
        try:
            quali = session_results(year, rnd, "Q").results
            race = session_results(year, rnd, "R").results
        except Exception:
            continue
        qa = next((x for x in quali if x.driver_code == a), None)
        qb = next((x for x in quali if x.driver_code == b), None)
        ra = next((x for x in race if x.driver_code == a), None)
        rb = next((x for x in race if x.driver_code == b), None)
        if qa and qb and qa.position and qb.position:
            if qa.position < qb.position:
                q_a += 1
            elif qb.position < qa.position:
                q_b += 1
        if ra and rb and ra.position and rb.position:
            if ra.position < rb.position:
                r_a += 1
            elif rb.position < ra.position:
                r_b += 1
        try:
            laps = session_laps(year, rnd, "R").laps
        except Exception:
            continue
        by_lap: dict[int, dict[str, Any]] = {}
        for lap in laps:
            by_lap.setdefault(lap.lap_number, {})[lap.driver_code] = lap
        for pair in by_lap.values():
            la, lb = pair.get(a), pair.get(b)
            if not la or not lb:
                continue
            if la.lap_time_ms and lb.lap_time_ms:
                lap_deltas.append(la.lap_time_ms - lb.lap_time_ms)
            if la.sector1_ms and lb.sector1_ms:
                s1.append(la.sector1_ms - lb.sector1_ms)
            if la.sector2_ms and lb.sector2_ms:
                s2.append(la.sector2_ms - lb.sector2_ms)
            if la.sector3_ms and lb.sector3_ms:
                s3.append(la.sector3_ms - lb.sector3_ms)
    mean = lambda xs: sum(xs) / len(xs) if xs else None

    def _median(xs: list[float]) -> float | None:
        if not xs:
            return None
        s = sorted(xs)
        mid = len(s) // 2
        return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2

    fl_a = fl_b = None
    try:
        if round_number:
            laps_one = session_laps(year, round_number, "R").laps
            a_times = [l.lap_time_ms for l in laps_one if l.driver_code == a and l.lap_time_ms]
            b_times = [l.lap_time_ms for l in laps_one if l.driver_code == b and l.lap_time_ms]
            fl_a = min(a_times) if a_times else None
            fl_b = min(b_times) if b_times else None
    except Exception:
        pass
    return CompareDriversResponse(
        driver_a=a,
        driver_b=b,
        year=year,
        round_number=round_number,
        quali_wins_a=q_a,
        quali_wins_b=q_b,
        race_wins_a=r_a,
        race_wins_b=r_b,
        avg_lap_delta_ms=mean(lap_deltas),
        sector1_delta_ms=mean(s1),
        sector2_delta_ms=mean(s2),
        sector3_delta_ms=mean(s3),
        race_pace_median_delta_ms=_median(lap_deltas),
        fastest_lap_a_ms=fl_a,
        fastest_lap_b_ms=fl_b,
    )


_COORDS = {
    "netherlands": (52.3888, 4.5409),
    "zandvoort": (52.3888, 4.5409),
    "bahrain": (26.0325, 50.5106),
    "australia": (-37.8497, 144.968),
    "japan": (34.8431, 136.541),
    "china": (31.3389, 121.22),
    "miami": (25.9581, -80.2389),
    "imola": (44.3439, 11.7167),
    "monaco": (43.7347, 7.4206),
    "spain": (41.57, 2.2611),
    "canada": (45.5, -73.5228),
    "austria": (47.2197, 14.7647),
    "britain": (52.0786, -1.0169),
    "belgium": (50.4372, 5.9714),
    "hungary": (47.5789, 19.2486),
    "italy": (45.6156, 9.2811),
    "azerbaijan": (40.3725, 49.8533),
    "singapore": (1.2914, 103.864),
    "usa": (30.1328, -97.6411),
    "mexico": (19.4042, -99.0907),
    "brazil": (-23.7036, -46.6997),
    "las_vegas": (36.1147, -115.173),
    "qatar": (25.49, 51.4542),
    "abu_dhabi": (24.4672, 54.6031),
    "saudi_arabia": (21.6319, 39.1044),
}


def forecast(circuit_key: str) -> ForecastResponse:
    latlon = _COORDS.get(circuit_key.lower())
    if latlon is None:
        for key, val in _COORDS.items():
            if key in circuit_key.lower() or circuit_key.lower() in key:
                latlon = val
                break
    if latlon is None:
        return ForecastResponse(circuit_key=circuit_key, source="unavailable")
    lat, lon = latlon

    def _fetch() -> dict[str, Any]:
        return get_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,precipitation_probability,wind_speed_10m",
            },
        )

    try:
        data = cached(f"forecast:{circuit_key}", TTL_FORECAST, _fetch)
        cur = data.get("current") or {}
        return ForecastResponse(
            circuit_key=circuit_key,
            source="open-meteo",
            temperature_c=_float(cur.get("temperature_2m")),
            precipitation_probability=_float(cur.get("precipitation_probability")),
            wind_speed_kmh=_float(cur.get("wind_speed_10m")),
            as_of=datetime.now(timezone.utc),
        )
    except Exception:
        return ForecastResponse(circuit_key=circuit_key, source="unavailable")


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
