"""ARIS Copilot — LLM narrator + tool-caller + hybrid retrieval.

Does not change ``recommend()`` or ``simulate()``. Race math always goes
through the existing ARIS functions.
"""

from aris.copilot.agent import CopilotResult, run_copilot
from aris.copilot.context import CopilotContext, FieldCar, get_context, set_context
from aris.copilot.tools import TOOL_SCHEMAS, execute_tool

__all__ = [
    "CopilotContext",
    "CopilotResult",
    "FieldCar",
    "TOOL_SCHEMAS",
    "execute_tool",
    "get_context",
    "run_copilot",
    "set_context",
]
