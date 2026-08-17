"""Unit tests for ReviewContext value object."""

import pytest

from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext


class TestReviewContext:
    """Tests for ReviewContext immutable value object."""

    def test_creates_context_with_required_fields(self) -> None:
        """ReviewContext should capture PR review metadata."""
        context = ReviewContext(
            language="python",
            file_paths=["src/main.py", "tests/test_main.py"],
            diff="+def foo():\n+    pass",
        )

        assert context.language == "python"
        assert context.file_paths == ["src/main.py", "tests/test_main.py"]
        assert context.diff == "+def foo():\n+    pass"
        assert context.repository_context is None

    def test_accepts_optional_repository_context(self) -> None:
        """ReviewContext should accept optional repository context string."""
        context = ReviewContext(
            language="go",
            file_paths=["main.go"],
            diff="+func main() {}",
            repository_context="hexagonal architecture detected",
        )

        assert context.repository_context == "hexagonal architecture detected"

    @pytest.mark.parametrize(
        ("field", "value", "expected_msg"),
        [
            ("language", "", "language cannot be empty"),
            ("language", "   ", "language cannot be empty"),
            ("file_paths", [], "file_paths cannot be empty"),
        ],
    )
    def test_rejects_invalid_fields(
        self, field: str, value: object, expected_msg: str
    ) -> None:
        """ReviewContext should reject empty language and empty file_paths."""
        kwargs: dict[str, object] = {
            "language": "python",
            "file_paths": ["file.py"],
            "diff": "diff",
        }
        kwargs[field] = value

        with pytest.raises(ValueError, match=expected_msg):
            ReviewContext(**kwargs)

    def test_is_immutable(self) -> None:
        """ReviewContext should be immutable (frozen dataclass)."""
        context = ReviewContext(
            language="python",
            file_paths=["test.py"],
            diff="+code",
        )

        with pytest.raises(AttributeError):
            context.language = "go"
