"""ItemSeverity — classification of how critical a review finding is."""

from enum import StrEnum


class ItemSeverity(StrEnum):
    """Classification of how critical a review finding is."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"
