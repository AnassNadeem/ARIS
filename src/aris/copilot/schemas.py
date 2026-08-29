"""JSON schemas for Copilot tool-calling. The LLM never receives RaceState."""

from __future__ import annotations

from typing import Any

COMPOUND_ENUM = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_gap",
        "description": (
            "Return the requested driver's gap to the leader, the car ahead, "
            "and the car behind, plus a short field order (position, compound, "
            "tyre life). Uses the current live/replay RaceState. Optional lap "
            "selects a replay lap when field history is available."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "driver": {
                    "type": "string",
                    "description": "Driver code, e.g. 'VER' or 'NOR'.",
                },
                "lap": {
                    "type": "integer",
                    "description": "Replay lap number. Omit for the current lap.",
                },
                "vs_driver": {
                    "type": "string",
                    "description": (
                        "When the user asks 'gap to X' from the focus car, "
                        "the other driver code. Returns the interval, not X's gap to leader."
                    ),
                },
            },
            "required": ["driver"],
        },
    },
    {
        "name": "get_undercut_window",
        "description": (
            "Compute the undercut window for a focus driver vs a rival, "
            "optionally for a specific compound. Delegates to ARIS "
            "simulate_undercut / rival pit estimates. Never invent deltas."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "focus_driver": {
                    "type": "string",
                    "description": "Driver code, e.g. 'VER'",
                },
                "rival_driver": {
                    "type": "string",
                    "description": "Driver code, e.g. 'NOR'",
                },
                "compound": {
                    "type": "string",
                    "enum": COMPOUND_ENUM,
                    "description": "Optional pit compound filter.",
                },
            },
            "required": ["focus_driver", "rival_driver"],
        },
    },
    {
        "name": "get_deg_slope",
        "description": (
            "Return the degradation slope (s/lap) for a compound at a circuit "
            "or weekend (FP2-fitted, else G1.5 fallback)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "compound": {"type": "string", "enum": COMPOUND_ENUM},
                "circuit_id": {
                    "type": "string",
                    "description": "Circuit or country name, e.g. 'Netherlands'.",
                },
                "year": {"type": "integer"},
                "round_number": {"type": "integer"},
            },
            "required": ["compound"],
        },
    },
    {
        "name": "simulate",
        "description": (
            "Simulate remaining race for one action (pit now/later, compound, "
            "or stay out). Returns expected remaining time and delta vs stay. "
            "RaceState is injected; do not invent lap times."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "PIT_NOW, PIT_LAP, or STAY_OUT.",
                },
                "compound": {
                    "type": "string",
                    "enum": COMPOUND_ENUM,
                    "description": "Pit compound when action is a stop.",
                },
                "pit_lap": {
                    "type": "integer",
                    "description": "Absolute race lap for PIT_LAP.",
                },
                "kind": {
                    "type": "string",
                    "description": "Alias of action (pit_now / stay_out / pit_lap).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "recommend",
        "description": (
            "Return the top-3 strategy actions with deltas vs stay-out, "
            "P10/P90, and explanations. RaceState is injected."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_sc_risk",
        "description": (
            "Return P(SC/VSC in the next `horizon` laps) for the current lap "
            "(or a replay lap). Circuit prior is the useful part; lap-to-lap "
            "AUC is only ~0.55."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lap": {"type": "integer", "description": "Replay lap. Omit for current."},
                "horizon": {
                    "type": "integer",
                    "description": "Lookahead in laps (5 or 10).",
                    "default": 5,
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_wet_state",
        "description": (
            "Return current track_state (DRY/DAMP/CROSSOVER/WET/DRYING) and "
            "confidence from the rule-based T10-C classifier."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lap": {"type": "integer", "description": "Replay lap. Omit for current."},
            },
            "required": [],
        },
    },
    {
        "name": "run_mc_comparison",
        "description": (
            "Run per-lap Monte Carlo for multiple actions and return E[time], "
            "P10/P90, and P(best). Delegates to compare_actions_mc. RaceState "
            "is injected. Pass action dicts; do not compute noise yourself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of action dicts (kind/compound/pit_lap).",
                },
                "n_scenarios": {"type": "integer", "default": 200},
            },
            "required": ["actions"],
        },
    },
    {
        "name": "get_driver_style",
        "description": (
            "Return simple driver priors and style stats (tyre management, "
            "typical stint lengths, lap-time variance). From ARIS priors, "
            "not invented numbers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "driver": {"type": "string", "description": "Driver code, e.g. 'HAM'."},
            },
            "required": ["driver"],
        },
    },
    {
        "name": "get_circuit_info",
        "description": (
            "Return circuit characteristics: lap length, typical degradation, "
            "historical SC rate, pit loss. From track YAML + priors."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "circuit_id": {
                    "type": "string",
                    "description": "Circuit key, alias, or country, e.g. 'spa'.",
                },
            },
            "required": ["circuit_id"],
        },
    },
    {
        "name": "get_session_result",
        "description": (
            "Return the classified winner and podium for a completed race "
            "from ARIS session-result records. Use for 'who won', 'last year', "
            "or podium questions. Does not invent results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Season year, e.g. 2024."},
                "country": {
                    "type": "string",
                    "description": "Race country or circuit name, e.g. 'Netherlands'.",
                },
                "last_year": {
                    "type": "boolean",
                    "description": "If true, look up year-1 at this circuit.",
                },
                "podium": {
                    "type": "boolean",
                    "description": "If true, include P1–P3 not just the winner.",
                },
            },
            "required": [],
        },
    },
]

SCHEMA_BY_NAME: dict[str, dict[str, Any]] = {s["name"]: s for s in TOOL_SCHEMAS}
