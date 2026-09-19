"""BaseChatClient — shared abstractions and budget tracking for LLM chat clients."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
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


class BaseChatClient(AgentChatPort, ABC):
    """Abstract base class for LLM chat clients with retry and budget control."""

    def __init__(
        self,
        model: str,
        host: str,
        timeout: int = 120,
        max_retries: int = 5,
        max_llm_calls: int | None = None,
    ) -> None:
        """Initialize base client parameters and budget tracking."""
        self._model = model
        self._host = self._normalize_host(host)
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_llm_calls = max_llm_calls
        self._calls_started = 0

    @property
    def model(self) -> str:
        """Return the configured model identifier."""
        return self._model

    @staticmethod
    def _normalize_host(host: str) -> str:
        """Ensure host URL starts with an HTTP scheme and has no trailing slashes."""
        cleaned = host.strip().rstrip("/")
        if not cleaned.startswith(("http://", "https://")):
            return f"http://{cleaned}"
        return cleaned

    def send(self, messages: list[ConversationMessage]) -> str:
        """Send messages to the LLM backend with retry loop and budget tracking."""
        self._assert_budget_available()
        self._calls_started += 1
        call_index = self._calls_started
        started_at = time.monotonic()
        logger.info(
            "LLM chat call %s starting (%d messages in history)",
            self._describe_call(call_index),
            len(messages),
        )
        url = self._endpoint_url()
        payload = self._format_payload(messages)
        for attempt in range(self._max_retries):
            try:
                return self._execute_attempt_with_logging(
                    url,
                    payload,
                    attempt,
                    call_index,
                    started_at,
                    len(messages),
                )
            except requests.RequestException as exc:
                self._handle_attempt_failure(
                    exc, url, attempt, call_index, started_at
                )
        raise LlmUnavailableError("All chat requests exhausted")

    def reset_budget(self) -> None:
        """Reset the per-review call counter so a new review starts fresh."""
        self._calls_started = 0

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

    def _sleep_backoff(self, attempt: int) -> None:
        """Pause execution using exponential backoff before the next attempt."""
        time.sleep(2**attempt)

    @abstractmethod
    def _endpoint_url(self) -> str:
        """Return the full HTTP endpoint URL for the chat request."""
        ...

    @abstractmethod
    def _format_payload(
        self, messages: list[ConversationMessage]
    ) -> dict[str, Any]:
        """Format domain conversation messages into backend-specific JSON payload."""
        ...

    @abstractmethod
    def _send_attempt(
        self, url: str, payload: dict[str, Any], attempt: int
    ) -> str:
        """Send a single HTTP request attempt and return the accumulated string."""
        ...

    def _execute_attempt_with_logging(
        self,
        url: str,
        payload: dict[str, Any],
        attempt: int,
        call_index: int,
        started_at: float,
        messages_count: int,
    ) -> str:
        """Execute one attempt and log success."""
        result = self._send_attempt(url, payload, attempt)
        elapsed = time.monotonic() - started_at
        logger.info(
            "LLM chat call %s finished in %.1fs "
            "(%d chars, %d messages in history)",
            self._describe_call(call_index),
            elapsed,
            len(result),
            messages_count,
        )
        return result

    def _handle_attempt_failure(
        self,
        exc: requests.RequestException,
        url: str,
        attempt: int,
        call_index: int,
        started_at: float,
    ) -> None:
        """Log attempt failure and sleep or raise if attempts are exhausted."""
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
            "Chat attempt %d/%d failed (%s), retrying...",
            attempt + 1,
            self._max_retries,
            exc,
        )
        self._sleep_backoff(attempt)
