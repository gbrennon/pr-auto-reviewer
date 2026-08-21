import logging
import sys
from pathlib import Path

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyRenderer,
)
from pr_auto_reviewer.infrastructure.review_publishers.review_json_serializer import (
    ReviewJsonSerializer,
)

logger = logging.getLogger(__name__)


class TerminalReviewPublisherAdapter(ReviewPublisherPort):
    """Publish a review to the terminal as human-readable text plus JSON.

    Body formatting and JSON serialization are delegated to collaborators
    ``ReviewBodyRenderer`` and ``ReviewJsonSerializer``.
    """

    def __init__(
        self,
        body_renderer: ReviewBodyRenderer,
        output_path: str | None = None,
    ) -> None:
        self._body_renderer = body_renderer
        self._output_path = output_path
        self._serializer = ReviewJsonSerializer()

    def publish(
        self,
        pr_id: PullRequestId,
        review: CodeReview,
        diff: PullRequestDiff | None = None,
    ) -> None:
        body = self._body_renderer.render(review)
        json_text = self._serializer.serialize(review)

        output_lines = [
            f"\n{'=' * 60}",
            f"  Review for {pr_id}",
            f"{'=' * 60}\n",
            "--- HUMAN-READABLE ---",
            body,
            "\n--- JSON ---\n",
            json_text,
            f"\n{'=' * 60}\n",
        ]
        output = "\n".join(output_lines)

        if self._output_path is None:
            logger.info(
                "Terminal output for PR %s: verdict=%s, items=%d -> stdout",
                pr_id,
                review.verdict.value,
                len(review.items),
            )
            sys.stdout.write(output)
            sys.stdout.flush()
        else:
            dest_path = Path(self._output_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(output)
            logger.info("Review written to %s", dest_path)