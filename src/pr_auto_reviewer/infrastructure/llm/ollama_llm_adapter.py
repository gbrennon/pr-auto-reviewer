"""OllamaLlmAdapter — implements LlmReviewPort using a local Ollama instance."""

import json
import logging
import time
import os
from typing import Any

import requests
from dotenv import load_dotenv

from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder
from pr_auto_reviewer.infrastructure.llm.review_response_parser import ReviewResponseParser

logger = logging.getLogger(__name__)
load_dotenv()

_SEP = "=" * 72


class OllamaLlmAdapter(LlmReviewPort):
    """Call a local Ollama instance to review a pull-request diff."""

    def __init__(self, host: str, model: str, compose_review_prompt: object | None = None, fragment_selector: object | None = None, fragment_composer: object | None = None) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._prompt_builder = PromptBuilder()
        self._compose_review_prompt = compose_review_prompt
        self._fragment_selector = fragment_selector
        self._fragment_composer = fragment_composer

    # ------------------------------------------------------------------
    # Public API — LlmReviewPort
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Internal — Ollama HTTP call
    # ------------------------------------------------------------------

    def _call_ollama(self, prompt_text: str) -> CodeReview:
        """Send *prompt_text* to Ollama, parse the response into a CodeReview."""
        t0 = time.monotonic()
        logger.info("Calling Ollama at %s with model %s", self._host, self._model)

        prompt_chars = len(prompt_text)
        logger.info("Prompt built: %d chars", prompt_chars)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(_SEP)
            logger.debug("FULL PROMPT (%d chars):\n%s", prompt_chars, prompt_text)
            logger.debug(_SEP)

        timeout = int(os.getenv("OLLAMA_TIMEOUT", 120))
        try:
            # Split first fragment (system prompt) from user prompt
            SEP = "\n\n---\n\n"
            system_text = ""
            user_text = prompt_text
            if SEP in prompt_text:
                parts = prompt_text.split(SEP, 1)
                system_text = parts[0]
                user_text = parts[1]

            req: dict = {"model": self._model, "prompt": user_text, "stream": False}
            if system_text:
                req["system"] = system_text

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

        # Ollama metrics (always useful even at INFO level).
        eval_count = body.get("eval_count", "?")
        eval_duration = body.get("eval_duration", 0) / 1e9  # ns → s
        logger.info(
            "Ollama response: %d chars, %s tokens, %.1fs eval, %.0fms wall",
            len(raw_text), eval_count, eval_duration, response_ms,
        )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(_SEP)
            logger.debug("FULL OLLAMA RESPONSE (%d chars):\n%s", len(raw_text), raw_text)
            logger.debug(_SEP)

        review = ReviewResponseParser.parse(raw_text, self._model)
        logger.info(
            "Parsed review: verdict=%s, items=%d, summary='%s...'",
            review.verdict.value, len(review.items),
            review.summary[:80] if review.summary else "",
        )

        if logger.isEnabledFor(logging.DEBUG) and review.items:
            logger.debug("Review items:")
            for item in review.items:
                logger.debug(
                    "  [%s] %s (%s) — %s",
                    item.severity.value.upper(), item.file_path or "(no file)",
                    item.category, item.description,
                )

        return review
