"""ReviewPullRequestService — orchestrates the full review flow for a PR."""

from __future__ import annotations

import logging

from ..commands.review_pull_request_command import ReviewPullRequestCommand
from ...domain.entities.pull_request import PullRequest
from ...domain.exceptions.empty_diff_error import EmptyDiffError
from ...domain.value_objects.code_review import CodeReview
from ...domain.value_objects.commit_sha import CommitSha
from ...domain.value_objects.pull_request_diff import PullRequestDiff
from ...domain.value_objects.pull_request_id import PullRequestId
from ..ports.outbound.pull_request_repository import PullRequestRepository
from ..ports.outbound.changeset_fetcher_port import ChangesetFetcherPort
from ..ports.outbound.review_context_factory_port import ReviewContextFactoryPort
from ..ports.outbound.llm_review_port import LlmReviewPort
from ..ports.outbound.review_publisher_port import ReviewPublisherPort
from ..ports.inbound.review_pull_request_use_case import ReviewPullRequestUseCase

logger = logging.getLogger(__name__)


class ReviewPullRequestService(ReviewPullRequestUseCase):
    """Orchestrates: load PR → check if review needed → fetch diff →
    build context + compose prompt via ReviewContextFactoryPort →
    LLM review → publish → persist.
    """

    def __init__(
        self,
        pr_repository: PullRequestRepository,
        changeset_fetcher: ChangesetFetcherPort,
        review_context_factory: ReviewContextFactoryPort,
        llm_review: LlmReviewPort,
        review_publisher: ReviewPublisherPort,
    ) -> None:
        self._pr_repository = pr_repository
        self._changeset_fetcher = changeset_fetcher
        self._review_context_factory = review_context_factory
        self._llm_review = llm_review
        self._review_publisher = review_publisher

    def execute(self, command: ReviewPullRequestCommand) -> None:
        self._log_start(command)

        pr = self._load_or_create_pull_request(command)

        if not self._needs_review(command, pr):
            self._handle_already_reviewed(command, pr)
            return

        diff = self._fetch_diff(command)
        composed = self._review_context_factory.build(
            command.pr_id, diff,
            pr_title=command.title,
            pr_description=command.description,
        )
        review = self._run_llm_review_with_prompt(composed)

        self._publish_review(command.pr_id, review)
        pr = self._record_review(pr, review, command.head_sha)
        self._persist(pr)

    def _log_start(self, command: ReviewPullRequestCommand) -> None:
        sha_str = str(command.head_sha.value[:7]) if command.head_sha else "none"
        logger.info("Starting review for PR %s (SHA: %s, force=%s)",
                    command.pr_id, sha_str, command.force)

    def _load_or_create_pull_request(
        self, command: ReviewPullRequestCommand
    ) -> PullRequest:
        pr = self._pr_repository.find(command.pr_id)
        if pr is None:
            pr = PullRequest(
                id=command.pr_id,
                title=command.title,
                head_sha=command.head_sha,
            )
        return pr

    def _needs_review(
        self, command: ReviewPullRequestCommand, pr: PullRequest
    ) -> bool:
        return command.force or pr.needs_review(command.head_sha)

    def _handle_already_reviewed(
        self, command: ReviewPullRequestCommand, pr: PullRequest
    ) -> None:
        sha_str = str(command.head_sha.value[:7]) if command.head_sha else "none"
        logger.info(
            "PR %s already reviewed at SHA %s, skipping",
            command.pr_id, sha_str,
        )
        self._pr_repository.save(pr)

    def _fetch_diff(
        self, command: ReviewPullRequestCommand
    ) -> PullRequestDiff:
        logger.debug("Fetching diff for PR %s", command.pr_id)
        diff = self._changeset_fetcher.fetch(command.pr_id, command.head_sha)
        if not diff.diff_content.strip():
            raise EmptyDiffError(
                f"Empty diff for {command.pr_id} at {command.head_sha}"
            )
        logger.info(
            "Diff fetched: %d chars, %d file(s) with contents",
            len(diff.diff_content),
            len(diff.file_contents),
        )
        if logger.isEnabledFor(logging.DEBUG):
            file_list = sorted(diff.file_contents.keys()) if diff.file_contents else []
            logger.debug("Files with full contents: %s", file_list or "(none)")
        return diff

    def _run_llm_review_with_prompt(self, prompt) -> CodeReview:
        """Send the composed prompt to the LLM and log the result."""
        logger.info("Sending composed prompt to LLM for review...")
        review = self._llm_review.review_prompt(prompt)
        logger.info(
            "LLM review complete: verdict=%s, items=%d, summary_len=%d",
            review.verdict.value,
            len(review.items),
            len(review.summary) if review.summary else 0,
        )
        return review

    def _publish_review(
        self, pr_id: PullRequestId, review: CodeReview
    ) -> None:
        logger.info("Publishing review to platform...")
        self._review_publisher.publish(pr_id, review)

    def _record_review(
        self, pr: PullRequest, review: CodeReview, head_sha: CommitSha
    ) -> PullRequest:
        return pr.add_review(review, head_sha)

    def _persist(self, pr: PullRequest) -> None:
        self._pr_repository.save(pr)
