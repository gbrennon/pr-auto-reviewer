"""ReviewPullRequestService — orchestrates the full review flow for a PR."""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.messages.commands.audit_remediation_command import (
    AuditRemediationCommand,
)
from pr_auto_reviewer.domain.value_objects.review_audit_result import (
    ReviewAuditResult,
)
from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan
from pr_auto_reviewer.domain.value_objects.review_execution_result import (
    ReviewExecutionResult,
)

from ...domain.entities.pull_request import PullRequest
from ...domain.entities.review_item import ReviewItem
from ...domain.exceptions.empty_diff_error import EmptyDiffError
from ...domain.services.review_item_factory import ReviewItemFactory
from ...domain.services.suggestion_scope_policy import SuggestionScopePolicy
from ...domain.value_objects.code_review import CodeReview
from ...domain.value_objects.commit_sha import CommitSha
from ...domain.value_objects.issue_category import IssueCategory
from ...domain.value_objects.item_severity import ItemSeverity
from ...domain.value_objects.pull_request_diff import PullRequestDiff
from ...domain.value_objects.pull_request_id import PullRequestId
from ...domain.value_objects.review_item_status import ReviewItemStatus
from ...domain.value_objects.review_verdict import ReviewVerdict
from ...domain.value_objects.review_item_lifecycle import ReviewItemLifecycle
from ...domain.value_objects.sub_review_guardrails import SubReviewGuardrails
from ..ports.inbound.review_pull_request_port import ReviewPullRequestPort
from ..ports.outbound.changeset_fetcher_port import ChangesetFetcherPort
from ..ports.outbound.llm_review_port import LlmReviewPort
from ..ports.outbound.pull_request_repository_port import PullRequestRepositoryPort
from ..ports.outbound.review_context_factory_port import ReviewContextFactoryPort
from ..ports.outbound.review_publisher_port import ReviewPublisherPort
from ..ports.outbound.token_verifier_port import TokenVerifierPort

logger = logging.getLogger(__name__)

