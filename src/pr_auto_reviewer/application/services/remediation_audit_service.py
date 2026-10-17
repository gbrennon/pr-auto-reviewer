"""RemediationAuditService — prove prior findings resolved or keep them open."""

from __future__ import annotations

import re
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
from pr_auto_reviewer.domain.value_objects.review_audit_result import (
    ReviewAuditResult,
)
from pr_auto_reviewer.domain.value_objects.review_item_lifecycle import (
    ReviewItemLifecycle,
)
from pr_auto_reviewer.domain.value_objects.review_item_status import (
    ReviewItemStatus,
)
from pr_auto_reviewer.domain.value_objects.sub_agent_role import SubAgentRole


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
    """Audit every historical item and suggestion against updated code.

    Active records remain open unless the auditor returns a resolved status
    with non-empty proof reasoning. Resolved and dismissed records are
    terminal and are never reopened by a later audit.
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

    def execute(self, command: AuditRemediationCommand) -> ReviewAuditResult:
        """Audit all historical records and return their lifecycle projection."""
        items = list(command.prior_items)
        suggestions = list(command.prior_suggestions)
        if not items and not suggestions:
            return ReviewAuditResult(
                items=(),
                suggestions=(),
                lifecycles=tuple(command.prior_lifecycles),
            )

        findings_text = self._format_findings(
            items, command.repo_path, suggestions=suggestions,
        )
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

        normalized_results = self._normalized_results(results)
        has_result_ids = any(
            self._result_id(result) for result in normalized_results
        )
        lifecycle_by_id = {
            lifecycle.item_id: lifecycle
            for lifecycle in command.prior_lifecycles
            if lifecycle.item_id
        }
        audit_sha = command.current_sha or command.base_sha
        audited_items: list[ReviewItem] = []
        audited_suggestions: list[ReviewItem] = []
        lifecycles: list[ReviewItemLifecycle] = []
        seen_lifecycle_ids: set[str] = set()

        for index, item in enumerate(items):
            result = self._matching_result(
                item, index, len(items), normalized_results,
                has_result_ids, "item",
            )
            audited, lifecycle = self._audit_record(
                item, result, lifecycle_by_id.get(item.id), audit_sha,
                command.repo_path,
            )
            audited_items.append(audited)
            if lifecycle is not None:
                lifecycles.append(lifecycle)
                if lifecycle.item_id:
                    seen_lifecycle_ids.add(lifecycle.item_id)

        for index, suggestion in enumerate(suggestions):
            result = self._matching_result(
                suggestion, index, len(items), normalized_results,
                has_result_ids, "suggestion",
            )
            audited, lifecycle = self._audit_record(
                suggestion, result, lifecycle_by_id.get(suggestion.id),
                audit_sha,
                command.repo_path,
            )
            audited_suggestions.append(audited)
            if lifecycle is not None:
                lifecycles.append(lifecycle)
                if lifecycle.item_id:
                    seen_lifecycle_ids.add(lifecycle.item_id)

        lifecycles.extend(
            lifecycle
            for lifecycle in command.prior_lifecycles
            if lifecycle.item_id not in seen_lifecycle_ids
        )
        return ReviewAuditResult(
            items=tuple(audited_items),
            suggestions=tuple(audited_suggestions),
            lifecycles=tuple(lifecycles),
        )

    def _audit_record(
        self,
        item: ReviewItem,
        result: dict[str, Any] | None,
        lifecycle: ReviewItemLifecycle | None,
        audit_sha: str,
        repo_path: Path,
    ) -> tuple[ReviewItem, ReviewItemLifecycle | None]:
        """Apply one fail-closed audit result and lifecycle transition."""
        prior_status = lifecycle.status if lifecycle is not None else item.status
        terminal = prior_status in {
            ReviewItemStatus.RESOLVED,
            ReviewItemStatus.DISMISSED,
        } or item.status in {
            ReviewItemStatus.RESOLVED,
            ReviewItemStatus.DISMISSED,
        }
        prior_explanation = (
            lifecycle.status_explanation
            if lifecycle is not None
            else self._item_explanation(item)
        )
        if terminal:
            status = prior_status
            if status not in {
                ReviewItemStatus.RESOLVED,
                ReviewItemStatus.DISMISSED,
            }:
                status = item.status
            explanation = prior_explanation
        else:
            status, explanation = self._status_from_result(result)

        materialized = self._materialize_item(
            item, status, explanation, repo_path,
        )
        projected = self._project_lifecycle(
            item.id, lifecycle, status, explanation, audit_sha,
        )
        return materialized, projected

    def _status_from_result(
        self, result: dict[str, Any] | None,
    ) -> tuple[ReviewItemStatus, str]:
        """Return a status while requiring proof for resolution."""
        fallback = "Remediation was not proven; the record remains open."
        if not isinstance(result, dict):
            return ReviewItemStatus.OPEN, fallback
        reasoning = result.get("reasoning")
        if (
            str(result.get("status", "")).lower() == "resolved"
            and isinstance(reasoning, str)
            and self._has_resolution_evidence(reasoning)
        ):
            return ReviewItemStatus.RESOLVED, reasoning.strip()
        if isinstance(reasoning, str) and reasoning.strip():
            return ReviewItemStatus.OPEN, reasoning.strip()
        return ReviewItemStatus.OPEN, fallback

    @staticmethod
    def _has_resolution_evidence(reasoning: str) -> bool:
        """Require a cited path and a concrete remediation outcome."""
        has_path = re.search(
            r"\b[\w./-]+\.[A-Za-z0-9_]+(?::\d+)?\b", reasoning,
        )
        normalized = reasoning.lower()
        proof_markers = (
            "acceptance criteria",
            "reproduction",
            "no longer triggers",
            "tests pass",
            "tests passed",
            "verified",
        )
        return has_path is not None and any(
            marker in normalized for marker in proof_markers
        )

    def _project_lifecycle(
        self,
        item_id: str,
        lifecycle: ReviewItemLifecycle | None,
        status: ReviewItemStatus,
        explanation: str,
        audit_sha: str,
    ) -> ReviewItemLifecycle | None:
        if not item_id or not audit_sha:
            return lifecycle
        if lifecycle is None:
            lifecycle = ReviewItemLifecycle.first_appearance(
                item_id, audit_sha,
            )
        assert lifecycle is not None
        if status is ReviewItemStatus.DISMISSED:
            return lifecycle.dismiss(audit_sha, explanation=explanation)
        return lifecycle.audit(
            audit_sha,
            present=True,
            proof=status is ReviewItemStatus.RESOLVED,
            explanation=explanation,
        )

    def _materialize_item(
        self,
        item: ReviewItem,
        status: ReviewItemStatus,
        explanation: str,
        repo_path: Path,
    ) -> ReviewItem:
        """Render lifecycle status and only current code evidence."""
        values: dict[str, Any] = {
            "status": status,
        }
        if hasattr(item, "status_explanation"):
            values["status_explanation"] = explanation
        if not self._current_code_exists(repo_path, item):
            values["current_code"] = ""
            values["suggested_fix"] = ""
        return replace(item, **values)

    def _current_code_exists(self, repo_path: Path, item: ReviewItem) -> bool:
        if not item.file_path or not item.current_code:
            return True
        try:
            current_file = (repo_path / item.file_path).read_text()
        except (OSError, UnicodeDecodeError):
            return False
        current_lines = {
            line.strip() for line in current_file.splitlines() if line.strip()
        }
        evidence_lines = {
            line.strip() for line in item.current_code.splitlines()
            if line.strip()
        }
        return bool(evidence_lines) and evidence_lines <= current_lines

    def _item_explanation(self, item: ReviewItem) -> str:
        """Read a materialized explanation when supported by ReviewItem."""
        explanation = getattr(item, "status_explanation", "")
        return explanation if isinstance(explanation, str) else ""

    def _normalized_results(
        self, results: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Accept only a well-formed result list; malformed input fails closed."""
        if not isinstance(results, list):
            return []
        return [result for result in results if isinstance(result, dict)]

    def _matching_result(
        self,
        item: ReviewItem,
        index: int,
        item_count: int,
        results: list[dict[str, Any]],
        has_result_ids: bool,
        record_type: str,
    ) -> dict[str, Any] | None:
        """Match by ID, retaining positional matching for legacy transcripts."""
        for result in results:
            result_id = self._result_id(result)
            if result_id != item.id or not result_id:
                continue
            result_type = self._result_type(result)
            if result_type and result_type != record_type:
                continue
            return result
        if has_result_ids:
            return None
        expected_index = index if record_type == "item" else item_count + index
        for result in results:
            if result.get("finding_index") == expected_index:
                return result
        return None

    def _result_id(self, result: dict[str, Any]) -> str:
        """Return a finding identifier from the auditor result."""
        for key in ("finding_id", "item_id", "suggestion_id"):
            value = result.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def _result_type(self, result: dict[str, Any]) -> str:
        """Normalize the optional item-versus-suggestion result section."""
        value = result.get("record_type", result.get("section", ""))
        if not isinstance(value, str):
            return "__invalid__"
        normalized = value.lower().strip()
        if not normalized:
            return ""
        if normalized in {"finding", "findings", "item", "items"}:
            return "item"
        if normalized in {"suggestion", "suggestions"}:
            return "suggestion"
        return "__invalid__"

    def _format_findings(
        self,
        items: list[ReviewItem],
        repo_path: Path,
        suggestions: list[ReviewItem] | None = None,
    ) -> str:
        """Render item and suggestion history with stable identifiers."""
        suggestion_records = suggestions or []
        sections = [
            "## ITEMS\n\n" + "\n\n".join(
                self._format_finding(index, item, repo_path, "item")
                for index, item in enumerate(items)
            ),
            "## SUGGESTIONS\n\n" + "\n\n".join(
                self._format_finding(index, item, repo_path, "suggestion")
                for index, item in enumerate(suggestion_records)
            ),
        ]
        return "\n\n".join(section for section in sections if section.strip())

    def _format_finding(
        self,
        index: int,
        item: ReviewItem,
        repo_path: Path,
        record_type: str = "item",
    ) -> str:
        """Render one historical record with enriched remediation context."""
        file_content = self._read_current_file(repo_path, item.file_path or "")
        return (
            f"## Finding {index}\n\n"
            f"- **Record type:** {record_type}\n"
            f"- **Finding ID:** `{item.id or '(legacy positional)'}`\n"
            f"- **File:** `{item.file_path or '(unknown)'}`\n"
            f"- **Severity:** {item.severity.value}\n"
            f"- **Category:** {item.category.value}\n"
            f"- **Description:** {item.description}\n"
            f"- **Detection method:** {item.detection_method or '(none)'}\n"
            f"- **Reproduction:** {item.reproduction or '(none)'}\n"
            f"- **Acceptance criteria:** "
            f"{item.acceptance_criteria or '(none)'}\n"
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
