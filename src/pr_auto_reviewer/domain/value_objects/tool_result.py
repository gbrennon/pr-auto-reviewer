"""ToolResult — the outcome of executing a tool call against the repository."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """The result of executing a ToolCall against the repository.

    ``status`` is ``"success"`` or ``"error"``. On success, ``data``
    carries the tool-specific payload. On error, ``error`` carries a
    human-readable message.
    """

    status: str
    data: dict[str, Any] | None = None
    error: str | None = None