class ReviewPullRequestService(ReviewPullRequestPort):
    """Orchestrates: load PR → check if review needed → fetch diff →
    build context + compose prompt via ReviewContextFactoryPort →
    LLM review → publish → persist.
    """

    def __init__(
        self,
        pr_repository: PullRequestRepositoryPort,
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

    def execute(self, command: ReviewPullRequestCommand) -> ReviewExecutionResult:
        self._log_start(command)

        pr = self._load_or_create_pull_request(command)

        if not self._needs_review(command, pr):
            self._handle_already_reviewed(command, pr)
            return ReviewExecutionResult(
                reviewed=False,
                duration_seconds=None,
            )

        review_started_at = self._now()

        if self._token_verifier:
            self._token_verifier.verify(command.pr_id)

        diff = self._fetch_diff(command)
        audit_result = self._audit_history(pr, diff)
        description = self._augment_description(command.description, pr)
        composed = self._review_context_factory.build(
            command.pr_id, diff,
            pr_title=command.title,
            pr_description=description,
            target_branch=command.target_branch,
        )

        if self._command_bus is not None:
            review = self._run_multi_phase_review(
                composed, command, diff, pr, audit_result,
            )
        else:
            review = self._run_single_turn_review(composed)
        review = self._filter_suggestion_scope(review, diff)
        review = self._add_deterministic_findings(review, diff)
        review = self._merge_audited_history(
            review,
            audit_result,
            self._historical_ids(pr),
            review_contains_audit=(
                self._command_bus is not None
                and self._plan is not None
                and diff.clone_path is not None
            ),
        )
        if audit_result is not None:
            pr = pr.apply_audit_result(audit_result)

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
        duration_seconds = self._now() - review_started_at
        pr = self._record_review(
            pr,
            review,
            command.head_sha,
            command.review_request_event_id,
            command.latest_review_id,
            command.latest_review_dismissed,
        )
        self._persist(pr)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "REVIEW COMPLETE | pr=%s verdict=%s items=%d summary='%s'",
                command.pr_id,
                review.verdict.value,
                len(review.items),
                (review.summary or "")[:80],
            )
        return ReviewExecutionResult(
            reviewed=True,
            duration_seconds=duration_seconds,
        )
    @staticmethod
    def _now() -> float:
        return time.perf_counter()

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
        if command.force or pr.needs_review(command.head_sha):
            return True
        if (
            command.review_request_event_id is not None
            and command.review_request_event_id
            > (pr.last_review_request_event_id or 0)
        ):
            return True
        return self._platform_review_requires_review(command, pr)

    @staticmethod
    def _platform_review_requires_review(
        command: ReviewPullRequestCommand, pr: PullRequest
    ) -> bool:
        if not command.latest_review_dismissed or command.latest_review_id is None:
            return False
        if pr.last_platform_review_id is None:
            return True
        if command.latest_review_id > pr.last_platform_review_id:
            return True
        return (
            command.latest_review_id == pr.last_platform_review_id
            and not pr.last_platform_review_dismissed
        )

    def _handle_already_reviewed(
        self, command: ReviewPullRequestCommand, pr: PullRequest
    ) -> None:
        sha_str = str(command.head_sha.value[:7]) if command.head_sha else "none"
        logger.info(
            "PR %s already reviewed at SHA %s, skipping",
            command.pr_id, sha_str,
        )
        if command.review_request_event_id is not None:
            pr = pr.record_review_request_event(command.review_request_event_id)
        if command.latest_review_id is not None:
            pr = pr.record_platform_review(
                command.latest_review_id,
                command.latest_review_dismissed,
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
            file_list = diff.changed_paths
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
        self,
        composed: Any,
        command: ReviewPullRequestCommand,
        diff: PullRequestDiff,
        existing_pr: PullRequest,
        audit_result: ReviewAuditResult | None,
    ) -> CodeReview:
        """Run multi-phase review with the pre-phase audit history."""
        if self._plan is None:
            logger.warning(
                "No review plan wired; falling back to single-turn review"
            )
            return self._run_single_turn_review(composed)
        if diff.clone_path is None:
            logger.warning(
                "PR %s has no local clone; falling back to single-turn review",
                command.pr_id,
            )
            return self._run_single_turn_review(composed)

        changed_files: list[str] = diff.changed_paths
        base_sha: str = (
            str(diff.base_sha) if diff.base_sha is not None else ""
        )
        existing_item_ids = self._historical_ids(existing_pr)
        audit = audit_result or ReviewAuditResult(
            items=(), suggestions=(), lifecycles=(),
        )

        logger.info(
            "Dispatching multi-phase review for %s (changed files: %s)",
            command.pr_id,
            ", ".join(changed_files) or "(none)",
        )
        return self._command_bus.dispatch(
            RunMultiPhaseReviewCommand(
                plan=self._plan,
                repo_path=diff.clone_path,
                changed_files=changed_files,
                model="code-review:latest",
                review_session=datetime.now(UTC).strftime("%Y%m%d_%H%M%S"),
                base_sha=base_sha,
                existing_item_ids=existing_item_ids,
                prior_items=list(audit.items),
                prior_suggestions=list(audit.suggestions),
            )
        )


    @staticmethod
    def _content_signature(item: ReviewItem) -> tuple[str, str]:
        """Return the whitespace-normalized content signature of *item*."""
        code = " ".join(item.current_code.split())
        path = str(item.file_path) if item.file_path else ""
        if code:
            return (path, code)
        desc = " ".join(item.description.split())
        return (path, desc)
    def _audit_history(
        self,
        pr: PullRequest,
        diff: PullRequestDiff,
    ) -> ReviewAuditResult | None:
        """Audit every historical item before running normal review phases."""
        if self._command_bus is None or diff.clone_path is None:
            return self._fail_closed_history(pr, diff)
        audit = self._command_bus.dispatch(
            AuditRemediationCommand(
                prior_items=list(pr.historical_items()),
                prior_suggestions=list(pr.historical_suggestions()),
                prior_lifecycles=pr.lifecycles,
                repo_path=diff.clone_path,
                changed_files=diff.changed_paths,
                review_session=datetime.now(UTC).strftime("%Y%m%d_%H%M%S"),
                base_sha=str(diff.base_sha) if diff.base_sha else "",
                current_sha=str(diff.head_sha),
            )
        )
        if isinstance(audit, ReviewAuditResult):
            if not self._audit_covers_history(pr, audit):
                return self._fail_closed_history(pr, diff)
            return audit
        return self._fail_closed_history(pr, diff)

    @staticmethod
    def _audit_covers_history(
        pr: PullRequest, audit: ReviewAuditResult,
    ) -> bool:
        """Return whether an audit result includes every identified record."""
        historical_records = (
            *pr.historical_items(),
            *pr.historical_suggestions(),
        )
        if any(not record.id for record in historical_records):
            return False
        expected_ids = {record.id for record in historical_records}
        actual_ids = {
            record.id
            for record in (*audit.items, *audit.suggestions)
            if record.id
        }
        return expected_ids <= actual_ids

    def _fail_closed_history(
        self, pr: PullRequest, diff: PullRequestDiff,
    ) -> ReviewAuditResult:
        """Carry history forward as open when remediation auditing is unavailable."""
        audit_sha = str(diff.head_sha)
        lifecycles = tuple(
            lifecycle.audit(
                audit_sha,
                present=True,
                proof=False,
                explanation="Remediation audit was unavailable; record remains open.",
            )
            if lifecycle.is_active
            else lifecycle
            for lifecycle in pr.lifecycles
        )
        lifecycle_by_id = {
            lifecycle.item_id: lifecycle for lifecycle in lifecycles
        }
        return ReviewAuditResult(
            items=self._project_fail_closed(
                pr.historical_items(), lifecycle_by_id,
            ),
            suggestions=self._project_fail_closed(
                pr.historical_suggestions(), lifecycle_by_id,
            ),
            lifecycles=lifecycles,
        )

    @staticmethod
    def _project_fail_closed(
        records: tuple[ReviewItem, ...],
        lifecycles: dict[str, ReviewItemLifecycle],
    ) -> tuple[ReviewItem, ...]:
        """Materialize fail-closed lifecycle status on historical records."""
        projected: list[ReviewItem] = []
        for record in records:
            lifecycle = lifecycles.get(record.id)
            if lifecycle is None:
                projected.append(
                    replace(
                        record,
                        status=(
                            ReviewItemStatus.OPEN
                            if record.is_active
                            else record.status
                        ),
                    )
                )
                continue
            projected.append(
                replace(
                    record,
                    status=lifecycle.status,
                    status_explanation=lifecycle.status_explanation,
                )
            )
        return tuple(projected)

    @staticmethod
    def _historical_ids(pr: PullRequest) -> frozenset[str]:
        """Return every ID reserved by persisted evidence and lifecycles."""
        ids = {
            item.id
            for item in (*pr.historical_items(), *pr.historical_suggestions())
            if item.id
        }
        ids.update(
            item.id
            for review in pr.reviews
            for item in (*review.items, *review.suggestions, *review.praise)
            if item.id
        )
        ids.update(
            lifecycle.item_id for lifecycle in pr.lifecycles if lifecycle.item_id
        )
        return frozenset(ids)

    @staticmethod
    def _is_active(item: ReviewItem) -> bool:
        """Return whether an item may suppress a newly reported duplicate."""
        return item.status in (
            ReviewItemStatus.CREATED,
            ReviewItemStatus.OPEN,
        )

    def _merge_audited_history(
        self,
        review: CodeReview,
        audit_result: ReviewAuditResult | None,
        reserved_ids: frozenset[str],
        review_contains_audit: bool = False,
    ) -> CodeReview:
        """Merge audited records and mark genuinely new records as CREATED."""
        if audit_result is None:
            audited_items: tuple[ReviewItem, ...] = ()
            audited_suggestions: tuple[ReviewItem, ...] = ()
        else:
            audited_items = audit_result.items
            audited_suggestions = audit_result.suggestions

        historical_ids = {
            item.id for item in (*audited_items, *audited_suggestions) if item.id
        }
        active_items = {
            item.id for item in audited_items if item.id and self._is_active(item)
        }
        active_suggestions = {
            item.id
            for item in audited_suggestions
            if item.id and self._is_active(item)
        }
        active_item_signatures = {
            self._content_signature(item)
            for item in audited_items
            if self._is_active(item)
        }
        active_suggestion_signatures = {
            self._content_signature(item)
            for item in audited_suggestions
            if self._is_active(item)
        }
        audited_item_keys = (
            {
                (item.id, self._content_signature(item))
                for item in audited_items
                if self._is_active(item)
            }
            if review_contains_audit
            else set()
        )
        audited_suggestion_keys = (
            {
                (item.id, self._content_signature(item))
                for item in audited_suggestions
                if self._is_active(item)
            }
            if review_contains_audit
            else set()
        )
        reserved = set(reserved_ids) | set(historical_ids)

        def prepare(
            entries: list[ReviewItem],
            active_ids: set[str],
            active_signatures: set[tuple[str, str]],
            audited_keys: set[tuple[str, tuple[str, str]]],
        ) -> list[ReviewItem]:
            result: list[ReviewItem] = []
            for entry in entries:
                key = (entry.id, self._content_signature(entry))
                if key in audited_keys:
                    continue
                if (
                    entry.id in active_ids
                    or self._content_signature(entry) in active_signatures
                ):
                    continue
                item = replace(
                    entry,
                    status=ReviewItemStatus.CREATED,
                    status_explanation=(
                        entry.status_explanation or "First appearance in review"
                    ),
                )
                if not item.id or item.id in reserved:
                    item = replace(
                        item,
                        id=ReviewItemFactory.generate_id(frozenset(reserved)),
                    )
                reserved.add(item.id)
                result.append(item)
            return result

        fresh_items = prepare(
            list(review.items),
            active_items,
            active_item_signatures,
            audited_item_keys,
        )
        fresh_suggestions = prepare(
            list(review.suggestions),
            active_suggestions,
            active_suggestion_signatures,
            audited_suggestion_keys,
        )
        merged_items = list(audited_items) + fresh_items
        merged_suggestions = list(audited_suggestions) + fresh_suggestions
        praise: list[ReviewItem] = []
        for entry in review.praise:
            if not entry.id or entry.id in reserved:
                entry = replace(
                    entry,
                    id=ReviewItemFactory.generate_id(frozenset(reserved)),
                )
            reserved.add(entry.id)
            praise.append(entry)
        derived_verdict = SubReviewGuardrails().verdict_for(merged_items)
        verdict = (
            ReviewVerdict.CHANGES_REQUESTED
            if review.verdict is ReviewVerdict.CHANGES_REQUESTED
            else derived_verdict
        )
        return replace(
            review,
            items=merged_items,
            suggestions=merged_suggestions,
            praise=praise,
            verdict=verdict,
        )

    def _filter_suggestion_scope(
        self, review: CodeReview, diff: PullRequestDiff,
    ) -> CodeReview:
        """Keep only safe, changed-file-evidenced suggestions."""
        kept: list[ReviewItem] = []
        for suggestion in review.suggestions:
            materialized = self._materialize_suggestion(suggestion, diff)
            if materialized is not None:
                kept.append(materialized)
        return replace(review, suggestions=kept)

    def _materialize_suggestion(
        self, suggestion: ReviewItem, diff: PullRequestDiff,
    ) -> ReviewItem | None:
        """Normalize a suggestion only when its target is safe and evidenced."""
        file_path = str(suggestion.file_path or "").strip()
        if not file_path:
            return suggestion
        normalized = self._safe_suggestion_path(file_path, diff)
        if normalized is None:
            return None
        if not SuggestionScopePolicy.keep(
            file_path, suggestion.description, diff.changed_paths, normalized,
        ):
            return None
        return replace(suggestion, file_path=normalized)

    def _safe_suggestion_path(
        self, file_path: str, diff: PullRequestDiff,
    ) -> str | None:
        repo_path = diff.clone_path
        if repo_path is None:
            return file_path if file_path in diff.changed_paths else None
        if self._is_external_absolute_path(file_path, repo_path):
            return None
        normalized = ReviewItemFactory._normalize_file_path(
            file_path, repo_path, diff.changed_paths,
        )
        if normalized is None:
            return None
        if (
            normalized not in diff.changed_paths
            and not self._exists_inside_repo(normalized, repo_path)
        ):
            return None
        return normalized

    @staticmethod
    def _is_external_absolute_path(file_path: str, repo_path: Path) -> bool:
        """Return whether an absolute citation resolves outside the clone."""
        cited_path = Path(file_path)
        return (
            cited_path.is_absolute()
            and not cited_path.resolve().is_relative_to(repo_path.resolve())
        )

    @staticmethod
    def _exists_inside_repo(file_path: str, repo_path: Path) -> bool:
        """Return whether a path exists inside the clone."""
        resolved = (repo_path / file_path).resolve()
        return resolved.is_relative_to(repo_path.resolve()) and resolved.exists()

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
                    id=ReviewItemFactory.generate_id(),
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
        """Return IDs of open review items whose severity is blocking."""
        return [
            item.id
            for item in review.items
            if item.is_open_blocking and item.id
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
        self,
        pr: PullRequest,
        review: CodeReview,
        head_sha: CommitSha,
        review_request_event_id: int | None = None,
        latest_review_id: int | None = None,
        latest_review_dismissed: bool = False,
    ) -> PullRequest:
        if review_request_event_id is not None:
            pr = pr.record_review_request_event(review_request_event_id)
        if latest_review_id is not None:
            pr = pr.record_platform_review(
                latest_review_id,
                latest_review_dismissed,
            )
        return pr.add_review(review, head_sha)

    def _persist(self, pr: PullRequest) -> None:
        self._pr_repository.save(pr)

