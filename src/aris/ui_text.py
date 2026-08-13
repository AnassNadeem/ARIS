"""Streamlit-free copy and formatting helpers for the ARIS dashboard."""

from __future__ import annotations

DISCLAIMER_SHORT = (
    "ARIS is unofficial and is not affiliated with, associated with, authorized "
    "by, or endorsed by Formula 1, the FIA, Formula One Group, or any Formula 1 "
    "team or rights holder."
)

DISCLAIMER_URL = "https://github.com/AnassNadeem/ARIS#readme"

# Locked numbers from docs/ZANDVOORT-2026-READINESS.md / docs/PHASE-E3-SUMMARY.md.
# Do not round a miss into a pass.
HEADLINE_CALENDAR_BLEND_MAE_S = 0.583
HEADLINE_CALENDAR_AIMED_S = 0.783
HEADLINE_CALENDAR_PASS = "23/24"
HEADLINE_NL_2024_MAE_S = 0.502
HEADLINE_NL_2024_AIMED_S = 0.640
HEADLINE_NL_2025_MAE_S = 0.566
HEADLINE_NL_2025_AIMED_S = 0.603
HEADLINE_CHINA_MAE_S = 0.596
HEADLINE_CHINA_AIMED_S = 0.563
HEADLINE_CHINA_MISS_S = 0.033

PREFERRED_DRIVER_CODES = ("VER", "NOR", "PIA", "LEC", "HAM", "RUS")


def format_race_clock(seconds: float) -> str:
    """Render a race-time total as h:mm:ss (or m:ss if under an hour)."""
    total = int(round(float(seconds)))
    if total < 0:
        sign = "-"
        total = abs(total)
    else:
        sign = ""
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{sign}{hours}:{minutes:02d}:{secs:02d}"
    return f"{sign}{minutes}:{secs:02d}"


def format_callout_delta(delta_vs_stay_out_s: float, *, suffix: str = " vs stay out") -> str:
    """Gold-callout delta line. Matches apps/components/recommend_panel.py."""
    sign = "+" if delta_vs_stay_out_s > 0 else ""
    return f"{sign}{delta_vs_stay_out_s:.1f}s{suffix}"


def recommendation_caveat(
    narration_context: dict | None = None,
    evidence: str = "",
) -> str | None:
    """Caveat strip copy. Prefers narration_context, then evidence 'caveat:'."""
    ctx = narration_context or {}
    raw = ctx.get("confidence_caveat") or None
    if raw:
        return str(raw)
    if evidence and "caveat:" in evidence.lower():
        return evidence.split("caveat:", 1)[-1].strip()
    return None


def weekend_form_empty_message(session_types: list[str] | None) -> str:
    """Friendly copy when weekend_form() is empty — never a blank panel."""
    types = {str(t).upper() for t in (session_types or []) if t}
    if not types:
        return (
            "Waiting for weekend data. No sessions are ingested for this round yet."
        )
    practice = {"FP1", "FP2", "FP3", "S", "SS", "SR"}
    quali = {"Q", "SQ", "SS"}
    if types <= {"R"}:
        return (
            "Waiting for FP1 data… Weekend form needs practice (FP1, or Sprint "
            "long runs) and preferably qualifying. Race-only ingest is not enough."
        )
    if not (types & practice):
        return (
            "Waiting for practice data… Qualifying is in, but FP1 / Sprint long "
            "runs have not been ingested yet."
        )
    if not (types & quali) and not (types & practice):
        return "Waiting for FP1 data…"
    return (
        "Waiting for weekend form… practice or qualifying is listed, but no "
        "timed laps were found to fill the table."
    )
