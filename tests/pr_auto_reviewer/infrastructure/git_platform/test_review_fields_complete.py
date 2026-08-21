"""Regression tests: review pipeline must never emit empty JSON fields.

Covers the fixes that made the terminal review output carry real content:
LLM item dicts with ``issue``/``severity`` keys survive normalization and
the factory; suggestions are grounded against repo files; the terminal
JSON omits empty nested fields; and the ``commented`` verdict is the
failure marker, not a silent default.
"""

import json
from pathlib import Path

from pr_auto_reviewer.application.services.turn_parser import TurnParser
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.services.review_item_factory import ReviewItemFactory
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)
from pr_auto_reviewer.infrastructure.review_publishers.terminal_publisher import (
    TerminalReviewPublisherAdapter,
)
from tests.fakes.fake_review_body_renderer_factory import FakeReviewBodyRendererFactory


_BODY = FakeReviewBodyRendererFactory.make()


class TestItemDictNormalization:
    """LLM items using ``issue``/``severity`` keys must survive parsing."""

    def test_issue_key_maps_to_description_and_suggested_fix(self) -> None:
        normalized = ReviewResponseParser._normalize_item_dict({
            "file": "src/a.py",
            "issue": "Missing validation for phase dependencies.",
            "severity": "High",
        })
        assert normalized["description"] == (
            "Missing validation for phase dependencies."
        )
        assert normalized["severity"] == "major"
        assert normalized["suggested_fix"] != ""
        assert normalized["current_code"] == ""

    def test_high_severity_maps_to_major(self) -> None:
        normalized = ReviewResponseParser._normalize_item_dict({
            "file": "a.py", "issue": "x", "severity": "High",
        })
        assert normalized["severity"] == "major"

    def test_medium_severity_maps_to_minor(self) -> None:
        normalized = ReviewResponseParser._normalize_item_dict({
            "file": "a.py", "issue": "x", "severity": "medium",
        })
        assert normalized["severity"] == "minor"


class TestTurnParserItemExtraction:
    """TurnParser must pass normalized item dicts into raw_items."""

    def test_verdict_branch_normalizes_issue_items(self) -> None:
        parser = TurnParser(ReviewResponseParser())
        result = parser._parse(json.dumps({
            "verdict": "Needs Improvement",
            "reason": "lacks error handling",
            "items": [
                {"file": "src/a.py", "issue": "No error handling.",
                 "severity": "High"},
            ],
        }))
        assert result.kind == "verdict"
        assert result.metadata is not None
        assert len(result.raw_items or []) == 1
        assert result.raw_items[0]["description"] == "No error handling."
        assert result.raw_items[0]["severity"] == "major"

    def test_verdict_branch_keeps_string_items_out_of_raw_items(self) -> None:
        parser = TurnParser(ReviewResponseParser())
        result = parser._parse(json.dumps({
            "verdict": "approved",
            "items": ["Review multi_phase_orchestrator.py"],
        }))
        assert result.kind == "verdict"
        assert result.raw_items == []
        assert result.metadata is not None
        assert result.metadata["suggestions"] != []

    def test_positive_verdict_coerces_to_approved(self) -> None:
        parser = TurnParser(ReviewResponseParser())
        result = parser._parse(json.dumps({
            "verdict": "Positive",
            "reason": "codebase is clean",
            "items": [],
        }))
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"

    def test_no_issues_found_coerces_to_approved(self) -> None:
        parser = TurnParser(ReviewResponseParser())
        result = parser._parse(json.dumps({
            "verdict": "no_issues_found",
            "items": [],
        }))
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"


class TestFactoryKeepsUnverifiedItems:
    """Factory must not drop items solely for missing code snippets."""

    def test_item_without_code_survives_with_evidence(self, tmp_path) -> None:
        repo = tmp_path / "repo"
        target = repo / "src" / "multi_phase_review_orchestrator.py"
        target.parent.mkdir(parents=True)
        target.write_text(
            "def run_phases(self, plan):\n"
            "    for phase in plan.phases:\n"
            "        process(phase)\n"
        )
        factory = ReviewItemFactory()
        normalized = ReviewResponseParser._normalize_item_dict({
            "file": "src/multi_phase_review_orchestrator.py",
            "issue": "Missing validation for phase dependencies.",
            "severity": "high",
        })
        items, _skips = factory.create(
            [normalized],
            repo,
            ["src/multi_phase_review_orchestrator.py"],
        )
        assert len(items) == 1
        assert items[0].description == (
            "Missing validation for phase dependencies."
        )
        assert items[0].suggested_fix != ""
        assert items[0].current_code != ""


