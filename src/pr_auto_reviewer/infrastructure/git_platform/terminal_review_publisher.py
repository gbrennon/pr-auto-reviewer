"""TerminalReviewPublisherAdapter — prints review to stdout or file."""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.git_platform.review_publisher import (
    format_review_body,
)

logger = logging.getLogger(__name__)


def _review_to_json(review: CodeReview) -> str:
    """Serialize a CodeReview to pretty-printed JSON."""

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


class TerminalReviewPublisherAdapter(ReviewPublisherPort):
    """Outputs a CodeReview to stdout or a file, including JSON."""

    def __init__(self, output_dest: str = "stdout") -> None:
        self._output_dest = output_dest

    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None:
        body = format_review_body(review)
        json_text = _review_to_json(review)

        output_lines = [
            f"\n{'=' * 60}",
            f"  Review for {pr_id}",
            f"{'=' * 60}\n",
            "--- HUMAN-READABLE ---",
            body,
            f"\n--- JSON ---\n",
            json_text,
            f"\n{'=' * 60}\n",
        ]
        output = "\n".join(output_lines)

        logger.info(
            "Terminal output for PR %s: verdict=%s, items=%d -> %s",
            pr_id, review.verdict.value, len(review.items), self._output_dest,
        )

        if self._output_dest == "stdout":
            sys.stdout.write(output)
            sys.stdout.flush()
        else:
            dest_path = Path(self._output_dest)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(output)
            logger.info("Review written to %s", dest_path)
