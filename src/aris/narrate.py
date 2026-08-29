"""LLM narration layer — structured recommendation → one-sentence radio call."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from aris.recommend import HOLD_WET_NARRATION, Recommendation, RecommendationResult
from aris.simulate import ActionKind


@dataclass
class FieldDriver:
    code: str
    name: str
    compound: str
    tyre_life: int
    position: int
    gap_to_leader: float


@dataclass
class RadioField:
    """Lightweight field snapshot for radio / template chat (not Postgres FieldState)."""

    drivers: list[FieldDriver]

    def get_driver(self, code: str) -> FieldDriver | None:
        needle = (code or "").upper()
        for drv in self.drivers:
            if drv.code.upper() == needle:
                return drv
        return None

    def driver_at_position(self, pos: int) -> FieldDriver | None:
        for drv in self.drivers:
            if drv.position == pos:
                return drv
        return None


def generate_template_response(
    question: str,
    field: RadioField | None,
    focus_driver: str,
    current_lap: int,
    total_laps: int,
) -> str:
    q = question.lower()

    if any(w in q for w in ["gap", "behind", "ahead", "leader", "front"]):
        if field:
            focus = field.get_driver(focus_driver)
            leader = field.driver_at_position(1)
            p2 = field.driver_at_position(2)
            if leader and focus:
                p2_txt = f"{p2.code} P2 at +{p2.gap_to_leader:.1f}s. " if p2 else ""
                return (
                    f"{leader.code} leads. "
                    f"{p2_txt}"
                    f"We are P{focus.position} at "
                    f"+{focus.gap_to_leader:.1f}s."
                )
        return "Gap data not available for this lap."

    if any(w in q for w in ["position", "where", "place", "running"]):
        if field:
            focus = field.get_driver(focus_driver)
            if focus:
                return (
                    f"Currently P{focus.position}, "
                    f"+{focus.gap_to_leader:.1f}s off the lead."
                )
        return "Position data unavailable."

    if any(w in q for w in ["tyre", "tire", "compound", "rubber"]):
        if field:
            for driver in field.drivers:
                name_l = driver.name.lower()
                if driver.code.lower() in q or any(part and part in q for part in name_l.split()):
                    return (
                        f"{driver.code} is on {driver.compound}, "
                        f"{driver.tyre_life} laps old."
                    )
            focus = field.get_driver(focus_driver)
            if focus:
                return (
                    f"We are on {focus.compound}, "
                    f"{focus.tyre_life} laps old."
                )
        return "Tyre data unavailable."

    if any(w in q for w in ["lap", "remaining", "left", "to go"]):
        remaining = total_laps - current_lap
        return f"Lap {current_lap} of {total_laps}. {remaining} laps remaining."

    if any(w in q for w in ["pit", "box", "stop"]):
        return (
            "Ask ARIS for a strategy recommendation using the "
            "recommend button, or type 'should we pit?' for an analysis."
        )

    return (
        "I don't have enough context to answer that right now. "
        "Try asking about gaps, tyres, or positions."
    )


DEFAULT_MODEL = "llama3.1:8b-instruct-q5_K_M"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
TIMEOUT_S = 30.0
HF_MODEL = os.getenv("ARIS_HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")

CHAT_SYSTEM_PROMPT = """
You are ARIS, a Formula 1 race engineer assistant speaking on the
radio. Answer in plain English. Be direct and concise. Lead with
the number or answer, then the context.

Rules:
- Never show field names like "grid_pos=" or "finish_pos="
- Never show database keys, IDs, or session numbers
- Never reproduce raw query results
- If citing a race, say "the 2025 Abu Dhabi race" not
  "session_results year=2025 round=24"
- Maximum 3 sentences
- If you don't know, say "No data available for that"

