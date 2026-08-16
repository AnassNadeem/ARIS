"""Pirelli C-code compound identity — distinct from FastF1 SOFT/MEDIUM/HARD.

FastF1 ``Compound`` is event-relative (the white/yellow/red nomination). The
true C1–C6 identity is not in the timing feed; this module joins a sourced
(year, event) mapping onto that relative label.

Eras (physical compounds are not comparable across these cuts):
  2019-2021  13-inch C1–C5
  2022       18-inch first generation (2022 C1 was renamed C0 in 2023)
  2023-2025  18-inch after the C0 reclassification; C6 added in 2025
  2026       range recalibrated for lower-downforce cars; C1–C5 only
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from aris.physics.tires import DEFAULT_COMPOUND_SLOPE, normalize_compound

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NOMINATIONS_PATH = _REPO_ROOT / "data" / "compounds" / "nominations.json"
_SLOPES_PATH = _REPO_ROOT / "data" / "compounds" / "true_compound_slopes.json"
_ISOTONIC_SLOPES_PATH = _REPO_ROOT / "data" / "compounds" / "true_compound_slopes_isotonic.json"
_POOLED_SLOPES_PATH = _REPO_ROOT / "data" / "compounds" / "true_compound_slopes_pooled.json"

# Opt-in overlay for simulate()/recommend()/Strategy UI. Default is off:
# shipped path is G1.5 global fallback slopes + G1.4 physics-delta.
TRUE_COMPOUND_SLOPES_ENV = "ARIS_TRUE_COMPOUND_SLOPES"
TRUE_COMPOUND_MODES = ("off", "unconstrained", "isotonic", "pooled")

DRY_RELATIVE = frozenset({"SOFT", "MEDIUM", "HARD"})
WET_RELATIVE = frozenset({"INTERMEDIATE", "WET"})
C_CODES = ("C0", "C1", "C2", "C3", "C4", "C5", "C6")

# Extra needles → canonical JSON ``event`` name. Track YAML aliases are also
# tried at lookup time via aris.tracks when available.
_EVENT_ALIASES: dict[str, str] = {
    "netherlands": "Netherlands",
    "zandvoort": "Netherlands",
    "dutch": "Netherlands",
    "bahrain": "Bahrain",
    "sakhir": "Bahrain",
    "saudiarabia": "Saudi Arabia",
    "saudi": "Saudi Arabia",
    "jeddah": "Saudi Arabia",
    "australia": "Australia",
    "melbourne": "Australia",
    "albertpark": "Australia",
    "japan": "Japan",
    "suzuka": "Japan",
    "china": "China",
    "shanghai": "China",
    "chinese": "China",
    "miami": "Miami",
    "emiliaromagna": "Emilia Romagna",
    "imola": "Emilia Romagna",
    "monaco": "Monaco",
    "montecarlo": "Monaco",
    "canada": "Canada",
    "montreal": "Canada",
    "montréal": "Canada",
    "spain": "Spain",
    "barcelona": "Spain",
    "catalunya": "Spain",
    "barcelonacatalunya": "Spain",
    "madrid": "Madrid",
    "madring": "Madrid",
    "austria": "Austria",
    "spielberg": "Austria",
    "redbullring": "Austria",
    "britain": "Britain",
    "greatbritain": "Britain",
    "silverstone": "Britain",
    "british": "Britain",
    "hungary": "Hungary",
    "budapest": "Hungary",
    "hungaroring": "Hungary",
    "belgium": "Belgium",
    "spa": "Belgium",
    "spafrancorchamps": "Belgium",
    "italy": "Italy",
    "monza": "Italy",
    "italian": "Italy",
    "azerbaijan": "Azerbaijan",
    "baku": "Azerbaijan",
    "singapore": "Singapore",
    "marinabay": "Singapore",
    "unitedstates": "United States",
    "usa": "United States",
    "austin": "United States",
    "cota": "United States",
    "us": "United States",
    "mexicocity": "Mexico City",
    "mexico": "Mexico City",
    "saopaulo": "Sao Paulo",
    "brazil": "Sao Paulo",
    "interlagos": "Sao Paulo",
    "lasvegas": "Las Vegas",
    "vegas": "Las Vegas",
    "qatar": "Qatar",
    "lusail": "Qatar",
    "abudhabi": "Abu Dhabi",
    "yasisland": "Abu Dhabi",
    "yasmarina": "Abu Dhabi",
    "france": "France",
    "paulricard": "France",
    "portugal": "Portugal",
    "portimao": "Portugal",
    "russia": "Russia",
    "sochi": "Russia",
    "turkey": "Turkey",
    "istanbul": "Turkey",
    "styria": "Styria",
    "tuscany": "Tuscany",
    "mugello": "Tuscany",
    "70thanniversary": "70th Anniversary",
    "eifel": "Eifel",
    "nurburgring": "Eifel",
}


def _norm(value: str | None) -> str:
    if not value:
        return ""
    return (
        str(value)
        .lower()
        .replace("grand prix", "")
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("'", "")
        .replace(".", "")
    )


def compound_era(year: int) -> str:
    if year >= 2026:
        return "2026"
    if year >= 2023:
        return "2023-2025"
    if year == 2022:
        return "2022"
    if 2019 <= year <= 2021:
        return "2019-2021"
    return "unknown"


@dataclass(frozen=True)
class CompoundNomination:
    year: int
    round: int | None
    event: str
    hard: str
    medium: str
    soft: str
    era: str
    source_url: str

    def c_code_for(self, relative: str) -> str | None:
        key = normalize_compound(relative)
        if key == "HARD":
            return self.hard
        if key == "MEDIUM":
            return self.medium
        if key == "SOFT":
            return self.soft
        return None

    def as_relative_map(self) -> dict[str, str]:
        return {"HARD": self.hard, "MEDIUM": self.medium, "SOFT": self.soft}


@lru_cache(maxsize=1)
def _load_doc() -> dict[str, Any]:
    if not _NOMINATIONS_PATH.exists():
        return {"nominations": [], "unmapped": [], "eras": {}}
    return json.loads(_NOMINATIONS_PATH.read_text(encoding="utf-8"))


def all_nominations() -> list[CompoundNomination]:
    out: list[CompoundNomination] = []
    for raw in _load_doc().get("nominations", []):
        out.append(
            CompoundNomination(
                year=int(raw["year"]),
                round=int(raw["round"]) if raw.get("round") is not None else None,
                event=str(raw["event"]),
                hard=str(raw["hard"]).upper(),
                medium=str(raw["medium"]).upper(),
                soft=str(raw["soft"]).upper(),
                era=str(raw.get("era") or compound_era(int(raw["year"]))),
                source_url=str(raw.get("source_url") or ""),
            )
        )
    return out


def unmapped_races() -> list[dict[str, Any]]:
    return list(_load_doc().get("unmapped", []))


def _canonical_event(event: str | None) -> str:
    token = _norm(event)
    if not token:
        return ""
    if token in _EVENT_ALIASES:
        return _EVENT_ALIASES[token]
    # Prefix / contains match for "Dutch Grand Prix" etc.
    for needle, canon in _EVENT_ALIASES.items():
        if len(needle) >= 4 and needle in token:
            return canon
    return str(event or "").strip()


def lookup_nomination(
    year: int,
    event: str | None = None,
    *,
    round_no: int | None = None,
) -> CompoundNomination | None:
    """Return the sourced nomination, or None if this race is genuinely unmapped."""
    rows = [n for n in all_nominations() if n.year == int(year)]
    if not rows:
        return None

    if round_no is not None:
        by_round = [n for n in rows if n.round == int(round_no)]
        if len(by_round) == 1:
            return by_round[0]
        if len(by_round) > 1 and event:
            canon = _canonical_event(event)
            hit = [n for n in by_round if _norm(n.event) == _norm(canon) or n.event == canon]
            if hit:
                return hit[0]
        if by_round:
            return by_round[0]

    if not event:
        return None
    canon = _canonical_event(event)
    hits = [
        n
        for n in rows
        if _norm(n.event) == _norm(canon) or _canonical_event(n.event) == canon
    ]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        logger.warning(
            "compound identity ambiguous year=%s event=%s round=%s matches=%s — leaving unmapped",
            year,
            event,
            round_no,
            [h.event for h in hits],
        )
        return None
    return None


def compound_identity(
    relative: str | None,
    year: int,
    event: str | None = None,
    *,
    round_no: int | None = None,
) -> str:
    """True C-code for a dry relative label, else the normalized relative label.

    INTERMEDIATE/WET/UNKNOWN stay as themselves. Unmapped dry races stay
    SOFT/MEDIUM/HARD — the engine still has the event-relative name.
    """
    rel = normalize_compound(relative)
    if rel in WET_RELATIVE or rel not in DRY_RELATIVE:
        return rel
    nom = lookup_nomination(year, event, round_no=round_no)
    if nom is None:
        return rel
    code = nom.c_code_for(rel)
    return code or rel


def join_compound_identity(
    frame: Any,
    *,
    year: int,
    event: str | None = None,
    round_no: int | None = None,
    compound_col: str = "Compound",
    out_col: str = "CompoundIdentity",
) -> Any:
    """Add ``CompoundIdentity`` next to the event-relative Compound column."""
    import pandas as pd

    work = frame.copy()
    nom = lookup_nomination(year, event, round_no=round_no)
    rel = work[compound_col].map(normalize_compound)
    if nom is None:
        work[out_col] = rel
        return work
    mapping = nom.as_relative_map()
    work[out_col] = rel.map(lambda c: mapping.get(c, c))
    return work


def parse_true_compound_mode(raw: str | bool | None = None) -> str:
    """Map env/arg to ``off`` | ``unconstrained`` | ``isotonic`` | ``pooled``. Unknown → off."""
    if raw is True:
        return "unconstrained"
    if raw is False:
        return "off"
    if raw is None:
        raw = os.getenv(TRUE_COMPOUND_SLOPES_ENV, "")
    token = str(raw).strip().lower()
    if token in ("", "0", "off", "false", "no"):
        return "off"
    if token in ("1", "true", "yes", "on", "unconstrained", "g2"):
        return "unconstrained"
    if token in ("isotonic", "constrained", "g3"):
        return "isotonic"
    if token in ("pooled", "g4", "context", "gbt"):
        return "pooled"
    logger.warning(
        "unknown %s=%r — treating as off (shipped G1.5 slopes)",
        TRUE_COMPOUND_SLOPES_ENV,
        raw,
    )
    return "off"


def true_compound_overlay_enabled(raw: str | bool | None = None) -> bool:
    return parse_true_compound_mode(raw) != "off"


def _slopes_path_for_mode(mode: str) -> Path:
    if mode == "isotonic":
        return _ISOTONIC_SLOPES_PATH
    if mode == "pooled":
        return _POOLED_SLOPES_PATH
    return _SLOPES_PATH


@lru_cache(maxsize=4)
def load_true_compound_slopes(mode: str = "unconstrained") -> dict[str, dict[str, float]]:
    """era -> {C-code: slope s/lap}. Missing file → empty (callers fall back)."""
    path = _slopes_path_for_mode(mode)
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    eras = doc.get("eras") or {}
    out: dict[str, dict[str, float]] = {}
    for era, payload in eras.items():
        slopes = payload.get("slopes") if isinstance(payload, dict) else payload
        if not isinstance(slopes, dict):
            continue
        out[str(era)] = {str(k).upper(): float(v) for k, v in slopes.items() if v is not None}
    return out


def pooled_event_key(year: int, event: str | None, round_no: int | None = None) -> str:
    nom = lookup_nomination(year, event, round_no=round_no)
    if nom is not None:
        rnd = nom.round if nom.round is not None else round_no
        return f"{nom.year}|{nom.event}|{rnd}"
    return f"{year}|{event}|{round_no}"


@lru_cache(maxsize=1)
def load_pooled_event_slopes() -> dict[str, dict[str, float]]:
    """``year|event|round`` -> {SOFT,MEDIUM,HARD} slopes from the G4 event table."""
    if not _POOLED_SLOPES_PATH.exists():
        return {}
    doc = json.loads(_POOLED_SLOPES_PATH.read_text(encoding="utf-8"))
    events = doc.get("events") or {}
    out: dict[str, dict[str, float]] = {}
    for key, payload in events.items():
        if not isinstance(payload, dict):
            continue
        slopes = payload.get("slopes") if "slopes" in payload else payload
        if not isinstance(slopes, dict):
            continue
        rel = {
            str(k).upper(): float(v)
            for k, v in slopes.items()
            if k is not None and str(k).upper() in DRY_RELATIVE and v is not None
        }
        if rel:
            out[str(key)] = rel
    return out


def event_relative_slopes(
    year: int,
    event: str | None = None,
    *,
    round_no: int | None = None,
    mode: str | bool | None = "unconstrained",
) -> tuple[dict[str, float] | None, dict[str, Any]]:
    """SOFT/MEDIUM/HARD slopes from true-compound fits for this race.

    Returns ``(slopes, meta)``. ``slopes`` is None when the race is unmapped or
    the true-compound fit is missing — callers keep YAML / global defaults.

    This helper always computes the overlay when asked. The shipped
    ``load_track_config`` path only calls it when ``ARIS_TRUE_COMPOUND_SLOPES``
    is an explicit opt-in (see ``parse_true_compound_mode``).
    """
    resolved = parse_true_compound_mode(mode if mode is not True else "unconstrained")
    if resolved == "off":
        resolved = "unconstrained"
    nom = lookup_nomination(year, event, round_no=round_no)
    meta: dict[str, Any] = {
        "year": year,
        "event": event,
        "round_no": round_no,
        "mapped": nom is not None,
        "source": "global_fallback",
        "mode": resolved,
    }
    if nom is None:
        logger.info(
            "compound identity UNMAPPED year=%s event=%s round=%s — using global/YAML defaults",
            year,
            event,
            round_no,
        )
        meta["reason"] = "unmapped"
        return None, meta

    if resolved == "pooled":
        event_key = pooled_event_key(year, event, round_no)
        event_slopes = load_pooled_event_slopes().get(event_key)
        if event_slopes and all(k in event_slopes for k in ("HARD", "MEDIUM", "SOFT")):
            meta.update(
                {
                    "nomination_event": nom.event,
                    "hard": nom.hard,
                    "medium": nom.medium,
                    "soft": nom.soft,
                    "era": nom.era,
                    "source_url": nom.source_url,
                    "source": "true_compound_pooled_event",
                    "slopes": event_slopes,
                    "event_key": event_key,
                }
            )
            return event_slopes, meta

    meta.update(
        {
            "nomination_event": nom.event,
            "hard": nom.hard,
            "medium": nom.medium,
            "soft": nom.soft,
            "era": nom.era,
            "source_url": nom.source_url,
        }
    )
    fitted = load_true_compound_slopes(resolved).get(nom.era) or {}
    slopes: dict[str, float] = {}
    missing: list[str] = []
    for rel, code in (("HARD", nom.hard), ("MEDIUM", nom.medium), ("SOFT", nom.soft)):
        if code in fitted:
            slopes[rel] = float(fitted[code])
        else:
            missing.append(f"{rel}={code}")
            slopes[rel] = float(DEFAULT_COMPOUND_SLOPE[rel])
    if missing:
        logger.info(
            "compound identity mapped year=%s %s H/M/S=%s/%s/%s but missing true-compound "
            "slopes for %s (era=%s) — those keys use DEFAULT_COMPOUND_SLOPE",
            year,
            nom.event,
            nom.hard,
            nom.medium,
            nom.soft,
            missing,
            nom.era,
        )
        meta["source"] = "mapped_partial_default"
        meta["missing_codes"] = missing
        # If *all* three fell back, treat as no overlay so YAML stays authoritative.
        if len(missing) == 3 and not fitted:
            meta["reason"] = "mapped_but_no_fit"
            return None, meta
        return slopes, meta

    logger.info(
        "compound identity mapped year=%s %s H/M/S=%s/%s/%s era=%s slopes=%s",
        year,
        nom.event,
        nom.hard,
        nom.medium,
        nom.soft,
        nom.era,
        slopes,
    )
    meta["source"] = (
        "true_compound_pooled_era"
        if resolved == "pooled"
        else ("true_compound_isotonic" if resolved == "isotonic" else "true_compound")
    )
    meta["slopes"] = slopes
    return slopes, meta


HARDNESS_ORDER = ("C1", "C2", "C3", "C4", "C5", "C6")


def _pava_increasing(
    values: list[float],
    weights: list[float],
) -> list[float]:
    """Weighted pool-adjacent-violators, non-decreasing.

    Blocks are (sum_wy, sum_w). Adjacent blocks are merged while the left
    mean exceeds the right mean, then expanded back to the original length.
    """
    if not values:
        return []
    blocks: list[list[float]] = []  # [sum_wy, sum_w, n]
    for y, w in zip(values, weights, strict=True):
        ww = float(w) if float(w) > 0 else 1.0
        blocks.append([float(y) * ww, ww, 1.0])
        while len(blocks) >= 2:
            left, right = blocks[-2], blocks[-1]
            left_mean = left[0] / left[1]
            right_mean = right[0] / right[1]
            if left_mean <= right_mean + 1e-15:
                break
            merged = [left[0] + right[0], left[1] + right[1], left[2] + right[2]]
            blocks[-2:] = [merged]
    out: list[float] = []
    for sum_wy, sum_w, n in blocks:
        mean = sum_wy / sum_w
        out.extend([mean] * int(n))
    return out


def constrain_slopes_isotonic(
    unconstrained: dict[str, float],
    weights: dict[str, float] | None = None,
    *,
    order: tuple[str, ...] = HARDNESS_ORDER,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Enforce C1 <= C2 <= ... (degradation non-decreasing toward softer).

    Returns ``(constrained_slopes, pair_notes)``. ``pair_notes`` records, for
    each adjacent pair in ``order`` that is present, whether the constraint
    compressed them to equal values (data could not distinguish) or had to
    pull an inverted unconstrained pair back into order.
    """
    present = [c for c in order if c in unconstrained and unconstrained[c] is not None]
    if len(present) < 2:
        return dict(unconstrained), []
    y = [float(unconstrained[c]) for c in present]
    w = [float((weights or {}).get(c, 1.0)) for c in present]
    y_hat = _pava_increasing(y, w)
    constrained = dict(unconstrained)
    for code, val in zip(present, y_hat, strict=True):
        constrained[code] = round(float(val), 4)

    notes: list[dict[str, Any]] = []
    for a, b in zip(present, present[1:], strict=False):
        u_a, u_b = float(unconstrained[a]), float(unconstrained[b])
        c_a, c_b = float(constrained[a]), float(constrained[b])
        inverted = u_a > u_b + 1e-9
        pooled = abs(c_a - c_b) <= 1e-9
        changed = abs(c_a - u_a) > 1e-6 or abs(c_b - u_b) > 1e-6
        if inverted and pooled:
            kind = "inverted_compressed_to_equal"
        elif inverted and changed:
            kind = "inverted_materially_changed"
        elif pooled and changed:
            kind = "compressed_to_equal"
        elif inverted:
            kind = "inverted_unchanged"  # should not happen
        else:
            kind = "unchanged"
        notes.append(
            {
                "pair": f"{a}<={b}",
                "unconstrained": {a: round(u_a, 4), b: round(u_b, 4)},
                "constrained": {a: round(c_a, 4), b: round(c_b, 4)},
                "inverted": inverted,
                "pooled_equal": pooled,
                "kind": kind,
            }
        )
    return constrained, notes


def clear_compound_caches() -> None:
    _load_doc.cache_clear()
    load_true_compound_slopes.cache_clear()
    load_pooled_event_slopes.cache_clear()
