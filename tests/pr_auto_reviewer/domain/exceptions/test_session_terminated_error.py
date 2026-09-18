"""Tests for SessionTerminatedError."""

from pr_auto_reviewer.domain.exceptions import DomainError, SessionTerminatedError


def test_session_terminated_error_is_domain_error() -> None:
    error = SessionTerminatedError("session terminated")

    assert isinstance(error, DomainError)
    assert str(error) == "session terminated"
