from tests.fakes.fake_conversation_logger import FakeMarkdownConversationLogger


class TestFakeMarkdownConversationLogger:
    """Tests using the fake MarkdownConversationLogger."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake logger can be instantiated."""
        fake = FakeMarkdownConversationLogger()
        assert fake is not None
        assert hasattr(fake, "log_conversation")

    def test_fake_log_conversation(self) -> None:
        """Fake log_conversation tracks calls without writing to disk."""
        fake = FakeMarkdownConversationLogger()
        from datetime import datetime
        from pathlib import Path

        messages = []
        metadata = {
            "model": "test-model",
            "turns": 1,
            "verdict": "commented",
            "item_count": 0,
            "agent_role": "engineer",
        }

        phase_name = "Bug Hunt — Diff"
        pr_identifier = "owner/repo#1"

        result = fake.log_conversation(phase_name, pr_identifier, messages, metadata)

        # Verify call was tracked
        assert len(fake.log_conversation_calls) == 1
        call_phase, call_pr, call_msgs, call_meta = fake.log_conversation_calls[0]
        assert call_phase == phase_name
        assert call_pr == pr_identifier
        assert call_msgs == messages
        assert call_meta == metadata

        # Verify fake path is returned
        assert isinstance(result, Path)