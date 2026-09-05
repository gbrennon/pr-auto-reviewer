"""LlamaCppAdapter — implements LlmReviewPort using a llama.cpp server."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.infrastructure.llm.base_llm_adapter import BaseLlmAdapter
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)

logger = logging.getLogger(__name__)


class LlamaCppAdapter(BaseLlmAdapter):
    """Call a llama.cpp server chat completion endpoint to review a pull request."""

    backend_name: str = "llama_cpp"

    def __init__(
        self,
        host: str = "http://localhost:8080",
        model: str = "default",
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
        http_post: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize llama.cpp adapter with target endpoint and options."""
        super().__init__(
            host=host,
            model=model,
            compose_review_prompt=compose_review_prompt,
            fragment_selector=fragment_selector,
            fragment_composer=fragment_composer,
            max_tokens=max_tokens,
            max_file_chars=max_file_chars,
            max_files=max_files,
            max_structure_lines=max_structure_lines,
            use_compact_template=use_compact_template,
            timeout=timeout,
            max_retries=max_retries,
            response_parser=response_parser,
        )
        self._http_post = http_post

    def _build_messages(self, prompt_text: str) -> list[dict[str, str]]:
        """Split prompt text on fragment separator to extract system instructions."""
        separator = "\n\n---\n\n"
        if separator in prompt_text:
            system_text, user_text = prompt_text.split(separator, 1)
            return [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ]
        return [{"role": "user", "content": prompt_text}]

    def _extract_text_field(self, message: dict[str, Any], key: str) -> str:
        """Extract non-empty string field from dictionary."""
        val = message.get(key)
        if isinstance(val, str) and val.strip():
            return val
        return ""

    def _extract_content_from_message(self, message: Any) -> str:
        """Extract main content or fallback reasoning content from message payload."""
        if not isinstance(message, dict):
            return ""
        content = self._extract_text_field(message, "content")
        if content:
            return content
        return self._extract_text_field(message, "reasoning_content")

    def _extract_choice_text(self, choices: Any) -> str:
        """Extract text from the first choice in completion choices array."""
        if not isinstance(choices, list) or not choices:
            return ""
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return ""
        return self._extract_content_from_message(first_choice.get("message"))

    def _extract_content_and_timing(
        self, body: dict[str, Any], response_ms: float
    ) -> tuple[str, float, Any, float]:
        """Extract response text, token counts, and durations from completion body."""
        raw_text = self._extract_choice_text(body.get("choices"))
        if not raw_text:
            raise LlmUnavailableError(
                "llama.cpp returned an empty response — model may have failed silently."
            )
        usage = body.get("usage")
        eval_count = (
            usage.get("completion_tokens", "?")
            if isinstance(usage, dict)
            else "?"
        )
        timings = body.get("timings")
        eval_duration = 0.0
        if isinstance(timings, dict):
            predicted_ms = timings.get("predicted_ms") or 0.0
            eval_duration = float(predicted_ms) / 1000.0
        return raw_text, response_ms, eval_count, eval_duration

    def _send_request(
        self, prompt_text: str, timeout: int
    ) -> tuple[str, float, Any, float]:
        """Send chat completion request to llama.cpp OpenAI-compatible API."""
        url = f"{self._host}/v1/chat/completions"
        payload = {
            "model": self._model,
            "messages": self._build_messages(prompt_text),
            "stream": False,
        }
        start_time = time.monotonic()
        post_fn = self._http_post or requests.post
        try:
            response = post_fn(url, json=payload, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("llama.cpp request failed: %s", exc)
            raise LlmUnavailableError(
                f"llama.cpp @ {self._host} unreachable or error: {exc}"
            ) from exc
        response_ms = (time.monotonic() - start_time) * 1000.0
        try:
            body: dict[str, Any] = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("llama.cpp returned invalid JSON: %s", exc)
            raise LlmUnavailableError(
                f"llama.cpp returned invalid JSON: {exc}"
            ) from exc
        return self._extract_content_and_timing(body, response_ms)
