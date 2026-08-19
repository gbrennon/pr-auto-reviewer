"""ReviewPullRequestService — orchestrates the full review flow for a PR."""

from __future__ import annotations

import logging
from typing import Any

from pr_auto_reviewer.domain.agent.review_plan import ReviewPlan
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)

from ...domain.entities.pull_request import PullRequest
from ...domain.entities.review_item import ReviewItem
from ...domain.exceptions.empty_diff_error import EmptyDiffError
from ...domain.services.review_item_factory import ReviewItemFactory
from ...domain.value_objects.code_review import CodeReview
from ...domain.value_objects.commit_sha import CommitSha
from ...domain.value_objects.issue_category import IssueCategory
from ...domain.value_objects.item_severity import ItemSeverity
from ...domain.value_objects.pull_request_diff import PullRequestDiff
from ...domain.value_objects.pull_request_id import PullRequestId
from ...domain.value_objects.review_verdict import ReviewVerdict
from ..ports.inbound.review_pull_request_use_case import ReviewPullRequestUseCase
from ..ports.outbound.changeset_fetcher_port import ChangesetFetcherPort
from ..ports.outbound.llm_review_port import LlmReviewPort
from ..ports.outbound.pull_request_repository import PullRequestRepository
from ..ports.outbound.review_context_factory_port import ReviewContextFactoryPort
from ..ports.outbound.review_publisher_port import ReviewPublisherPort
from ..ports.outbound.token_verifier_port import TokenVerifierPort

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
        token_verifier: TokenVerifierPort | None = None,
        command_bus: Any = None,
        conversation_logger: Any = None,
        plan: ReviewPlan | None = None,
    ) -> None:
        self._pr_repository = pr_repository
        self._changeset_fetcher = changeset_fetcher
        self._review_context_factory = review_context_factory
        self._llm_review = llm_review
        self._review_publisher = review_publisher
        self._token_verifier = token_verifier
        self._command_bus = command_bus
        self._conversation_logger = conversation_logger
        self._plan = plan

    def execute(self, command: ReviewPullRequestCommand) -> None:
        self._log_start(command)

        pr = self._load_or_create_pull_request(command)

        if not self._needs_review(command, pr):
            self._handle_already_reviewed(command, pr)
            return

        if self._token_verifier:
            self._token_verifier.verify(command.pr_id)

        diff = self._fetch_diff(command)
        description = self._augment_description(command.description, pr)
        composed = self._review_context_factory.build(
            command.pr_id, diff,
            pr_title=command.title,
            pr_description=description,
            target_branch=command.target_branch,
        )

        # Use multi-phase orchestrator if command_bus is available,
        # otherwise fall back to single-turn review
        if self._command_bus is not None:
            review = self._run_multi_phase_review(composed, command)
        else:
            review = self._run_single_turn_review(composed)
        review = self._add_deterministic_findings(review, diff)
        review = ReviewItemFactory.ensure_unique_ids(review)

        blocking_ids = self._extract_blocking_ids(review)

        # Resolve old blocking items no longer flagged in this review
        if pr.unresolved_blocking_ids:
            resolved = [
                id_ for id_ in pr.unresolved_blocking_ids
                if id_ not in blocking_ids
            ]
            if resolved:
                pr = pr.with_resolved_blocking(*resolved)

        # Track new or persistent blocking items
        if blocking_ids:
            pr = pr.with_unresolved_blocking(*blocking_ids)

        # Guard: don't approve while any blocking issues remain unresolved.
        # Override the LLM verdict to CHANGES_REQUESTED when old or new
        # blockers are still open, regardless of what the model returned.
        if (
            pr.unresolved_blocking_ids
            and review.verdict != ReviewVerdict.CHANGES_REQUESTED
        ):
            review = CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                reason=self._build_unresolved_reason(
                    pr.unresolved_blocking_ids, review,
                ),
                summary=review.summary,
                items=review.items,
                suggestions=review.suggestions,
                praise=review.praise,
                model_used=review.model_used,
            )

        self._publish_review(command.pr_id, review, diff)
        pr = self._record_review(pr, review, command.head_sha)
        self._persist(pr)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "REVIEW COMPLETE | pr=%s verdict=%s items=%d summary='%s'",
                command.pr_id,
                review.verdict.value,
                len(review.items),
                (review.summary or "")[:80],
            )
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
        if command.force:
            return True
        if pr.needs_review(command.head_sha):
            return True
        if command.review_requested and pr.reviews:
            logger.info("PR %s has been re-requested for review, reviewing again",
                        command.pr_id)
            return True
        return False

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

    def _run_multi_phase_review(
        self, composed: Any, command: ReviewPullRequestCommand,
    ) -> CodeReview:
        """Run multi-phase review by dispatching the command to the command bus.

        The command handler registered against ``RunMultiPhaseReviewCommand``
        executes the orchestrator, keeping this inbound service decoupled
        from the other inbound use case.
        """
        if self._plan is None:
            logger.warning(
                "No review plan wired; falling back to single-turn review"
            )
            return self._run_single_turn_review(composed)
        plan = self._plan
        diff = self._fetch_diff(command)
        if diff.clone_path is None:
            logger.warning(
                "PR %s has no local clone; falling back to single-turn review",
                command.pr_id,
            )
            return self._run_single_turn_review(composed)

        changed_files: list[str] = sorted(diff.file_contents.keys()) if diff.file_contents else []

        # Load existing PR to get existing review item IDs for unique ID generation
        existing_pr = self._pr_repository.find(command.pr_id)
        existing_item_ids = frozenset()
        if existing_pr is not None:
            existing_ids = set()
            for review in existing_pr.reviews:
                for item in review.items:
                    if item.id:
                        existing_ids.add(item.id)
                for suggestion in review.suggestions:
                    if suggestion.id:
                        existing_ids.add(suggestion.id)
                for praise in review.praise:
                    if praise.id:
                        existing_ids.add(praise.id)
            existing_item_ids = frozenset(existing_ids)

        return self._command_bus.dispatch(
            RunMultiPhaseReviewCommand(
                plan=plan,
                repo_path=diff.clone_path,
                changed_files=changed_files,
                model="code-review:latest",
                existing_item_ids=existing_item_ids,
            )
        )

    def _run_single_turn_review(self, prompt) -> CodeReview:
        """Run single-turn LLM review.

        When no command_bus is available, this method sends the composed
        prompt to the LLM once and returns the result. This is the fallback
        path when the full multi-phase infrastructure is not wired.
        """
        logger.info("Sending composed prompt to LLM for single-turn review...")
        review = self._llm_review.review_prompt(prompt)
        logger.info(
            "LLM review complete: verdict=%s, items=%d, summary_len=%d",
            review.verdict.value,
            len(review.items),
            len(review.summary) if review.summary else 0,
        )
        return review

    def _find_noisy_info_logs(self, diff_text: str) -> list[ReviewItem]:
        current_file = ""
        items: list[ReviewItem] = []
        noisy_markers = (
            "GET ", "GET_RAW ", "POST ", "return:", "keys=", "chars",
            "tokens", "fragments", "params=", "body_keys=", "diff=",
            "files=", "commits=", "response:",
        )

        for line in diff_text.splitlines():
            if line.startswith("+++ b/"):
                current_file = line.removeprefix("+++ b/")
                continue
            if not line.startswith("+") or line.startswith("+++"):
                continue

            current_code = line[1:]
            stripped = current_code.strip()
            if "logger.info(" not in stripped:
                continue
            if not any(marker in stripped for marker in noisy_markers):
                continue

            suggested_fix = current_code.replace("logger.info(", "logger.debug(", 1)
            items.append(
                ReviewItem(
                    severity=ItemSeverity.MINOR,
                    category=IssueCategory.MAINTAINABILITY,
                    file_path=current_file or None,
                    description=(
                        "This diagnostic log is emitted at info level, so normal "
                        "runs will include request/response or internal workflow "
                        "details. Move it to debug so verbose output is opt-in."
                    ),
                    current_code=current_code,
                    suggested_fix=suggested_fix,
                    id=ReviewItemFactory._generate_id(),
                )
            )
            if len(items) >= 5:
                break

        return items

    def _add_deterministic_findings(
        self, review: CodeReview, diff: PullRequestDiff
    ) -> CodeReview:
        """Add concrete fallback findings for noisy logging regressions."""
        log_items = self._find_noisy_info_logs(diff.diff_content)
        if not log_items:
            return review

        log_code = {item.current_code for item in log_items}
        merged_items = log_items + [
            item for item in review.items
            if item.current_code not in log_code
        ]
        merged_items = merged_items[:8]

        summary = review.summary or (
            "The PR adds diagnostic logging that would be visible during normal "
            "runs. Request/response and internal workflow details should stay "
            "behind debug or verbose logging."
        )
        praise = review.praise or [
            ReviewItem(
                severity=ItemSeverity.INFO,
                category=IssueCategory.GENERAL,
                file_path="",
                description=(
                    "The logging additions are consistently placed around the "
                    "operations they observe."
                ),
                line="",
                id="",
                current_code="",
                suggested_fix="",
            )
        ]
        return CodeReview(
            verdict=review.verdict,
            reason=review.reason,
            summary=summary,
            items=merged_items,
            suggestions=review.suggestions,
            praise=praise,
            model_used=review.model_used,
        )


    def _augment_description(
        self, description: str | None, pr: PullRequest,
    ) -> str | None:
        """Append pending blocking items text when there are unresolved blockers."""
        if not pr.unresolved_blocking_ids:
            return description
        items: list[ReviewItem] = []
        for review in pr.reviews:
            for item in review.items:
                if item.id and item.id in pr.unresolved_blocking_ids:
                    items.append(item)
        if not items:
            return description

        lines = ["\n## Previously Unresolved Blocking Items", ""]
        for item in items:
            location = f" ({item.file_path})" if item.file_path else ""
            lines.append(
                f"- **#{item.id}** [{item.severity.value}]"
                f" {item.description}{location}"
            )
        lines.append("")
        lines.append(
            "Please verify whether these items have been addressed in this update."
        )
        pending = "\n".join(lines)

        if description:
            return description + "\n" + pending
        return pending

    def _extract_blocking_ids(self, review: CodeReview) -> list[str]:
        """Return IDs of review items whose severity is blocking."""
        return [
            item.id
            for item in review.items
            if item.is_blocking and item.id
        ]

    def _build_unresolved_reason(
        self, unresolved_ids: frozenset[str], review: CodeReview,
    ) -> str:
        """Build a reason string listing each unresolved blocking item.

        Looks up item details (description, severity, file path) from the
        current review so the PR author sees exactly what's still blocking.
        """
        item_by_id = {item.id: item for item in review.items if item.id}
        lines = [
            ("This PR cannot be approved because the following blocking "
             "issues remain unresolved:"),
            "",
        ]
        for id_ in sorted(unresolved_ids):
            item = item_by_id.get(id_)
            if item is not None:
                location = f" ({item.file_path})" if item.file_path else ""
                lines.append(
                    f"- **#{id_}** [{item.severity.value}]"
                    f" {item.description}{location}"
                )
            else:
                lines.append(f"- **#{id_}** (details from prior review)")
        return "\n".join(lines)

    def _publish_review(
        self, pr_id: PullRequestId, review: CodeReview, diff: PullRequestDiff
    ) -> None:
        logger.info("Publishing review to platform...")
        self._review_publisher.publish(pr_id, review, diff)
    def _record_review(
        self, pr: PullRequest, review: CodeReview, head_sha: CommitSha,
    ) -> PullRequest:
        return pr.add_review(review, head_sha)

    def _persist(self, pr: PullRequest) -> None:
        self._pr_repository.save(pr)

