"""SuggestionOrigin — provenance of review suggestions."""

from enum import StrEnum


class SuggestionOrigin(StrEnum):
    """Identify whether suggestions came from architecture review output."""

    ARCHITECTURE = "architecture"
    LEGACY_UNKNOWN = "legacy_unknown"
