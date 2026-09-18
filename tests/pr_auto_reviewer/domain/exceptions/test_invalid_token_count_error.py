"""Tests for InvalidTokenCountError."""

from pr_auto_reviewer.domain.exceptions import DomainError, InvalidTokenCountError


def test_invalid_token_count_error_is_domain_error() -> None:
    error = InvalidTokenCountError("invalid token count")

    assert isinstance(error, DomainError)
    assert str(error) == "invalid token count"
