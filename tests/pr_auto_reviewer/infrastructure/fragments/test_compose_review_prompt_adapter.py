"""Tests for ComposeReviewPromptAdapter using stub repository."""

from __future__ import annotations

import logging

import pytest

from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext
from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import (
    ComposeReviewPromptAdapter,
)
from tests.fakes.fragment_repository_fakes import StubFragmentRepository
from tests.fakes.prompt_renderer_fakes import FakePromptRenderer


class TestComposeReviewPromptAdapter:
    """Tests for the infrastructure adapter using stub repository."""

    @staticmethod
    def _make_adapter(
        by_language: list[PromptFragment] | None = None,
        universal: list[PromptFragment] | None = None,
        **kwargs,
    ) -> tuple[ComposeReviewPromptAdapter, StubFragmentRepository]:
        """Create an adapter wired to a stub repository with given fragments."""
        repo = StubFragmentRepository(by_language=by_language, universal=universal)
        adapter = ComposeReviewPromptAdapter(repository=repo, **kwargs)
        return adapter, repo

    def test_executes_full_composition_workflow(self) -> None:
        """Service should orchestrate selection -> composition -> result."""
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

        adapter, _repo = self._make_adapter(
            by_language=[python_fragment], universal=[universal_fragment],
        )
        result = adapter.execute(context)

        assert isinstance(result, ComposedPrompt)
        assert "# SOLID Principles" in result.content
        assert "# Python Review" in result.content
        assert "## Diff" in result.content
        assert "+def new_function():" in result.content
        assert "Full diff is included below" in result.content
        assert result.fragments_used == ["solid", "python-errors"]
        assert result.total_tokens > 0

    def test_raises_error_when_no_fragments_selected(self) -> None:
        """Service should raise ValueError when no fragments are available."""
        context = ReviewContext(
            language="unknown-language",
            file_paths=["test.xyz"],
            diff="+code",
        )

        adapter, _repo = self._make_adapter()
        with pytest.raises(
            ValueError,
            match="No fragments found for language: unknown-language",
        ):
            adapter.execute(context)

    def test_calls_repository_with_correct_language(self) -> None:
        """Service should pass language from context to repository."""
        context = ReviewContext(
            language="go",
            file_paths=["main.go"],
            diff="+func main() {}",
        )

        go_fragment = PromptFragment(
            id="go-concurrency",
            content="# Go review",
            language="go",
            priority=85,
            category="concurrency",
        )

        adapter, repo = self._make_adapter(
            by_language=[go_fragment], universal=[],
        )
        adapter.execute(context)

        assert repo.find_by_language_calls == ["go"]

    def test_execute_logs_entry_and_return(self, caplog) -> None:
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

        adapter, _repo = self._make_adapter(
            by_language=[
                PromptFragment(
                    id="py", content="# Python", language="python",
                    priority=80, category="errors",
                ),
            ],
            universal=[
                PromptFragment(
                    id="solid", content="# SOLID", language=None,
                    priority=100, category="architecture",
                ),
            ],
        )
        adapter.execute(context)

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

    def test_with_budget_constraints_filters_by_token_limit(self) -> None:
        """When max_tokens is configured, low-priority fragments are dropped."""
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

        adapter, _repo = self._make_adapter(
            by_language=[small_fragment], universal=[large_fragment],
            max_tokens=1000,
        )
        result = adapter.execute(context)

        assert "# Small" in result.content
        assert "large" not in (result.fragments_used or [])

    def test_with_renderer_uses_renderer_for_substitution(self) -> None:
        """Renderer receives the raw fragment template with actual diff variables."""

        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def f(): pass",
        )

        fragment = PromptFragment(
            id="py", content="Review {{ language }} code\n{{ diff }}",
            language="python", priority=80, category="errors",
        )

        mock_renderer = FakePromptRenderer(return_value="RENDERED_PROMPT")

        adapter, _repo = self._make_adapter(
            by_language=[fragment], universal=[],
            renderer=mock_renderer,
        )
        result = adapter.execute(context)

        assert mock_renderer.called
        call_args = mock_renderer.call_args
        template_arg: str = call_args[0][0]
        variables_arg: dict = call_args[0][1]
        assert "{{ diff }}" in template_arg
        assert "Full diff is included below" in variables_arg["diff"]
        assert "Full diff is included below" in variables_arg["code"]
        assert variables_arg["language"] == "python"
        assert "RENDERED_PROMPT" in result.content
        assert "## Diff" in result.content
        assert "+def f(): pass" in result.content

    def test_diff_appears_inline_within_fragments(self) -> None:
        """Diff is rendered inline inside each fragment, co-located with instructions."""
        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def foo():\n+    return 42",
        )

        fragment = PromptFragment(
            id="py", content="# Error Handling\n\n```\n{{ code }}\n```\n\nCheck bare excepts.",
            language="python", priority=80, category="errors",
        )

        adapter, _repo = self._make_adapter(
            by_language=[fragment], universal=[],
        )
        result = adapter.execute(context)

        assert "# Error Handling" in result.content
        assert "Check bare excepts." in result.content
        assert "## Diff" in result.content
        assert "+def foo():" in result.content
        assert "+    return 42" in result.content
        assert "Full diff is included below" in result.content

    def test_with_repository_context_appends_it(self) -> None:
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

        adapter, _repo = self._make_adapter(
            by_language=[fragment], universal=[],
        )
        result = adapter.execute(context)

        assert "Repo Structure" in result.content