class TestTerminalJsonNoEmptyFields:
    """Final JSON output must never contain empty nested fields."""

    def _publish_json(self, tmp_path: Path, review: CodeReview) -> dict:
        out_file = tmp_path / "review.txt"
        adapter = TerminalReviewPublisherAdapter(
            body_renderer=_BODY,
            output_path=str(out_file),
        )
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        mark = "--- JSON ---\n"
        content = out_file.read_text()
        payload = content.split(mark, 1)[1].split("\n===", 1)[0]
        return json.loads(payload)

    def test_full_review_has_no_empty_values(self, tmp_path: Path) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="lacks error handling",
            summary="lacks error handling",
            items=[
                ReviewItem(
                    severity=ItemSeverity.MAJOR,
                    category=IssueCategory.MAINTAINABILITY,
                    file_path="src/a.py",
                    description="Missing validation.",
                    line="10-14",
                    id="ab12",
                    current_code="def f():",
                    suggested_fix="Add validation.",
                ),
            ],
            suggestions=[ReviewItem(
                    severity="info",
                    category="general",
                    file_path="src/a.py",
                    line="10-14",
                    description="Add validation.",
                    current_code="def f():",
                    suggested_fix="Add validation.",
                )],
            praise=[ReviewItem(
                    severity="info",
                    category="general",
                    file_path="",
                    description="Good structure.",
                    line="",
                    id="",
                    current_code="",
                    suggested_fix="Good structure.",
                )],
            model_used="code-review:latest",
        )
        payload = self._publish_json(tmp_path, review)
        assert payload["verdict"] == "changes_requested"
        assert payload["reason"] != ""
        assert payload["summary"] != ""
        assert payload["items"] != []
        assert payload["suggestions"] != []
        assert payload["praise"] != []
        assert payload["model_used"] != ""

        def _assert_no_empty(value):
            if isinstance(value, dict):
                for key, val in value.items():
                    assert val not in ("", None), f"empty {key}={val!r}"
                    _assert_no_empty(val)
            elif isinstance(value, list):
                for val in value:
                    _assert_no_empty(val)

        _assert_no_empty(payload)

    def test_string_suggestion_omits_empty_code_fields(self, tmp_path: Path) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="ok",
            summary="ok",
            suggestions=[ReviewItem(
                    severity="info",
                    category="general",
                    file_path="",
                    description="Implement rate limiting for LLM calls",
                    line="",
                    id="",
                    current_code="",
                    suggested_fix="Implement rate limiting for LLM calls",
                )],
            model_used="m",
        )
        payload = self._publish_json(tmp_path, review)
        suggestion = payload["suggestions"][0]
        assert suggestion["description"]
        assert "current_code" not in suggestion
        assert "suggested_code" not in suggestion
        assert "file" not in suggestion
        assert "line" not in suggestion

    def test_praise_omits_empty_file(self, tmp_path: Path) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="ok",
            summary="ok",
            praise=[ReviewItem(
                    severity="info",
                    category="general",
                    file_path="",
                    description="Good structure.",
                    line="",
                    id="",
                    current_code="",
                    suggested_fix="Good structure.",
                )],
            model_used="m",
        )
        payload = self._publish_json(tmp_path, review)
        praise = payload["praise"][0]
        assert praise["description"]
        assert "file" not in praise


