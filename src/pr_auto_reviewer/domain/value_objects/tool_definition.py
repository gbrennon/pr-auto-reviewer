"""ToolDefinition — describes an exploration tool the LLM can invoke."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    """A tool available to the LLM during agentic review conversations.

    Each tool has a name, a human-readable description, and a JSON Schema
    subset describing its parameters.
    """

    name: str
    description: str
    parameter_schema: dict[str, Any]
