"""LLM narration layer — structured recommendation → one-sentence radio call."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from aris.recommend import Recommendation, RecommendationResult

DEFAULT_MODEL = "llama3.1:8b-instruct-q5_K_M"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
TIMEOUT_S = 30.0


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
