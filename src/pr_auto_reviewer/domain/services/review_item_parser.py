"""ReviewItemParser — pure domain service to parse a review body into ReviewItems."""

from __future__ import annotations

import re
import uuid as _uuid

from ..entities.review_item import ReviewItem
from ..value_objects.issue_category import IssueCategory
from ..value_objects.item_severity import ItemSeverity


class ReviewItemParser:
    """Pure domain service. Receives the markdown body of a posted review
    and returns a structured list of ReviewItem. Contains all parsing rules
    — no I/O, no ports."""

    _ITEM_PATTERN = re.compile(
        r"^(?P<number>\d+)\.\s+\[(?P<category>[^\]]+)\]\s+\[(?P<severity>[A-Z]+)\]"
        r"(?: (?P<file_info>[^\n]+))?"
        r"(?:\n\n(?P<description>[^\n]+))?",
        re.MULTILINE,
    )

    @classmethod
    def _extract_fields(cls,
        file_info: str | None, description: str | None,
    ) -> tuple[str | None, str, str]:
        if description is not None:
            file_path, line = _split_file_info(file_info)
            return file_path, line, description.strip()

        if file_info:
            file_info = file_info.strip()
            if ":" in file_info and file_info.rsplit(":", 1)[1].isdigit():
                fp, ln = file_info.rsplit(":", 1)
                return fp, ln, ""
            return None, "", file_info

        return None, "", ""

    def parse(self, raw_body: str) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        for match in self._ITEM_PATTERN.finditer(raw_body):
            file_path, line, description = self._extract_fields(
                match.group("file_info"), match.group("description"),
            )

            item_id = format(_uuid.uuid7().int, "04x")[:4]
            items.append(ReviewItem(
                severity=ItemSeverity.from_value(match.group("severity")),
                category=IssueCategory.from_value(match.group("category")),
                file_path=file_path,
                description=description,
                line=line,
                id=item_id,
            ))
        return items


def _split_file_info(file_info: str | None) -> tuple[str | None, str]:
    if not file_info:
        return None, ""
    file_info = file_info.strip()
    if ":" in file_info:
        parts = file_info.rsplit(":", 1)
        if parts[1].isdigit():
            return parts[0], parts[1]
    return file_info, ""
