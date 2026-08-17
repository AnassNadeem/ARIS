"""Grounded Ask ARIS — retrieve, cite, do not invent numbers.

Replaces keyword matching in keyword_qa.py. Same contract as narrate.py:
numbers in the answer are copied from retrieved sources.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from aris.ask.memory import ConversationMemory
from aris.ask.retrieve import DEFAULT_TOP_K, MIN_COSINE, AskDocument, AskIndex, Hit
from aris.ask.sources import (
    DEFAULT_INDEX_DIR,
    SHIPPED_TRUE_COMPOUND_MODE,
    build_index,
    is_shipped_model_config,
    json_number,
    session_documents,
)
from aris.engine.session import RaceEngineSession

ABSTAIN = (
    "No relevant source retrieved for that question. I won't guess — "
    "ask about a logged decision, a classified result in session_results, "
    "or a strategy concept in the knowledge base."
)

_DRIVER_RE = re.compile(r"\b([A-Za-z]{3})\b")
_LAP_RE = re.compile(r"\blap\s+(\d+)\b", re.I)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_ROUND_RE = re.compile(r"\bround\s+(\d+)\b", re.I)
_ANAPHORA_RE = re.compile(
    r"\b(that call|that recommendation|that one|on that call|the delta on that)\b",
    re.I,
)
_KNOWN_DRIVER_CODES = frozenset(
    {
        "VER", "PER", "SAI", "LEC", "RUS", "NOR", "HAM", "PIA", "ALO", "GAS",
        "STR", "RIC", "TSU", "ALB", "ZHO", "BOT", "OCO", "MAG", "HUL", "SAR",
        "COL", "BEA", "ANT", "HAD", "LAW", "DOO", "DEV", "MSC", "KVY", "RAI",
        "GIO", "LAT", "MAZ", "VET", "GRO", "ERI", "VAN", "NAS", "BOR",
    }
)


def answer_question(
    session: RaceEngineSession | None,
    question: str,
    *,
    use_llm: bool = False,
    memory: ConversationMemory | None = None,
    index: AskIndex | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    """Grounded answer from retrieved sources only.

    ``use_llm`` is accepted for call-site compatibility. Generation is extractive
    so cited numbers cannot drift from the record (same contract as narrate.py
    fallback). An LLM may only wrap those copied facts later; it is not used here.
    """
    del use_llm  # extractive path only — numbers come from retrieved facts
    if _ANAPHORA_RE.search(question) and not (memory and (memory.last_decision_docs or memory.turns)):
        return ABSTAIN
    store = index or _default_index()
    query = memory.query_with_context(question) if memory else question
    ephemeral = _ephemeral_docs(session, memory)
    hits = _search(store, query, extra=ephemeral, k=top_k)
    hits = _apply_constraints(query, hits)
    hits = _prefer_shipped_model(hits)
    usable = [h for h in hits if h.cosine >= MIN_COSINE or h.doc.source in {"session", "memory"}]
    if not usable:
        return ABSTAIN
    if memory:
        memory.remember_decision_hits([h.doc for h in usable])
    return _compose(question, usable)


def _ephemeral_docs(
    session: RaceEngineSession | None,
    memory: ConversationMemory | None,
) -> list[AskDocument]:
    docs: list[AskDocument] = []
    if session is not None:
        docs.extend(session_documents(session))
    if memory is not None:
        docs.extend(memory.memory_documents())
    return docs


def _search(
    store: AskIndex,
    query: str,
    *,
    extra: list[AskDocument],
    k: int,
) -> list[Hit]:
    if not extra:
        return store.search(query, k=k)
    merged = AskIndex.from_documents([*store.documents, *extra])
    return merged.search(query, k=k)


def _query_constraints(question: str) -> dict[str, Any]:
    q = question.strip()
    lap_m = _LAP_RE.search(q)
    year_m = _YEAR_RE.search(q)
    round_m = _ROUND_RE.search(q)
    drivers = [
        m.group(1).upper()
        for m in _DRIVER_RE.finditer(q)
        if m.group(1).upper() in _KNOWN_DRIVER_CODES
    ]
    return {
        "lap": int(lap_m.group(1)) if lap_m else None,
        "year": int(year_m.group(1)) if year_m else None,
        "round_no": int(round_m.group(1)) if round_m else None,
        "drivers": drivers,
        "q_lower": q.lower(),
    }


def _apply_constraints(question: str, hits: list[Hit]) -> list[Hit]:
    cons = _query_constraints(question)
    q_lower = cons["q_lower"]
    if (
        cons["lap"] is None
        and not cons["drivers"]
        and cons["year"] is None
        and cons["round_no"] is None
    ):
        return hits
    countries_in_q = {
        str(h.doc.facts.get("country") or "").lower()
        for h in hits
        if str(h.doc.facts.get("country") or "")
        and str(h.doc.facts.get("country") or "").lower() in q_lower
    }
    filtered: list[Hit] = []
    for hit in hits:
        facts = hit.doc.facts
        country = str(facts.get("country") or "").lower()
        if hit.doc.source in {"decision", "race", "memory"}:
            if cons["year"] is not None and facts.get("year") not in (None, cons["year"]):
                continue
            if cons["round_no"] is not None and facts.get("round_no") not in (None, cons["round_no"]):
                continue
            if cons["drivers"] and facts.get("driver_code") and str(facts.get("driver_code")).upper() not in cons["drivers"]:
                continue
            if countries_in_q and country and country not in countries_in_q:
                continue
        if hit.doc.source == "decision":
            if cons["lap"] is not None and facts.get("lap") != cons["lap"]:
                continue
        elif hit.doc.source == "race":
            if cons["lap"] is not None:
                if not any(tok in q_lower for tok in ("finish", "grid", "classified", "points", "result")):
                    continue
        filtered.append(hit)
    return filtered


def _prefer_shipped_model(hits: list[Hit]) -> list[Hit]:
    """When overlay and G1.5 copies of the same lap both retrieve, keep G1.5.

    Does not invent a winner among untagged same-config re-runs. Overlay
    modes are the rejected G2/G3/G4 experiments; shipped is ``off``.
    """
    decision_hits = [h for h in hits if h.doc.source == "decision"]
    if not decision_hits:
        return hits
    shipped = [
        h
        for h in decision_hits
        if is_shipped_model_config(
            str(h.doc.facts.get("true_compound_slopes") or SHIPPED_TRUE_COMPOUND_MODE)
        )
    ]
    overlay = [h for h in decision_hits if h not in shipped]
    if not (shipped and overlay):
        return hits
    keep = {id(h) for h in shipped}
    return [h for h in hits if h.doc.source != "decision" or id(h) in keep]


def _compose(question: str, hits: list[Hit]) -> str:
    q = question.lower()
    primary = hits[0].doc
    lines: list[str] = []
    if primary.source == "decision":
        lines.append(_decision_answer(primary))
    elif primary.source in {"race", "memory"} and primary.facts.get("delta_vs_stay_out_s") is not None:
        lines.append(_decision_answer(primary))
    elif primary.source == "race":
        lines.append(_race_answer(primary))
    elif primary.source == "session":
        lines.append(_session_answer(primary))
    else:
        lines.append(_concept_answer(primary))

    extra_concepts = [h.doc for h in hits[1:] if h.doc.source == "concept"]
    if extra_concepts and primary.source != "concept" and any(
        tok in q for tok in ("undercut", "overcut", "safety car", "vsc", "why", "how")
    ):
        lines.append(extra_concepts[0].text.split("Source:")[0].strip())

    lines.append("")
    lines.append("Cited:")
    seen: set[str] = set()
    for hit in hits:
        cite = hit.doc.citation
        if cite in seen:
            continue
        seen.add(cite)
        lines.append(f"- {cite}")
        if len(seen) >= 3:
            break
    return "\n".join(lines)


def _decision_answer(doc: AskDocument) -> str:
    f = doc.facts
    parts = [
        f"ARIS logged {f.get('event')} for {f.get('driver_code')} at {f.get('year')} "
        f"{f.get('country')} round {f.get('round_no')} lap {f.get('lap')}: {f.get('label')}.",
        f"delta_vs_stay_out_s={json_number(f.get('delta_vs_stay_out_s'))}",
        f"mean_race_time_s={json_number(f.get('mean_race_time_s'))}",
    ]
    if f.get("pit_compound") is not None:
        parts.append(f"pit_compound={json_number(f.get('pit_compound'))}")
    if f.get("pit_lap") is not None:
        parts.append(f"pit_lap={json_number(f.get('pit_lap'))}")
    if f.get("confidence_std_s") is not None:
        parts.append(f"confidence_std_s={json_number(f.get('confidence_std_s'))}")
    return " ".join(parts)


def _race_answer(doc: AskDocument) -> str:
    f = doc.facts
    if "match_rate" in f:
        return (
            f"2024 walk-forward: match_rate={json_number(f.get('match_rate'))} "
            f"({f.get('n_match')}/{f.get('n_scored')}); "
            f"always_stay_out_rate={json_number(f.get('always_stay_out_rate'))} "
            f"({f.get('always_stay_out_n')}/{f.get('always_stay_out_d')}); "
            f"mean_position_delta={json_number(f.get('mean_position_delta'))}."
        )
    return (
        f"Classified result {f.get('year')} round {f.get('round_no')} {f.get('country')} "
        f"{f.get('driver_code')}: grid_pos={json_number(f.get('grid_pos'))} "
        f"finish_pos={json_number(f.get('finish_pos'))} "
        f"points={json_number(f.get('points'))} "
        f"pit_in_count={json_number(f.get('pit_in_count'))}."
    )


def _session_answer(doc: AskDocument) -> str:
    f = doc.facts
    return (
        f"Current snapshot {f.get('driver_code')} lap {f.get('lap')}: "
        f"compound={json_number(f.get('compound'))} tyre_life={json_number(f.get('tyre_life'))} "
        f"position={json_number(f.get('position'))} "
        f"gap_to_leader_s={json_number(f.get('gap_to_leader_s'))} "
        f"gap_ahead_s={json_number(f.get('gap_ahead_s'))}."
    )


def _concept_answer(doc: AskDocument) -> str:
    body = doc.text
    if "Source:" in body:
        body = body.split("Source:")[0].strip()
    return body


@lru_cache(maxsize=1)
def _default_index() -> AskIndex:
    meta = DEFAULT_INDEX_DIR / "meta.json"
    if meta.exists():
        return AskIndex.load(DEFAULT_INDEX_DIR)
    return build_index()
