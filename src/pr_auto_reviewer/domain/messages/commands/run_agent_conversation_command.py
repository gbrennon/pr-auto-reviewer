"""RunAgentConversationCommand — input for running a single-phase agent conversation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...value_objects.conversation_purpose import ConversationPurpose


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
    review_session: str
    """Opaque review-run key (start timestamp) grouping transcripts for one run."""
    model: str = ""
    phase_name: str = ""
    purpose: ConversationPurpose = ConversationPurpose.REVIEWER_PHASE
    existing_item_ids: frozenset[str] = frozenset()
    coverage_files: tuple[str, ...] | None = None
    """Files that must be read before this phase may accept a verdict."""
