"""Pydantic schemas for review item validation in the infrastructure layer."""

from pydantic import BaseModel, field_validator


class ReviewItemSchema(BaseModel):
    """Schema for a single review finding extracted from LLM output.

    Validates and coerces fields from both JSON and prose-parsed dicts
    before they enter the domain layer via ReviewItemFactory.
    """

    file: str = ""
    severity: str = "info"
    category: str = "maintainability"
    description: str = ""
    line: str = ""
    current_code: str = ""
    suggested_fix: str = ""

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v: object) -> str:
        if not isinstance(v, str):
            return "info"
        lowered = v.strip().lower()
        valid = {"critical", "major", "minor", "info"}
        if lowered in valid:
            return lowered
        for candidate in valid:
            if candidate in lowered:
                return candidate
        return "info"

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, v: object) -> str:
        if not isinstance(v, str):
            return "maintainability"
        return v.strip().lower()

    @field_validator("line", mode="before")
    @classmethod
    def _normalize_line(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @classmethod
    def from_parser_dict(cls, data: dict[str, object]) -> "ReviewItemSchema":
        """Construct from a parser-produced dict, tolerating missing keys."""
        return cls(
            file=str(data.get("file", "")),
            severity=str(data.get("severity", "info")),
            category=str(data.get("category", "maintainability")),
            description=str(data.get("description", "")),
            line=str(data.get("line", "")),
            current_code=str(data.get("current_code", "")),
            suggested_fix=str(data.get("suggested_fix", "")),
        )
