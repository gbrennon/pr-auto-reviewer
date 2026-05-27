"""ComposeReviewPromptAdapter — infrastructure adapter composing review prompts from fragments."""

from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.outbound.compose_review_prompt_port import (
    ComposeReviewPromptPort,
)
from pr_auto_reviewer.application.ports.outbound.fragment_repository_port import (
    FragmentRepositoryPort,
)
from pr_auto_reviewer.application.ports.outbound.prompt_renderer_port import (
    PromptRendererPort,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.infrastructure.fragments.token_budget_manager import (
    TokenBudgetManager,
)

logger = logging.getLogger(__name__)

DEFAULT_SEPARATOR = "\n\n---\n\n"


class ComposeReviewPromptAdapter(ComposeReviewPromptPort):
    """Infrastructure adapter that composes a complete review prompt from fragments.

    Implements :class:`ComposeReviewPromptPort`, the outbound port for
    prompt composition.  Resides in the infrastructure layer as an adapter.

    Orchestration flow:

    1. Select relevant fragments from the repository.
    2. Compose them into a final prompt via rendering and joining.
    3. Return the assembled :class:`ComposedPrompt`.

    Fragment selection merges language-specific and universal fragments,
    sorted by priority descending.  When ``max_tokens`` is configured,
    fragments are greedily filtered (highest priority first) until the
    token budget is exhausted.

    Fragment composition renders each fragment with variables from the
    review context, joins them with a markdown separator, estimates
    token count, and returns the result.
    """

    def __init__(
        self,
        repository: FragmentRepositoryPort,
        renderer: PromptRendererPort | None = None,
        max_tokens: int | None = None,
        separator: str = DEFAULT_SEPARATOR,
        max_total_chars: int = 60_000,
    ) -> None:
        self._repository = repository
        self._renderer = renderer
        self._separator = separator
        self._budget_manager = (
            TokenBudgetManager(max_tokens) if max_tokens else None
        )
        self._max_total_chars = max_total_chars

    def execute(self, context: ReviewContext) -> ComposedPrompt:
        """Execute the composition for *context*."""
        logger.info(
            "ComposeReviewPromptAdapter.execute(language=%s, files=%d, diff=%d chars)",
            context.language, len(context.file_paths), len(context.diff),
        )
        fragments = self._select_fragments(context)

        if not fragments:
            raise ValueError(
                f"No fragments found for language: {context.language}",
            )

        return self._compose_prompt(fragments, context)

    def _select_fragments(self, context: ReviewContext) -> list[PromptFragment]:
        """Select language-specific + universal fragments, sorted by priority."""
        language_fragments = self._repository.find_by_language(context.language)
        universal_fragments = self._repository.find_universal()

        all_fragments = language_fragments + universal_fragments
        sorted_fragments = sorted(
            all_fragments, key=lambda f: f.priority, reverse=True,
        )

        if self._budget_manager is not None:
            return self._apply_budget_constraints(sorted_fragments)

        return sorted_fragments

    def _apply_budget_constraints(
        self, fragments: list[PromptFragment],
    ) -> list[PromptFragment]:
        """Greedily select highest-priority fragments that fit the budget."""
        selected: list[PromptFragment] = []
        self._budget_manager.reset()  # type: ignore[union-attr]

        for fragment in fragments:
            if self._budget_manager.fits_budget(fragment.content):  # type: ignore[union-attr]
                self._budget_manager.consume(fragment.content)  # type: ignore[union-attr]
                selected.append(fragment)

        return selected

    def _compose_prompt(
        self,
        fragments: list[PromptFragment],
        context: ReviewContext,
    ) -> ComposedPrompt:
        """Compose *fragments* into a single prompt for LLM consumption.

        To avoid blowing past the model's context window, the diff is
        included **once** at the end of the prompt rather than being
        duplicated inside every fragment.  When the total prompt would
        still exceed ``self._max_total_chars`` the diff is truncated."""
        if not fragments:
            raise ValueError(
                "Cannot compose prompt from empty fragment list",
            )

        # Render every fragment with a short placeholder for code/diff.
        # The real diff is appended once at the end.
        rendered_sections: list[str] = []
        fragment_ids: list[str] = []

        for fragment in fragments:
            rendered = self._render_fragment(fragment, context, inline_diff=False)
            rendered_sections.append(rendered)
            fragment_ids.append(fragment.id)

        body = self._separator.join(rendered_sections)

        if context.repository_context:
            body += self._separator + context.repository_context

        reminder = (
            self._separator
            + "**REMEMBER:** Output ONLY a raw JSON object. "
            + "No markdown. No code fences. No explanation. "
            + 'Start with "{" and end with "}".'
        )

        # How many chars remain for the diff?
        overhead = len(body) + len(reminder) + len(self._separator)
        available = max(0, self._max_total_chars - overhead)

        diff_text = context.diff
        if len(diff_text) > available > 0:
            # Truncate at whole-line boundaries.
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

        final_content = (
            body
            + self._separator
            + "## Diff\n\n```diff\n"
            + diff_text
            + "\n```"
            + reminder
        )

        estimated_tokens = len(final_content) // 4

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Composed prompt: chars=%d tokens=%d fragments=%d "
                "diff_chars=%d (was %d)",
                len(final_content),
                estimated_tokens,
                len(fragment_ids),
                len(diff_text),
                len(context.diff),
            )

        result = ComposedPrompt(
            content=final_content,
            fragments_used=fragment_ids,
            total_tokens=estimated_tokens,
        )
        logger.info(
            "ComposeReviewPromptAdapter return: chars=%d tokens=%d fragments=%s",
            len(result.content), result.total_tokens, result.fragments_used,
        )
        return result

    def _render_fragment(
        self,
        fragment: PromptFragment,
        context: ReviewContext,
        inline_diff: bool = True,
    ) -> str:
        """Render a single fragment with variable substitution.

        When *inline_diff* is ``False`` the ``{{ code }}`` / ``{{ diff }}``
        placeholders are replaced with a short pointer — the real diff is
        appended once at the end of the prompt by the caller."""
        diff_content: str
        if inline_diff:
            diff_content = context.diff
        else:
            diff_content = (
                "[Full diff is included below — review the "
                + f"{len(context.diff)}-character diff for issues]"
            )

        variables: dict[str, str] = {
            "code": diff_content,
            "diff": diff_content,
            "language": context.language,
            "file_paths": "\n".join(context.file_paths),
            "repository_context": context.repository_context or "",
            "issue_category_values": IssueCategory.prompt_values(),
            "issue_severity_values": ItemSeverity.prompt_values(),
        }

        if self._renderer is not None:
            return self._renderer.render(fragment.content, variables)

        content = fragment.content
        content = content.replace("{{ code }}", diff_content)
        content = content.replace("{{ diff }}", diff_content)
        content = content.replace("{{ language }}", context.language)
        content = content.replace("{{ file_paths }}", variables["file_paths"])
        content = content.replace(
            "{{ issue_category_values }}", variables["issue_category_values"],
        )
        content = content.replace(
            "{{ issue_severity_values }}", variables["issue_severity_values"],
        )
        content = content.replace(
            "{{ repository_context }}", context.repository_context or "",
        )
        return content
