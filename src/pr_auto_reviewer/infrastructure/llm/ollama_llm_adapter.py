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

    def __init__(self, host: str, model: str) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._prompt_builder = PromptBuilder()

    def review(self, diff: PullRequestDiff, context: RepositoryContext) -> CodeReview:
        t0 = time.monotonic()
        logger.info("Calling Ollama at %s with model %s", self._host, self._model)

        prompt = self._prompt_builder.build(diff, context)
        prompt_chars = len(prompt)
        logger.info("Prompt built: %d chars", prompt_chars)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(_SEP)
            logger.debug("FULL PROMPT (%d chars):\n%s", prompt_chars, prompt)
            logger.debug(_SEP)

        timeout = int(os.getenv("OLLAMA_TIMEOUT", 120))
        try:
            response = requests.post(
                f"{self._host}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
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
