"""IssueCategory — classification of the kind of review finding."""

from enum import StrEnum


class IssueCategory(StrEnum):
    """Classification of the kind of review finding."""

    BUG = "bug"
    SECURITY = "security"
    DESIGN = "design"
    PERFORMANCE = "performance"
    TESTABILITY = "testability"
    QUALITY = "quality"
    DOCUMENTATION = "documentation"
    TEST = "test"
    TYPO = "typo"
    MAINTAINABILITY = "maintainability"
    STYLE = "style"
    DOCS = "docs"
    NAMING = "naming"
    GENERAL = "general"

    @classmethod
    def from_value(cls, value: str | None) -> "IssueCategory":
        """Return the category for *value*, accepting legacy aliases."""
        normalized = (value or "").strip().lower()
        aliases = {
            "architecture": cls.DESIGN,
            "solid": cls.DESIGN,
            "doc": cls.DOCS,
            "tests": cls.TEST,
            "correctness": cls.BUG,
            "safety": cls.SECURITY,
            "best-practices": cls.QUALITY,
            "error-handling": cls.BUG,
            "concurrency": cls.BUG,
        }
        if normalized in aliases:
            return aliases[normalized]
        try:
            return cls(normalized)
        except ValueError:
            return cls.GENERAL

    @classmethod
    def prompt_values(cls) -> str:
        """Return the canonical prompt-facing issue category list."""
        return "/".join(category.value for category in (
            cls.BUG,
            cls.SECURITY,
            cls.DESIGN,
            cls.PERFORMANCE,
            cls.TESTABILITY,
            cls.QUALITY,
            cls.DOCUMENTATION,
            cls.TEST,
            cls.TYPO,
            cls.MAINTAINABILITY,
            cls.STYLE,
            cls.DOCS,
            cls.NAMING,
            cls.GENERAL,
        ))
