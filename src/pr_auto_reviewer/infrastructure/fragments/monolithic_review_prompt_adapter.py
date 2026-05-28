"""MonolithicReviewPromptAdapter — uses a single Jinja2 template, no fragments."""

from __future__ import annotations

import logging
from pathlib import Path

import jinja2

from pr_auto_reviewer.application.ports.outbound.compose_review_prompt_port import (
    ComposeReviewPromptPort,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "llm" / "templates"


class MonolithicReviewPromptAdapter(ComposeReviewPromptPort):
    """Builds prompts from a single Jinja2 template — no fragments.

    Implements :class:`ComposeReviewPromptPort` as a drop-in replacement
    for :class:`ComposeReviewPromptAdapter`.  Renders one monolithic
    template with the review context, appends the diff (with truncation
    to fit ``max_total_chars``), and returns the assembled prompt.

    The entire prompt goes into Ollama's ``prompt`` field (no ``---``
    separator, so no system/user split).
    """

    def __init__(
        self,
        template_dir: str | Path = _TEMPLATES_DIR,
        max_total_chars: int = 60_000,
    ) -> None:
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            keep_trailing_newline=True,
        )
        self._template = self._env.get_template("monolithic_review_prompt.j2")
        self._max_total_chars = max_total_chars

    def execute(self, context: ReviewContext) -> ComposedPrompt:
        """Build the prompt from *context*.

        Renders the monolithic template with language, file paths, and
        repository context, then appends the diff (truncated to fit
        ``self._max_total_chars``) and a JSON reminder.
        """
        repository_context = context.repository_context or ""
        if len(repository_context) > 4_000:
            repository_context = (
                repository_context[:4_000]
                + "\n... (repository context truncated to keep diff reviewable)\n"
            )

        body = self._template.render(
            language=context.language,
            file_paths="\n".join(context.file_paths),
            repository_context=repository_context,
        )

        reminder = (
            "\n\n**REMEMBER:** Output ONLY a JSON object. "
            "No markdown. No code fences. No explanation. "
            'Start with "{" and end with "}".'
        )

        diff_header = "\n## Diff\n\n```diff\n"
        diff_footer = "\n```"
        overhead = len(body) + len(reminder) + len(diff_header) + len(diff_footer)
        available = max(0, self._max_total_chars - overhead)

        diff_text = context.diff
        if len(diff_text) > available > 0:
            truncated = diff_text[:available]
            last_newline = truncated.rfind("\n")
            if last_newline > available // 2:
                diff_text = truncated[:last_newline] + (
                    f"\n... (diff truncated from {len(context.diff)} "
                    f"to {last_newline} chars to fit context window)\n"
                )
            else:
                diff_text = truncated + (
                    f"\n... (diff truncated from {len(context.diff)} "
                    f"to {available} chars)\n"
                )
        elif available == 0 and len(diff_text) > 0:
            diff_text = "\n... (diff omitted — too large for budget)\n"

        content = body + diff_header + diff_text + diff_footer + reminder

        logger.debug(
            "Monolithic prompt: chars=%d tokens=%d diff_chars=%d (was %d)",
            len(content), len(content) // 4,
            len(diff_text), len(context.diff),
        )

        return ComposedPrompt(
            content=content,
            fragments_used=["monolithic"],
            total_tokens=len(content) // 4,
        )
