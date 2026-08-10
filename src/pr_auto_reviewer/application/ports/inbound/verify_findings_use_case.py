"""VerifyFindingsUseCase — inbound port for verifying blocking findings against source code."""

from typing import Protocol

from pr_auto_reviewer.domain.messages.commands.verify_findings_command import (
    VerifyFindingsCommand,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem


class VerifyFindingsUseCase(Protocol):
    """Verify CRITICAL/MAJOR findings against actual source code.

    Returns the filtered list — unverified (hallucinated) findings are dropped.
    """

    def execute(self, command: VerifyFindingsCommand) -> list[ReviewItem]:
        ...
