from pathlib import Path
from typing import Any

import pytest

from pr_auto_reviewer.application.ports.outbound.changeset_fetcher_port import (
    ChangesetFetcherPort,
)
from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.application.ports.outbound.pull_request_repository_port import (
    PullRequestRepositoryPort,
)
from pr_auto_reviewer.application.ports.outbound.review_context_factory_port import (
    ReviewContextFactoryPort,
)
from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.application.services.multi_phase_review_orchestrator_service import (
    MultiPhaseReviewOrchestratorService,
)
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
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


class PullRequestRepositoryFake(PullRequestRepositoryPort):
    def __init__(self) -> None:
        self.saved: PullRequest | None = None

    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        return self.saved

    def save(self, pr: PullRequest) -> None:
        self.saved = pr

    def reset(self) -> None:
        self.saved = None


class ChangesetFetcherFake(ChangesetFetcherPort):
    def __init__(self, diff: PullRequestDiff) -> None:
        self._diff = diff

    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        return self._diff


class ReviewContextFactoryFake(ReviewContextFactoryPort):
    def build(
        self,
        pr_id: PullRequestId,
        diff: PullRequestDiff,
        pr_title: str | None = None,
        pr_description: str | None = None,
        target_branch: str = "",
    ) -> ComposedPrompt:
        return ComposedPrompt(
            content="review content",
            fragments_used=[],
            total_tokens=1,
        )


class LlmReviewFake(LlmReviewPort):
    def review(self, diff: PullRequestDiff, context: Any):
        raise AssertionError("single-turn review should not run")

    def review_prompt(self, prompt: ComposedPrompt):
        raise AssertionError("single-turn review should not run")


class ReviewPublisherFake(ReviewPublisherPort):
    def __init__(self) -> None:
        self.review = None

    def publish(
        self,
        pr_id: PullRequestId,
        review,
        diff: PullRequestDiff | None = None,
    ) -> None:
        self.review = review


@pytest.mark.e2e
class TestRelativeMetadataPathsE2E:
    def test_review_command_publishes_relative_metadata_paths(
        self, tmp_path: Path,
    ) -> None:
        relative_path = "crates/application/src/services/run_workflow_service.rs"
        absolute_path = tmp_path / relative_path
        absolute_path.parent.mkdir(parents=True)
        absolute_path.write_text("pub struct RunWorkflowService;\n")
        pr_id = PullRequestId(repository="owner/repo", number=153)
        head_sha = CommitSha("abc123")
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=head_sha,
            diff_content="diff --git a/file b/file\n",
            file_contents={relative_path: absolute_path.read_text()},
            clone_path=tmp_path,
        )
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
        command_bus.register(RunMultiPhaseReviewCommand, orchestrator.execute)
        publisher = ReviewPublisherFake()
        service = ReviewPullRequestService(
            pr_repository=PullRequestRepositoryFake(),
            changeset_fetcher=ChangesetFetcherFake(diff),
            review_context_factory=ReviewContextFactoryFake(),
            llm_review=LlmReviewFake(),
            review_publisher=publisher,
            command_bus=command_bus,
            plan=plan,
        )

        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id,
            head_sha=head_sha,
            title="Review path output",
        ))

        assert publisher.review is not None
        assert publisher.review.suggestions[0].file_path == relative_path
        assert publisher.review.praise[0].file_path == relative_path
