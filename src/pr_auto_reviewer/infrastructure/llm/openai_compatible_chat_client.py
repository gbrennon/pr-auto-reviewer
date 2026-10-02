"""Shared streaming client for OpenAI-compatible chat completion APIs."""

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


class OpenAiCompatibleChatClient(BaseChatClient):
    """Stream chat completions from an OpenAI-compatible HTTP API."""

    def __init__(
        self,
        model: str = "default",
        host: str = "http://localhost:11434",
        timeout: int = 120,
        max_retries: int = 5,
        max_llm_calls: int | None = None,
        http_post: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize a client whose host may optionally include the `/v1` path."""
        super().__init__(
            model=model,
            host=self._normalize_api_base(host),
            timeout=timeout,
            max_retries=max_retries,
            max_llm_calls=max_llm_calls,
        )
        self._http_post = http_post

    @staticmethod
    def _normalize_api_base(host: str) -> str:
        """Return a host with exactly one `/v1` API path suffix."""
        cleaned = host.strip().rstrip("/")
        if not cleaned.startswith(("http://", "https://")):
            cleaned = f"http://{cleaned}"
        if cleaned.endswith("/v1"):
            return cleaned
        return f"{cleaned}/v1"

    def _endpoint_url(self) -> str:
        """Return the shared chat completions endpoint URL."""
        return f"{self._host}/chat/completions"

    def _format_payload(
        self, messages: list[ConversationMessage]
    ) -> dict[str, Any]:
        """Format conversation messages as an OpenAI chat completion request."""
        return {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": True,
        }

    def _parse_stream_chunk(
        self, line: str | bytes, attempt: int
    ) -> dict[str, Any] | None:
        """Parse one SSE data line and skip malformed or terminal lines."""
        text = line.decode("utf-8") if isinstance(line, bytes) else line
        cleaned = text.strip()
        if cleaned.startswith("data:"):
            cleaned = cleaned[5:].strip()
        if not cleaned or cleaned == "[DONE]":
            return None
        try:
            parsed: dict[str, Any] = json.loads(cleaned)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning(
                "Skipping unparseable SSE line (attempt %d/%d): %.300s",
                attempt + 1,
                self._max_retries,
                str(line),
            )
            return None
        return parsed

    def _extract_delta(self, chunk: dict[str, Any]) -> dict[str, Any]:
        """Extract the first streamed delta or complete message object."""
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return {}
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return {}
        delta = first_choice.get("delta")
        if isinstance(delta, dict):
            return delta
        message = first_choice.get("message")
        return message if isinstance(message, dict) else {}

    def _append_text(
        self,
        delta: dict[str, Any],
        content_parts: list[str],
        reasoning_parts: list[str],
    ) -> None:
        """Append content or reasoning text from one streamed delta."""
        content = delta.get("content")
        if isinstance(content, str) and content:
            content_parts.append(content)
        reasoning = delta.get("reasoning_content") or delta.get("thinking")
        if isinstance(reasoning, str) and reasoning:
            reasoning_parts.append(reasoning)

    def _accumulate_stream(
        self, response: requests.Response, attempt: int
    ) -> str:
        """Accumulate content from an SSE response, falling back to reasoning."""
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            chunk = self._parse_stream_chunk(line, attempt)
            if chunk is not None:
                self._append_text(
                    self._extract_delta(chunk), content_parts, reasoning_parts
                )
        return "".join(content_parts) or "".join(reasoning_parts)

    def _send_attempt(
        self, url: str, payload: dict[str, Any], attempt: int
    ) -> str:
        """Send one streaming request and return its accumulated text."""
        post_fn = self._http_post or requests.post
        response = post_fn(
            url,
            json=payload,
            timeout=self._timeout,
            stream=True,
        )
        response.raise_for_status()
        if hasattr(response, "encoding"):
            response.encoding = "utf-8"
        return self._accumulate_stream(response, attempt)
