"""AgentChatPort — send conversation messages to an LLM and receive a response."""

from typing import Protocol

from pr_auto_reviewer.domain.agent.conversation_message import (
    ConversationMessage,
)


class AgentChatPort(Protocol):
    """Send a list of conversation messages to an LLM and return the response.

    Infrastructure adapters implement this to talk to specific LLM
    backends (Ollama, OpenAI, etc.).
    """

    def send(self, messages: list[ConversationMessage]) -> str:
        """Send *messages* to the LLM and return the raw text response."""
        ...
