"""AgentExchangeEvent — emitted when a support-role LLM exchange finishes."""

from __future__ import annotations

from dataclasses import dataclass, field

from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)


@dataclass(frozen=True)
class AgentExchangeEvent:
    """A finished single-shot exchange from a non-peer sub-agent.

    The advisor, manager, and verifier talk to the model outside the
    peer conversation loop; this event carries their prompt/response
    transcript so every LLM interaction leaves an audit trail.
    """

    role: str
    phase_name: str
    pr_identifier: str
    messages: list[ConversationMessage]
    metadata: dict[str, str] = field(default_factory=dict)
