from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from pr_auto_reviewer.application.services.remediation_audit_service import (
    RemediationAuditService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.audit_remediation_command import (
    AuditRemediationCommand,
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


class FakeAuditTranscriptRunner:
    """Fake transcript seam returning canned audit results."""

    def __init__(self, results: list[dict[str, Any]] | None) -> None:
        self._results = results

    def run(
        self,
        system_prompt: str,
        repo_path: Path,
        changed_files: list[str],
        base_sha: str,
    ) -> tuple[list[dict[str, Any]] | None, list[ConversationMessage]]:
        return self._results, []


class TestRemediationAuditExecute:
    """The auditor resolves historical records only with explicit proof."""

    def test_matches_results_by_finding_id(self) -> None:
        service = self._build_service(
            FakeAuditTranscriptRunner([
                {
                    "finding_id": "second",
                    "status": "open",
                    "reasoning": "still present",
                },
                {
                    "finding_id": "first",
                    "status": "resolved",
                    "reasoning": "src/parser.py:10 current source and reproduction prove the fix",
                },
            ]),
        )

        result = service.execute(self._command(self._prior()))

        assert isinstance(result, ReviewAuditResult)
        assert [item.status for item in result.items] == [
            ReviewItemStatus.RESOLVED,
            ReviewItemStatus.OPEN,
        ]

    def test_resolves_only_with_non_empty_proof(self) -> None:
        service = self._build_service(
            FakeAuditTranscriptRunner([{
                "finding_id": "first",
                "status": "resolved",
                "reasoning": "  ",
            }])
        )

        result = service.execute(self._command(self._prior()))

        assert result.items[0].status is ReviewItemStatus.OPEN

    def test_rejects_vague_resolution_reasoning(self) -> None:
        service = self._build_service(
            FakeAuditTranscriptRunner([{
                "finding_id": "first",
                "status": "resolved",
                "reasoning": "fixed",
            }])
        )

        result = service.execute(self._command(self._prior()))

        assert result.items[0].status is ReviewItemStatus.OPEN

    def test_returns_lifecycle_transition_explanation(self) -> None:
        lifecycle = ReviewItemLifecycle.first_appearance(
            "first", "old-sha", "first observed",
        )
        command = self._command(
            self._prior(), prior_lifecycles=(lifecycle,), current_sha="new-sha",
        )
        service = self._build_service(
            FakeAuditTranscriptRunner([{
                "finding_id": "first",
                "status": "resolved",
                "reasoning": "src/a.py:10 current source and reproduction prove the fix",
            }])
        )

        result = service.execute(command)

        assert result.lifecycles[0].status is ReviewItemStatus.RESOLVED
        assert result.lifecycles[0].last_audited_sha == "new-sha"
        assert result.lifecycles[0].transitions[-1].explanation.startswith(
            "src/a.py:10"
        )

    def test_preserves_suggestion_section(self) -> None:
        suggestion = self._item("suggestion", status=ReviewItemStatus.OPEN)
        service = self._build_service(
            FakeAuditTranscriptRunner([{
                "finding_id": "suggestion",
                "record_type": "suggestion",
                "status": "open",
                "reasoning": "still useful",
            }])
        )

        result = service.execute(
            self._command(self._prior(), prior_suggestions=[suggestion])
        )

        assert [item.id for item in result.items] == ["first", "second"]
        assert [item.id for item in result.suggestions] == ["suggestion"]
        assert result.suggestions[0].status is ReviewItemStatus.OPEN

    def test_preserves_terminal_records(self) -> None:
        resolved = self._item("resolved", status=ReviewItemStatus.RESOLVED)
        dismissed = self._item("dismissed", status=ReviewItemStatus.DISMISSED)
        service = self._build_service(
            FakeAuditTranscriptRunner([
                {"finding_id": "resolved", "status": "open"},
                {"finding_id": "dismissed", "status": "resolved", "reasoning": "x"},
            ])
        )

        result = service.execute(
            self._command([resolved, dismissed], current_sha="new-sha")
        )

        assert [item.status for item in result.items] == [
            ReviewItemStatus.RESOLVED,
            ReviewItemStatus.DISMISSED,
        ]

    def test_defaults_active_records_open_when_transcript_aborts(self) -> None:
        service = self._build_service(FakeAuditTranscriptRunner(None))

        result = service.execute(self._command(self._prior()))

        assert all(item.status is ReviewItemStatus.OPEN for item in result.items)

    def test_defaults_active_records_open_when_results_malformed(self) -> None:
        service = self._build_service(
            FakeAuditTranscriptRunner(cast(list[dict[str, Any]], ["bad"]))
        )

        result = service.execute(self._command(self._prior()))

        assert all(item.status is ReviewItemStatus.OPEN for item in result.items)

    def test_ignores_result_with_unknown_record_type(self) -> None:
        service = self._build_service(
            FakeAuditTranscriptRunner([{
                "finding_id": "first",
                "record_type": "other",
                "status": "resolved",
                "reasoning": "untrusted proof",
            }])
        )

        result = service.execute(self._command(self._prior()))

        assert result.items[0].status is ReviewItemStatus.OPEN

    def test_uses_positional_results_for_legacy_transcript(self) -> None:
        service = self._build_service(
            FakeAuditTranscriptRunner([{
                "finding_index": 1,
                "status": "resolved",
                "reasoning": "src/a.py:20 current source and reproduction prove the fix",
            }])
        )

        result = service.execute(self._command(self._prior()))

        assert [item.status for item in result.items] == [
            ReviewItemStatus.OPEN,
            ReviewItemStatus.RESOLVED,
        ]

    @staticmethod
    def _item(item_id: str, status: ReviewItemStatus = ReviewItemStatus.OPEN) -> ReviewItem:
        return ReviewItem(
            severity="major",
            category="correctness",
            file_path="src/a.py",
            description=item_id,
            id=item_id,
            status=status,
        )

    @classmethod
    def _prior(cls) -> list[ReviewItem]:
        return [cls._item("first"), cls._item("second")]

    @classmethod
    def _command(
        cls,
        prior_items: list[ReviewItem],
        prior_suggestions: list[ReviewItem] | None = None,
        prior_lifecycles: tuple[ReviewItemLifecycle, ...] = (),
        current_sha: str = "current-sha",
    ) -> AuditRemediationCommand:
        return AuditRemediationCommand(
            prior_items=prior_items,
            prior_suggestions=prior_suggestions or [],
            prior_lifecycles=prior_lifecycles,
            repo_path=Path("."),
            changed_files=["src/a.py"],
            review_session="s",
            current_sha=current_sha,
        )

    @staticmethod
    def _build_service(
        runner: FakeAuditTranscriptRunner,
    ) -> RemediationAuditService:
        return RemediationAuditService(
            transcript_runner=runner,
            audit_prompt="PROMPT\n{findings}",
            command_bus=None,
        )
