"""OllamaChatClient — send conversation messages to Ollama's chat API."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.exceptions.review_budget_exhausted_error import (
    ReviewBudgetExhaustedError,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)

logger = logging.getLogger(__name__)


class OllamaChatClient(AgentChatPort):
    """Send conversation messages to Ollama's chat API and return the response.

    Converts ``ConversationMessage`` objects to Ollama's chat format,
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
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_llm_calls = max_llm_calls
        self._calls_started = 0

    def send(self, messages: list[ConversationMessage]) -> str:
        """Send *messages* to Ollama and return the accumulated response.

        Raises:
            ReviewBudgetExhaustedError: When ``max_llm_calls`` was set and
                every allowed call has already been consumed.
        """
        self._assert_budget_available()
        self._calls_started += 1
        call_index = self._calls_started
        started_at = time.monotonic()
        logger.info(
            "LLM chat call %s starting (%d messages in history)",
            self._describe_call(call_index),
            len(messages),
        )
        url = f"{self._host}/api/chat"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
            "stream": True,
        }
        for attempt in range(self._max_retries):
            try:
                http_response = requests.post(
                    url,
                    json=payload,
                    timeout=self._timeout,
                    stream=True,
                )
                http_response.raise_for_status()
                http_response.encoding = "utf-8"
                content_parts: list[str] = []
                thinking_parts: list[str] = []
                for line in http_response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        chunk: dict[str, Any] = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(
                            "Skipping unparseable streaming line "
                            "(attempt %d/%d): %.300s",
                            attempt + 1,
                            self._max_retries,
                            line,
                        )
                        continue
                    message = chunk.get("message", {})
                    if isinstance(message, list):
                        for msg in message:
                            if isinstance(msg, dict):
                                content_parts.append(
                                    msg.get("content", "")
                                )
                                thinking_parts.append(
                                    msg.get("thinking", "")
                                )
                    else:
                        content_parts.append(message.get("content", ""))
                        thinking_parts.append(message.get("thinking", ""))
                    if chunk.get("done"):
                        break
                result = "".join(content_parts)
                if not result:
                    result = "".join(thinking_parts)
                    logger.debug(
                        "No content in response; fell back to %d chars of thinking",
                        len(result),
                    )
                elapsed = time.monotonic() - started_at
                logger.info(
                    "LLM chat call %s finished in %.1fs "
                    "(%d chars, %d messages in history)",
                    self._describe_call(call_index),
                    elapsed,
                    len(result),
                    len(messages),
                )
                return result
            except requests.RequestException as exc:
                elapsed = time.monotonic() - started_at
                logger.info(
                    "LLM chat call %s failed after %.1fs",
                    self._describe_call(call_index),
                    elapsed,
                )
                if attempt == self._max_retries - 1:
                    raise LlmUnavailableError(
                        f"Chat request to {url} failed after "
                        f"{self._max_retries} attempts: {exc}"
                    ) from exc
                logger.warning(
                    "Chat attempt %d/%d failed, retrying...",
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(2**attempt)
        raise LlmUnavailableError("All chat requests exhausted")

    def _assert_budget_available(self) -> None:
        """Raise when the configured LLM call budget is fully consumed."""
        if (
            self._max_llm_calls is not None
            and self._calls_started >= self._max_llm_calls
        ):
            raise ReviewBudgetExhaustedError(
                f"LLM call budget of {self._max_llm_calls} exhausted; "
                "refusing to send another chat request"
            )

    def _describe_call(self, call_index: int) -> str:
        """Render the budget-aware label used in call log lines."""
        if self._max_llm_calls is None:
            return f"#{call_index}"
        return f"#{call_index}/{self._max_llm_calls}"
