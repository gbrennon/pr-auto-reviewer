"""ReviewItemParser — pure domain service to parse a review body into ReviewItems."""

from __future__ import annotations

import re

from ..entities.review_item import ReviewItem
from ..value_objects.issue_category import IssueCategory
from ..value_objects.item_severity import ItemSeverity


class ReviewItemParser:
    """Pure domain service. Receives the markdown body of a posted review
    and returns a structured list of ReviewItem. Contains all parsing rules
    — no I/O, no ports."""

    _ITEM_PATTERN = re.compile(
        r"^\d+\.\s*\*\*(?P<severity>[A-Z]+)\*\*\s*\[(?P<category>\w+)](?:\s*`(?P<file>[^`]+)`)?\s*[:-]?\s*(?P<description>.+)$",
        re.MULTILINE,
    )

    def parse(self, raw_body: str) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        for n, match in enumerate(self._ITEM_PATTERN.finditer(raw_body), start=1):
            file_path = match.group("file") or None

            items.append(ReviewItem(
                number=n,
                severity=ItemSeverity.from_value(match.group("severity")),
                category=IssueCategory.from_value(match.group("category")),
                file_path=file_path,
                description=match.group("description").strip(),
            ))
        return items
