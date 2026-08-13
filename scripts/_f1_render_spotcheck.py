"""F1.3 — engine recommend() → gold callout / caveat strip, two real races.

Traces one recommendation end-to-end without Streamlit, using the same
formatters the panel renders.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.io import db
from aris.plan.weekend_form import weekend_form, weekend_session_types
from aris.recommend import recommend
from aris.state import build_race_state
from aris.ui_text import (
    format_callout_delta,
    recommendation_caveat,
    weekend_form_empty_message,
)


def _race(year: int, country_substr: str) -> dict:
    races = db.fetch_races(year)
    hit = races[races["country"].astype(str).str.lower().str.contains(country_substr.lower())]
    if hit.empty:
        raise RuntimeError(f"no {country_substr} race for {year}")
    row = hit.iloc[0]
    return {
        "session_id": int(row["session_id"]),
        "year": year,
        "round_no": int(row["round_no"]),
        "country": str(row["country"]),
    }


def _ver(session_id: int) -> tuple[int, str]:
    drivers = db.fetch_drivers(session_id)
    hit = drivers[drivers["code"] == "VER"]
    drv = hit.iloc[0] if not hit.empty else drivers.iloc[0]
    return int(drv["driver_id"]), str(drv["code"])


def _trace(title: str, session_id: int, driver_id: str, driver_code: str, lap: int) -> dict:
    state = build_race_state(session_id, driver_id, lap)
    recs = recommend(state, top_k=3, mc_draws=15)
    top = recs.recommendations[0]
    headline = top.label
    escaped_headline = html.escape(headline)
    delta_raw = top.delta_vs_stay_out_s
    delta_text = format_callout_delta(delta_raw)
    caveat = recommendation_caveat(top.narration_context, top.evidence or "")
    caveat_html = f"Note: {html.escape(caveat)}" if caveat else None

    print(f"\n=== {title} ===", flush=True)
    print(
        f"state L{state.lap_number} {state.compound} tyre_life={state.tyre_life} "
        f"caveat={state.confidence_caveat!r}",
        flush=True,
    )
    print(f"recommend() rank1 label = {top.label!r}", flush=True)
    print(f"recommend() rank1 delta_vs_stay_out_s = {delta_raw!r}", flush=True)
    print(f"recommend() rank1 evidence (tail) = {top.evidence[-180:]!r}", flush=True)
    print(f"callout headline (raw)     = {headline!r}", flush=True)
    print(f"callout headline (escaped) = {escaped_headline!r}", flush=True)
    print(f"callout delta text         = {delta_text!r}", flush=True)
    print(f"caveat strip               = {caveat_html!r}", flush=True)
    print(
        "others: " + "; ".join(r.label for r in recs.recommendations),
        flush=True,
    )

    issues: list[str] = []
    if headline != top.label:
        issues.append("headline != engine label")
    if escaped_headline != html.escape(top.label):
        issues.append("escape mutated label unexpectedly")
    if "..." in headline or headline.endswith("…"):
        issues.append("headline looks truncated")
    rendered_num = float(delta_text.split("s")[0].replace("+", ""))
    # .1f rounding of the engine float — must be that rounding, not a different number.
    expected_1f = float(f"{delta_raw:.1f}")
    if abs(rendered_num - expected_1f) > 1e-9:
        issues.append(f"delta text {rendered_num} != .1f of engine {delta_raw}")
    if state.confidence_caveat:
        if caveat != state.confidence_caveat:
            issues.append(
                f"caveat mismatch engine={state.confidence_caveat!r} rendered={caveat!r}"
            )
        ctx_c = (top.narration_context or {}).get("confidence_caveat")
        if ctx_c != state.confidence_caveat:
            issues.append("narration_context caveat != RaceState.confidence_caveat")
    else:
        if caveat:
            issues.append(f"rendered caveat but state had none: {caveat!r}")
    hardcoded = ("TODO", "FIXME", "lorem", "placeholder", "Pit now for HARD — example")
    blob = f"{headline} {delta_text} {caveat or ''}".lower()
    for h in hardcoded:
        if h.lower() in blob:
            issues.append(f"hardcoded/stale copy marker {h!r}")
    if issues:
        print("ISSUES: " + "; ".join(issues), flush=True)
    else:
        print("RENDER MATCH - engine label/delta/caveat -> callout text.", flush=True)
    return {"issues": issues, "label": headline, "delta_text": delta_text, "caveat": caveat}


def main() -> int:
    print("=== F1.3 rendered-value spot check ===", flush=True)
    failed = False

    nl = _race(2025, "nether")
    nl_id, nl_code = _ver(nl["session_id"])
    forms = weekend_form(nl["year"], nl["round_no"])
    types = weekend_session_types(nl["year"], nl["round_no"])
    print(
        f"\n[2025 Zandvoort] session={nl['session_id']} {nl_code} "
        f"weekend_form n={len(forms)} types={types}",
        flush=True,
    )
    r1 = _trace("2025 Zandvoort / VER / L25", nl["session_id"], nl_id, nl_code, 25)

    bh = _race(2024, "bahrain")
    bh_id, bh_code = _ver(bh["session_id"])
    forms_b = weekend_form(bh["year"], bh["round_no"])
    types_b = weekend_session_types(bh["year"], bh["round_no"])
    empty_msg = weekend_form_empty_message(types_b)
    print(
        f"\n[2024 Bahrain] session={bh['session_id']} {bh_code} "
        f"weekend_form n={len(forms_b)} types={types_b}",
        flush=True,
    )
    print(f"weekend-form-blank copy: {empty_msg!r}", flush=True)
    if forms_b:
        print("WARN: expected race-only blank weekend form for 2024 Bahrain", flush=True)
    r2 = _trace("2024 Bahrain / VER / L20 (race-only weekend)", bh["session_id"], bh_id, bh_code, 20)

    if r1["issues"] or r2["issues"]:
        failed = True
    print("\nF1.3 " + ("FAIL" if failed else "OK"), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
