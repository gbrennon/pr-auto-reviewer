from pathlib import Path

import pytest

from pr_auto_reviewer.application.services.multi_phase_review_orchestrator_service import (
    MultiPhaseReviewOrchestratorService,
)
from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.review_phase import ReviewPhase
from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)


class PhaseResultHandler:
    def __init__(self, result: PhaseResult) -> None:
        self._result = result

    def __call__(self, command: RunAgentConversationCommand) -> PhaseResult:
        return self._result


@pytest.mark.integration
class TestMetadataPathIntegration:
    def test_public_orchestrator_normalizes_fallback_metadata_paths(
        self, tmp_path: Path,
    ) -> None:
        relative_path = "crates/application/src/services/run_workflow_service.rs"
        absolute_path = tmp_path / relative_path
        absolute_path.parent.mkdir(parents=True)
        absolute_path.write_text("pub struct RunWorkflowService;\n")
        phase_result = PhaseResult(
            items=[],
            llm_verdict="approved",
            llm_suggestions=[
                {"file": str(absolute_path), "description": "suggestion"},
            ],
            llm_praise=[
                {"file": str(absolute_path), "description": "praise"},
            ],
        )
        command_bus = InMemoryCommandBus({
            RunAgentConversationCommand: PhaseResultHandler(phase_result),
        })
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=command_bus,
            tool_factory=lambda repo_path, changed_files, base_sha: object(),
        )
        plan = ReviewPlan(
            phases=(ReviewPhase(
                phase_id="architect",
                phase_name="Architecture Review",
                system_prompt="",
            ),),
            methodology="m",
            suggestions_phase_id="architect",
        )

        review = orchestrator.execute(RunMultiPhaseReviewCommand(
            plan=plan,
            repo_path=tmp_path,
            changed_files=[relative_path],
            model="test",
            review_session="integration-test",
        ))

        assert review.suggestions[0].file_path == relative_path
        assert review.praise[0].file_path == relative_path
