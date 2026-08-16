"""OllamaLlmAdapter — implements LlmReviewPort using a local Ollama instance."""

import json
import logging
import time
from typing import Any

import requests
from pr_auto_reviewer.infrastructure.llm.response_normalizer import (
    RetryPromptBuilder,
)

from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder
from pr_auto_reviewer.infrastructure.llm.review_response_parser import ReviewResponseParser
from pr_auto_reviewer.infrastructure.llm.retry_orchestrator import RetryOrchestrator
logger = logging.getLogger(__name__)

_SEP = "=" * 72


class OllamaLlmAdapter(LlmReviewPort):
    """Call a local Ollama instance to review a pull-request diff."""

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
        ollama_timeout: int = 120,
        max_retries: int = 5,
    ) -> None:

        self._host = host.rstrip("/")
        self._model = model
        self._ollama_timeout = ollama_timeout
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

    def _dump_prompt_to_file(self, prompt_text: str, attempt: int) -> None:
        label = "correction" if attempt > 0 else "initial"
        path = f"/tmp/ollama-prompt-try{attempt + 1}-{label}.txt"
        with open(path, "w") as f:
            f.write(prompt_text)
        logger.debug("Try %d/%d — prompt dumped to %s (%d chars)", attempt + 1, self._max_retries, path, len(prompt_text))

    def _request_ollama(
        self, prompt_text: str, timeout: int,
    ) -> tuple[str, float, Any, float]:
        """Send one request to Ollama and return raw response details."""
        t0 = time.monotonic()
        logger.info("Calling Ollama at %s with model %s", self._host, self._model)
        logger.info("Prompt built: %d chars", len(prompt_text))

        try:
            # Split on the fragment separator to extract the system prompt.
            # The first fragment (reviewer-system-prompt, priority 1000) is sent
            # as the "system" parameter, overriding the Modelfile's baked-in
            # system prompt. This avoids context overflow from duplicate
            # instructions and ensures consistent review behaviour.
            SEP = "\n\n---\n\n"
            system_text = ""
            user_text = prompt_text
            if SEP in prompt_text:
                parts = prompt_text.split(SEP, 1)
                system_text = parts[0]
                user_text = parts[1]

            req: dict = {
                "model": self._model,
                "prompt": user_text,
                "stream": False,
            }
            if system_text:
                req["system"] = system_text

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Ollama request payload: model=%s prompt_chars=%d system_chars=%d",
                    self._model, len(user_text), len(system_text),
                )
                logger.debug(_SEP)
                logger.debug("SYSTEM PROMPT (%d chars):\n%s", len(system_text), system_text[:500])
                logger.debug(_SEP)
                logger.debug("USER PROMPT (%d chars):\n%s", len(user_text), user_text[:1000])
                logger.debug(_SEP)

            response = requests.post(
                f"{self._host}/api/generate",
                json=req,
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Ollama request failed: %s", exc)
            raise LlmUnavailableError(
                f"Ollama @ {self._host} unreachable or error: {exc}"
            ) from exc

        t1 = time.monotonic()
        response_ms = (t1 - t0) * 1000

        try:
            body: dict[str, Any] = response.json()
        except json.JSONDecodeError as exc:
            logger.error("Ollama returned invalid JSON: %s", exc)
            raise LlmUnavailableError(
                f"Ollama returned invalid JSON: {exc}"
            ) from exc

        raw_text: str = body.get("response", "")
        if not raw_text:
            if "response" in body:
                logger.error("Ollama returned empty response")
                raise LlmUnavailableError(
                    "Ollama returned an empty response — model may have failed silently."
                )
            raw_text = json.dumps(body)
            if not raw_text or raw_text == '{}':
                logger.error("Ollama returned empty response")
                raise LlmUnavailableError(
                    "Ollama returned an empty response — model may have failed silently."
                )

        eval_count = body.get("eval_count", "?")
        eval_duration = body.get("eval_duration", 0) / 1e9
        logger.info(
            "Ollama response: %d chars, %s tokens, %.1fs eval, %.0fms wall",
            len(raw_text), eval_count, eval_duration, response_ms,
        )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(_SEP)
            logger.debug("FULL OLLAMA RESPONSE (%d chars):\n%s", len(raw_text), raw_text)
            logger.debug(_SEP)

        return raw_text, response_ms, eval_count, eval_duration

    def _call_ollama(self, prompt_text: str) -> CodeReview:
        """Send *prompt_text* to Ollama, parse the response into a CodeReview."""
        prompt_chars = len(prompt_text)

        def _execute(p: str) -> str:
            raw_text, _response_ms, _eval_count, _eval_duration = (
                self._request_ollama(p, self._ollama_timeout)
            )
            return raw_text

        def _parse(raw_text: str) -> CodeReview:
            return ReviewResponseParser().parse(raw_text, self._model)

        review = self._orchestrator.execute_with_correction(
            execute_fn=_execute,
            parse_fn=_parse,
            original_prompt=prompt_text,
            on_before_attempt=self._dump_prompt_to_file,
        )

        if logger.isEnabledFor(logging.DEBUG) and review.items:
            logger.debug("Review items:")
            for item in review.items:
                logger.debug(
                    "  [%s] %s (%s) — %s",
                    item.severity.value.upper(), item.file_path or "(no file)",
                    item.category, item.description,
                )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(_SEP)
            logger.debug(
                "OLLAMA REVIEW SUMMARY | host=%s model=%s | "
                "prompt=%d chars (~%d tokens) | "
                "verdict=%s items=%d summary='%s'",
                self._host, self._model,
                prompt_chars, prompt_chars // 4,
                review.verdict.value, len(review.items),
                (review.summary or "")[:80],
            )
            logger.debug(_SEP)

        return review

    def review(self, diff: PullRequestDiff, context: RepositoryContext) -> CodeReview:
        """Build prompt from diff+context via PromptBuilder, then call Ollama.

        Deprecated: prefer :meth:`review_prompt` with fragment-based
        composition orchestrated by the application service.
        """
        prompt_str = self._prompt_builder.build(diff, context)
        return self._call_ollama(prompt_str)

    def review_prompt(self, prompt: ComposedPrompt) -> CodeReview:
        """Send an already-composed prompt to Ollama and return a CodeReview.

        Args:
            prompt: A fully assembled prompt ready for LLM consumption.

        Returns:
            The parsed code review.
        """
        logger.info(
            "Reviewing with composed prompt: %d chars, %d tokens, %d fragments used",
            len(prompt.content),
            prompt.total_tokens,
            len(prompt.fragments_used),
        )
        return self._call_ollama(prompt.content)

