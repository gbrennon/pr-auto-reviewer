"""RunAgentConversationUseCase — inbound port for running a single-phase agent conversation."""

from typing import Protocol

from pr_auto_reviewer.application.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.domain.agent.phase_result import PhaseResult


class RunAgentConversationUseCase(Protocol):
    """Run a single-phase multi-turn agent conversation with tool access."""

    def execute(self, command: RunAgentConversationCommand) -> PhaseResult:
        ...
