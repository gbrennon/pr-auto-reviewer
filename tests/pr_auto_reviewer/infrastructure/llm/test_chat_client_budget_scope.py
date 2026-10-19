"""Regression tests for shared chat-client call budgets."""

from __future__ import annotations

from contextvars import copy_context

import pytest

from pr_auto_reviewer.domain.exceptions.review_budget_exhausted_error import (
    ReviewBudgetExhaustedError,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from tests.pr_auto_reviewer.infrastructure.llm.fake_streaming_response import (
    FakeStreamingResponse,
)
from pr_auto_reviewer.infrastructure.llm.chat_client_settings import (
    ChatClientSettings,
)
from pr_auto_reviewer.infrastructure.llm.openai_compatible_chat_client import (
    OpenAiCompatibleChatClient,
)


class TestChatClientBudgetScope:
    """Verify that the configured call budget is shared by execution contexts."""

    def _response(self) -> FakeStreamingResponse:
        return FakeStreamingResponse()

    def _client(self, max_llm_calls: int | None) -> OpenAiCompatibleChatClient:
        response = self._response()
        return OpenAiCompatibleChatClient(
            ChatClientSettings(
                model="default",
                host="http://localhost:11434",
                timeout=120,
                max_retries=1,
                max_llm_calls=max_llm_calls,
                max_context_tokens=24_000,
            ),
            http_post=lambda *_args, **_kwargs: response,
        )

    def _messages(self) -> list[ConversationMessage]:
        return [ConversationMessage(role="user", content="review")]

    def test_call_budget_is_shared_across_execution_contexts(self) -> None:
        """A client must not exceed its aggregate call budget across contexts."""
        client = self._client(max_llm_calls=1)
        first_context = copy_context()
        second_context = copy_context()

        first_context.run(client.send, self._messages())

        with pytest.raises(ReviewBudgetExhaustedError):
            second_context.run(client.send, self._messages())

    def test_call_budget_rejects_second_call_in_same_context(self) -> None:
        """A finite budget rejects a second call without sending it."""
        client = self._client(max_llm_calls=1)

        client.send(self._messages())

        with pytest.raises(ReviewBudgetExhaustedError):
            client.send(self._messages())

    def test_zero_call_budget_rejects_the_first_call(self) -> None:
        """A zero budget prevents any request from being sent."""
        client = self._client(max_llm_calls=0)

        with pytest.raises(ReviewBudgetExhaustedError):
            client.send(self._messages())

    def test_reset_budget_allows_a_new_review(self) -> None:
        """Resetting the budget permits the next review to send a call."""
        client = self._client(max_llm_calls=1)

        client.send(self._messages())
        client.reset_budget()

        client.send(self._messages())

    def test_unlimited_budget_remains_unlimited_across_contexts(self) -> None:
        """An unset budget does not reject calls from copied contexts."""
        client = self._client(max_llm_calls=None)
        contexts = [copy_context() for _ in range(3)]

        for context in contexts:
            context.run(client.send, self._messages())
