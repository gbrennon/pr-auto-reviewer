"""Unit tests for ComposeReviewPromptAdapter — mocked ports."""

import logging
from unittest.mock import Mock

import pytest

from pr_auto_reviewer.application.ports.outbound.fragment_repository_port import (
    FragmentRepositoryPort,
)
from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import (
    ComposeReviewPromptAdapter,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext


class TestComposeReviewPromptAdapter:
    """Tests for the infrastructure adapter — all ports mocked."""

    @pytest.fixture
    def mock_repository(self) -> Mock:
        """Mock FragmentRepositoryPort."""
        return Mock(spec=FragmentRepositoryPort)

    @pytest.fixture
    def service(
        self, mock_repository: Mock,
    ) -> ComposeReviewPromptAdapter:
        """Adapter wired with mocked repository, no renderer."""
        return ComposeReviewPromptAdapter(repository=mock_repository)

    def test_executes_full_composition_workflow(
        self,
        service: ComposeReviewPromptAdapter,
        mock_repository: Mock,
    ) -> None:
        """Service should orchestrate selection → composition → result."""
        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def new_function():\n+    pass",
        )

        python_fragment = PromptFragment(
            id="python-errors",
            content="# Python Review\n\n{{ code }}",
            language="python",
            priority=80,
            category="errors",
        )
        universal_fragment = PromptFragment(
            id="solid",
            content="# SOLID Principles",
            language=None,
            priority=100,
            category="architecture",
        )

        mock_repository.find_by_language.return_value = [python_fragment]
        mock_repository.find_universal.return_value = [universal_fragment]

        result = service.execute(context)

        assert isinstance(result, ComposedPrompt)
        assert "# SOLID Principles" in result.content
        assert "# Python Review" in result.content
        # Diff is included once in a ## Diff section at the end.
        assert "## Diff" in result.content
        assert "+def new_function():" in result.content
        # Fragment uses a placeholder instead of the diff inline.
        assert "Full diff is included below" in result.content
        assert result.fragments_used == ["solid", "python-errors"]
        assert result.total_tokens > 0

    def test_raises_error_when_no_fragments_selected(
        self,
        service: ComposeReviewPromptAdapter,
        mock_repository: Mock,
    ) -> None:
        """Service should raise ValueError when no fragments are available."""
        context = ReviewContext(
            language="unknown-language",
            file_paths=["test.xyz"],
            diff="+code",
        )

        mock_repository.find_by_language.return_value = []
        mock_repository.find_universal.return_value = []

        with pytest.raises(
            ValueError,
            match="No fragments found for language: unknown-language",
        ):
            service.execute(context)

    def test_calls_repository_with_correct_language(
        self,
        service: ComposeReviewPromptAdapter,
        mock_repository: Mock,
    ) -> None:
        """Service should pass language from context to repository."""
        context = ReviewContext(
            language="go",
            file_paths=["main.go"],
            diff="+func main() {}",
        )

        mock_repository.find_by_language.return_value = [
            PromptFragment(
                id="go-concurrency",
                content="# Go review",
                language="go",
                priority=85,
                category="concurrency",
            ),
        ]
        mock_repository.find_universal.return_value = []

        service.execute(context)

        mock_repository.find_by_language.assert_called_once_with("go")

    def test_execute_logs_entry_and_return(
        self,
        service: ComposeReviewPromptAdapter,
        mock_repository: Mock,
        caplog,
    ) -> None:
        """Entry and return are logged when adapter logging is enabled."""
        caplog.set_level(
            logging.INFO,
            logger="pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter",
        )

        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def new_function():\n+    pass",
        )

        mock_repository.find_by_language.return_value = [
            PromptFragment(
                id="py", content="# Python", language="python",
                priority=80, category="errors",
            ),
        ]
        mock_repository.find_universal.return_value = [
            PromptFragment(
                id="solid", content="# SOLID", language=None,
                priority=100, category="architecture",
            ),
        ]

        service.execute(context)

        entry = [
            r.message for r in caplog.records
            if "ComposeReviewPromptAdapter.execute(" in r.message
        ]
        ret = [
            r.message for r in caplog.records
            if "ComposeReviewPromptAdapter return" in r.message
        ]

        assert len(entry) == 1
        assert "language=python" in entry[0]
        assert "files=1" in entry[0]
        assert "diff=" in entry[0]

        assert len(ret) == 1
        assert "chars=" in ret[0]
        assert "tokens=" in ret[0]


    def test_with_budget_constraints_filters_by_token_limit(
        self, mock_repository: Mock,
    ) -> None:
        """When max_tokens is configured, low-priority fragments are dropped."""
        from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import ComposeReviewPromptAdapter

        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def f(): pass",
        )

        large_fragment = PromptFragment(
            id="large", content="x" * 5000,
            language=None, priority=100, category="test",
        )
        small_fragment = PromptFragment(
            id="small", content="# Small",
            language="python", priority=80, category="errors",
        )

        mock_repository.find_by_language.return_value = [small_fragment]
        mock_repository.find_universal.return_value = [large_fragment]

        # Budget of ~1000 tokens (~4000 chars) — only small fragment fits
        adapter = ComposeReviewPromptAdapter(
            repository=mock_repository, max_tokens=1000,
        )
        result = adapter.execute(context)

        assert "# Small" in result.content
        assert "large" not in (result.fragments_used or [])

    def test_with_renderer_uses_renderer_for_substitution(
        self, mock_repository: Mock,
    ) -> None:
        """Renderer receives the raw fragment template with actual diff variables."""
        from unittest.mock import Mock as StdMock
        from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import ComposeReviewPromptAdapter

        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def f(): pass",
        )

        fragment = PromptFragment(
            id="py", content="Review {{ language }} code\n{{ diff }}",
            language="python", priority=80, category="errors",
        )

        mock_repository.find_by_language.return_value = [fragment]
        mock_repository.find_universal.return_value = []

        mock_renderer = StdMock()
        mock_renderer.render.return_value = "RENDERED_PROMPT"

        adapter = ComposeReviewPromptAdapter(
            repository=mock_repository, renderer=mock_renderer,
        )
        result = adapter.execute(context)

        assert mock_renderer.render.called
        # Renderer receives the raw template with {{ diff }}.
        # When called from _compose_prompt (inline_diff=False), diff is a placeholder.
        call_args = mock_renderer.render.call_args
        template_arg: str = call_args[0][0]
        variables_arg: dict = call_args[0][1]
        assert "{{ diff }}" in template_arg
        assert "Full diff is included below" in variables_arg["diff"]
        assert "Full diff is included below" in variables_arg["code"]
        assert variables_arg["language"] == "python"
        # The rendered content appears in the composed prompt.
        assert "RENDERED_PROMPT" in result.content
        # The real diff is in the ## Diff section.
        assert "## Diff" in result.content
        assert "+def f(): pass" in result.content

    def test_diff_appears_inline_within_fragments(
        self, mock_repository: Mock,
    ) -> None:
        """Diff is rendered inline inside each fragment, co-located with instructions."""
        from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import ComposeReviewPromptAdapter

        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def foo():\n+    return 42",
        )

        fragment = PromptFragment(
            id="py", content="# Error Handling\n\n```\n{{ code }}\n```\n\nCheck bare excepts.",
            language="python", priority=80, category="errors",
        )

        mock_repository.find_by_language.return_value = [fragment]
        mock_repository.find_universal.return_value = []

        adapter = ComposeReviewPromptAdapter(repository=mock_repository)
        result = adapter.execute(context)

        # Diff is included once in a ## Diff section at end, not inline per fragment.
        assert "# Error Handling" in result.content
        assert "Check bare excepts." in result.content
        assert "## Diff" in result.content
        assert "+def foo():" in result.content
        assert "+    return 42" in result.content
        # Fragment uses a placeholder, not the real diff.
        assert "Full diff is included below" in result.content

    def test_with_repository_context_appends_it(
        self, mock_repository: Mock,
    ) -> None:
        """Repository context is appended to the prompt when present."""
        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def f(): pass",
            repository_context="## Repo Structure\n```\nsrc/\n```",
        )

        fragment = PromptFragment(
            id="py", content="# Python",
            language="python", priority=80, category="errors",
        )

        mock_repository.find_by_language.return_value = [fragment]
        mock_repository.find_universal.return_value = []

        adapter = ComposeReviewPromptAdapter(repository=mock_repository)
        result = adapter.execute(context)

        assert "Repo Structure" in result.content
