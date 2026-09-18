"""Tests for the Session aggregate root."""

import pytest

from pr_auto_reviewer.domain.entities.session import Session
from pr_auto_reviewer.domain.exceptions import SessionTerminatedError
from pr_auto_reviewer.domain.value_objects.context_window import ContextWindow
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.session_id import SessionId
from pr_auto_reviewer.domain.value_objects.session_status import SessionStatus
from pr_auto_reviewer.domain.value_objects.token_count import TokenCount
from pr_auto_reviewer.domain.value_objects.token_usage import TokenUsage


class TestSession:
    """Session lifecycle and context behavior."""

    def test_initial_state_and_message_addition(self) -> None:
        session = Session(
            id=SessionId("test"),
            context_window=ContextWindow(max_tokens=TokenCount(100)),
        )

        updated = session.add_message(
            ConversationMessage(role="user", content="hello"), TokenCount(10)
        )

        assert session.status is SessionStatus.INITIALIZED
        assert updated.status is SessionStatus.ACTIVE
        assert len(updated.conversation) == 1
        assert updated.context_window.current_tokens == TokenCount(10)

    def test_terminal_session_rejects_messages(self) -> None:
        session = Session(
            id=SessionId("test"),
            context_window=ContextWindow(max_tokens=TokenCount(100)),
        ).complete()

        with pytest.raises(SessionTerminatedError, match="completed"):
            session.add_message(ConversationMessage(role="user", content="late"))

    def test_compaction_reduces_context_and_increments_count(self) -> None:
        session = Session(
            id=SessionId("test"),
            context_window=ContextWindow(max_tokens=TokenCount(1000)),
        )
        messages = [ConversationMessage(role="system", content="rules")]
        messages.extend(
            ConversationMessage(role="user", content=f"message {index} " + "x" * 80)
            for index in range(10)
        )
        for message in messages:
            session = session.add_message(message)

        compacted, result = session.compact_context()

        assert result.did_compact
        assert compacted.compaction_count == 1
        assert len(compacted.conversation) < len(session.conversation)
        assert compacted.context_window.current_tokens < session.context_window.current_tokens
        assert compacted.conversation.messages[0].role == "system"

    def test_record_usage_aggregates_tokens(self) -> None:
        session = Session(
            id=SessionId("test"),
            context_window=ContextWindow(max_tokens=TokenCount(100)),
        )

        updated = session.record_usage(TokenUsage(TokenCount(3), TokenCount(4))).record_usage(
            TokenUsage(TokenCount(2), TokenCount(1))
        )

        assert updated.token_usage.total_tokens == TokenCount(10)

    def test_complete_and_fail_transition_to_terminal_states(self) -> None:
        session = Session(
            id=SessionId("test"),
            context_window=ContextWindow(max_tokens=TokenCount(100)),
        )

        assert session.complete().status is SessionStatus.COMPLETED
        assert session.fail().status is SessionStatus.FAILED
