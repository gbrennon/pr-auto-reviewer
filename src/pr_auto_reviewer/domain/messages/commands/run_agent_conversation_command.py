"""RunAgentConversationCommand — input for running a single-phase agent conversation."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.application.ports.outbound.tool_execution_port import (
    ToolExecutionPort,
)


@dataclass(frozen=True)
class RunAgentConversationCommand:
    """Command to run a single-phase multi-turn agent conversation.

    Carries the system prompt, repository path, changed files, and the
    tool executor for repository exploration.
    """

    system_prompt: str
    repo_path: str
    changed_files: list[str]
    tool_execution: ToolExecutionPort
