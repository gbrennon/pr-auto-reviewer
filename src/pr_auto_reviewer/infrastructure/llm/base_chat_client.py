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

_DEFAULT_CONTEXT_TOKEN_LIMIT = 55_000
_ESTIMATED_CHARS_PER_TOKEN = 2


class BaseChatClient(AgentChatPort, ABC):
    """Abstract base class for LLM chat clients with retry and budget control."""

    def __init__(
        self,
        model: str,
        host: str,
        timeout: int = 120,
        max_retries: int = 5,
        max_llm_calls: int | None = None,
        max_context_tokens: int = _DEFAULT_CONTEXT_TOKEN_LIMIT,
    ) -> None:
        """Initialize base client parameters and budget tracking."""
        self._model = model
        self._host = self._normalize_host(host)
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_llm_calls = max_llm_calls
        self._max_context_tokens = max_context_tokens
        self._calls_started = 0

    @property
    def model(self) -> str:
        """Return the configured model identifier."""
        return self._model

    def _normalize_host(self, host: str) -> str:
        """Ensure host URL starts with an HTTP scheme and has no trailing slashes."""
        cleaned = host.strip().rstrip("/")
        if not cleaned.startswith(("http://", "https://")):
            return f"http://{cleaned}"
        return cleaned

    def _estimate_tokens(
        self, messages: list[ConversationMessage]
    ) -> int:
        """Estimate prompt tokens conservatively from message content."""
        return sum(
            max(
                1,
                (len(message.content) + _ESTIMATED_CHARS_PER_TOKEN - 1)
                // _ESTIMATED_CHARS_PER_TOKEN,
            )
            + 4
            for message in messages
        )

    def _group_history(
        self, messages: list[ConversationMessage]
    ) -> list[list[ConversationMessage]]:
        """Group each assistant response with the user messages that follow it."""
        groups: list[list[ConversationMessage]] = []
        current: list[ConversationMessage] = []
        for message in messages:
            if message.role == "assistant" and current:
                groups.append(current)
                current = []
            current.append(message)
        if current:
            groups.append(current)
        return groups

    def _bound_context(
        self, messages: list[ConversationMessage]
    ) -> list[ConversationMessage]:
        """Keep the initial prompt and newest complete turns in the budget."""
        if self._max_context_tokens <= 0:
            return messages
        estimated_tokens = self._estimate_tokens(messages)
        if estimated_tokens <= self._max_context_tokens:
            return messages
        prefix = list(messages[:2])
        prefix_tokens = self._estimate_tokens(prefix)
        if prefix_tokens >= self._max_context_tokens:
            raise LlmUnavailableError(
                "Initial chat prompt exceeds the configured context token budget"
            )
        remaining_tokens = self._max_context_tokens - prefix_tokens
        retained_reversed: list[list[ConversationMessage]] = []
        for group in reversed(self._group_history(messages[2:])):
            group_tokens = self._estimate_tokens(group)
            if group_tokens <= remaining_tokens:
                retained_reversed.append(group)
                remaining_tokens -= group_tokens
        retained = [
            message
            for group in reversed(retained_reversed)
            for message in group
        ]
        omitted_count = len(messages) - len(prefix) - len(retained)
        marker = ConversationMessage(
            role="user",
            content=(
                f"[{omitted_count} earlier messages omitted to stay within "
                f"the {self._max_context_tokens}-token context budget.]"
            ),
        )
        bounded = [*prefix, marker, *retained]
        while (
            retained_reversed
            and self._estimate_tokens(bounded) > self._max_context_tokens
        ):
            retained_reversed.pop()
            retained = [
                message
                for group in reversed(retained_reversed)
                for message in group
            ]
            bounded = [*prefix, marker, *retained]
        if self._estimate_tokens(bounded) > self._max_context_tokens:
            raise LlmUnavailableError(
                "Chat history cannot fit within the configured context token budget"
            )
        logger.warning(
            "Bounded chat history from %d to %d messages "
            "(estimated tokens %d to %d)",
            len(messages),
            len(bounded),
            estimated_tokens,
            self._estimate_tokens(bounded),
        )
        return bounded


    def send(self, messages: list[ConversationMessage]) -> str:
        """Send messages to the LLM backend with retry loop and budget tracking."""
        self._assert_budget_available()
        bounded_messages = self._bound_context(messages)
        self._calls_started += 1
        call_index = self._calls_started
        started_at = time.monotonic()
        logger.info(
            "LLM chat call %s starting (%d messages in history)",
            self._describe_call(call_index),
            len(bounded_messages),
        )
        url = self._endpoint_url()
        payload = self._format_payload(bounded_messages)
        for attempt in range(self._max_retries):
            try:
                return self._execute_attempt_with_logging(
                    url,
                    payload,
                    attempt,
                    call_index,
                    started_at,
                    len(bounded_messages),
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
