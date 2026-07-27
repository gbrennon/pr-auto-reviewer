"""RetryOrchestrator — runs the retry-with-correction loop for LLM review parsing."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.infrastructure.llm.response_normalizer import (
    RetryPromptBuilder,
)

logger = logging.getLogger(__name__)


class RetryOrchestrator:
    """Execute an LLM call with retry and correction-prompt feedback.

    Delegates the actual HTTP call (``execute_fn``) and response parsing
    (``parse_fn``) to the caller so the orchestrator stays focused on the
    retry loop, backoff, and correction-prompt interaction with the model.
    """

    def __init__(
        self,
        retry_builder: RetryPromptBuilder,
        max_retries: int = 5,
    ) -> None:
        self._retry_builder = retry_builder
        self._max_retries = max_retries

    def execute_with_correction(
        self,
        execute_fn: Callable[[str], str],
        parse_fn: Callable[[str], CodeReview],
        original_prompt: str,
        on_before_attempt: Callable[[str, int], None] | None = None,
    ) -> CodeReview:
        """Run the retry loop, returning a CodeReview."""
        review: CodeReview | None = None
        correction_prompt: str | None = None
        failures: list[str] = []

        for attempt in range(self._max_retries):
            if attempt > 0:
                delay = 2 ** (attempt - 1)
                logger.info(
                    "Try %d/%d — waiting %ds (previous failures: %s)",
                    attempt + 1, self._max_retries, delay,
                    ", ".join(failures[:3]),
                )
                time.sleep(delay)
            else:
                logger.info("Try 1/%d — sending review prompt", self._max_retries)

            current_prompt = correction_prompt if correction_prompt else original_prompt

            if on_before_attempt is not None:
                on_before_attempt(current_prompt, attempt)

            raw_text = execute_fn(current_prompt)

            review = parse_fn(raw_text)
            logger.info(
                "Try %d/%d — verdict=%s items=%d summary='%s'",
                attempt + 1, self._max_retries,
                review.verdict.value, len(review.items),
                (review.summary or "")[:80],
            )

            failures = self._retry_builder.diagnose_failures(review)
            if not failures:
                logger.info("Try %d/%d — accepted (no failures)", attempt + 1, self._max_retries)
                break

            correction_prompt = self._retry_builder.build_correction_prompt(original_prompt, failures)
            logger.info("Try %d/%d — rejected with %d failure(s):", attempt + 1, self._max_retries, len(failures))
            for f in failures:
                logger.info("Try %d/%d —   → %s", attempt + 1, self._max_retries, f)

        if review is None:
            raise LlmUnavailableError("LLM did not return a parseable review")

        return review
