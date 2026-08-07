"""ResponseParserPort — parse LLM review responses into structured data."""

from __future__ import annotations

from typing import Any, Protocol


class ResponseParserPort(Protocol):
    """Parse raw LLM text into item dicts and extract structured content."""

    def parse_items(self, content: str) -> list[dict[str, Any]]:
        """Extract a list of item dicts from a phase response."""
        ...

    @staticmethod
    def strip_frontmatter(text: str) -> str:
        """Remove YAML frontmatter delimited by ``---`` lines."""
        ...

    @staticmethod
    def extract_outermost_json(text: str) -> str | None:
        """Extract the outermost JSON object from *text*."""
        ...
