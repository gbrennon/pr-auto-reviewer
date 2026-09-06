"""LlamaCppChatClient — send conversation messages to llama.cpp chat API."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import requests

from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.infrastructure.llm.base_chat_client import BaseChatClient

logger = logging.getLogger(__name__)


class LlamaCppChatClient(BaseChatClient):
    """Send conversation messages to llama.cpp OpenAI-compatible API and return response.

    Converts ConversationMessage objects to OpenAI chat format, streams SSE
    responses from /v1/chat/completions, and accumulates tokens.
    """

    def __init__(
        self,
        model: str = "default",
        host: str = "http://localhost:8080",
        timeout: int = 120,
        max_retries: int = 5,
        max_llm_calls: int | None = None,
        http_post: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize llama.cpp chat client with endpoint configuration."""
        super().__init__(
            model=model,
            host=host,
            timeout=timeout,
            max_retries=max_retries,
            max_llm_calls=max_llm_calls,
        )
        self._http_post = http_post

    def _endpoint_url(self) -> str:
        """Return the OpenAI-compatible chat completions endpoint URL."""
        return f"{self._host}/v1/chat/completions"

    def _format_payload(
        self, messages: list[ConversationMessage]
    ) -> dict[str, Any]:
        """Format domain conversation messages into OpenAI chat completion payload."""
        return {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
            "stream": True,
        }

    def _strip_sse_prefix(self, text: str) -> str:
        """Strip SSE data prefix from a streaming line."""
        trimmed = text.strip()
        if trimmed.startswith("data: "):
            return trimmed[6:].strip()
        if trimmed.startswith("data:"):
            return trimmed[5:].strip()
        return trimmed

    def _parse_stream_chunk(
        self, line: str | bytes, attempt: int
    ) -> dict[str, Any] | None:
        """Parse an SSE line into a chunk dictionary."""
        text = line.decode("utf-8") if isinstance(line, bytes) else line
        cleaned = self._strip_sse_prefix(text)
        if not cleaned or cleaned == "[DONE]":
            return None
        try:
            parsed: dict[str, Any] = json.loads(cleaned)
            return parsed
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning(
                "Skipping unparseable SSE line (attempt %d/%d): %.300s",
                attempt + 1,
                self._max_retries,
                str(line),
            )
            return None

    def _extract_first_choice_dict(
        self, chunk: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract first dictionary item from choices array."""
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return {}
        first = choices[0]
        return first if isinstance(first, dict) else {}

    def _extract_delta_from_chunk(
        self, chunk: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract delta or message dictionary from choices array."""
        first = self._extract_first_choice_dict(chunk)
        delta = first.get("delta")
        if isinstance(delta, dict):
            return delta
        message = first.get("message")
        if isinstance(message, dict):
            return message
        return {}

    def _append_if_non_empty(self, target: list[str], val: Any) -> None:
        """Append value to target list if it is a non-empty string."""
        if isinstance(val, str) and val:
            target.append(val)

    def _append_delta_tokens(
        self,
        delta: dict[str, Any],
        content_parts: list[str],
        thinking_parts: list[str],
    ) -> None:
        """Append text and thinking tokens from a delta dictionary."""
        self._append_if_non_empty(content_parts, delta.get("content"))
        reasoning = delta.get("reasoning_content")
        if not reasoning:
            reasoning = delta.get("thinking")
        self._append_if_non_empty(thinking_parts, reasoning)

    def _accumulate_stream_parts(
        self, http_response: requests.Response, attempt: int
    ) -> tuple[list[str], list[str]]:
        """Read streaming lines and collect content and thinking tokens."""
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        for line in http_response.iter_lines(decode_unicode=True):
            if not line:
                continue
            chunk = self._parse_stream_chunk(line, attempt)
            if chunk is None:
                continue
            delta = self._extract_delta_from_chunk(chunk)
            self._append_delta_tokens(delta, content_parts, thinking_parts)
        return content_parts, thinking_parts

    def _send_attempt(
        self, url: str, payload: dict[str, Any], attempt: int
    ) -> str:
        """Execute one HTTP POST request attempt and accumulate tokens."""
        post_fn = self._http_post or requests.post
        http_response = post_fn(
            url,
            json=payload,
            timeout=self._timeout,
            stream=True,
        )
        http_response.raise_for_status()
        if hasattr(http_response, "encoding"):
            http_response.encoding = "utf-8"
        content_parts, thinking_parts = self._accumulate_stream_parts(
            http_response, attempt
        )
        result = "".join(content_parts)
        if not result:
            result = "".join(thinking_parts)
            logger.debug(
                "No content in response; fell back to %d chars of thinking",
                len(result),
            )
        return result
