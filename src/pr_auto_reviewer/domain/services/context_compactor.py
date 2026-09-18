"""Domain service for compacting long conversations."""

from __future__ import annotations

from collections import Counter

from ..value_objects.compaction_policy import CompactionPolicy
from ..value_objects.compaction_result import CompactionResult
from ..value_objects.context_window import ContextWindow
from ..value_objects.conversation import Conversation
from ..value_objects.conversation_message import ConversationMessage
from ..value_objects.token_count import TokenCount


class ContextCompactor:
    """Replace old conversation history with a structured summary."""

    def __init__(self, policy: CompactionPolicy | None = None) -> None:
        self._policy = policy or CompactionPolicy()

    def compact(
        self,
        conversation: Conversation,
        context_window: ContextWindow,
        summary: str | None = None,
    ) -> tuple[Conversation, ContextWindow, CompactionResult]:
        """Compact middle history while preserving system instructions and recent turns."""
        original_tokens = conversation.estimate_tokens(self._policy.chars_per_token)
        if len(conversation.messages) <= 1 + self._policy.preserve_recent_messages:
            return self._unchanged(conversation, context_window, original_tokens)

        first_message = conversation.messages[0]
        system_message = first_message if first_message.role == "system" else None
        tail = conversation.messages[1:] if system_message else conversation.messages
        if len(tail) <= self._policy.preserve_recent_messages:
            return self._unchanged(conversation, context_window, original_tokens)

        to_compact = tail[:-self._policy.preserve_recent_messages]
        to_keep = tail[-self._policy.preserve_recent_messages:]
        summary_content = self._summary_content(to_compact, summary)
        new_messages = (
            ([system_message] if system_message is not None else [])
            + [ConversationMessage(role="system", content=summary_content)]
            + list(to_keep)
        )
        compacted_conversation = Conversation(messages=tuple(new_messages))
        compacted_tokens = compacted_conversation.estimate_tokens(
            self._policy.chars_per_token
        )
        compacted_window = context_window.with_current_tokens(compacted_tokens)
        result = CompactionResult(
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            messages_before=len(conversation.messages),
            messages_after=len(compacted_conversation.messages),
            summary=summary_content,
        )
        return compacted_conversation, compacted_window, result

    def _unchanged(
        self,
        conversation: Conversation,
        context_window: ContextWindow,
        original_tokens: TokenCount,
    ) -> tuple[Conversation, ContextWindow, CompactionResult]:
        result = CompactionResult(
            original_tokens=original_tokens,
            compacted_tokens=original_tokens,
            messages_before=len(conversation.messages),
            messages_after=len(conversation.messages),
            summary="(no compaction needed)",
        )
        return conversation, context_window, result

    def _summary_content(
        self, messages: tuple[ConversationMessage, ...], summary: str | None
    ) -> str:
        if summary is not None:
            condensed = summary
        else:
            counts = Counter(message.role for message in messages)
            tool_names = sorted(
                {
                    message.tool_call.tool_name
                    for message in messages
                    if message.tool_call is not None
                }
            )
            tools = ", ".join(tool_names) if tool_names else "none"
            condensed = (
                f"Compacted {len(messages)} messages: "
                f"user={counts.get('user', 0)}, "
                f"assistant={counts.get('assistant', 0)}, "
                f"tool={counts.get('tool', 0)}; "
                f"executed tools: {tools}"
            )
        return self._policy.summary_prefix + condensed
