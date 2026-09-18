"""Tests for InvalidSessionIdError."""

from pr_auto_reviewer.domain.exceptions import DomainError, InvalidSessionIdError


def test_invalid_session_id_error_is_domain_error() -> None:
    error = InvalidSessionIdError("invalid session id")

    assert isinstance(error, DomainError)
    assert str(error) == "invalid session id"
