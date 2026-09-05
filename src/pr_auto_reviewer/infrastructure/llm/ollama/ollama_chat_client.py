"""OllamaChatClient — send conversation messages to Ollama's chat API."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.infrastructure.llm.base_chat_client import BaseChatClient

logger = logging.getLogger(__name__)


class OllamaChatClient(BaseChatClient):
    """Send conversation messages to Ollama's chat API and return the response.

    Converts ConversationMessage objects to Ollama's chat format,
    streams the response, and accumulates the full content. Pure HTTP
    adapter — no parsing, no tool logic, no phase awareness.
    """

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        timeout: int = 120,
        max_retries: int = 5,
        max_llm_calls: int | None = None,
    ) -> None:
        """Initialize Ollama chat client with target host and parameters."""
        super().__init__(
            model=model,
            host=host,
            timeout=timeout,
            max_retries=max_retries,
            max_llm_calls=max_llm_calls,
        )

    def _endpoint_url(self) -> str:
        """Return the full Ollama chat endpoint URL."""
        return f"{self._host}/api/chat"

    def _format_payload(
        self, messages: list[ConversationMessage]
    ) -> dict[str, Any]:
        """Format domain messages into Ollama chat request JSON payload."""
        return {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
            "stream": True,
        }

    def _sleep_backoff(self, attempt: int) -> None:
        """Pause execution with exponential backoff using module sleep."""
        time.sleep(2**attempt)

    def _parse_stream_chunk(
        self, line: str | bytes, attempt: int
    ) -> dict[str, Any] | None:
        """Parse a single streaming line into a JSON chunk dictionary."""
        try:
            text = line.decode("utf-8") if isinstance(line, bytes) else line
            parsed: dict[str, Any] = json.loads(text)
            return parsed
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning(
                "Skipping unparseable streaming line (attempt %d/%d): %.300s",
                attempt + 1,
                self._max_retries,
                str(line),
            )
            return None

    def _append_token_dict(
        self, item: Any, content_parts: list[str], thinking_parts: list[str]
    ) -> None:
        """Append content and thinking tokens from a single dictionary message."""
        if not isinstance(item, dict):
            return
        content_parts.append(item.get("content", ""))
        thinking_parts.append(item.get("thinking", ""))

    def _extract_message_tokens(
        self, message: Any, content_parts: list[str], thinking_parts: list[str]
    ) -> None:
        """Extract content and thinking tokens from a message container."""
        if isinstance(message, list):
            for item in message:
                self._append_token_dict(item, content_parts, thinking_parts)
            return
        self._append_token_dict(message, content_parts, thinking_parts)

    def _accumulate_stream_parts(
        self, http_response: requests.Response, attempt: int
    ) -> tuple[list[str], list[str]]:
        """Read streaming lines from HTTP response and collect token parts."""
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        for line in http_response.iter_lines(decode_unicode=True):
            if not line:
                continue
            chunk = self._parse_stream_chunk(line, attempt)
            if chunk is None:
                continue
            message = chunk.get("message", {})
            self._extract_message_tokens(message, content_parts, thinking_parts)
            if chunk.get("done"):
                break
        return content_parts, thinking_parts

    def _send_attempt(
        self, url: str, payload: dict[str, Any], attempt: int
    ) -> str:
        """Execute one HTTP POST request attempt and accumulate tokens."""
        http_response = requests.post(
            url,
            json=payload,
            timeout=self._timeout,
            stream=True,
        )
        http_response.raise_for_status()
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
