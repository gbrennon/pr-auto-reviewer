"""AgentChatPort — send conversation messages to an LLM and receive a response."""

from typing import Protocol

from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)


class AgentChatPort(Protocol):
    """Send a list of conversation messages to an LLM and return the response.

    Infrastructure adapters implement this to talk to specific LLM
    OpenAI-compatible language-model servers.
    """

    def send(self, messages: list[ConversationMessage]) -> str:
        """Send *messages* to the LLM and return the raw text response."""
        ...

    def reset_budget(self) -> None:
        """Reset the per-review LLM call budget so a new review starts fresh.

        Callers invoke this at the start of each review. Implementations
        without a budget treat it as a no-op.
        """
        ...
