"""Pydantic schemas for review item validation in the infrastructure layer."""

from pydantic import BaseModel, field_validator

from ...domain.value_objects.issue_category import IssueCategory
from ...domain.value_objects.item_severity import ItemSeverity


class ReviewItemSchema(BaseModel):
    """Schema for a single review finding extracted from LLM output."""

    file: str = ""
    severity: str
    category: str
    description: str
    line: str = ""
    current_code: str = ""
    suggested_fix: str = ""

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("severity must be a non-empty string")
        normalized = v.strip().lower()
        if not ItemSeverity.accepts(normalized):
            raise ValueError(f"invalid severity: {v}")
        return ItemSeverity.from_value(normalized).value

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("category must be a non-empty string")
        normalized = v.strip().lower()
        aliases = {
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
        if normalized in aliases:
            return aliases[normalized]
        if normalized not in {category.value for category in IssueCategory}:
            raise ValueError(f"invalid category: {v}")
        return normalized

    @field_validator("description", mode="before")
    @classmethod
    def _validate_description(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("description must be a non-empty string")
        return v

    @field_validator("line", mode="before")
    @classmethod
    def _normalize_line(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @classmethod
    def from_parser_dict(cls, data: dict[str, object]) -> ReviewItemSchema:
        """Construct from a parser-produced dict."""
        return cls(
            file=data.get("file", ""),
            severity=data.get("severity"),
            category=data.get("category"),
            description=data.get("description"),
            line=data.get("line", ""),
            current_code=data.get("current_code", ""),
            suggested_fix=data.get("suggested_fix", ""),
        )
