"""Tests for SessionId."""

import pytest

from pr_auto_reviewer.domain.exceptions import InvalidSessionIdError
from pr_auto_reviewer.domain.value_objects.session_id import SessionId


class TestSessionId:
    """Session identifier validation and generation."""

    def test_accepts_safe_identifiers(self) -> None:
        assert str(SessionId("review_01.alpha-2")) == "review_01.alpha-2"

    @pytest.mark.parametrize("value", ["", "bad id", "bad/slash", "bad!mark"])
    def test_rejects_invalid_identifiers(self, value: str) -> None:
        with pytest.raises(InvalidSessionIdError):
            SessionId(value)

    def test_generate_produces_unique_safe_identifiers(self) -> None:
        first = SessionId.generate()
        second = SessionId.generate("review")

        assert str(first).startswith("session_")
        assert str(second).startswith("review_")
        assert first != second
