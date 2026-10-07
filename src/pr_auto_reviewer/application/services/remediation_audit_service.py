"""RemediationAuditService — prove prior findings resolved or keep them open."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol

from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
    CommandBusPort,
)
from pr_auto_reviewer.application.services.pr_identifier_service import (
    PRIdentifierService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.audit_remediation_command import (
    AuditRemediationCommand,
)
from pr_auto_reviewer.domain.messages.events.agent_exchange_event import (
    AgentExchangeEvent,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.sub_agent_role import SubAgentRole
from pr_auto_reviewer.domain.value_objects.review_item_status import ReviewItemStatus

logger = logging.getLogger(__name__)


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


class RemediationAuditService:
    """Decide open/resolved for prior findings against the updated code.

    Prior findings default to ``ReviewItemStatus.OPEN``. A finding becomes
    ``ReviewItemStatus.RESOLVED`` only on explicit proof from the audit
    transcript, so defects are never resolved by absence or assumption.
    """

    def __init__(
        self,
        transcript_runner: AuditTranscriptRunner,
        audit_prompt: str,
        command_bus: CommandBusPort | None = None,
    ) -> None:
        self._transcript_runner = transcript_runner
        self._audit_prompt = audit_prompt
        self._command_bus = command_bus

    def execute(self, command: AuditRemediationCommand) -> list[ReviewItem]:
        """Audit every prior finding and return them with proof-gated status."""
        prior_items = list(command.prior_items)
        if not prior_items:
            return []

        findings_text = self._format_findings(prior_items, command.repo_path)
        prompt = self._audit_prompt.replace("{findings}", findings_text)

        results, transcript = self._transcript_runner.run(
            system_prompt=prompt,
            repo_path=command.repo_path,
            changed_files=command.changed_files,
            base_sha=command.base_sha,
        )
        self._publish_exchange(
            command.repo_path, command.review_session, prompt, transcript,
        )

        resolved = self._resolved_indices(results)
        return [
            replace(
                item,
                status=(
                    ReviewItemStatus.RESOLVED
                    if i in resolved
                    else ReviewItemStatus.OPEN
                ),
            )
            for i, item in enumerate(prior_items)
        ]

    def _resolved_indices(
        self, results: list[dict[str, Any]] | None,
    ) -> set[int]:
        """Prior-finding indices the auditor proved resolved.

        An aborted transcript yields no resolutions, keeping every
        prior finding open under the fail-closed rule.
        """
        if not results:
            return set()
        return {
            idx
            for r in results
            if isinstance((idx := r.get("finding_index")), int)
            and r.get("status") == "resolved"
        }

    def _format_findings(
        self, items: list[ReviewItem], repo_path: Path,
    ) -> str:
        """Render prior findings with their remediation context for auditing."""
        return "\n\n".join(
            self._format_finding(index, item, repo_path)
            for index, item in enumerate(items)
        )

    def _format_finding(
        self, index: int, item: ReviewItem, repo_path: Path,
    ) -> str:
        """Render a single prior finding block with enriched fields."""
        file_content = self._read_current_file(repo_path, item.file_path or "")
        return (
            f"## Finding {index}\n\n"
            f"- **File:** `{item.file_path or '(unknown)'}`\n"
            f"- **Severity:** {item.severity.value}\n"
            f"- **Category:** {item.category.value}\n"
            f"- **Description:** {item.description}\n"
            f"- **Detection method:** {item.detection_method or '(none)'}\n"
            f"- **Reproduction:** {item.reproduction or '(none)'}\n"
            f"- **Acceptance criteria:** {item.acceptance_criteria or '(none)'}\n"
            f"- **Current code:**\n```\n{item.current_code}\n```\n"
            f"- **File content (current):**\n```\n{file_content}\n```\n"
        )

    def _read_current_file(self, repo_path: Path, file_path: str) -> str:
        """Read the current file text, truncated, for auditing context."""
        if not file_path:
            return ""
        full_path = repo_path / file_path
        try:
            return full_path.read_text()[:2000]
        except (OSError, UnicodeDecodeError):
            return "(file could not be read)"

    def _publish_exchange(
        self,
        repo_path: Path,
        review_session: str,
        system_prompt: str,
        transcript: list[ConversationMessage],
    ) -> None:
        """Emit the finished audit exchange for the transcript log."""
        if self._command_bus is None:
            return
        self._command_bus.dispatch(AgentExchangeEvent(
            role=SubAgentRole.AUDITOR,
            phase_name="Remediation Audit",
            pr_identifier_service=PRIdentifierService.derive(repo_path),
            review_session=review_session,
            messages=transcript,
        ))
