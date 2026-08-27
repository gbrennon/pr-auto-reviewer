from ._helpers import *


class TestTurnObserverWiring:
    """The advisor observes turns and blocks repeat offenders."""

    def _observer(self, grades):
                
        class _ScriptedObserver:
            def __init__(self, script):
                self._script = list(script)

            def observe(
                self,
                peer_content: str,
                phase_name: str,
                review_session: str,
                pr_identifier_service: str = "",
                changed_files: list[str] | None = None,
            ) -> AdvisorDirective:
                return AdvisorDirective(
                    grade=SubAgentGrade.from_phrase(self._script.pop(0)),
                    feedback="off task",
                )

        return _ScriptedObserver(grades)

    def test_blocking_turn_injects_advisor_feedback(self) -> None:
        chat = MagicMock()
        chat.send.side_effect = [
            '{"action": "run_git", "args": "log --oneline -1"}',
            '{"verdict": "approved", "reason": "clean", "items": []}',
        ]
        bus = InMemoryCommandBus()
        bus.register(
            ParseReviewTurnCommand,
            TurnParserService(ReviewResponseParser()).execute,
        )
        service = AgentConversationService(
            chat_port=chat,
            command_bus=bus,
            max_turns=6,
            turn_observer=self._observer(["whatever", "okok"]),
        )
        result = service.execute(_command(_StubToolExecution()))

        assert result.llm_verdict == "approved"
        # The turn following the drifted one opens with the correction.
        post_drift_messages = chat.send.call_args_list[1][0][0]
        advisor_notes = [
            m for m in post_drift_messages
            if m.role == "user" and "ADVISOR" in m.content
        ]
        assert len(advisor_notes) == 1
        assert "off task" in advisor_notes[0].content

    def test_observer_is_not_called_on_the_final_verdict_turn(self) -> None:
        observed: list[str] = []

        class _RecordingObserver:
            def observe(
                self,
                peer_content: str,
                phase_name: str,
                review_session: str,
                pr_identifier_service: str = "",
                changed_files: list[str] | None = None,
            ) -> AdvisorDirective:
                observed.append(peer_content)
                return AdvisorDirective(grade=SubAgentGrade.OKOK)

        chat = MagicMock()
        chat.send.side_effect = [
            '{"action": "run_git", "args": "log --oneline -1"}',
            '{"verdict": "approved", "reason": "clean", "items": []}',
        ]
        bus = InMemoryCommandBus()
        bus.register(
            ParseReviewTurnCommand,
            TurnParserService(ReviewResponseParser()).execute,
        )
        service = AgentConversationService(
            chat_port=chat,
            command_bus=bus,
            max_turns=6,
            turn_observer=_RecordingObserver(),
        )

        result = service.execute(_command(_StubToolExecution()))

        assert result.llm_verdict == "approved"
        assert len(observed) == 1
        assert '"verdict"' not in observed[0]

    def test_repeated_blocks_abort_the_phase(self) -> None:
        import pytest as _pytest
        
                
        
        chat = MagicMock()
        chat.send.side_effect = [
            '{"action": "run_git", "args": "log --oneline -1"}',
            '{"action": "run_git", "args": "log --oneline -2"}',
        ]
        bus = InMemoryCommandBus()
        bus.register(
            ParseReviewTurnCommand,
            TurnParserService(ReviewResponseParser()).execute,
        )
        service = AgentConversationService(
            chat_port=chat,
            command_bus=bus,
            max_turns=6,
            turn_observer=self._observer(["don't do this!", "don't do this!"]),
            max_advisor_blocks=2,
        )

        with _pytest.raises(LlmUnavailableError, match="Advisor blocked"):
            service.execute(_command(_StubToolExecution()))

