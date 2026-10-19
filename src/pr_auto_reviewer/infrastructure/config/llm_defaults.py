"""Defaults for the OpenAI-compatible language-model client."""

from __future__ import annotations


class LlmDefaults:
    """Provide fallback values for the OpenAI-compatible LLM configuration."""

    host: str = "http://localhost:11434"
    model: str = "code-review:latest"
    timeout: int = 120
    context_tokens: int = 24_000
