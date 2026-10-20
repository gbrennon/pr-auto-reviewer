"""Parse OpenAI-compatible language-model configuration."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.config.llm_defaults import LlmDefaults
from pr_auto_reviewer.infrastructure.config.llm_settings import LlmSettings


class LlmConfigParser:
    """Build LLM settings from environment values and injected defaults."""

    def __init__(self, defaults: LlmDefaults) -> None:
        self._defaults = defaults

    def parse(self, source: dict[str, str], max_retries: int, max_turns: int, call_budget: int) -> LlmSettings:
        """Parse endpoint, model, timeout, and retry limits."""
        return LlmSettings(
            host=self._normalize_host(source.get("LLM_HOST", self._defaults.host)),
            model=source.get("LLM_MODEL", self._defaults.model).strip(),
            timeout=int(source.get("LLM_TIMEOUT", str(self._defaults.timeout))),
            context_tokens=int(
                source.get("MAX_CONTEXT_TOKENS", str(self._defaults.context_tokens))
            ),
            max_retries=max_retries,
            max_turns=max_turns,
            call_budget=call_budget,
        )

    def _normalize_host(self, host: str) -> str:
        cleaned = host.strip().rstrip("/")
        if cleaned.startswith(("http://", "https://")):
            return cleaned
        return f"http://{cleaned}"
