"""Tests for ContextWindowExceededError."""

from pr_auto_reviewer.domain.exceptions import (
    ContextWindowExceededError,
    DomainError,
)


def test_context_window_exceeded_error_is_domain_error() -> None:
    error = ContextWindowExceededError("context window exceeded")

    assert isinstance(error, DomainError)
    assert str(error) == "context window exceeded"
