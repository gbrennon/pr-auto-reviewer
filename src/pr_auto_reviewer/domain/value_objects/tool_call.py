"""ToolCall — a request from the LLM to invoke an exploration tool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """A parsed tool invocation from the LLM's response.

    Carries the tool name and its arguments as extracted from the
    conversation turn JSON.
    """

    tool_name: str
    arguments: dict[str, Any]
