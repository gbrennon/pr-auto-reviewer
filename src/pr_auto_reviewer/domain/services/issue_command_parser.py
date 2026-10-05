"""IssueCommandParser — pure domain service to parse commands from comment bodies."""

from __future__ import annotations

import re

from ..value_objects.issue_command import IssueCommand
from ..value_objects.issue_command_action import IssueCommandAction


class IssueCommandParser:
    """Pure domain service for parsing PR review commands."""

    _COMMAND_PATTERN = re.compile(
        r"/?\s*(?:(?P<create>create[- ]?issue)(?:\s+for)?|"
        r"(?P<dismiss>dismiss))\s+"
        r"(?P<ids>[a-zA-Z0-9\-]+(?:\s*,\s*[a-zA-Z0-9\-]+)*)",
        re.IGNORECASE,
    )

    def parse(self, comment_id: str, comment_body: str) -> IssueCommand | None:
        match = self._COMMAND_PATTERN.search(comment_body)
        if not match:
            return None

        raw = match.group("ids")
        ids: list[str] = []
        for part in raw.split(","):
            part = part.strip()
            if part:
                ids.append(part)

        if not ids:
            return None

        return IssueCommand(
            comment_id=comment_id,
            item_ids=ids,
            action=(
                IssueCommandAction.DISMISS
                if match.group("dismiss")
                else IssueCommandAction.CREATE_ISSUE
            ),
        )
