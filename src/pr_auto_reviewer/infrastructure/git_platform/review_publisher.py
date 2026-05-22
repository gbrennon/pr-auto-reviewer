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
    ReviewVerdict.APPROVED: "APPROVED",
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
    ) -> None:
        self._client = client
        self._reviewer_username = reviewer_username
        self._reviewer_token = reviewer_token

    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None:
        verdict_event = _VERDICT_TO_EVENT.get(
            review.verdict, "COMMENT"
        )

        logger.info(
            "Publishing review for PR %s: verdict=%s, event=%s, "
            "items_count=%d, summary_len=%d",
            pr_id,
            review.verdict.value,
            verdict_event,
            len(review.items),
            len(review.summary) if review.summary else 0,
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
            self._client.post(
                reviewers_path, {"reviewers": [self._reviewer_username]},
            )
        except Exception:
            logger.warning(
                "Failed to request reviewer '%s' for %s (non-fatal)",
                self._reviewer_username,
                pr_id,
            )

        reviews_path = (
            f"/repos/{pr_id.repository}/pulls/{pr_id.number}/reviews"
        )
        try:
            self._client.post(
                reviews_path,
                {"event": verdict_event, "body": body},
            )
        except Exception as exc:
            raise ReviewPublishError(
                f"Failed to publish review for {pr_id}: {exc}"
            ) from exc
