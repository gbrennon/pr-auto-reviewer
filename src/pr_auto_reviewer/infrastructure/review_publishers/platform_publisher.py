from __future__ import annotations

import logging
import re

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.exceptions.review_publish_error import (
    ReviewPublishError,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyFormatter,
)

logger = logging.getLogger(__name__)

_VERDICT_TO_EVENT: dict[ReviewVerdict, str] = {
    ReviewVerdict.APPROVED: "APPROVE",
    ReviewVerdict.CHANGES_REQUESTED: "REQUEST_CHANGES",
    ReviewVerdict.COMMENTED: "COMMENT",
}

_body_formatter = ReviewBodyFormatter()

class PlatformReviewPublisherAdapter(ReviewPublisherPort):
    def __init__(
        self,
        client: GitPlatformHttpClient,
        reviewer_token: str,
        reviewer_username: str,
        owner_client: GitPlatformHttpClient,
        review_mode: str = "formal",
    ) -> None:
        self._client = client
        self._reviewer_username = reviewer_username
        self._reviewer_token = reviewer_token
        self._review_mode = review_mode
        self._owner_client = owner_client

    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None:
        self._verify_tokens(pr_id)

        verdict_event = _VERDICT_TO_EVENT.get(review.verdict, "COMMENT")

        logger.info(
            "Publishing review for PR %s: verdict=%s, event=%s, "
            "items_count=%d, summary_len=%d, mode=%s",
            pr_id,
            review.verdict.value,
            verdict_event,
            len(review.items),
            len(review.summary) if review.summary else 0,
            self._review_mode,
        )

        if verdict_event == "COMMENT":
            non_blocking_items = [i for i in review.items if not i.severity.is_blocking]
            comment_review = CodeReview(
                verdict=review.verdict,
                reason=review.reason,
                summary=review.summary,
                items=non_blocking_items,
                suggestions=review.suggestions,
                praise=review.praise,
                model_used=review.model_used,
            )
            comment_body = _body_formatter.format(
                comment_review,
                start_number=self._count_existing_items(pr_id),
            )
            self._publish_comment(pr_id, comment_body)
            return

        blocking = [i for i in review.items if i.severity.is_blocking]
        body = _body_formatter.format(review, start_number=self._count_existing_items(pr_id))

        self._request_reviewer(pr_id)
        self._publish_formal_review(pr_id, review, verdict_event, body, blocking)

    def _verify_tokens(self, pr_id: PullRequestId) -> None:
        """Run preflight verification for both reviewer and owner tokens
        before publishing.  Wraps ``PreflightVerificationError`` as
        ``ReviewPublishError`` so the caller gets a uniform error type."""
        from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
            PreflightVerificationError,
        )
        try:
            self._client.verify_token_for_pr(pr_id)
        except PreflightVerificationError as exc:
            raise ReviewPublishError(
                f"Reviewer token preflight failed for {pr_id}: {exc}",
            ) from exc
        try:
            self._owner_client.verify_token_for_pr(pr_id)
        except PreflightVerificationError as exc:
            raise ReviewPublishError(
                f"Owner token preflight failed for {pr_id}: {exc}",
            ) from exc

    def _count_existing_items(self, pr_id: PullRequestId) -> int:
        """Return count of existing reviews on this PR, used to offset
        issue numbers so new items don't reuse numbers from prior reviews."""
        try:
            reviews = self._client.get(
                f"/repos/{pr_id.repository}/pulls/{pr_id.number}/reviews",
                repo=pr_id.repository,
            )
            return len(reviews) if isinstance(reviews, list) else 0
        except Exception:
            return 0

    def _request_reviewer(self, pr_id: PullRequestId) -> None:
        reviewers_path = (
            f"/repos/{pr_id.repository}/pulls/{pr_id.number}/requested_reviewers"
        )
        try:
            resp = self._owner_client.post(
                reviewers_path,
                {"reviewers": [self._reviewer_username]},
                repo=pr_id.repository,
            )
            if self._owner_client._platform_mode == "forgejo":
                logger.debug("Codeberg Request Reviewer Response: %s", resp)
            elif self._owner_client._platform_mode == "github":
                logger.debug("GitHub Request Reviewer Response: %s", resp)
        except Exception as exc:
            if self._owner_client._platform_mode == "github" and "422" in str(exc):
                logger.warning(
                    "GitHub reviewer request failed (422): reviewer '%s' may not have "
                    "write access to the repository. Add the reviewer as a collaborator "
                    "with write permissions on GitHub.",
                    self._reviewer_username,
                )
            else:
                logger.warning(
                    "Failed to request reviewer '%s' for %s (non-fatal)",
                    self._reviewer_username,
                    pr_id,
                )

    def _publish_comment(self, pr_id: PullRequestId, body: str) -> None:
        comments_path = (
            f"/repos/{pr_id.repository}/issues/{pr_id.number}/comments"
        )
        logger.info("Posting comment on %s: %d chars", pr_id, len(body))
        try:
            response = self._client.post(comments_path, {"body": body}, repo=pr_id.repository)
            if self._client._platform_mode == "forgejo":
                logger.debug("Codeberg Comment Response: %s", response)
        except Exception as exc:
            logger.warning(
                "Failed to post comment on %s (non-fatal): %s", pr_id, exc
            )

    def _publish_formal_review(
        self,
        pr_id: PullRequestId,
        review: CodeReview,
        verdict_event: str,
        body: str,
        blocking: list,
    ) -> None:
        reviews_path = f"/repos/{pr_id.repository}/pulls/{pr_id.number}/reviews"
        payload: dict[str, object] = {"event": verdict_event, "body": body}

        try:
            pr_info = self._owner_client.get(
                f"/repos/{pr_id.repository}/pulls/{pr_id.number}",
                repo=pr_id.repository,
            )
            payload["commit_id"] = pr_info["head"]["sha"]
        except Exception as exc:
            raise ReviewPublishError(
                f"Failed to resolve commit_id for formal review of {pr_id}: {exc}",
            ) from exc

        try:
            diff_text = self._owner_client.get_raw(
                f"/repos/{pr_id.repository}/pulls/{pr_id.number}.diff",
                headers={"Accept": "application/vnd.github.v3.diff"}
                if self._client._platform_mode == "github"
                else {},
                repo=pr_id.repository,
            )
            inline = self._build_inline_comments(diff_text, blocking, [])
            if inline:
                payload["comments"] = inline
                logger.info("Added %d inline comments to formal review", len(inline))
        except Exception as exc:
            logger.warning(
                "Failed to resolve inline comments for formal review: %s", exc,
            )

        try:
            response = self._client.post(reviews_path, payload, repo=pr_id.repository)
            if self._client._platform_mode == "forgejo":
                logger.debug("Codeberg Review Response Body: %s", response)
        except Exception as exc:
            if "403" in str(exc):
                logger.error(
                    "GitHub returned 403 Forbidden when publishing review. "
                    "Ensure the token has 'repo' scope and the reviewer is "
                    "authorized to post reviews on this repository."
                )
            raise ReviewPublishError(
                f"Failed to publish review for {pr_id}: {exc}"
            ) from exc
    def _build_inline_comments(
        self, diff_text: str, items: list, suggestions: list[dict],
    ) -> list[dict]:
        comments: list[dict] = []

        for item in items:
            pos_data = self._find_diff_position(
                diff_text, item.file_path, item.current_code
            )
            if pos_data:
                if self._client._platform_mode == "github":
                    comments.append(
                        {
                            "path": item.file_path,
                            "position": pos_data["position"],
                            "body": item.description,
                        }
                    )
                elif self._client._platform_mode == "forgejo":
                    line_no = pos_data["new_line"] or pos_data["old_line"]
                    key = "new_position" if pos_data["new_line"] else "old_position"
                    comments.append(
                        {
                            "path": item.file_path,
                            "body": item.description,
                            key: line_no,
                        }
                    )

        for s in suggestions:
            s_file = s.file
            s_code = s.current_code
            if not s_file or not s_code:
                continue
            pos_data = self._find_diff_position(diff_text, s_file, s_code)
            if pos_data:
                s_body = s.description
                if self._client._platform_mode == "github":
                    comments.append(
                        {
                            "path": s_file,
                            "position": pos_data["position"],
                            "body": s_body,
                        }
                    )
                elif self._client._platform_mode == "forgejo":
                    line_no = pos_data["new_line"] or pos_data["old_line"]
                    key = "new_position" if pos_data["new_line"] else "old_position"
                    comments.append(
                        {
                            "path": s_file,
                            "body": s_body,
                            key: line_no,
                        }
                    )

        return comments

    @staticmethod
    def _find_diff_position(
        diff_text: str, file_path: str | None, current_code: str
    ) -> dict[str, int] | None:
        if not file_path or not current_code:
            return None

        lines = diff_text.splitlines()
        in_target_file = False
        position = 0
        old_line = 0
        new_line = 0

        snippet_lines = [
            line.strip() for line in current_code.splitlines() if line.strip()
        ]
        if not snippet_lines:
            return None
        target_snippet = snippet_lines[0]

        for line in lines:
            if line.startswith("diff --git"):
                in_target_file = file_path in line
                position = 0
                old_line = 0
                new_line = 0
                continue

            if not in_target_file:
                continue

            if line.startswith("@@"):
                m = re.search(r"-(\d+)(?:,\d+)? \+(\d+)", line)
                if m:
                    old_line = int(m.group(1)) - 1
                    new_line = int(m.group(2)) - 1
                position += 1
                continue

            if line.startswith(("--- ", "+++ ")):
                continue

            position += 1

            if line.startswith("-"):
                old_line += 1
                content = line[1:]
                if target_snippet in content:
                    return {
                        "position": position,
                        "old_line": old_line,
                        "new_line": None,
                    }
            elif line.startswith("+"):
                new_line += 1
                content = line[1:]
                if target_snippet in content:
                    return {
                        "position": position,
                        "old_line": None,
                        "new_line": new_line,
                    }
            else:
                old_line += 1
                new_line += 1
                content = line
                if target_snippet in content:
                    return {
                        "position": position,
                        "old_line": old_line,
                        "new_line": new_line,
                    }

        return None
