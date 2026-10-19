"""State for one LLM request attempt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChatAttempt:
    """Carry request and timing data through chat-attempt helpers."""

    url: str
    payload: dict[str, Any]
    attempt: int
    call_index: int
    started_at: float
    messages_count: int
