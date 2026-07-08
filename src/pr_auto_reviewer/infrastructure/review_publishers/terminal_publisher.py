from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyFormatter,
)

logger = logging.getLogger(__name__)

_body_formatter = ReviewBodyFormatter()

class TerminalReviewPublisherAdapter(ReviewPublisherPort):
    def __init__(self, output_path: str | None = None) -> None:
        self._output_path = output_path

    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None:
        body = _body_formatter.format(review)
        json_text = self._review_to_json(review)

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

    @staticmethod
    def _review_to_json(review: CodeReview) -> str:
        def _convert(item):
            if isinstance(item, ReviewItem):
                return {
                    "number": item.number,
                    "severity": item.severity.value,
                    "category": item.category.value,
                    "file_path": item.file_path,
                    "description": item.description,
                    "line": item.line,
                    "id": item.id,
                    "current_code": item.current_code,
                    "suggested_fix": item.suggested_fix,
                }
            return item

        data = {
            "verdict": review.verdict.value,
            "reason": review.reason,
            "summary": review.summary,
            "items": [_convert(it) for it in review.items],
            "suggestions": review.suggestions,
            "praise": review.praise,
            "model_used": review.model_used,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
