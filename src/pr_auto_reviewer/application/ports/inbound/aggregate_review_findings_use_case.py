"""AggregateReviewFindingsUseCase — inbound port for merging review findings."""

from typing import Protocol

from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview


class AggregateReviewFindingsUseCase(Protocol):
    """Deduplicate and merge review items across phases into a CodeReview."""

    def execute(self, command: AggregateReviewFindingsCommand) -> CodeReview:
        ...
