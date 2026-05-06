"""Tests for LlmResponseMalformedError."""

import pytest

from pr_auto_reviewer.domain.exceptions.llm_response_malformed_error import (
    LlmResponseMalformedError,
)


class TestLlmResponseMalformedError:
    """Tests for LlmResponseMalformedError."""

    def test_stores_raw_text(self) -> None:
        """Stores the raw LLM response text."""
        raw = "invalid json response"
        error = LlmResponseMalformedError(raw)

        assert error.raw_text == raw

    def test_inherits_from_domain_error(self) -> None:
        """Inherits from DomainError."""
        error = LlmResponseMalformedError("test")

        assert isinstance(error, Exception)

    def test_has_default_message(self) -> None:
        """Has a default error message."""
        error = LlmResponseMalformedError("test")

        assert "LLM response could not be parsed" in str(error)

    def test_can_raise_and_catch(self) -> None:
        """Can be raised and caught as DomainError."""
        raw = "some malformed response"
        error = LlmResponseMalformedError(raw)

        with pytest.raises(Exception) as exc_info:
            raise error

        assert exc_info.value is error