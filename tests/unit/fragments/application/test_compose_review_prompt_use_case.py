"""Unit tests for ComposeReviewPromptService — mocked ports."""

from unittest.mock import Mock

import pytest

from pr_auto_reviewer.application.ports.outbound.fragment_repository_port import (
    FragmentRepositoryPort,
)
from pr_auto_reviewer.application.services.compose_review_prompt_service import (
    ComposeReviewPromptService,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext


class TestComposeReviewPromptService:
    """Tests for the application service — all ports mocked."""

    @pytest.fixture
    def mock_repository(self) -> Mock:
        """Mock FragmentRepositoryPort."""
        return Mock(spec=FragmentRepositoryPort)

    @pytest.fixture
    def service(
        self, mock_repository: Mock,
    ) -> ComposeReviewPromptService:
        """Service wired with mocked repository, no renderer."""
        return ComposeReviewPromptService(repository=mock_repository)

    def test_executes_full_composition_workflow(
        self,
        service: ComposeReviewPromptService,
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
        assert "+def new_function():" in result.content
        assert result.fragments_used == ["solid", "python-errors"]
        assert result.total_tokens > 0

    def test_raises_error_when_no_fragments_selected(
        self,
        service: ComposeReviewPromptService,
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
        service: ComposeReviewPromptService,
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

