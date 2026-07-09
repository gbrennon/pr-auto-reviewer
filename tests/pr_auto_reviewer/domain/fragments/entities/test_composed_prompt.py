"""Unit tests for ComposedPrompt value object."""

import pytest

from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt

class TestComposedPrompt:
    """Tests for ComposedPrompt immutable value object."""

    def test_creates_composed_prompt_with_required_fields(self) -> None:
        """ComposedPrompt should hold final rendered content and telemetry."""
        prompt = ComposedPrompt(
            content="# Review\n\nCheck this code...",
            fragments_used=["python-errors", "solid-principles"],
            total_tokens=150,
        )

        assert prompt.content == "# Review\n\nCheck this code..."
        assert prompt.fragments_used == ["python-errors", "solid-principles"]
        assert prompt.total_tokens == 150

    def test_is_immutable(self) -> None:
        """ComposedPrompt should be immutable (frozen dataclass)."""
        prompt = ComposedPrompt(
            content="# Review",
            fragments_used=["frag-1"],
            total_tokens=50,
        )

        with pytest.raises(AttributeError):
            prompt.content = "new content"

    @pytest.mark.parametrize(
        ("field", "value", "expected_msg"),
        [
            ("content", "", "content cannot be empty"),
            ("content", "   ", "content cannot be empty"),
            ("total_tokens", -1, "total_tokens must be non-negative"),
            ("total_tokens", -50, "total_tokens must be non-negative"),
        ],
    )
    def test_rejects_invalid_fields(
        self, field: str, value: object, expected_msg: str
    ) -> None:
        """ComposedPrompt should reject empty content and negative token count."""
        kwargs: dict[str, object] = {
            "content": "valid content",
            "fragments_used": ["f-1"],
            "total_tokens": 10,
        }
        kwargs[field] = value

        with pytest.raises(ValueError, match=expected_msg):
            ComposedPrompt(**kwargs)

    def test_allows_zero_tokens(self) -> None:
        """ComposedPrompt should allow zero tokens (empty prompt edge case)."""
        prompt = ComposedPrompt(
            content="minimal",
            fragments_used=[],
            total_tokens=0,
        )

        assert prompt.total_tokens == 0

    def test_allows_empty_fragments_used(self) -> None:
        """ComposedPrompt should allow empty fragment list."""
        prompt = ComposedPrompt(
            content="some content",
            fragments_used=[],
            total_tokens=10,
        )

        assert prompt.fragments_used == []
