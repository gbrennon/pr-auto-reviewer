"""ResponseParserPort — parse LLM review responses into structured data."""

from __future__ import annotations

from typing import Any, Protocol


class ResponseParserPort(Protocol):
    """Parse raw LLM text into item dicts and extract structured content."""

    @classmethod
    def parse_items(cls, raw_text: str) -> list[dict[str, Any]]:
        """Extract a list of item dicts from a phase response."""
        ...

    @classmethod
    def strip_frontmatter(cls, text: str) -> str:
        """Remove YAML frontmatter delimited by ``---`` lines."""
        ...

    @classmethod
    def extract_outermost_json(cls, text: str) -> str | None:
        """Extract the outermost JSON object from *text*."""
        ...

    @classmethod
    def _extract_verdict_md(cls, raw_text: str) -> Any:
        """Extract the verdict from markdown-formatted LLM output."""
        ...