class TestOrchestratorCommentedIsFailureMarker:
    """``commented`` must stay as the failure marker with diagnostic fills."""

    @staticmethod
    def _build_review_orchestrator():
        from pr_auto_reviewer.application.services.multi_phase_review_orchestrator import (
            MultiPhaseReviewOrchestrator,
        )
        from pr_auto_reviewer.domain.agent.turn_parse_result import TurnParseResult
        from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
            ParseReviewTurnCommand,
        )
        from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
            InMemoryCommandBus,
        )
        from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
            ReviewResponseParser,
        )

        bus = InMemoryCommandBus()
        parser = ReviewResponseParser()

        def _parse_turn(command: ParseReviewTurnCommand) -> TurnParseResult:
            return TurnParser(parser)._parse(command.content)

        bus.register(ParseReviewTurnCommand, _parse_turn)
        return MultiPhaseReviewOrchestrator(
            command_bus=bus, tool_factory=lambda *a: None
        ), bus

    def test_legit_llm_verdict_survives_no_items_path(self) -> None:
        from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
        from pr_auto_reviewer.domain.agent.review_phase import ReviewPhase
        from pr_auto_reviewer.domain.agent.review_plan import ReviewPlan
        from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
            RunAgentConversationCommand,
        )

        orchestrator, bus = self._build_review_orchestrator()

        def _run_phase(command: RunAgentConversationCommand) -> PhaseResult:
            return PhaseResult(
                items=[],
                llm_verdict="approved",
                llm_reason="No critical bugs identified.",
                llm_suggestions=[
                    {"file": "", "line": "", "description": "Add rate limiting."}
                ],
            )

        bus.register(RunAgentConversationCommand, _run_phase)
        plan = ReviewPlan(
            methodology="review",
            phases=(ReviewPhase(
                phase_id="advisor", phase_name="Advisor", system_prompt="x"
            ),),
        )
        review = orchestrator._run_phases_full_retry(
            plan=plan,
            repo_path=Path("."),
            changed_files=[],
            model="code-review:latest",
        )
        assert review.verdict == ReviewVerdict.APPROVED
        assert review.reason != ""
        assert review.summary != ""
        assert review.suggestions != []

    def test_comment_stays_marker_with_diagnostics(self) -> None:
        from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
        from pr_auto_reviewer.domain.agent.review_phase import ReviewPhase
        from pr_auto_reviewer.domain.agent.review_plan import ReviewPlan
        from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
            RunAgentConversationCommand,
        )

        orchestrator, bus = self._build_review_orchestrator()

        def _run_phase(command: RunAgentConversationCommand) -> PhaseResult:
            return PhaseResult(items=[], llm_verdict="commented")

        bus.register(RunAgentConversationCommand, _run_phase)
        plan = ReviewPlan(
            methodology="review",
            phases=(ReviewPhase(
                phase_id="advisor", phase_name="Advisor", system_prompt="x"
            ),),
        )
        review = orchestrator._run_phases_full_retry(
            plan=plan,
            repo_path=Path("."),
            changed_files=[],
            model="code-review:latest",
        )
        assert review.verdict == ReviewVerdict.COMMENTED
        assert review.reason != ""
        assert review.summary != ""
        assert "failure" in review.summary

    def test_rebuild_after_verification_explains_dropped_findings(self) -> None:
        from pr_auto_reviewer.application.services.multi_phase_review_orchestrator import (
            MultiPhaseReviewOrchestrator,
        )
        from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
            InMemoryCommandBus,
        )

        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=InMemoryCommandBus(), tool_factory=lambda *a: None
        )
        previous = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="Found 1 critical (1 maintainability) and 2 major.",
            summary="Found 3 issue(s) (3 blocking across 3 file(s)).",
            items=[
                ReviewItem(id="id-1",
                    severity=ItemSeverity.CRITICAL,
                    category=IssueCategory.MAINTAINABILITY,
                    file_path="src/a.py",
                    description="Missing validation.",
                    current_code="def f():",
                    suggested_fix="Add validation.",
                ),
                ReviewItem(id="id-2",
                    severity=ItemSeverity.MAJOR,
                    category=IssueCategory.MAINTAINABILITY,
                    file_path="src/b.py",
                    description="No error handling.",
                    current_code="def g():",
                    suggested_fix="Add handling.",
                ),
            ],
            model_used="code-review:latest",
        )
        rebuilt = orchestrator._rebuild_after_verification(
            [], "code-review:latest", previous=previous
        )
        assert rebuilt.items == []
        assert "dropped" in rebuilt.reason
        assert "did not survive" in rebuilt.summary
        assert "2" in rebuilt.summary
        assert "3" not in rebuilt.reason