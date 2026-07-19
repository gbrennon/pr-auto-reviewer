"""ItemSeverity — classification of how critical a review finding is."""

from enum import StrEnum

_PROMPT_ALIASES = {
    "high": "major",
    "medium": "minor",
    "low": "info",
}

class ItemSeverity(StrEnum):
    """Classification of how critical a review finding is."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"

    @property
    def is_blocking(self) -> bool:
        """PR-blocking severities require changes before merge."""
        return self in (ItemSeverity.CRITICAL, ItemSeverity.MAJOR)

    @classmethod
    def from_value(cls, value: str | None) -> "ItemSeverity":
        """Return the severity for *value*, accepting prompt aliases."""
        normalized = (value or "").strip().lower()
        if normalized in _PROMPT_ALIASES:
            normalized = _PROMPT_ALIASES[normalized]
        try:
            return cls(normalized)
        except ValueError:
            return cls.INFO

    @classmethod
    def accepts(cls, value: str | None) -> bool:
        """Return True when *value* is a known severity or prompt alias."""
        normalized = (value or "").strip().lower()
        return normalized in _PROMPT_ALIASES or normalized in {
            item.value for item in cls
        }

    @classmethod
    def prompt_values(cls) -> str:
        """Return the canonical prompt-facing severity list."""
        return "high/medium/info"
