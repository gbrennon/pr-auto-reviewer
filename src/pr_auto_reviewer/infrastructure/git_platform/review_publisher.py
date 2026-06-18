"""GitReviewPublisherAdapter — wraps GitPlatformHttpClient to implement ReviewPublisherPort."""

from __future__ import annotations

import logging
from pathlib import Path

import jinja2

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.exceptions.review_publish_error import (
    ReviewPublishError,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

logger = logging.getLogger(__name__)

_VERDICT_TO_EVENT: dict[ReviewVerdict, str] = {
    ReviewVerdict.APPROVED: "APPROVE",
    ReviewVerdict.CHANGES_REQUESTED: "REQUEST_CHANGES",
    ReviewVerdict.COMMENTED: "COMMENT",
}


_TEMPLATES_DIR = Path(__file__).parent.parent / "llm" / "templates"
_review_output_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    keep_trailing_newline=True,
)


def format_review_body(review: CodeReview) -> str:
    """Render a CodeReview via the review_output.j2 Jinja2 template."""
    verdict_text = review.verdict.value.replace("_", " ").title()

    # Assign sequential numbers to suggestions (continuing from items)
    next_num = len(review.items) + 1
    suggestions = getattr(review, 'suggestions', [])
    numbered_suggestions = []
    for i, s in enumerate(suggestions):
        s_copy = dict(s)
        s_copy["number"] = next_num + i
        numbered_suggestions.append(s_copy)

    template = _review_output_env.get_template("review_output.j2")
    return template.render(
        review=review,
        verdict_text=verdict_text,
        suggestions=numbered_suggestions,
    )


class GitReviewPublisherAdapter(ReviewPublisherPort):
    """Publishes a CodeReview as a formal PR review on the remote platform."""

    def __init__(
        self,
        client: GitPlatformHttpClient,
        reviewer_token: str,
        reviewer_username: str,
        review_mode: str = "formal",
    ) -> None:
        self._client = client
        self._reviewer_username = reviewer_username
        self._reviewer_token = reviewer_token
        self._review_mode = review_mode

    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None:
        verdict_event = _VERDICT_TO_EVENT.get(
            review.verdict, "COMMENT"
        )
        
        # Codeberg/Gitea uses "APPROVED" instead of "APPROVE"
        if self._client._platform_mode == "codeberg" and verdict_event == "APPROVE":
            verdict_event = "APPROVED"

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

        body = format_review_body(review)

        logger.debug(
            "Review body preview: %s", body[:500] if body else "empty",
        )

        reviewers_path = (
            f"/repos/{pr_id.repository}/pulls/{pr_id.number}"
            f"/requested_reviewers"
        )
        try:
            resp = self._client.post(
                reviewers_path, {"reviewers": [self._reviewer_username]},
            )
            if self._client._platform_mode == "codeberg":
                logger.debug("Codeberg Request Reviewer Response: %s", resp)
        except Exception:
            logger.warning(
                "Failed to request reviewer '%s' for %s (non-fatal)",
                self._reviewer_username,
                pr_id,
            )

        if self._client._platform_mode == "github" and self._review_mode == "comment":
            reviews_path = (
                f"/repos/{pr_id.repository}/issues/{pr_id.number}/comments"
            )
            payload = {"body": body}
        else:
            reviews_path = (
                f"/repos/{pr_id.repository}/pulls/{pr_id.number}/reviews"
            )
            payload = {"event": verdict_event, "body": body}
            
            if self._client._platform_mode == "codeberg":
                payload["official"] = True
            
            # Formal reviews should include inline comments
            if self._review_mode == "formal":
                try:
                    # 1. Get diff to resolve positions
                    # The path for the diff is the same for both platforms (standard Git diff)
                    diff_text = self._client.get_raw(
                        f"/repos/{pr_id.repository}/pulls/{pr_id.number}.diff",
                        headers={"Accept": "application/vnd.github.v3.diff"} if self._client._platform_mode == "github" else {},
                    )
                    
                    # 2. Build inline comments for each review item
                    comments = []
                    for item in review.items:
                        pos_data = self._get_diff_position(diff_text, item.file_path, item.current_code)
                        if pos_data:
                            if self._client._platform_mode == "github":
                                comments.append({
                                    "path": item.file_path,
                                    "position": pos_data["position"],
                                    "body": item.description,
                                })
                            elif self._client._platform_mode == "codeberg":
                                # Codeberg uses old_position or new_position
                                # If it's a deleted line, use old_position. 
                                # If it's an added line, use new_position.
                                # If it's context, we prefer new_position.
                                line_no = pos_data["new_line"] or pos_data["old_line"]
                                key = "new_position" if pos_data["new_line"] else "old_position"
                                comments.append({
                                    "path": item.file_path,
                                    "body": item.description,
                                    key: line_no,
                                })
                    
                    if comments:
                        payload["comments"] = comments
                        logger.info("Added %d inline comments to formal review", len(comments))

                    # Both GitHub and Codeberg/Gitea typically require commit_id for reviews with comments
                    pr_info = self._client.get(f"/repos/{pr_id.repository}/pulls/{pr_id.number}")
                    payload["commit_id"] = pr_info["head"]["sha"]
                        
                except Exception as exc:
                    logger.error("Failed to resolve inline comments for formal review: %s", exc)

        try:
            response = self._client.post(
                reviews_path,
                payload,
            )
            if self._client._platform_mode == "codeberg":
                logger.debug("Codeberg Review Response Body: %s", response)
        except Exception as exc:
            # GitHub specifically returns 403 Forbidden if the token lacks sufficient
            # permissions to post a review or if the user is the PR author.
            if "403" in str(exc):
                logger.error(
                    "GitHub returned 403 Forbidden when publishing review. "
                    "Ensure the token has 'repo' scope and the reviewer is "
                    "authorized to post reviews on this repository."
                )
            raise ReviewPublishError(
                f"Failed to publish review for {pr_id}: {exc}"
            ) from exc

    def _get_diff_position(self, diff_text: str, file_path: str | None, current_code: str) -> dict[str, int] | None:
        """
        Finds the diff positions for the given code snippet.
        
        Returns a dictionary containing:
        - 'position': GitHub's 1-based diff index.
        - 'old_line': Raw line number in the old file.
        - 'new_line': Raw line number in the new file.
        """
        if not file_path or not current_code:
            return None

        lines = diff_text.splitlines()
        in_target_file = False
        position = 0
        old_line = 0
        new_line = 0
        
        snippet_lines = [l.strip() for l in current_code.splitlines() if l.strip()]
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
                # Parse @@ -old_start,old_count +new_start,new_count @@
                import re
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
                    return {"position": position, "old_line": old_line, "new_line": None}
            elif line.startswith("+"):
                new_line += 1
                content = line[1:]
                if target_snippet in content:
                    return {"position": position, "old_line": None, "new_line": new_line}
            else:
                old_line += 1
                new_line += 1
                content = line
                if target_snippet in content:
                    return {"position": position, "old_line": old_line, "new_line": new_line}
                    
        return None

