"""Tests for RetryOrchestrator."""

from typing import cast

import pytest

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.response_normalizer import (
    RetryPromptBuilder,
)
from pr_auto_reviewer.infrastructure.llm.retry_orchestrator import (
    RetryOrchestrator,
)


class _FakeRetryPromptBuilder:
    """Stub RetryPromptBuilder that returns a configurable sequence of failures."""

    def __init__(self, failures_sequence: list[list[str]] | None = None) -> None:
        self._failures_sequence = failures_sequence or [[]]
        self._call_index = 0
        self.diagnose_calls: list[CodeReview] = []
        self.build_calls: list[tuple[str, list[str]]] = []

    def diagnose_failures(self, review: CodeReview) -> list[str]:
        self.diagnose_calls.append(review)
        idx = min(self._call_index, len(self._failures_sequence) - 1)
        failures = self._failures_sequence[idx]
        self._call_index += 1
        return list(failures)

    def build_correction_prompt(
        self, original_prompt: str, failures: list[str],
    ) -> str:
        self.build_calls.append((original_prompt, list(failures)))
        return f"CORRECTION: {original_prompt}"


class TestRetryOrchestrator:
    """Tests for RetryOrchestrator.execute_with_correction."""

    def _make_review_with_items(
        self, verdict: ReviewVerdict = ReviewVerdict.CHANGES_REQUESTED,
    ) -> CodeReview:
        items = [
            ReviewItem(id="id-1",
                severity=ItemSeverity.MAJOR,
                category=IssueCategory.BUG,
                file_path="src/foo.py",
                description="Null pointer risk",
                current_code="x()",
                suggested_fix="if x: x()",
            ),
        ]
        return CodeReview(
            verdict=verdict,
            reason="Issues found",
            items=items,
            model_used="test-model",
        )

    def test_success_on_first_attempt(self) -> None:
        builder = _FakeRetryPromptBuilder()
        orchestrator = RetryOrchestrator(
            retry_builder=cast(RetryPromptBuilder, builder),
        )
        execute_calls: list[str] = []
        parse_calls: list[str] = []

        def _execute(prompt: str) -> str:
            execute_calls.append(prompt)
            return "RAW REVIEW TEXT"

        def _parse(raw_text: str) -> CodeReview:
            parse_calls.append(raw_text)
            return self._make_review_with_items()

        result = orchestrator.execute_with_correction(
            execute_fn=_execute,
            parse_fn=_parse,
            original_prompt="Review this PR",
        )

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert len(execute_calls) == 1
        assert execute_calls[0] == "Review this PR"
        assert len(parse_calls) == 1
        assert len(builder.diagnose_calls) == 1
        assert builder.build_calls == []

    def test_retries_on_diagnose_failure_then_succeeds(self) -> None:
        builder = _FakeRetryPromptBuilder([["missing fields"], []])
        orchestrator = RetryOrchestrator(
            retry_builder=cast(RetryPromptBuilder, builder),
        )
        execute_calls: list[str] = []

        def _execute(prompt: str) -> str:
            execute_calls.append(prompt)
            return "RAW"

        def _parse(raw_text: str) -> CodeReview:
            return self._make_review_with_items()

        result = orchestrator.execute_with_correction(
            execute_fn=_execute,
            parse_fn=_parse,
            original_prompt="PR review",
        )

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(execute_calls) == 2
        assert execute_calls[0] == "PR review"
        assert execute_calls[1] == "CORRECTION: PR review"
        assert len(builder.diagnose_calls) == 2
        assert len(builder.build_calls) == 1

    def test_max_retries_exhausted_returns_last_review(self) -> None:
        builder = _FakeRetryPromptBuilder([["a"], ["b"], ["c"]])
        orchestrator = RetryOrchestrator(
            retry_builder=cast(RetryPromptBuilder, builder),
            max_retries=3,
        )
        execute_calls: list[str] = []

        def _execute(prompt: str) -> str:
            execute_calls.append(prompt)
            return "RAW"

        def _parse(raw_text: str) -> CodeReview:
            return self._make_review_with_items()

        result = orchestrator.execute_with_correction(
            execute_fn=_execute,
            parse_fn=_parse,
            original_prompt="PR",
        )

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(execute_calls) == 3
        assert len(builder.diagnose_calls) == 3
        assert len(builder.build_calls) == 3

    def test_zero_max_retries_raises_llm_unavailable(self) -> None:
        builder = _FakeRetryPromptBuilder()
        orchestrator = RetryOrchestrator(
            retry_builder=cast(RetryPromptBuilder, builder),
            max_retries=0,
        )

        def _execute(prompt: str) -> str:
            return "RAW"

        def _parse(raw_text: str) -> CodeReview:
            return self._make_review_with_items()

        with pytest.raises(
            LlmUnavailableError, match="did not return a parseable review",
        ):
            orchestrator.execute_with_correction(
                execute_fn=_execute,
                parse_fn=_parse,
                original_prompt="PR",
            )

    def test_execute_fn_exception_propagates(self) -> None:
        builder = _FakeRetryPromptBuilder()
        orchestrator = RetryOrchestrator(
            retry_builder=cast(RetryPromptBuilder, builder),
        )

        class TestError(Exception):
            pass

        def _execute(prompt: str) -> str:
            raise TestError("boom")

        def _parse(raw_text: str) -> CodeReview:
            return self._make_review_with_items()

        with pytest.raises(TestError, match="boom"):
            orchestrator.execute_with_correction(
                execute_fn=_execute,
                parse_fn=_parse,
                original_prompt="PR",
            )

    def test_parse_fn_exception_propagates(self) -> None:
        builder = _FakeRetryPromptBuilder()
        orchestrator = RetryOrchestrator(
            retry_builder=cast(RetryPromptBuilder, builder),
        )

        class TestError(Exception):
            pass

        def _execute(prompt: str) -> str:
            return "RAW"

        def _parse(raw_text: str) -> CodeReview:
            raise TestError("bad parse")

        with pytest.raises(TestError, match="bad parse"):
            orchestrator.execute_with_correction(
                execute_fn=_execute,
                parse_fn=_parse,
                original_prompt="PR",
            )

    def test_backoff_sleep_on_retry(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import pr_auto_reviewer.infrastructure.llm.retry_orchestrator as mod

        sleep_calls: list[float] = []
        monkeypatch.setattr(mod.time, "sleep", sleep_calls.append)
        builder = _FakeRetryPromptBuilder([["fail1"], ["fail2"], []])
        orchestrator = RetryOrchestrator(
            retry_builder=cast(RetryPromptBuilder, builder),
            max_retries=5,
        )

        def _execute(prompt: str) -> str:
            return "RAW"

        def _parse(raw_text: str) -> CodeReview:
            return self._make_review_with_items()

        orchestrator.execute_with_correction(
            execute_fn=_execute,
            parse_fn=_parse,
            original_prompt="PR",
        )

        assert sleep_calls == [1.0, 2.0]

    def test_on_before_attempt_callback(self) -> None:
        builder = _FakeRetryPromptBuilder([["fail1"], []])
        orchestrator = RetryOrchestrator(
            retry_builder=cast(RetryPromptBuilder, builder),
        )
        callback_calls: list[tuple[str, int]] = []

        def _on_before(prompt: str, attempt: int) -> None:
            callback_calls.append((prompt, attempt))

        def _execute(prompt: str) -> str:
            return "RAW"

        def _parse(raw_text: str) -> CodeReview:
            return self._make_review_with_items()

        orchestrator.execute_with_correction(
            execute_fn=_execute,
            parse_fn=_parse,
            original_prompt="ORIGINAL",
            on_before_attempt=_on_before,
        )

        assert len(callback_calls) == 2
        assert callback_calls[0] == ("ORIGINAL", 0)
        assert callback_calls[1] == ("CORRECTION: ORIGINAL", 1)
