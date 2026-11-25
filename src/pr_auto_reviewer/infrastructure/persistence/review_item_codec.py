"""JsonFilePullRequestRepository — persistence adapter for PullRequest aggregate.

Implements PullRequestRepositoryPort. Replaces the STATE_FILE bash script approach
with atomic writes and structured deserialization.
"""

from __future__ import annotations

import logging

from ...domain.entities.review_item import ReviewItem
from ...domain.value_objects.issue_category import IssueCategory
from ...domain.value_objects.item_severity import ItemSeverity

logger = logging.getLogger(__name__)

_STATE_KEY_SEPARATOR = "/"


class ReviewItemCodec:
    """Serialize and deserialize ``ReviewItem`` to and from JSON dicts."""

    @staticmethod
    def serialize(item: ReviewItem) -> dict:
        return {
            "id": item.id,
            "severity": item.severity.value,
            "category": item.category.value,
            "file_path": item.file_path,
            "description": item.description,
            "line": item.line,
            "current_code": item.current_code,
            "suggested_fix": item.suggested_fix,
            "root_cause": item.root_cause,
            "reproduction": item.reproduction,
            "acceptance_criteria": item.acceptance_criteria,
            "detection_method": item.detection_method,
            "status": item.status.value,
            "status_explanation": item.status_explanation,
        }

    @staticmethod
    def deserialize(raw_item: dict) -> ReviewItem:
        return ReviewItem(
            severity=ItemSeverity.from_value(raw_item.get("severity")),
            category=IssueCategory.from_value(raw_item.get("category")),
            file_path=raw_item.get("file_path"),
            description=raw_item.get("description", ""),
            id=raw_item.get("id", ""),
            line=raw_item.get("line", ""),
            current_code=raw_item.get("current_code", ""),
            suggested_fix=raw_item.get("suggested_fix", ""),
            root_cause=raw_item.get("root_cause", ""),
            reproduction=raw_item.get("reproduction", ""),
            acceptance_criteria=raw_item.get("acceptance_criteria", ""),
            detection_method=raw_item.get("detection_method", ""),
            status=raw_item.get("status", "open"),
            status_explanation=raw_item.get("status_explanation", ""),
        )

