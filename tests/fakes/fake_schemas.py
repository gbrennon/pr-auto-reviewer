"""Fake schemas for tests - replaces Pydantic models with simple dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeReviewItemSchema:
    """Fake review item schema for testing."""

    file: str = ""
    severity: str = "info"
    category: str = "maintainability"
    description: str = ""
    line: str = ""
    current_code: str = ""
    suggested_fix: str = ""

    def model_dump(self) -> dict[str, str]:
        """Return dict representation."""
        return {
            "file": self.file,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "line": self.line,
            "current_code": self.current_code,
            "suggested_fix": self.suggested_fix,
        }

    @classmethod
    def from_parser_dict(cls, data: dict[str, object]) -> "FakeReviewItemSchema":
        """Construct from a parser-produced dict."""
        return cls(
            file=str(data.get("file", "")),
            severity=str(data.get("severity", "info")),
            category=str(data.get("category", "maintainability")),
            description=str(data.get("description", "")),
            line=str(data.get("line", "")),
            current_code=str(data.get("current_code", "")),
            suggested_fix=str(data.get("suggested_fix", "")),
        )


@dataclass
class FakeReviewItem:
    """Fake domain review item for testing."""

    file: str = ""
    severity: str = "info"
    category: str = "maintainability"
    description: str = ""
    line: str = ""
    current_code: str = ""
    suggested_fix: str = ""

    def model_dump(self) -> dict[str, str]:
        """Return dict representation."""
        return {
            "file": self.file,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "line": self.line,
            "current_code": self.current_code,
            "suggested_fix": self.suggested_fix,
        }