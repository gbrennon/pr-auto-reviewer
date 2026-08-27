"""Shared helpers, fixtures, and imports for the split test modules."""

import json
from pathlib import Path

from pr_auto_reviewer.application.services.finding_verifier_service import (
    FindingVerifierService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.verify_findings_command import (
    VerifyFindingsCommand,
)
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity


def _item(
    item_id: str = "id-1",
    *,
    severity: ItemSeverity = ItemSeverity.MAJOR,
    category: IssueCategory = IssueCategory.BUG,
    file_path: str | None = "src/a.py",
    current_code: str = "bad",
    suggested_fix: str = "good",
) -> ReviewItem:
    return ReviewItem(
        id=item_id,
        severity=severity,
        category=category,
        file_path=file_path,
        description=f"finding {item_id}",
        line="42",
        current_code=current_code,
        suggested_fix=suggested_fix,
    )


def _verifier(
    mock_chat_port, mock_tool_factory, responses: list[str] | None = None,
) -> FindingVerifierService:
    if responses is not None:
        mock_chat_port.send.side_effect = responses
    return FindingVerifierService(
        mock_chat_port, "verify {findings}", mock_tool_factory
    )


__all__ = ['FindingVerifierService', 'IssueCategory', 'ItemSeverity', 'Path', 'ReviewItem', 'VerifyFindingsCommand', '_item', '_verifier', 'json']
