"""RemediationAuditService — prove prior findings resolved or keep them open."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)


class AuditTranscriptRunner(Protocol):
    """Seam that runs the auditor conversation and returns its results."""

    def run(
        self,
        system_prompt: str,
        repo_path: Path,
        changed_files: list[str],
        base_sha: str,
    ) -> tuple[list[dict[str, Any]] | None, list[ConversationMessage]]:
        """Return parsed audit results and the full transcript."""
        ...

