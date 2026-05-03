"""ReviewPullRequestService — orchestrates the full review flow for a PR."""

from __future__ import annotations

from ..commands.review_pull_request_command import ReviewPullRequestCommand
from ..commands.process_issue_commands_command import ProcessIssueCommandsCommand
from ...domain.entities.pull_request import PullRequest
from ...domain.exceptions.empty_diff_error import EmptyDiffError
from ...domain.value_objects.review_verdict import ReviewVerdict
from ..ports.outbound.pull_request_repository import PullRequestRepository
from ..ports.outbound.changeset_fetcher_port import ChangesetFetcherPort
from ..ports.outbound.repository_context_port import RepositoryContextPort
from ..ports.outbound.llm_review_port import LlmReviewPort
from ..ports.outbound.review_publisher_port import ReviewPublisherPort
from ..ports.outbound.command_bus_port import CommandBusPort
from ..ports.inbound.review_pull_request_use_case import ReviewPullRequestUseCase


class ReviewPullRequestService(ReviewPullRequestUseCase):
    """Orchestrates: load PR → check if review needed → fetch diff →
    build context → LLM review → publish → persist → dispatch commands.

    Contains zero business logic — only coordination of domain objects
    and outbound ports.
    """

    def __init__(
        self,
        pr_repository: PullRequestRepository,
        changeset_fetcher: ChangesetFetcherPort,
        repository_context: RepositoryContextPort,
        llm_review: LlmReviewPort,
        review_publisher: ReviewPublisherPort,
        command_bus: CommandBusPort,
    ) -> None:
        self._pr_repository = pr_repository
        self._changeset_fetcher = changeset_fetcher
        self._repository_context = repository_context
        self._llm_review = llm_review
        self._review_publisher = review_publisher
        self._command_bus = command_bus

    def execute(self, command: ReviewPullRequestCommand) -> None:
        # 1. Load or create aggregate
        pr = self._pr_repository.find(command.pr_id)
        if pr is None:
            pr = PullRequest(
                id=command.pr_id,
                title=command.title,
                head_sha=command.head_sha,
            )

        # 2. Idempotency guard — already reviewed this SHA?
        if not pr.needs_review(command.head_sha):
            self._pr_repository.save(pr)
            self._command_bus.dispatch(
                ProcessIssueCommandsCommand(
                    pr_id=command.pr_id, head_sha=command.head_sha
                )
            )
            return

        # 3. Fetch diff
        diff = self._changeset_fetcher.fetch(command.pr_id, command.head_sha)
        if not diff.diff_content.strip():
            raise EmptyDiffError(
                f"Empty diff for {command.pr_id} at {command.head_sha}"
            )

        # 4. Build review context
        context = self._repository_context.fetch(command.pr_id)

        # 5. Run LLM review
        review = self._llm_review.review(diff, context)

        # 6. Publish to platform
        self._review_publisher.publish(command.pr_id, review)

        # 7. Record review on aggregate
        pr = pr.add_review(review, command.head_sha)

        # 8. Persist
        self._pr_repository.save(pr)

        # 9. If approved, dispatch issue-commands processing
        if review.verdict == ReviewVerdict.APPROVED:
            self._command_bus.dispatch(
                ProcessIssueCommandsCommand(
                    pr_id=command.pr_id, head_sha=command.head_sha
                )
            )
