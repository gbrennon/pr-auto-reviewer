"""ComposedPrompt — immutable value object for a fully assembled prompt."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComposedPrompt:
    """Final assembled prompt ready for LLM consumption.

    Holds the rendered content, the list of fragment IDs that were used
    to build it (for telemetry / debugging), and an estimated token count.
    """

    content: str
    fragments_used: list[str]
    total_tokens: int

    def __post_init__(self) -> None:
        """Validate fields after dataclass construction."""
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be empty")
        if self.total_tokens < 0:
            raise ValueError("total_tokens must be non-negative")
