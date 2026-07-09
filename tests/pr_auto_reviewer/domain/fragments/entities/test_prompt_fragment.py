"""Unit tests for PromptFragment value object."""

import pytest

from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment


class TestPromptFragment:
    """Tests for PromptFragment immutable value object."""

    def test_creates_fragment_with_required_fields(self) -> None:
        """PromptFragment should be constructible with required fields."""
        fragment = PromptFragment(
            id="python-error-handling",
            content="# Error Handling\n\nCheck for exceptions.",
            language="python",
            priority=80,
            category="error-handling",
        )

        assert fragment.id == "python-error-handling"
        assert fragment.content == "# Error Handling\n\nCheck for exceptions."
        assert fragment.language == "python"
        assert fragment.priority == 80
        assert fragment.category == "error-handling"

    def test_fragment_is_immutable(self) -> None:
        """PromptFragment should be immutable (frozen dataclass)."""
        fragment = PromptFragment(
            id="test-id",
            content="test content",
            language="python",
            priority=50,
            category="test",
        )

        with pytest.raises(AttributeError):
            fragment.id = "new-id"

    def test_creates_universal_fragment_without_language(self) -> None:
        """PromptFragment with language=None represents universal fragment."""
        fragment = PromptFragment(
            id="solid-principles",
            content="# SOLID\n\nCheck for violations.",
            language=None,
            priority=100,
            category="architecture",
        )

        assert fragment.language is None
        assert fragment.is_universal()

    @pytest.mark.parametrize(
        ("field", "value", "expected_msg"),
        [
            ("id", "", "id cannot be empty"),
            ("id", "   ", "id cannot be empty"),
            ("priority", -1, "priority must be non-negative"),
            ("priority", -100, "priority must be non-negative"),
        ],
    )
    def test_rejects_invalid_fields(
        self, field: str, value: object, expected_msg: str
    ) -> None:
        """PromptFragment should reject empty ID and negative priority."""
        kwargs = {
            "id": "valid-id",
            "content": "content",
            "language": "python",
            "priority": 50,
            "category": "test",
        }
        kwargs[field] = value

        with pytest.raises(ValueError, match=expected_msg):
            PromptFragment(**kwargs)

    def test_fragments_with_same_id_are_equal(self) -> None:
        """Fragments are equal if IDs match (value object equality)."""
        frag1 = PromptFragment(
            id="same-id",
            content="content A",
            language="python",
            priority=50,
            category="test",
        )
        frag2 = PromptFragment(
            id="same-id",
            content="content B",
            language="go",
            priority=80,
            category="other",
        )

        assert frag1 == frag2
        assert hash(frag1) == hash(frag2)

    def test_fragments_with_different_ids_are_not_equal(self) -> None:
        """Fragments with different IDs are not equal."""
        frag1 = PromptFragment(
            id="id-a", content="x", language=None, priority=1, category="x"
        )
        frag2 = PromptFragment(
            id="id-b", content="x", language=None, priority=1, category="x"
        )

        assert frag1 != frag2

    def test_default_metadata_is_empty_dict(self) -> None:
        """PromptFragment metadata defaults to empty dict."""
        fragment = PromptFragment(
            id="test",
            content="content",
            language="python",
            priority=50,
            category="test",
        )

        assert fragment.metadata == {}

    def test_accepts_explicit_metadata(self) -> None:
        """PromptFragment should accept custom metadata."""
        fragment = PromptFragment(
            id="test",
            content="content",
            language="python",
            priority=50,
            category="test",
            metadata={"source": "community", "version": 1},
        )

        assert fragment.metadata == {"source": "community", "version": 1}

    def test_not_equal_to_non_prompt_fragment(self) -> None:
        """PromptFragment.__eq__ returns NotImplemented for other types."""
        fragment = PromptFragment(
            id="test",
            content="content",
            language=None,
            priority=50,
            category="test",
        )
        assert fragment.__eq__("not a fragment") is NotImplemented
