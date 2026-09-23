"""Parsed language-model configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LlmSettings:
    """Configuration consumed by the OpenAI-compatible chat client."""

    host: str
    model: str
    timeout: int
    max_retries: int
    max_turns: int
    call_budget: int
