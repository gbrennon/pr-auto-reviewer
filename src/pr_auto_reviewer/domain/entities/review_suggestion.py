"""ReviewSuggestion — a single suggestion produced by the AI review."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewSuggestion:
    """A single suggestion produced by the AI review.

    Immutable. Suggests an improvement without being a blocking issue.
    """

    description: str = ""
    file: str = ""
    line: str = ""
    current_code: str = ""
    suggested_code: str = ""