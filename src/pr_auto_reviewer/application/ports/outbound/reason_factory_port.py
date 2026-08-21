"""ReasonFactoryPort — make a human-readable reason string from review items."""

from typing import Protocol

from pr_auto_reviewer.domain.entities.review_item import ReviewItem


class ReasonFactoryPort(Protocol):
    """Make an expressive reason string from a list of review items.

    Infrastructure adapters implement this to provide reason-string
    formatting (e.g. grouping by severity and category).
    """

    def make(self, items: list[ReviewItem]) -> str: ...
