"""Load the three Ask ARIS retrieval sources.

1. Decision-record log (Phase G JSONL, real propose events)
2. Historical race summaries (session_results + pit_in counts — not narratives)
3. Strategy-concept reference docs (short, cited)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from aris.ask.retrieve import AskDocument, AskIndex

_REPO_ROOT = Path(__file__).resolve().parents[3]
CONCEPTS_DIR = _REPO_ROOT / "data" / "ask" / "concepts"
FIXTURES_DIR = _REPO_ROOT / "data" / "ask" / "fixtures"
DEFAULT_INDEX_DIR = _REPO_ROOT / "data" / "ask" / "index"
DEFAULT_DECISION_DIR = _REPO_ROOT / "results" / "decisions"
FIXTURE_DECISIONS_PATH = FIXTURES_DIR / "decisions.jsonl"
SHIPPED_TRUE_COMPOUND_MODE = "off"
# G2 appended overlay-walk proposes onto the same JSONL files as G1.5.
# Cutoff is G3.2's documented split (scripts/_g3_audit_decisions.py).
# Untagged records after this instant are overlay-window, not shipped G1.5.
_OVERLAY_WALK_START = datetime(2026, 8, 13, 20, 0, tzinfo=timezone.utc)

# 2024 walk-forward figures from docs/strategy-backtest.md (aimed vs actual there).
BACKTEST_2024 = {
    "year": 2024,
    "match_rate": 0.125,
    "n_match": 5,
    "n_scored": 40,
    "always_stay_out_rate": 0.250,
    "always_stay_out_n": 10,
    "always_stay_out_d": 40,
    "mean_position_delta": 2.58,
    "n_inflections": 61,
    "n_pit_inflections": 42,
    "n_sc_vsc_inflections": 19,
    "source": "docs/strategy-backtest.md",
}


def json_number(value: Any) -> str:
    """Canonical JSON number/string so answers can match records exactly."""
    return json.dumps(value)


def _decision_dirs() -> list[Path]:
    """Decision JSONL locations.

    ``ARIS_ASK_DECISION_DIRS`` is an exclusive override (pathsep-separated
    files or directories). Tests set it to the 14-event fixture so a live
    ``results/decisions/`` tree cannot leak in. Unset → live dir + fixture.
    """
    extra = os.getenv("ARIS_ASK_DECISION_DIRS")
    if extra:
        dirs = [Path(p.strip()) for p in extra.split(os.pathsep) if p.strip()]
    else:
        dirs = [DEFAULT_DECISION_DIR, FIXTURES_DIR]
    seen: set[Path] = set()
    out: list[Path] = []
    for path in dirs:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(path)
    return out


def _parse_record_ts(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def model_config_for_record(rec: dict[str, Any]) -> str:
    """Return the tyre-model config that produced this propose.

    Tagged records (``true_compound_slopes`` written at persist time) are
    authoritative. Untagged historical JSONL is *not* guessed by label or
    delta: G2/G3/G4 overlay walks appended onto the same files as G1.5, and
    the only recoverable signal is G3.2's documented timestamp split.
    """
    tagged = rec.get("true_compound_slopes")
    if tagged is not None and str(tagged).strip() != "":
        return str(tagged).strip().lower()
    ts = _parse_record_ts(rec.get("ts"))
    if ts is None:
        return "unknown"
    if ts >= _OVERLAY_WALK_START:
        return "unknown-overlay"
    return SHIPPED_TRUE_COMPOUND_MODE


def is_shipped_model_config(mode: str) -> bool:
    return mode == SHIPPED_TRUE_COMPOUND_MODE


def _include_overlay_decisions() -> bool:
    return os.getenv("ARIS_ASK_INCLUDE_OVERLAY_DECISIONS", "") == "1"


def load_decision_documents(
    *,
    propose_only: bool = True,
    include_overlay: bool | None = None,
) -> list[AskDocument]:
    """Index persisted JSONL decision records. Dedupes by event_id.

    Default: only G1.5-shipped proposes (``true_compound_slopes=off``, or
    untagged records from the pre-overlay walk window). Overlay-experiment
    walks stay out of Ask unless ``include_overlay=True`` or
    ``ARIS_ASK_INCLUDE_OVERLAY_DECISIONS=1``.
    """
    if include_overlay is None:
        include_overlay = _include_overlay_decisions()
    docs: list[AskDocument] = []
    seen: set[str] = set()
    files: list[Path] = []
    for directory in _decision_dirs():
        if directory.is_file() and directory.suffix == ".jsonl":
            files.append(directory)
            continue
        if not directory.is_dir():
            continue
        files.extend(sorted(directory.glob("*.jsonl")))
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            rec = json.loads(line)
            event_id = str(rec.get("event_id") or "")
            if not event_id or event_id in seen:
                continue
            if propose_only and rec.get("event") != "propose":
                continue
            mode = model_config_for_record(rec)
            if not include_overlay and not is_shipped_model_config(mode):
                continue
            rec.setdefault("_source_file", path.name)
            rec["true_compound_slopes"] = mode
            docs.append(decision_to_document(rec))
            seen.add(event_id)
    return docs


def decision_to_document(rec: dict[str, Any]) -> AskDocument:
    recd = rec.get("recommendation") or {}
    action = recd.get("action") or {}
    event_id = str(rec.get("event_id"))
    source_file = str(rec.get("_source_file") or rec.get("source_file") or "")
    facts = {
        "event": rec.get("event"),
        "event_id": event_id,
        "kind": rec.get("kind"),
        "year": rec.get("year"),
        "round_no": rec.get("round_no"),
        "country": rec.get("country"),
        "driver_code": rec.get("driver_code"),
        "lap": rec.get("lap"),
        "label": recd.get("label"),
        "delta_vs_stay_out_s": recd.get("delta_vs_stay_out_s"),
        "mean_race_time_s": recd.get("mean_race_time_s"),
        "confidence_std_s": recd.get("confidence_std_s"),
        "p10_delta_s": recd.get("p10_delta_s"),
        "p90_delta_s": recd.get("p90_delta_s"),
        "pit_compound": action.get("pit_compound"),
        "pit_lap": action.get("pit_lap"),
        "action_kind": action.get("kind"),
        "source_file": source_file,
        "accepted": rec.get("accepted"),
        "choice_id": rec.get("choice_id"),
        "true_compound_slopes": rec.get("true_compound_slopes")
        or model_config_for_record(rec),
    }
    text = (
        f"ARIS decision record event={rec.get('event')} kind={rec.get('kind')} "
        f"year={rec.get('year')} round {rec.get('round_no')} country={rec.get('country')} "
        f"driver {rec.get('driver_code')} lap {rec.get('lap')} "
        f"label {recd.get('label')} "
        f"delta_vs_stay_out_s {json_number(recd.get('delta_vs_stay_out_s'))} "
        f"mean_race_time_s {json_number(recd.get('mean_race_time_s'))} "
        f"confidence_std_s {json_number(recd.get('confidence_std_s'))} "
        f"pit_compound {action.get('pit_compound')} pit_lap {action.get('pit_lap')} "
        f"action_kind {action.get('kind')} source_file {source_file} "
        f"true_compound_slopes {facts['true_compound_slopes']}"
    )
    citation = (
        f"decision event_id={event_id} file={source_file} "
        f"{rec.get('year')} {rec.get('country')} {rec.get('driver_code')} lap {rec.get('lap')}"
    )
    title = (
        f"{rec.get('year')} {rec.get('country')} {rec.get('driver_code')} "
        f"L{rec.get('lap')} {recd.get('label')}"
    )
    return AskDocument(
        doc_id=f"decision:{event_id}",
        source="decision",
        title=title,
        text=text,
        citation=citation,
        facts=facts,
    )


def load_race_documents() -> list[AskDocument]:
    """Classified-result summaries from the real session_results dump (not invented)."""
    docs: list[AskDocument] = []
    path = FIXTURES_DIR / "races.json"
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            docs.append(_race_row_to_doc(row))
    docs.append(_backtest_2024_doc())
    return docs


def _race_row_to_doc(row: dict[str, Any]) -> AskDocument:
    year = row.get("year")
    round_no = row.get("round_no")
    country = row.get("country")
    code = row.get("driver_code")
    facts = {
        "year": year,
        "round_no": round_no,
        "country": country,
        "driver_code": code,
        "full_name": row.get("full_name"),
        "team": row.get("team"),
        "grid_pos": row.get("grid_pos"),
        "finish_pos": row.get("finish_pos"),
        "points": row.get("points"),
        "pit_in_count": row.get("pit_in_count"),
        "session_id": row.get("session_id"),
    }
    text = (
        f"Historical race classified result from session_results. "
        f"year={year} round {round_no} country={country} driver {code} "
        f"full_name={row.get('full_name')} team={row.get('team')} "
        f"grid_pos={json_number(row.get('grid_pos'))} "
        f"finish_pos={json_number(row.get('finish_pos'))} "
        f"points={json_number(row.get('points'))} "
        f"pit_in_count={json_number(row.get('pit_in_count'))}. "
        f"Not a race narrative; grid/finish/points/pit-in count only."
    )
    citation = (
        f"session_results year={year} round={round_no} country={country} "
        f"driver={code} session_id={row.get('session_id')}"
    )
    return AskDocument(
        doc_id=f"race:{year}:r{round_no}:{code}",
        source="race",
        title=f"{year} R{round_no} {country} {code}",
        text=text,
        citation=citation,
        facts=facts,
    )


def _backtest_2024_doc() -> AskDocument:
    b = BACKTEST_2024
    text = (
        "ARIS 2024 walk-forward strategy backtest summary from docs/strategy-backtest.md. "
        f"match_rate aimed > always-stay-out {json_number(b['always_stay_out_rate'])} "
        f"({b['always_stay_out_n']}/{b['always_stay_out_d']}); "
        f"actual match_rate {json_number(b['match_rate'])} "
        f"({b['n_match']}/{b['n_scored']}). "
        f"mean_position_delta aimed <= 0; actual {json_number(b['mean_position_delta'])}. "
        f"inflections {b['n_inflections']} (pit {b['n_pit_inflections']}, "
        f"SC/VSC {b['n_sc_vsc_inflections']}). "
        "This is the documented walk-forward result, not a race commentary."
    )
    return AskDocument(
        doc_id="race:backtest:2024",
        source="race",
        title="2024 walk-forward backtest summary",
        text=text,
        citation="docs/strategy-backtest.md 2024 walk-forward",
        facts=dict(b),
    )


def load_concept_documents() -> list[AskDocument]:
    docs: list[AskDocument] = []
    if not CONCEPTS_DIR.is_dir():
        return docs
    for path in sorted(CONCEPTS_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = _split_front_matter(raw)
        doc_id = str(meta.get("id") or path.stem)
        source_line = str(meta.get("source") or path.name)
        url = str(meta.get("url") or "")
        title = _first_heading(body) or path.stem
        text = f"{title}. {body.strip()} Source: {source_line} {url}".strip()
        docs.append(
            AskDocument(
                doc_id=f"concept:{doc_id}",
                source="concept",
                title=title,
                text=text,
                citation=f"concept {path.name} | {source_line}",
                facts={
                    "concept_id": doc_id,
                    "source": source_line,
                    "url": url,
                    "path": str(path.relative_to(_REPO_ROOT)).replace("\\", "/"),
                },
            )
        )
    return docs


def _split_front_matter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        meta[key.strip()] = val.strip()
    return meta, parts[2]


def _first_heading(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def session_documents(session: Any) -> list[AskDocument]:
    """Ephemeral live snapshot, cited as session_snapshot — not a persistent source."""
    try:
        state = session.build_state()
        gaps = session.gaps_for_driver() if hasattr(session, "gaps_for_driver") else {}
    except Exception:
        return []
    pits = []
    if getattr(session, "committed_pits", None):
        pits = [p.model_dump() if hasattr(p, "model_dump") else dict(p) for p in session.committed_pits]
    facts = {
        "driver_code": session.driver_code,
        "year": session.year,
        "round_no": session.round_no,
        "country": session.country,
        "lap": state.lap_number,
        "compound": state.compound,
        "tyre_life": state.tyre_life,
        "position": gaps.get("position"),
        "gap_to_leader_s": gaps.get("gap_to_leader_s"),
        "gap_ahead_s": gaps.get("gap_ahead_s"),
        "committed_pits": pits,
    }
    text = (
        f"Current session snapshot for driver {session.driver_code} "
        f"{session.year} {session.country} round {session.round_no} "
        f"lap {state.lap_number} compound {state.compound} tyre_life {state.tyre_life} "
        f"position {gaps.get('position')} gap_to_leader_s {json_number(gaps.get('gap_to_leader_s'))} "
        f"gap_ahead_s {json_number(gaps.get('gap_ahead_s'))} "
        f"committed_pits {json.dumps(pits, default=str)}"
    )
    return [
        AskDocument(
            doc_id="session:snapshot",
            source="session",
            title="Current session snapshot",
            text=text,
            citation=(
                f"session_snapshot {session.year} {session.country} "
                f"{session.driver_code} lap {state.lap_number}"
            ),
            facts=facts,
        )
    ]


def collect_documents(*, include_session: Any | None = None) -> list[AskDocument]:
    docs = load_decision_documents() + load_race_documents() + load_concept_documents()
    if include_session is not None:
        docs.extend(session_documents(include_session))
    return docs


def build_index(*, include_session: Any | None = None) -> AskIndex:
    return AskIndex.from_documents(collect_documents(include_session=include_session))


def save_index(index: AskIndex, directory: Path | None = None) -> Path:
    path = directory or DEFAULT_INDEX_DIR
    index.save(path)
    return path
