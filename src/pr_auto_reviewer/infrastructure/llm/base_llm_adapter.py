"""BaseLlmAdapter — abstract base class for direct LLM review adapters."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from pr_auto_reviewer.application.ports.outbound.llm_review_port import (
    LlmReviewPort,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
    ComposedPrompt,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
    PullRequestDiff,
)
from pr_auto_reviewer.domain.value_objects.repository_context import (
    RepositoryContext,
)
from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder
from pr_auto_reviewer.infrastructure.llm.response_normalizer import (
    RetryPromptBuilder,
)
from pr_auto_reviewer.infrastructure.llm.retry_orchestrator import (
    RetryOrchestrator,
)
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)

logger = logging.getLogger(__name__)

_SEPARATOR_LINE = "=" * 72


class BaseLlmAdapter(LlmReviewPort, ABC):
    """Abstract base adapter managing prompt assembly, retries, and review parsing."""

    backend_name: str = "base"

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
        timeout: int = 120,
        max_retries: int = 5,
        response_parser: ReviewResponseParser | None = None,
    ) -> None:
        """Initialize base LLM adapter parameters and orchestrators."""
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries
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
        self._retry_builder = RetryPromptBuilder()
        self._orchestrator = RetryOrchestrator(
            retry_builder=self._retry_builder,
            max_retries=self._max_retries,
        )
        self._response_parser = response_parser or ReviewResponseParser()

    def review(
        self, diff: PullRequestDiff, context: RepositoryContext
    ) -> CodeReview:
        """Build prompt from diff and context via PromptBuilder, then execute review."""
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

    @abstractmethod
    def _send_request(
        self, prompt_text: str, timeout: int
    ) -> tuple[str, float, Any, float]:
        """Send prompt to the backend and return raw text and timing stats."""
        ...

    def _dump_prompt_to_file(self, prompt_text: str, attempt: int) -> None:
        """Persist the prompt text to a temporary diagnostic file."""
        label = "correction" if attempt > 0 else "initial"
        dump_path = (
            f"/tmp/pr-reviewer-prompt-{self.backend_name}"
            f"-attempt-{attempt + 1}-{label}.txt"
        )
        with open(dump_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(prompt_text)
        logger.debug(
            "Try %d/%d — prompt dumped to %s (%d chars)",
            attempt + 1,
            self._max_retries,
            dump_path,
            len(prompt_text),
        )

    def _log_review_items(self, review: CodeReview) -> None:
        """Log structured review items when debug logging is active."""
        if not logger.isEnabledFor(logging.DEBUG) or not review.items:
            return
        logger.debug("Review items:")
        for item in review.items:
            logger.debug(
                "  [%s] %s (%s) — %s",
                item.severity.value.upper(),
                item.file_path or "(no file)",
                item.category,
                item.description,
            )

    def _log_review_summary(
        self, review: CodeReview, prompt_chars: int
    ) -> None:
        """Log top-level summary banner for the completed review."""
        if not logger.isEnabledFor(logging.DEBUG):
            return
        logger.debug(_SEPARATOR_LINE)
        logger.debug(
            "%s REVIEW SUMMARY | host=%s model=%s | "
            "prompt=%d chars (~%d tokens) | "
            "verdict=%s items=%d summary='%s'",
            self.backend_name.upper(),
            self._host,
            self._model,
            prompt_chars,
            prompt_chars // 4,
            review.verdict.value,
            len(review.items),
            (review.summary or "")[:80],
        )
        logger.debug(_SEPARATOR_LINE)

    def _call_llm(self, prompt_text: str) -> CodeReview:
        """Execute review request through correction orchestrator and parser."""
        prompt_chars = len(prompt_text)

        def _execute(payload_text: str) -> str:
            raw_text, _, _, _ = self._send_request(
                payload_text, self._timeout
            )
            return raw_text

        def _parse(raw_text: str) -> CodeReview:
            return self._response_parser.parse(raw_text, self._model)

        review = self._orchestrator.execute_with_correction(
            execute_fn=_execute,
            parse_fn=_parse,
            original_prompt=prompt_text,
            on_before_attempt=self._dump_prompt_to_file,
        )
        self._log_review_items(review)
        self._log_review_summary(review, prompt_chars)
        return review
