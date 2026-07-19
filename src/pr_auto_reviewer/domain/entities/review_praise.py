"""ReviewPraise — a single praise item produced by the AI review."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewPraise:
    """A single praise item produced by the AI review.

    Immutable. Highlights something done well in the PR.
    Praise is never enumerated — it's purely qualitative.
    """

    description: str
    file: str = ""
