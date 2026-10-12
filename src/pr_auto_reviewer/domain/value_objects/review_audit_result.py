"""Result of auditing prior review items and suggestions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .review_item_lifecycle import ReviewItemLifecycle

if TYPE_CHECKING:
    from ..entities.review_item import ReviewItem


@dataclass(frozen=True)
class ReviewAuditResult:
    """Audited item projections and their immutable lifecycle histories."""

    items: tuple[ReviewItem, ...] = ()
    suggestions: tuple[ReviewItem, ...] = ()
    lifecycles: tuple[ReviewItemLifecycle, ...] = ()

    def __post_init__(self) -> None:
        """Normalize result collections to immutable tuples."""
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "suggestions", tuple(self.suggestions))
        object.__setattr__(self, "lifecycles", tuple(self.lifecycles))
