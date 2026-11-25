"""JsonFilePullRequestRepository — persistence adapter for PullRequest aggregate.

Implements PullRequestRepositoryPort. Replaces the STATE_FILE bash script approach
with atomic writes and structured deserialization.
"""

from __future__ import annotations

from ...domain.entities.review_item import ReviewItem
from ...domain.exceptions import RepositoryCorruptedError
from ...domain.value_objects.issue_category import IssueCategory
from ...domain.value_objects.item_severity import ItemSeverity

_CATEGORY_ALIASES = {
    "architecture": "design",
    "solid": "design",
    "doc": "docs",
    "tests": "test",
    "correctness": "bug",
    "safety": "security",
    "best-practices": "quality",
    "error-handling": "bug",
    "concurrency": "bug",
}


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
        try:
            if not isinstance(raw_item, dict):
                raise ValueError("review item payload must be an object")
            item_id = ReviewItemCodec._required_text(raw_item, "id")
            description = ReviewItemCodec._required_text(
                raw_item, "description"
            )
            severity = ReviewItemCodec._severity(raw_item)
            category = ReviewItemCodec._category(raw_item)
            return ReviewItem(
                severity=severity,
                category=category,
                file_path=raw_item.get("file_path"),
                description=description,
                id=item_id,
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
        except RepositoryCorruptedError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise RepositoryCorruptedError(
                f"Persisted review item is malformed: {exc}"
            ) from exc

    @staticmethod
    def _required_text(raw_item: dict, field: str) -> str:
        value = raw_item[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        return value

    @staticmethod
    def _severity(raw_item: dict) -> ItemSeverity:
        value = raw_item["severity"]
        if not isinstance(value, str) or not ItemSeverity.accepts(value):
            raise ValueError(f"invalid severity: {value}")
        return ItemSeverity.from_value(value)

    @staticmethod
    def _category(raw_item: dict) -> IssueCategory:
        value = raw_item["category"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"invalid category: {value}")
        normalized = value.strip().lower()
        valid = {category.value for category in IssueCategory}
        if normalized not in valid and normalized not in _CATEGORY_ALIASES:
            raise ValueError(f"invalid category: {value}")
        return IssueCategory.from_value(normalized)
