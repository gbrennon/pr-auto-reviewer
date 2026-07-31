"""Tests for OllamaExploratoryChatAdapter full-review retry logic."""

from __future__ import annotations
from pathlib import Path

import json
import time as _time
import tempfile
from typing import Any, cast

import pytest
import requests as _requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter import (
    OllamaExploratoryChatAdapter,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from tests.pr_auto_reviewer.infrastructure.llm._test_helpers import (
    TestHelpers,
    _FakeStreamingResponse,
)


class TestRuleOfTrialsFullRetry:
    """Tests for full-review retry logic (_run_phases_full_retry)."""

    def test_full_retry_exhausted_returns_accumulated_items(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """When all full-review attempts are exhausted, return accumulated items."""
        accumulated_items: list[ReviewItem] = []

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("CHANGES_REQUESTED")
            )

        def fake_run_phases(*args: object, **kwargs: object) -> CodeReview:
            if not accumulated_items:
                accumulated_items.append(
                    ReviewItem(
                        number=1,
                        severity=ItemSeverity.MAJOR,
                        category=IssueCategory.SECURITY,
                        file_path="src/foo.py",
                        description="SQL injection risk",
                        line="42",
                        current_code="query = 'SELECT * FROM users WHERE id = ' + uid",
                        suggested_fix="query = 'SELECT * FROM users WHERE id = %s'",
                    )
                )
            accum = cast("list[ReviewItem]", args[2])
            accum.extend(accumulated_items)
            raise LlmUnavailableError("Phase exceeded max turns")

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            adapter,
            "_run_phases",
            fake_run_phases,
        )

        result = adapter.review_prompt(prompt_with_repo)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert result.items[0].description == "SQL injection risk"

    def test_full_retry_exhausted_with_no_items_returns_approved(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """When all full-review attempts are exhausted with no items, return APPROVED."""

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("APPROVED", issues=[])
            )

        def fake_run_phases(*args: object, **kwargs: object) -> CodeReview:
            raise LlmUnavailableError("Phase exceeded max turns")

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            adapter,
            "_run_phases",
            fake_run_phases,
        )

        result = adapter.review_prompt(prompt_with_repo)
        assert result.verdict == ReviewVerdict.APPROVED
        assert result.reason == "No issues found across all review phases."
        assert len(result.items) == 0

    def test_full_retry_succeeds_on_second_attempt(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """When second full-review attempt succeeds, return its result."""
        attempt_count = 0

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("APPROVED", issues=[])
            )

        def fake_run_phases(*args: object, **kwargs: object) -> CodeReview:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise LlmUnavailableError("Phase exceeded max turns")
            return CodeReview(
                verdict=ReviewVerdict.APPROVED,
                reason="Second attempt succeeded",
                summary="All checks passed",
                items=[],
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            adapter,
            "_run_phases",
            fake_run_phases,
        )

        result = adapter.review_prompt(prompt_with_repo)
        assert result.verdict == ReviewVerdict.APPROVED
        assert result.reason == "Second attempt succeeded"
        assert len(result.items) == 0

    def test_full_retry_preserves_best_attempt_items(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """When all attempts fail, return items from the attempt with most items."""
        attempt_count = 0

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("CHANGES_REQUESTED")
            )

        def fake_run_phases(*args: object, **kwargs: object) -> CodeReview:
            nonlocal attempt_count
            attempt_count += 1
            items = []
            if attempt_count == 1:
                items.append(
                    ReviewItem(
                        number=1,
                        severity=ItemSeverity.MAJOR,
                        category=IssueCategory.SECURITY,
                        file_path="src/foo.py",
                        description="First attempt item",
                        line="42",
                        current_code="bad code 1",
                        suggested_fix="good code 1",
                    )
                )
            elif attempt_count == 2:
                items.extend([
                    ReviewItem(
                        number=1,
                        severity=ItemSeverity.CRITICAL,
                        category=IssueCategory.SECURITY,
                        file_path="src/bar.py",
                        description="Second attempt item 1",
                        line="10",
                        current_code="bad code 2",
                        suggested_fix="good code 2",
                    ),
                    ReviewItem(
                        number=2,
                        severity=ItemSeverity.MAJOR,
                        category=IssueCategory.BUG,
                        file_path="src/baz.py",
                        description="Second attempt item 2",
                        line="5",
                        current_code="bad code 3",
                        suggested_fix="good code 3",
                    ),
                ])
            accum = cast("list[ReviewItem]", args[2])
            accum.extend(items)
            raise LlmUnavailableError("Phase exceeded max turns")

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            adapter,
            "_run_phases",
            fake_run_phases,
        )

        result = adapter.review_prompt(prompt_with_repo)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 2
        assert result.items[0].description == "Second attempt item 1"
        assert result.items[1].description == "Second attempt item 2"

    def test_full_retry_injects_previous_findings_as_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Full-review retry injects previous findings as context."""
        attempt_count = 0
        captured_prompt: str | None = None

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("APPROVED", issues=[])
            )

        def fake_run_phases(*args: object, **kwargs: object) -> CodeReview:
            nonlocal attempt_count, captured_prompt
            attempt_count += 1
            if attempt_count == 1:
                raise LlmUnavailableError("Phase exceeded max turns")
            # Second attempt should succeed
            return CodeReview(
                verdict=ReviewVerdict.APPROVED,
                reason="Second attempt with context",
                summary="All checks passed",
                items=[],
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            adapter,
            "_run_phases",
            fake_run_phases,
        )

        result = adapter.review_prompt(prompt_with_repo)
        assert result.verdict == ReviewVerdict.APPROVED
        assert result.reason == "Second attempt with context"
        assert len(result.items) == 0


class TestBuildFeedbackContext:
    """Tests for _build_feedback_context static method."""

    def test_round_1_includes_escalation_and_verdict(self) -> None:
        result = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="No issues found across all review phases.",
            model_used="test-model",
        )
        context = OllamaExploratoryChatAdapter._build_feedback_context(result, 1)
        assert "Attempt #1" in context
        assert "This is unusual for a real code change" in context
        assert "approved" in context
        assert "No issues found across all review phases." in context

    def test_round_2_includes_harder_escalation_and_verdict(self) -> None:
        result = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="Prior attempt found nothing.",
            model_used="test-model",
        )
        context = OllamaExploratoryChatAdapter._build_feedback_context(result, 2)
        assert "Attempt #2" in context
        assert "This is your 2nd attempt" in context
        assert "Every prior attempt also found nothing" in context
        assert "changes_requested" in context
        assert "Prior attempt found nothing." in context


class TestFeedbackLoop:
    """Tests for _run_feedback_loop triggered from _run_phases_full_retry."""

    def test_feedback_loop_triggers_when_phases_return_zero_items(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """When _run_phases returns zero items, feedback loop re-runs and returns fresh items."""
        call_count = 0

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("CHANGES_REQUESTED")
            )

        def fake_run_phases(
            repo_path: str,
            changed_files: list[str],
            *_args: object,
            initial_feedback: str = "",
            **kwargs: object,
        ) -> CodeReview:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return CodeReview(
                    verdict=ReviewVerdict.APPROVED,
                    reason="No issues found.",
                    model_used="test-model",
                )
            return CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                reason="Found issues on feedback re-run.",
                model_used="test-model",
                items=[
                    ReviewItem(
                        number=1,
                        severity=ItemSeverity.MAJOR,
                        category=IssueCategory.SECURITY,
                        file_path="src/foo.py",
                        description="SQL injection via feedback loop",
                        line="42",
                        current_code="bad",
                        suggested_fix="good",
                    )
                ],
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(adapter, "_run_phases", fake_run_phases)

        result = adapter.review_prompt(prompt_with_repo)
        assert call_count >= 2
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert result.items[0].description == "SQL injection via feedback loop"

    def test_feedback_loop_exhausted_returns_last_result(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """All feedback rounds exhausted with zero items → return last result."""
        call_count = 0

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("APPROVED", issues=[])
            )

        def fake_run_phases(
            repo_path: str,
            changed_files: list[str],
            *_args: object,
            initial_feedback: str = "",
            **kwargs: object,
        ) -> CodeReview:
            nonlocal call_count
            call_count += 1
            return CodeReview(
                verdict=ReviewVerdict.APPROVED,
                reason=f"Attempt {call_count}: no issues.",
                model_used="test-model",
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(adapter, "_run_phases", fake_run_phases)

        result = adapter.review_prompt(prompt_with_repo)
        assert call_count == 1 + adapter._MAX_FEEDBACK_ROUNDS
        assert result.verdict == ReviewVerdict.APPROVED
        assert len(result.items) == 0

    def test_feedback_loop_llm_unavailable_returns_previous(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """LlmUnavailableError during feedback → returns previous_result immediately."""
        call_count = 0

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("APPROVED", issues=[])
            )

        def fake_run_phases(
            repo_path: str,
            changed_files: list[str],
            *_args: object,
            initial_feedback: str = "",
            **kwargs: object,
        ) -> CodeReview:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return CodeReview(
                    verdict=ReviewVerdict.APPROVED,
                    reason="Initial zero-item result.",
                    model_used="test-model",
                )
            raise LlmUnavailableError("Phase exceeded max turns")

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(adapter, "_run_phases", fake_run_phases)

        result = adapter.review_prompt(prompt_with_repo)
        assert call_count == 2
        assert result.verdict == ReviewVerdict.APPROVED
        assert result.reason == "Initial zero-item result."
        assert len(result.items) == 0
