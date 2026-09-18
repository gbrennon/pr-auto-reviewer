"""Tests for SessionStatus."""

from pr_auto_reviewer.domain.value_objects.session_status import SessionStatus


class TestSessionStatus:
    """Session lifecycle status behavior."""

    def test_terminal_statuses_are_completed_and_failed(self) -> None:
        assert SessionStatus.COMPLETED.is_terminal
        assert SessionStatus.FAILED.is_terminal
        assert not SessionStatus.ACTIVE.is_terminal

    def test_only_open_statuses_accept_messages(self) -> None:
        assert SessionStatus.INITIALIZED.can_accept_messages
        assert SessionStatus.ACTIVE.can_accept_messages
        assert not SessionStatus.COMPACTING.can_accept_messages
        assert not SessionStatus.COMPLETED.can_accept_messages
