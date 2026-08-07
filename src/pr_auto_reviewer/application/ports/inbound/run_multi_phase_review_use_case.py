"""RunMultiPhaseReviewUseCase — inbound port for executing a multi-phase review plan."""

from typing import Protocol

from pr_auto_reviewer.application.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview


class RunMultiPhaseReviewUseCase(Protocol):
    """Execute a full multi-phase review plan with retry and feedback loops."""

    def execute(self, command: RunMultiPhaseReviewCommand) -> CodeReview:
        ...
