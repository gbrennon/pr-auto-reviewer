"""IssueCommandParser — pure domain service to parse commands from comment bodies."""

from __future__ import annotations

import re

from ..value_objects.issue_command import IssueCommand


class IssueCommandParser:
    """Pure domain service. Detects command syntax in a comment body
    (e.g. ``/create issue 1,3`` or ``/create-issue for 1,3``) and returns
    an IssueCommand VO, or None."""

    _COMMAND_PATTERN = re.compile(
        r"/?\s*create[- ]?issue(?:\s+for)?\s+(?P<numbers>[\d,\s]+)",
        re.IGNORECASE,
    )

    def parse(self, comment_id: str, comment_body: str) -> IssueCommand | None:
        match = self._COMMAND_PATTERN.search(comment_body)
        if not match:
            return None

        raw = match.group("numbers")
        numbers: list[int] = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                numbers.append(int(part))

        if not numbers:
            return None

        return IssueCommand(
            comment_id=comment_id,
            item_numbers=numbers,
        )