Format context given to you as natural background information,
not as database rows. Extract the relevant numbers and present
them naturally.
""".strip()


def format_context_for_llm(raw_records: list[dict[str, Any]]) -> str:
    """Convert database records / RAG text to readable English paragraphs."""
    lines: list[str] = []
    for rec in raw_records:
        rtype = rec.get("type")
        if rtype == "session_results":
            lines.append(
                f"In the {rec.get('year')} {rec.get('country')} race, "
                f"{rec.get('driver')} started P{rec.get('grid_pos')} and "
                f"finished P{rec.get('finish_pos')} scoring {rec.get('points')} points."
            )
        elif rtype == "pit_stop":
            lines.append(
                f"{rec.get('driver')} pitted on lap {rec.get('lap')} "
                f"and switched to {rec.get('compound')}."
            )
        elif rtype == "decision_record":
            lines.append(
                f"ARIS recommended {rec.get('action')} on lap {rec.get('lap')}: "
                f"{rec.get('reasoning')}"
            )
        else:
            text = str(rec.get("text") or "")
            text = (
                text.replace("grid_pos=", "started P")
                .replace("finish_pos=", "finished P")
                .replace("session_results ", "")
            )
            if text:
                lines.append(text)
    return "\n".join(lines) if lines else "No relevant historical data found."


def _call_ollama(system: str, user: str, timeout: float = 5.0) -> str:
    resp = httpx.post(
        f"{_ollama_base_url()}/api/chat",
        json={
            "model": _ollama_model(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    msg = data.get("message") or {}
    text = (msg.get("content") or data.get("response") or "").strip()
    if not text:
        raise RuntimeError("empty ollama response")
    return text.split("\n")[0].strip()


def _call_huggingface(system: str, user: str, timeout: float = 8.0) -> str:
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN") or ""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    prompt = f"<s>[INST] {system}\n\n{user} [/INST]"
    resp = httpx.post(
        f"https://api-inference.huggingface.co/models/{HF_MODEL}",
        headers=headers,
        json={"inputs": prompt, "parameters": {"max_new_tokens": 120, "temperature": 0.2}},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list) and data:
        text = str(data[0].get("generated_text") or "")
    elif isinstance(data, dict):
        text = str(data.get("generated_text") or data.get("error") or "")
        if data.get("error"):
            raise RuntimeError(text)
    else:
        text = str(data)
    # Strip the prompt echo if present.
    if "[/INST]" in text:
        text = text.split("[/INST]", 1)[-1]
    text = text.strip()
    if not text:
        raise RuntimeError("empty huggingface response")
    return text.split("\n")[0].strip()


def call_llm_with_fallback(
    question: str,
    *,
    context: str = "",
    fallback: str = "",
) -> str:
    user = question if not context else f"Context:\n{context}\n\nQuestion: {question}"
    try:
        return _call_ollama(CHAT_SYSTEM_PROMPT, user, timeout=5.0)
    except Exception:
        pass
    if os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN"):
        try:
            return _call_huggingface(CHAT_SYSTEM_PROMPT, user, timeout=8.0)
        except Exception:
            pass
    return fallback


def _ollama_base_url() -> str:
    return os.getenv("ARIS_OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")


def _ollama_model() -> str:
    return os.getenv("ARIS_LLM_MODEL", DEFAULT_MODEL)


def _build_prompt(rec: Recommendation, state_context: dict[str, Any]) -> str:
    ctx = {**state_context, **rec.narration_context}
    caveat_line = ""
    if ctx.get("confidence_caveat"):
        caveat_line = (
            " If confidence_caveat is present, end the sentence by mentioning it "
            "so the engineer hears the lower-confidence warning."
        )
    return (
        "You are an F1 race engineer on the radio. Given ONLY the JSON data below, "
        "write exactly ONE sentence recommending the strategy. "
        "Include the lap-time delta in seconds. Do not invent numbers not in the data. "
        f"Be concise like a radio call.{caveat_line}\n\n"
        f"DATA:\n{json.dumps(ctx, indent=2)}\n\n"
        "RADIO CALL:"
    )


def _fallback_narration(rec: Recommendation) -> str:
    if rec.label.startswith("OVERCUT_") or rec.narration_context.get("overcut_rival"):
        rival = rec.narration_context.get("overcut_rival") or rec.action.overcut_rival or "rival"
        n = rec.narration_context.get("overcut_n") or rec.action.overcut_n or 2
        delta = rec.narration_context.get("overcut_window_delta_s")
        if delta is None:
            delta = rec.action.overcut_window_delta_s
        if delta is None:
            delta = rec.delta_vs_stay_out_s
        return (
            f"Overcut window — {rival} is coming in. Stay out {n} more laps, "
            f"build the gap, then box. Net: {delta:.1f}s in our favour."
        )
    if rec.wet_heuristic:
        remaining = rec.narration_context.get("laps_remaining", "?")
        label = rec.label or ""
        if rec.action.kind == ActionKind.STAY_OUT and not rec.action.pit_laps:
            return (
                f"{HOLD_WET_NARRATION} "
                f"[HEURISTIC — reduced confidence in wet conditions]"
            )
        if "DRY_WINDOW" in label:
            return (
                "Track may be drying. Box for slicks — DRY_WINDOW. "
                "[HEURISTIC — reduced confidence in wet conditions]"
            )
        delta = rec.narration_context.get("delta_s", rec.delta_vs_stay_out_s)
        compound = rec.action.pit_compound or "intermediates"
        return (
            f"Rain affecting lap times. Box for {compound.lower()} — estimated "
            f"{delta:.0f}s net gain over {remaining} laps. "
            f"[HEURISTIC — reduced confidence in wet conditions]"
        )
    delta = rec.narration_context.get("delta_s", rec.delta_vs_stay_out_s)
    driver = rec.narration_context.get("driver", "driver")
    lap = rec.narration_context.get("lap", "?")
    sign = "+" if delta > 0 else ""
    text = (
        f"{driver}, recommend {rec.label.lower()} at lap {lap} — "
        f"expected {sign}{delta:.1f}s vs staying out."
    )
    caveat = rec.narration_context.get("confidence_caveat")
    if caveat:
        text = f"{text} Note: {caveat}."
    note = rec.narration_context.get("confidence_note") or rec.confidence_note
    if note and rec.p10_delta_s != rec.p90_delta_s:
        text = (
            f"{text} 90% band [{rec.p10_delta_s:+.1f}s, {rec.p90_delta_s:+.1f}s]."
        )
    sc_line = rec.narration_context.get("sc_risk_line")
    if sc_line:
        text = f"{text} {sc_line}"
    return text


def narrate_recommendation(
    rec: Recommendation,
    *,
    state_context: dict[str, Any] | None = None,
    use_llm: bool = True,
) -> str:
    """Turn the top recommendation into a one-sentence radio call."""
    ctx = state_context or rec.narration_context
    if not use_llm:
        return _fallback_narration(rec)

    prompt = _build_prompt(rec, ctx)
    try:
        resp = httpx.post(
            f"{_ollama_base_url()}/api/generate",
            json={"model": _ollama_model(), "prompt": prompt, "stream": False},
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        if text:
            return text.split("\n")[0].strip()
    except (httpx.HTTPError, json.JSONDecodeError, KeyError):
        pass
    return _fallback_narration(rec)


def narrate_result(
    result: RecommendationResult,
    *,
    use_llm: bool = True,
) -> str:
    """Narrate the #1 recommendation from a full result."""
    if not result.recommendations:
        return "No strategy recommendation available for this lap."
    top = result.recommendations[0]
    return narrate_recommendation(top, use_llm=use_llm)
