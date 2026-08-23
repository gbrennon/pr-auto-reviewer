"""ResponseParserPort — parse LLM review responses into structured data."""

from __future__ import annotations

from typing import Any, Protocol

from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


class ResponseParserPort(Protocol):
    """Parse raw LLM text into item dicts and extract structured content.

    The full contract the conversation layer depends on: item
    extraction, JSON/markdown discovery, verdict extraction, and prose
    suggestion/praise parsing. Implementations may provide members as
    instance, class, or static methods; callers always invoke through
    an injected instance.
    """

    def parse_items(self, raw_text: str) -> list[dict[str, Any]]:
        """Extract a list of item dicts from a phase response."""
        ...

    def parse_item_observations(self, raw_text: str) -> list[dict[str, Any]]:
        """Extract fix-less findings as non-blocking observation dicts."""
        ...

    def strip_frontmatter(self, text: str) -> str:
        """Remove YAML frontmatter delimited by ``---`` lines."""
        ...

    def extract_outermost_json(self, text: str) -> str | None:
        """Extract the outermost JSON object from *text*."""
        ...

    def extract_verdict_md(self, raw_text: str) -> ReviewVerdict:
        """Extract the verdict from markdown-formatted LLM output.

        Raises ``ReviewVerdictError`` when no explicit APPROVED or
        CHANGES_REQUESTED verdict is present — callers decide the
        fallback instead of receiving a silent default.
        """
        ...

    def sanitize_json_literals(self, text: str) -> str:
        """Escape raw control characters inside JSON string literals."""
        ...

    def normalize_item_dict(self, item: dict[str, Any]) -> dict[str, Any]:
        """Map LLM JSON item fields onto the canonical item schema."""
        ...

    def parse_prose_recommendations(
        self, content: str
    ) -> list[dict[str, str]]:
        """Extract non-blocking improvement prose as suggestion entries."""
        ...

    def parse_prose_praise(self, content: str) -> list[dict[str, str]]:
        """Extract strengths/positive prose as praise entries."""
        ...
