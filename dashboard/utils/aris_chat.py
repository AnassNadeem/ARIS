"""ARIS chat — Ollama (Llama 3.1) with Anthropic Haiku fallback."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
TIMEOUT_S = 30.0


def _try_ollama(system_prompt: str, user_message: str) -> str | None:
    url = os.getenv("ARIS_OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")
    model = os.getenv("ARIS_LLM_MODEL", DEFAULT_OLLAMA_MODEL)
    try:
        resp = httpx.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "stream": False,
            },
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        text = resp.json().get("message", {}).get("content", "").strip()
        return text if text else None
    except (httpx.HTTPError, json.JSONDecodeError, KeyError):
        return None


def _try_anthropic(system_prompt: str, user_message: str) -> str | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    model = os.getenv("ARIS_ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 256,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
            },
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        if blocks and blocks[0].get("type") == "text":
            return blocks[0]["text"].strip()
    except (httpx.HTTPError, json.JSONDecodeError, KeyError):
        return None
    return None


def _rule_based_response(user_message: str, race_state: dict[str, Any]) -> str:
    """Grounded fallback when no LLM is available."""
    q = user_message.lower()
    lap = race_state.get("current_lap", "?")
    compound = race_state.get("compound", "MEDIUM")
    tyre_life = race_state.get("tyre_life", 0)
    deg = race_state.get("deg_rate", 0.05)
    pw = race_state.get("pit_window", {})
    mc = race_state.get("mc_probabilities", {})

    if "norris" in q or "nor" in q:
        cars = race_state.get("cars", [])
        nor = next((c for c in cars if c.get("driver") == "NOR"), None)
        if nor:
            return (
                f"NOR P{nor['pos']} on {nor['tyre']} — {nor['age']} laps old, "
                f"last lap {nor.get('last_lap', '—'):.3f}s. Gap {nor.get('gap', 0):.1f}s."
            )
    if "pit" in q and ("now" in q or "vs" in q or "lap" in q):
        opt = pw.get("optimal", 41)
        return (
            f"L{lap}: deg {deg:.2f}s/lap on {compound} ({tyre_life} laps). "
            f"Optimal window L{pw.get('open', 40)}-{pw.get('close', 44)}. "
            f"Pitting now costs ~22s; waiting to L{opt} covers undercut. Recommend wait."
        )
    if "tyre" in q or "tire" in q or "deg" in q:
        return (
            f"{compound} stint {race_state.get('stint_num', 1)} — {tyre_life} laps, "
            f"deg {deg:.2f}s/lap. Track {race_state.get('track_temp_c', 38)}°C. "
            f"P1 prob {mc.get('p1', 0.68):.0%}."
        )
    if "gap" in q or "lec" in q or "leclerc" in q:
        behind = race_state.get("gap_behind_s")
        ahead = race_state.get("gap_ahead_s")
        pos = race_state.get("position", "?")
        gap_leader = race_state.get("gap_to_leader_s", 0)
        leader_txt = "LEADER" if pos == 1 else f"+{gap_leader:.1f}s"
        behind_txt = f"+{behind:.1f}s" if behind is not None else "—"
        ahead_txt = f"{ahead:.1f}s" if ahead is not None else "—"
        return f"P{pos} — {leader_txt}. Behind: {behind_txt} | Ahead gap: {ahead_txt}"
    return (
        f"L{lap} update: {compound} {tyre_life} laps, ARIS pred "
        f"{race_state.get('aris_pred', 0):.3f}s vs actual {race_state.get('actual', '—')}. "
        f"P1 {mc.get('p1', 0.68):.0%}."
    )


def get_aris_response(user_message: str, race_state: dict[str, Any]) -> str:
    """
    Build context from race_state and call LLM.
    Tries Ollama first, then Anthropic, then rule-based fallback.
    """
    system_prompt = (
        "You are ARIS, an F1 race strategy AI on the pit wall. "
        f"You have full knowledge of all cars' data. Current race state: "
        f"{json.dumps(race_state, default=str)}. "
        "Answer concisely in 2-3 sentences. Reference specific numbers. "
        "Never say you don't know — reason from the data provided."
    )

    response = _try_ollama(system_prompt, user_message)
    if response:
        return response

    response = _try_anthropic(system_prompt, user_message)
    if response:
        return response

    return _rule_based_response(user_message, race_state)
