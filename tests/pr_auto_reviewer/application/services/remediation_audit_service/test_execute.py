from __future__ import annotations

from pathlib import Path

from pr_auto_reviewer.application.services.remediation_audit_service import (
    RemediationAuditService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.audit_remediation_command import (
    AuditRemediationCommand,
)


class FakeAuditTranscriptRunner:
    """Fake transcript seam returning canned audit results."""

    def __init__(self, results: list[dict]) -> None:
        self._results = results

    def run(self, **kwargs: object) -> tuple[list[dict], list]:
        return self._results, []


class NullCommandBus:
    """No-op command bus capturing nothing."""

    def dispatch(self, *args: object, **kwargs: object) -> None:
        return None


class TestRemediationAuditExecute:
    """The auditor resolves prior findings only with explicit proof."""

    def test_keeps_open_when_not_proven(self) -> None:
        service = self._build_service(
            FakeAuditTranscriptRunner(
                [{"finding_index": 0, "status": "open", "reasoning": "still raises"}]
            )
        )
        out = service.execute(self._command())
        assert out[0].status == "open"

    def test_resolves_only_with_proof(self) -> None:
        service = self._build_service(
            FakeAuditTranscriptRunner(
                [{
                    "finding_index": 0,
                    "status": "resolved",
                    "reasoning": "fixed + repro passes",
                }]
            )
        )
        out = service.execute(self._command())
        assert out[0].status == "resolved"

    def test_defaults_open_when_result_missing(self) -> None:
        service = self._build_service(FakeAuditTranscriptRunner([]))
        out = service.execute(self._command())
        assert out[0].status == "open"

    def test_defaults_open_when_transcript_aborts(self) -> None:
        service = self._build_service(FakeAuditTranscriptRunner(None))
        out = service.execute(self._command())
        assert out[0].status == "open"

    @staticmethod
    def _prior() -> list[ReviewItem]:
        return [
            ReviewItem(
                severity="major",
                category="correctness",
                file_path="src/a.py",
                description="off-by-one",
                id="aaaa",
                reproduction="parse([1,2,3]) -> IndexError",
                acceptance_criteria="parse returns 3 items, no error",
                detection_method="boundary analysis",
            ),
        ]

    @classmethod
    def _command(cls) -> AuditRemediationCommand:
        return AuditRemediationCommand(
            prior_items=cls._prior(),
            repo_path=Path("."),
            changed_files=["src/a.py"],
            review_session="s",
        )

    @staticmethod
    def _build_service(
        runner: FakeAuditTranscriptRunner,
    ) -> RemediationAuditService:
        return RemediationAuditService(
            transcript_runner=runner,
            audit_prompt="PROMPT\n{findings}",
            command_bus=NullCommandBus(),
        )
