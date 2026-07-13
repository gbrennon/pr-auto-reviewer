"""BaseLlmAdapter — shared retry loop, normalization, and prompt management.

Subclasses implement :meth:`_send_request` to call a specific LLM backend API.
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any

from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder
from pr_auto_reviewer.infrastructure.llm.response_normalizer import (
    ResponseFieldNormalizer,
    RetryPromptBuilder,
)
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)

logger = logging.getLogger(__name__)

_SEP = "=" * 72


class BaseLlmAdapter(LlmReviewPort, ABC):
    """Shared logic for LLM backend adapters.

    Subclasses must implement :meth:`_send_request` for their specific API.
    """

    backend_name: str = "LLM"

    def __init__(
        self,
        host: str,
        model: str,
        compose_review_prompt: object | None = None,
        fragment_selector: object | None = None,
        fragment_composer: object | None = None,
        max_tokens: int = 9999,
        max_file_chars: int = 3000,
        max_files: int = 10,
        max_structure_lines: int = 100,
        use_compact_template: bool = False,
        _http_post: Any = None,
    ) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._prompt_builder = PromptBuilder(
            max_tokens=max_tokens,
            max_file_chars=max_file_chars,
            max_files=max_files,
            max_structure_lines=max_structure_lines,
            use_compact_template=use_compact_template,
        )
        self._compose_review_prompt = compose_review_prompt
        self._fragment_selector = fragment_selector
        self._fragment_composer = fragment_composer
        self._normalizer = ResponseFieldNormalizer()
        self._retry_builder = RetryPromptBuilder()
        self._http_post = _http_post

    @property
    def _post(self):
        """HTTP POST callable — injected or defaults to requests.post."""
        if self._http_post is not None:
            return self._http_post
        import requests
        return requests.post

    def review(self, diff: PullRequestDiff, context: RepositoryContext) -> CodeReview:
        """Build prompt from diff+context via PromptBuilder, then call LLM."""
        prompt_str = self._prompt_builder.build(diff, context)
        return self._call_llm(prompt_str)

    def review_prompt(self, prompt: ComposedPrompt) -> CodeReview:
        """Send an already-composed prompt to the LLM and return a CodeReview."""
        logger.info(
            "Reviewing with composed prompt: %d chars, %d tokens, %d fragments used",
            len(prompt.content),
            prompt.total_tokens,
            len(prompt.fragments_used),
        )
        return self._call_llm(prompt.content)

    def _call_llm(self, prompt_text: str) -> CodeReview:
        """Send *prompt_text* to the LLM backend, parse the response into a CodeReview.

        Retries up to 3 times with exponential backoff and correction prompts.
        """
        prompt_chars = len(prompt_text)
        timeout = int(os.getenv("LLM_TIMEOUT", os.getenv("OLLAMA_TIMEOUT", 120)))
        review: CodeReview | None = None
        last_response_chars = 0
        last_eval_count: Any = "?"
        last_eval_duration = 0.0
        last_response_ms = 0.0
        correction_prompt = None
        for attempt in range(3):
            if attempt > 0:
                delay = 2 ** (attempt - 1)
                logger.info(
                    "Try %d/3 — waiting %ds (previous failures: %s)",
                    attempt + 1,
                    delay,
                    ", ".join(failures[:3]),
                )
                time.sleep(delay)
            else:
                logger.info("Try 1/3 — sending review prompt to %s", self.backend_name)

            current_prompt = correction_prompt if correction_prompt else prompt_text

            self._dump_prompt_to_file(current_prompt, attempt)

            raw_text, response_ms, eval_count, eval_duration = self._send_request(
                current_prompt,
                timeout,
            )
            last_response_chars = len(raw_text)
            last_eval_count = eval_count
            last_eval_duration = eval_duration
            last_response_ms = response_ms

            review = ReviewResponseParser.parse(raw_text, self._model)
            logger.info(
                "Try %d/3 — verdict=%s items=%d summary='%s'",
                attempt + 1,
                review.verdict.value,
                len(review.items),
                (review.summary or "")[:80],
            )

            failures = self._retry_builder.diagnose_failures(review)
            if not failures:
                logger.info("Try %d/3 — accepted (no failures)", attempt + 1)
                break
            correction_prompt = self._retry_builder.build_correction_prompt(
                prompt_text, failures
            )
            logger.info(
                "Try %d/3 — rejected with %d failure(s):", attempt + 1, len(failures)
            )
            for f in failures:
                logger.info("Try %d/3 —   → %s", attempt + 1, f)

        if review is None:
            raise LlmUnavailableError(
                f"{self.backend_name} did not return a parseable review"
            )

        if logger.isEnabledFor(logging.DEBUG) and review.items:
            logger.debug("Review items:")
            for item in review.items:
                logger.debug(
                    "  [%s] %s (%s) — %s",
                    item.severity.value.upper(),
                    item.file_path or "(no file)",
                    item.category,
                    item.description,
                )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(_SEP)
            logger.debug(
                "%s REVIEW SUMMARY | host=%s model=%s | "
                "prompt=%d chars (~%d tokens) | "
                "response=%d chars %s eval_tokens %.1fs eval %.0fms wall | "
                "verdict=%s items=%d summary='%s'",
                self.backend_name.upper(),
                self._host,
                self._model,
                prompt_chars,
                prompt_chars // 4,
                last_response_chars,
                last_eval_count,
                last_eval_duration,
                last_response_ms,
                review.verdict.value,
                len(review.items),
                (review.summary or "")[:80],
            )
            logger.debug(_SEP)

        return review

    @abstractmethod
    def _send_request(
        self,
        prompt_text: str,
        timeout: int,
    ) -> tuple[str, float, Any, float]:
        """Send one request to the LLM backend and return raw response details.

        Returns:
            Tuple of (raw_text, response_ms, eval_count, eval_duration).
        """
        ...

    def _dump_prompt_to_file(self, prompt_text: str, attempt: int) -> None:
        label = "correction" if attempt > 0 else "initial"
        path = f"/tmp/pr-reviewer-prompt-{self.backend_name}-attempt-{attempt + 1}.txt"
        with open(path, "w") as fh:
            fh.write(prompt_text)
        logger.info(
            "Try %d/3 — prompt dumped to %s (%d chars)",
            attempt + 1,
            path,
            len(prompt_text),
        )
