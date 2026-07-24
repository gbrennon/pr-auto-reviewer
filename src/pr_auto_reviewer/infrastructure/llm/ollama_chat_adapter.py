"""OllamaChatAdapter — implements LlmReviewPort using Ollama /api/chat."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.llm.review_response_parser import ReviewResponseParser

logger = logging.getLogger(__name__)


class OllamaChatAdapter(LlmReviewPort):
    """Sends a composed prompt to Ollama /api/chat and parses the review.

    Uses the chat endpoint for models fine-tuned on the chat template.
    The application drives the review — the prompt includes the full diff
    and file contents pre-computed by the changeset fetcher.
    """

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        ollama_timeout: int = 120,
        max_retries: int = 5,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = ollama_timeout
        self._max_retries = max_retries
        self._parser = ReviewResponseParser()

    def review(
        self, diff: PullRequestDiff, context: RepositoryContext,
    ) -> CodeReview:
        raise NotImplementedError(
            "Direct review() is not supported. "
            "Use the fragment-based flow via review_prompt()."
        )

    def review_prompt(self, prompt: ComposedPrompt) -> CodeReview:
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": prompt.content},
        ]

        response: dict[str, Any] | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._call_chat(messages)
                break
            except LlmUnavailableError:
                if attempt == self._max_retries - 1:
                    raise
                logger.warning(
                    "Chat attempt %d/%d failed, retrying...",
                    attempt + 1, self._max_retries,
                )
                time.sleep(2 ** attempt)

        if response is None:
            raise LlmUnavailableError("All chat requests exhausted")

        content = response.get("message", {}).get("content", "")
        if not content:
            raise LlmUnavailableError("Empty response from LLM chat API")

        return self._parser.parse(content, self._model)

    def _call_chat(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        url = f"{self._host}/api/chat"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }

        try:
            http_response = requests.post(
                url, json=payload, timeout=self._timeout,
            )
            http_response.raise_for_status()
        except requests.RequestException as exc:
            raise LlmUnavailableError(
                f"Chat request to {url} failed: {exc}"
            ) from exc

        return http_response.json()
