"""ComposeReviewPromptAdapter — infrastructure adapter composing review prompts from fragments."""

from __future__ import annotations

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
from pr_auto_reviewer.infrastructure.fragments.token_budget_manager import (
    TokenBudgetManager,
)

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
    ) -> None:
        self._repository = repository
        self._renderer = renderer
        self._separator = separator
        self._budget_manager = (
            TokenBudgetManager(max_tokens) if max_tokens else None
        )

    def execute(self, context: ReviewContext) -> ComposedPrompt:
        """Execute the composition for *context*."""
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
        """Compose *fragments* into a single prompt for LLM consumption."""
        if not fragments:
            raise ValueError(
                "Cannot compose prompt from empty fragment list",
            )

        rendered_sections: list[str] = []
        fragment_ids: list[str] = []

        for fragment in fragments:
            rendered = self._render_fragment(fragment, context)
            rendered_sections.append(rendered)
            fragment_ids.append(fragment.id)

        final_content = self._separator.join(rendered_sections)

        if context.repository_context:
            final_content += self._separator + context.repository_context

        final_content += (
            self._separator
            + "**REMEMBER:** Output ONLY a raw JSON object. "
            + "No markdown. No code fences. No explanation. "
            + 'Start with "{" and end with "}".'
        )

        estimated_tokens = len(final_content) // 4

        return ComposedPrompt(
            content=final_content,
            fragments_used=fragment_ids,
            total_tokens=estimated_tokens,
        )

    def _render_fragment(
        self,
        fragment: PromptFragment,
        context: ReviewContext,
    ) -> str:
        """Render a single fragment with variable substitution."""
        variables: dict[str, str] = {
            "code": context.diff,
            "diff": context.diff,
            "language": context.language,
            "file_paths": "\n".join(context.file_paths),
            "repository_context": context.repository_context or "",
        }

        if self._renderer is not None:
            return self._renderer.render(fragment.content, variables)

        content = fragment.content
        content = content.replace("{{ code }}", context.diff)
        content = content.replace("{{ diff }}", context.diff)
        content = content.replace("{{ language }}", context.language)
        content = content.replace(
            "{{ repository_context }}", context.repository_context or "",
        )
        return content
