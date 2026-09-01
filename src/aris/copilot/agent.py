"""Copilot agent loop: rewrite → retrieve → plan tools → execute → respond."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from aris.copilot.context import CopilotContext, get_context, set_context
from aris.copilot.prompts import SYSTEM_PROMPT
from aris.copilot.retrieval import retrieve
from aris.copilot.schemas import TOOL_SCHEMAS
from aris.copilot.tools import execute_tool

_DRIVER_RE = re.compile(r"\b([A-Za-z]{3})\b")
_KNOWN_DRIVERS = frozenset(
    {
        "VER", "PER", "SAI", "LEC", "RUS", "NOR", "HAM", "PIA", "ALO", "GAS",
        "STR", "RIC", "TSU", "ALB", "ZHO", "BOT", "OCO", "MAG", "HUL", "SAR",
        "COL", "BEA", "ANT", "HAD", "LAW", "DOO", "DEV", "MSC", "ANT", "BOR",
    }
)
_COMPOUND_RE = re.compile(r"\b(SOFT|MEDIUM|HARD|INTERMEDIATE|INTER|WET)\b", re.I)
_PIT_NOW_RE = re.compile(r"\bpit now\b|\bbox now\b|\bif we pit\b", re.I)
_LEADER_RE = re.compile(r"\bwho(?:'s| is) (?:the )?lead(?:er|ing)\b", re.I)
_WON_RE = re.compile(r"\bwho won\b|\blast year\b|\bpodium\b|\bwinner\b", re.I)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_MD_HEADING_RE = re.compile(r"^#{1,6}\s+", re.M)
_MD_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$", re.M)
_WORD_LIMIT = 150


@dataclass
class CopilotResult:
    response: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    needs_approval: bool = False


def run_copilot(
    message: str,
    context: CopilotContext | None = None,
    *,
    use_llm: bool | None = None,
) -> CopilotResult:
    """One user message → retrieve, call ARIS tools, narrate. No race math in the LLM."""
    if context is not None:
        set_context(context)
    ctx = get_context()
    llm = ctx.use_llm if use_llm is None else bool(use_llm)
    question = (message or "").strip()
    skip_rag = _is_factual_query(question)
    chunks = [] if skip_rag else retrieve(question, k=10, top_n=5, use_llm_rewrite=llm)
    planned = plan_tools(question, chunks, use_llm=llm)
    executed: list[dict[str, Any]] = []
    tool_results: dict[str, Any] = {}
    for call in planned:
        result = execute_tool(call["name"], call.get("arguments") or {})
        executed.append({"name": call["name"], "arguments": call.get("arguments") or {}, "result": result})
        name = call["name"]
        if name in {"simulate", "get_driver_style"}:
            key = f"{name}_all"
            bucket = tool_results.setdefault(key, [])
            if isinstance(bucket, list):
                bucket.append(result)
        tool_results[name] = result
    recs = _extract_recommendations(tool_results)
    needs = _needs_approval(question, recs, tool_results)
    retrieved = [
        {
            "chunk_id": c.chunk_id,
            "source": c.source,
            "title": c.title,
            "section": c.section,
            "text": c.text[:400],
            "score": c.score,
        }
        for c in chunks
    ]
    answer = generate_response(
        question,
        tool_results=tool_results,
        chunks=retrieved,
        use_llm=llm,
    )
    if not _wants_long(question):
        answer = clip_words(answer, _WORD_LIMIT)
    return CopilotResult(
        response=answer,
        tool_calls=executed,
        retrieved_chunks=retrieved,
        recommendations=recs,
        needs_approval=needs,
    )


def _is_factual_query(question: str) -> bool:
    """Live/history facts go through tools, not retrieved docs."""
    q = (question or "").lower()
    if _LEADER_RE.search(question) or _WON_RE.search(question):
        return True
    if any(
        w in q
        for w in (
            "gap to",
            "who's in p",
            "who is in p",
            "tyre life",
            "tire life",
            "who's leading",
            "who is leading",
        )
    ) and "undercut" not in q and "recommend" not in q:
        return True
    return False


def plan_tools(
    question: str,
    chunks: list[Any] | None = None,
    *,
    use_llm: bool = False,
) -> list[dict[str, Any]]:
    del chunks  # retrieval is independent of tool planning
    if use_llm:
        llm_plan = _llm_plan(question)
        if llm_plan is not None:
            return llm_plan
    return _heuristic_plan(question)


def _heuristic_plan(question: str) -> list[dict[str, Any]]:
    q = question.lower()
    drivers = _drivers_in(question)
    compound = _compound_in(question)
    ctx = get_context()
    focus = (ctx.state.driver_code if ctx.state else None) or (drivers[0] if drivers else "VER")
    calls: list[dict[str, Any]] = []

    def add(name: str, **args: Any) -> None:
        payload = {k: v for k, v in args.items() if v is not None}
        if any(c["name"] == name and c.get("arguments") == payload for c in calls):
            return
        calls.append({"name": name, "arguments": payload})

    if _LEADER_RE.search(question):
        leader = ctx.car_at_position(1)
        add("get_gap", driver=(leader.driver_code if leader else focus))
    if _WON_RE.search(question):
        year_m = _YEAR_RE.search(question)
        add(
            "get_session_result",
            year=int(year_m.group(1)) if year_m else None,
            last_year="last year" in q or "last podium" in q,
            podium="podium" in q,
        )
    if any(w in q for w in ("undercut", "overcut window")):
        rival = next((d for d in drivers if d != focus.upper()), None) or (
            drivers[1] if len(drivers) > 1 else "NOR"
        )
        focus_code = drivers[0] if drivers else focus
        add("get_undercut_window", focus_driver=focus_code, rival_driver=rival, compound=compound)
    if any(w in q for w in ("best strategy", "recommend", "what should we", "from here", "top-3", "top 3")):
        add("recommend")
    if _PIT_NOW_RE.search(q) or "delta vs stay" in q or "cover" in q or "if we pit" in q:
        action = "PIT_NOW" if "stay" not in q.split("vs")[0] else "PIT_NOW"
        if "cover" in q:
            add("simulate", action="PIT_NOW", compound=compound or "HARD")
            add("simulate", action="STAY_OUT")
        else:
            add("simulate", action=action, compound=compound)
    if any(w in q for w in ("gap", "who's in p", "who is in p", "p3", "tyre life", "tire life", "position")):
        if "gap to" in q and drivers and "leader" not in q:
            named = drivers[0]
            if named != str(focus).upper():
                add("get_gap", driver=focus, vs_driver=named)
            else:
                add("get_gap", driver=named)
        else:
            target = drivers[0] if drivers else focus
            add("get_gap", driver=target)
    if any(w in q for w in ("deg slope", "degradation slope", "s/lap")):
        add("get_deg_slope", compound=compound or "HARD")
    if any(w in q for w in ("sc risk", "vsc risk", "safety car risk", "p(sc")):
        add("get_sc_risk")
    if any(w in q for w in ("wet", "damp", "rainfall", "intermediate", "track state")) and "two compound" not in q:
        add("get_wet_state")
    if any(w in q for w in ("monte carlo", "p(best)", "p10", "p90")) and "recommend" not in q:
        add(
            "run_mc_comparison",
            actions=[
                {"action": "PIT_NOW", "compound": compound or "HARD"},
                {"action": "STAY_OUT"},
            ],
        )
    if any(w in q for w in ("easy on", "tyre style", "tire style", "manage tyr", "compared to")):
        for code in drivers or ["HAM", "VER"]:
            add("get_driver_style", driver=code)
    if any(w in q for w in ("spa", "high-deg", "high deg", "circuit", "zandvoort", "monaco")):
        circuit = "spa" if "spa" in q else ("netherlands" if "zandvoort" in q else None)
        if circuit or "circuit" in q:
            add("get_circuit_info", circuit_id=circuit or "netherlands")
    if "lap 33" in q or re.search(r"\bwhat happened\b", q):
        add("recommend")
    return calls


def _llm_plan(question: str) -> list[dict[str, Any]] | None:
    try:
        from aris.narrate import call_llm_with_fallback
    except Exception:
        return None
    schema_txt = json.dumps(
        [{"name": s["name"], "parameters": s["parameters"]} for s in TOOL_SCHEMAS],
        indent=2,
    )
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "Choose zero or more ARIS tools to answer the user. "
        "Return ONLY a JSON list of {\"name\": ..., \"arguments\": {...}}. "
        "Do not invent numbers. RaceState is injected automatically.\n\n"
        f"Tools:\n{schema_txt}\n\nQuestion: {question}"
    )
    text = call_llm_with_fallback(prompt, fallback="")
    if not text:
        return None
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return None
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    out: list[dict[str, Any]] = []
    known = {s["name"] for s in TOOL_SCHEMAS}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if name not in known:
            continue
        args = item.get("arguments") or item.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        args.pop("state", None)
        args.pop("race_state", None)
        out.append({"name": name, "arguments": args})
    return out


def generate_response(
    question: str,
    *,
    tool_results: dict[str, Any],
    chunks: list[dict[str, Any]],
    use_llm: bool = False,
) -> str:
    template = _template_answer(question, tool_results, chunks)
    if not use_llm:
        return template
    try:
        from aris.narrate import call_llm_with_fallback
    except Exception:
        return template
    context_lines = [template]
    if tool_results:
        context_lines.append("Tool results JSON:\n" + json.dumps(tool_results, default=str)[:4000])
    if chunks:
        cites = "; ".join(f"{c.get('chunk_id')} ({c.get('title')})" for c in chunks[:3])
        context_lines.append("Retrieved: " + cites)
    wrapped = call_llm_with_fallback(
        question,
        context="\n".join(context_lines),
        fallback=template,
    )
    return wrapped or template


def _template_answer(
    question: str,
    tool_results: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    rec = tool_results.get("recommend")
    if isinstance(rec, dict) and rec.get("top_3"):
        bits = []
        for row in rec["top_3"][:3]:
            delta = row.get("delta_vs_stay_out_s")
            p_best = row.get("p_best")
            p_txt = f", P(best)={p_best:.2f}" if isinstance(p_best, (int, float)) else ""
            try:
                dtxt = f"{float(delta):+.1f}s vs stay"
            except (TypeError, ValueError):
                dtxt = "delta n/a"
            bits.append(f"{row.get('rank')}. {row.get('label')} ({dtxt}{p_txt})")
        parts.append("Top-3 from ARIS recommend(): " + "; ".join(bits) + ".")
    sims = tool_results.get("simulate_all")
    if not isinstance(sims, list):
        sims = [tool_results["simulate"]] if isinstance(tool_results.get("simulate"), dict) else []
    sim_bits: list[str] = []
    for sim in sims:
        if not isinstance(sim, dict) or "delta_vs_stay_out_s" not in sim:
            continue
        try:
            delta = float(sim["delta_vs_stay_out_s"])
            sim_bits.append(
                f"{sim.get('label') or 'action'} {delta:+.1f}s vs stay "
                f"(remaining {float(sim.get('total_race_time_s') or 0):.1f}s)"
            )
        except (TypeError, ValueError):
            continue
    if sim_bits:
        parts.append("Simulate(): " + "; ".join(sim_bits) + ".")
    # Two simulate calls for cover vs stay are stored under the same key; use tool_calls list via extra.
    under = tool_results.get("get_undercut_window")
    if isinstance(under, dict) and not under.get("error"):
        laps = under.get("window_laps") or []
        gap = under.get("gap_to_rival_s")
        delta = under.get("delta_s")
        if laps:
            extra = ""
            if isinstance(gap, (int, float)):
                extra = f" (gap {gap:.1f}s, now delta {float(delta or 0):+.1f}s)"
            parts.append(
                f"Undercut window {under.get('focus_driver')} vs {under.get('rival_driver')} "
                f"is open laps {laps[0]}–{laps[-1]}{extra}."
            )
        else:
            parts.append("Undercut window is closed versus that rival at this lap.")
    gap_info = tool_results.get("get_gap")
    if isinstance(gap_info, dict) and not gap_info.get("error"):
        drv = gap_info.get("driver")
        pos = gap_info.get("position")
        gl = gap_info.get("gap_to_leader_s")
        order = gap_info.get("order") or []
        p3 = next((r for r in order if r.get("position") == 3), None)
        q_low = question.lower()
        vs = gap_info.get("vs_driver")
        gap_vs = gap_info.get("gap_to_target_s")
        if vs and isinstance(gap_vs, (int, float)) and "p3" not in q_low:
            mag = abs(float(gap_vs))
            focus_code = gap_info.get("focus_driver") or drv
            if mag < 0.05:
                parts.append(f"{focus_code} and {vs} are effectively side by side.")
            elif gap_vs > 0:
                parts.append(
                    f"Gap from {focus_code} to {vs} is {mag:.1f}s ({focus_code} behind)."
                )
            else:
                parts.append(
                    f"Gap from {focus_code} to {vs} is {mag:.1f}s ({focus_code} ahead)."
                )
        elif "p3" in q_low and p3:
            parts.append(
                f"P3 is {p3.get('driver')} on {p3.get('compound')}, "
                f"tyre life {p3.get('tyre_life')}."
            )
        elif _LEADER_RE.search(question) or ("leader" in q_low and "gap" not in q_low):
            parts.append(f"{drv} is the leader (P{pos}).")
        else:
            gl_txt = f"+{float(gl):.1f}s to leader" if isinstance(gl, (int, float)) else "gap n/a"
            parts.append(f"{drv} is P{pos}, {gl_txt}.")
            behind = gap_info.get("behind")
            if behind:
                parts.append(
                    f"{behind.get('driver')} is {float(behind.get('gap_s') or 0):.1f}s behind "
                    f"on {behind.get('compound')} ({behind.get('tyre_life')} laps)."
                )
    result_info = tool_results.get("get_session_result")
    if isinstance(result_info, dict) and not result_info.get("error"):
        year = result_info.get("year")
        country = result_info.get("country") or "this circuit"
        if "podium" in question.lower() and result_info.get("podium"):
            bits = []
            for row in result_info["podium"][:3]:
                name = row.get("full_name") or row.get("driver_code")
                bits.append(f"P{row.get('finish_pos')} {name}")
            parts.append(f"The {year} {country} podium was {', '.join(bits)}.")
        elif result_info.get("winner"):
            winner = result_info["winner"]
            name = winner.get("full_name") or winner.get("driver_code")
            code = winner.get("driver_code")
            parts.append(f"{name} ({code}) won the {year} {country} race.")
        else:
            parts.append(f"I don't have a classified winner for the {year} {country} race.")
    styles = tool_results.get("get_driver_style_all")
    if not isinstance(styles, list):
        styles = [tool_results["get_driver_style"]] if isinstance(tool_results.get("get_driver_style"), dict) else []
    style_bits = [str(st["text"]) for st in styles if isinstance(st, dict) and st.get("text")]
    if style_bits:
        parts.append(" ".join(style_bits))
    circ = tool_results.get("get_circuit_info")
    if isinstance(circ, dict) and circ.get("text"):
        parts.append(str(circ["text"]))
    sc = tool_results.get("get_sc_risk")
    if isinstance(sc, dict) and sc.get("p_sc") is not None:
        parts.append(
            f"P(SC/VSC next {sc.get('horizon')} laps) = {float(sc['p_sc']):.0%}. "
            f"{sc.get('note') or ''}"
        )
    wet = tool_results.get("get_wet_state")
    if isinstance(wet, dict) and wet.get("track_state"):
        parts.append(
            f"Track state {wet['track_state']} "
            f"(confidence {float(wet.get('confidence') or 0):.0%})."
        )
    slope = tool_results.get("get_deg_slope")
    if isinstance(slope, dict) and slope.get("slope_s_per_lap") is not None:
        parts.append(
            f"{slope.get('compound')} slope {float(slope['slope_s_per_lap']):.3f} s/lap "
            f"at {slope.get('circuit_id')}."
        )
    mc = tool_results.get("run_mc_comparison")
    if isinstance(mc, dict) and mc.get("actions"):
        mc_bits = []
        for row in mc["actions"][:3]:
            mc_bits.append(
                f"{row.get('action')}: E[time]={float(row.get('expected_total_s') or 0):.1f}s "
                f"P(best)={float(row.get('p_best') or 0):.2f}"
            )
        parts.append("MC comparison: " + "; ".join(mc_bits) + ".")
    cite = _pick_cite(question, chunks)
    if cite and _wants_citation(question):
        snippet = str(cite.get("text") or "").replace("\n", " ")
        snippet = snippet[:240].rsplit(" ", 1)[0] if len(snippet) > 240 else snippet
        parts.append(_strip_raw_markdown(snippet))
        parts.append(f"Cite: {cite.get('chunk_id')}.")
    text = " ".join(p.strip() for p in parts if p and str(p).strip())
    text = _strip_raw_markdown(text)
    if not _wants_citation(question):
        text = re.sub(r"\s*Cite:\s*\S+", "", text).strip(" .")
        if text and not text.endswith("."):
            text += "."
    if not text:
        text = (
            "I need an ARIS tool result or a retrieved source for that. "
            "Ask about gaps, strategy, undercut windows, or FIA rules."
        )
    return text


def _wants_citation(question: str) -> bool:
    q = (question or "").lower()
    return any(
        w in q
        for w in (
            "rule",
            "fia",
            "compound",
            "limit",
            "auc",
            "reg",
            "tyre",
            "tire",
            "vsc",
            "safety",
            "red flag",
            "two compound",
            "parc",
            "pit lane",
        )
    )


def _strip_raw_markdown(text: str) -> str:
    """Drop heading/table dumps from user-facing Copilot text."""
    if not text:
        return text
    cleaned = _MD_TABLE_RE.sub("", text)
    cleaned = _MD_HEADING_RE.sub("", cleaned)
    cleaned = cleaned.replace("\n", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _pick_cite(question: str, chunks: list[dict[str, Any]]) -> dict[str, Any] | None:
    q = (question or "").lower()
    preferred = "aris_doc"
    if any(w in q for w in ("rule", "fia", "compound", "vsc", "safety car", "red flag", "pit lane", "parc", "wet-declared", "two compound")):
        preferred = "fia_reg"
    elif any(w in q for w in ("hamilton", "verstappen", "alonso", "easy on", "tyre style")):
        preferred = "driver_prior"
    elif any(w in q for w in ("spa", "monaco", "zandvoort", "high-deg", "high deg", "circuit")):
        preferred = "circuit_prior"
    elif any(w in q for w in ("auc", "conformal", "monte carlo", "classifier", "aris")):
        preferred = "aris_doc"
    ranked = [c for c in chunks if c.get("source") == preferred]
    if ranked:
        return ranked[0]
    return chunks[0] if chunks else None


def _extract_recommendations(tool_results: dict[str, Any]) -> list[dict[str, Any]]:
    rec = tool_results.get("recommend")
    if isinstance(rec, dict) and rec.get("top_3"):
        return list(rec["top_3"])
    mc = tool_results.get("run_mc_comparison")
    if isinstance(mc, dict) and mc.get("actions"):
        out = []
        for i, row in enumerate(mc["actions"][:3], start=1):
            out.append(
                {
                    "rank": i,
                    "label": row.get("action"),
                    "delta_vs_stay_out_s": row.get("delta_vs_stay"),
                    "p_best": row.get("p_best"),
                    "p10_delta_s": None,
                    "p90_delta_s": None,
                }
            )
        return out
    return []


def _needs_approval(question: str, recs: list[dict[str, Any]], tool_results: dict[str, Any]) -> bool:
    if not recs and "simulate" not in tool_results:
        return False
    q = question.lower()
    if any(w in q for w in ("best strategy", "recommend", "should we", "cover", "pit now")):
        return True
    if recs and any("pit" in str(r.get("label") or "").lower() for r in recs):
        return True
    return False


def _drivers_in(question: str) -> list[str]:
    found = []
    for match in _DRIVER_RE.finditer(question or ""):
        code = match.group(1).upper()
        if code in _KNOWN_DRIVERS and code not in found:
            found.append(code)
    q = (question or "").lower()
    aliases = {
        "hamilton": "HAM",
        "verstappen": "VER",
        "norris": "NOR",
        "leclerc": "LEC",
        "russell": "RUS",
        "piastri": "PIA",
    }
    for name, code in aliases.items():
        if name in q and code not in found:
            found.append(code)
    return found


def _compound_in(question: str) -> str | None:
    match = _COMPOUND_RE.search(question or "")
    if not match:
        return None
    token = match.group(1).upper()
    return "INTERMEDIATE" if token == "INTER" else token


def _wants_long(question: str) -> bool:
    return bool(re.search(r"\b(more detail|in detail|explain fully|full dump)\b", question or "", re.I))


def clip_words(text: str, limit: int = _WORD_LIMIT) -> str:
    words = (text or "").split()
    if len(words) <= limit:
        return (text or "").strip()
    return " ".join(words[:limit]).rstrip(" ,;") + "…"


def word_count(text: str) -> int:
    return len((text or "").split())
