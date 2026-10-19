"""Resolved settings for an LLM chat client."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatClientSettings:
    """Carry fully resolved chat-client settings into the client implementation."""

    model: str
    host: str
    timeout: int
    max_retries: int
    max_llm_calls: int | None
    max_context_tokens: int
