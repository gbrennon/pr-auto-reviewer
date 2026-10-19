"""Shared streaming client for OpenAI-compatible chat completion APIs."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import requests

from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.infrastructure.llm.base_chat_client import BaseChatClient
from pr_auto_reviewer.infrastructure.llm.chat_client_settings import (
    ChatClientSettings,
)

logger = logging.getLogger(__name__)


class OpenAiCompatibleChatClient(BaseChatClient):
    """Stream chat completions from an OpenAI-compatible HTTP API."""

    def __init__(
        self,
        settings: ChatClientSettings,
        http_post: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize a client whose host may optionally include the `/v1` path."""
        normalized_settings = replace(
            settings, host=self._normalize_api_base(settings.host)
        )
        super().__init__(normalized_settings)
        self._http_post = http_post

    def _normalize_api_base(self, host: str) -> str:
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

    def _decode_line(self, line: str | bytes) -> str:
        """Return a streamed line as text regardless of transport encoding."""
        return line.decode("utf-8") if isinstance(line, bytes) else line

    def _sse_payload(self, line: str | bytes) -> str | None:
        """Return the JSON payload of an SSE line, skipping comment and terminal lines."""
        cleaned = self._decode_line(line).strip()
        if cleaned.startswith(":"):
            return None
        if cleaned.startswith("data:"):
            cleaned = cleaned[5:].strip()
        if not cleaned or cleaned == "[DONE]":
            return None
        return cleaned

    def _parse_stream_chunk(
        self, line: str | bytes, attempt: int
    ) -> dict[str, Any] | None:
        """Parse one SSE data line and skip comment, malformed, or terminal lines."""
        payload = self._sse_payload(line)
        if payload is None:
            return None
        try:
            parsed: dict[str, Any] = json.loads(payload)
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
        if not isinstance(choices, list):
            return {}
        first_choice = next(
            (choice for choice in choices if isinstance(choice, dict)), {}
        )
        delta = first_choice.get("delta")
        message = first_choice.get("message")
        return self._mapping_or_empty(delta or message)

    @staticmethod
    def _mapping_or_empty(value: Any) -> dict[str, Any]:
        """Return a mapping value or an empty mapping."""
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _append_fragment(value: Any, parts: list[str]) -> None:
        if isinstance(value, str) and value:
            parts.append(value)

    def _append_text(
        self,
        delta: dict[str, Any],
        content_parts: list[str],
        reasoning_parts: list[str],
    ) -> None:
        """Append content or reasoning text from one streamed delta."""
        self._append_fragment(delta.get("content"), content_parts)
        reasoning = delta.get("reasoning_content") or delta.get("thinking")
        self._append_fragment(reasoning, reasoning_parts)

    def _stream_timed_out(self, started_at: float) -> bool:
        return self._timeout > 0 and time.monotonic() - started_at >= self._timeout

    def _append_stream_line(
        self,
        line: str | bytes,
        attempt: int,
        content_parts: list[str],
        reasoning_parts: list[str],
    ) -> None:
        if not line:
            return
        chunk = self._parse_stream_chunk(line, attempt)
        if chunk is not None:
            self._append_text(
                self._extract_delta(chunk), content_parts, reasoning_parts
            )

    def _accumulate_stream(
        self, response: requests.Response, attempt: int
    ) -> str:
        """Accumulate content from an SSE response, falling back to reasoning."""
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        started_at = time.monotonic()
        for line in response.iter_lines(decode_unicode=True):
            if self._stream_timed_out(started_at):
                raise requests.Timeout(
                    f"Streaming response exceeded {self._timeout}-second deadline"
                )
            self._append_stream_line(
                line, attempt, content_parts, reasoning_parts
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
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                "LLM chat request rejected with HTTP %s: %.1000s",
                response.status_code,
                response.text,
            )
            raise
        if hasattr(response, "encoding"):
            response.encoding = "utf-8"
        return self._accumulate_stream(response, attempt)
