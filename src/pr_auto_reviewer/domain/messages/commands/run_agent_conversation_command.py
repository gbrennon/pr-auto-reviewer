"""RunAgentConversationCommand — input for running a single-phase agent conversation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunAgentConversationCommand:
    """Command to run a single-phase multi-turn agent conversation.

    Carries the system prompt, repository path, changed files, the
    tool executor for repository exploration, and the phase name
    for conversation logging.
    """

    system_prompt: str
    repo_path: Path
    changed_files: list[str]
    tool_execution: Any
    phase_name: str = ""
    existing_item_ids: frozenset[str] = frozenset()
