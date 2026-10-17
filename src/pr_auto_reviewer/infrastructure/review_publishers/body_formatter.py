from __future__ import annotations

import logging
from pathlib import Path

import jinja2

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_item_status import ReviewItemStatus

logger = logging.getLogger(__name__)


class ReviewBodyRenderer:
    """Renders review bodies using Jinja2 templates.

    Dependency-injected template directory allows flexible template
    locations without hardcoding paths in the class.
    """

    def __init__(self, template_dir: Path) -> None:
        self._template_dir = template_dir
        _jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            keep_trailing_newline=True,
        )
        self._template = _jinja_env.get_template("review_output.j2")

    def render(
        self,
        review: CodeReview,
        audit_records: list[ReviewItem] | None = None,
    ) -> str:
        """Render a review with optional remediation evidence."""
        return self._template.render(
            review=review,
            verdict_text=self._verdict_text(review),
            items=self._numbered_items(review.items),
            praise=self._numbered_praise(review.praise),
            suggestions=self._numbered_items(review.suggestions),
            audit_records=self._numbered_audit(audit_records or []),
        )

    @staticmethod
    def _verdict_text(review: CodeReview) -> str:
        return review.verdict.value.replace("_", " ").title()

    @staticmethod
    def _numbered_items(items: list[ReviewItem]) -> list[dict[str, object]]:
        return [
            {
                "id": item.id,
                "status": item.status,
                "status_explanation": item.status_explanation,
                "severity": item.severity,
                "category": item.category,
                "file_path": item.file_path,
                "line": item.line,
                "description": item.description,
                "current_code": item.current_code,
                "suggested_fix": item.suggested_fix,
            }
            for item in items
        ]

    @staticmethod
    def _numbered_praise(items: list[ReviewItem]) -> list[dict[str, object]]:
        return [
            {"description": item.description, "file_path": item.file_path}
            for item in items
        ]

    @staticmethod
    def _numbered_audit(
        records: list[ReviewItem],
    ) -> list[dict[str, object]]:
        return [
            {
                "id": record.id,
                "status": record.status,
                "is_blocking": record.is_blocking,
                "file_path": record.file_path,
                "line": record.line,
                "description": record.description,
                "status_explanation": record.status_explanation,
            }
            for record in records
            if record.status in {
                ReviewItemStatus.OPEN,
                ReviewItemStatus.RESOLVED,
            }
        ]
