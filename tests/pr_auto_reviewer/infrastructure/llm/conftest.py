"""Shared test fixtures for OllamaExploratoryChatAdapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_exploratory_chat_adapter import (
    OllamaExploratoryChatAdapter,
)


@pytest.fixture
def adapter() -> OllamaExploratoryChatAdapter:
    """Create OllamaExploratoryChatAdapter with low retries for fast tests."""
    return OllamaExploratoryChatAdapter(model="phi4", max_retries=2, ollama_timeout=10)


@pytest.fixture
def prompt_with_repo(tmp_path: Path) -> ComposedPrompt:
    """ComposedPrompt with repo_path — triggers multi-turn path."""
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "foo.py").write_text("def foo() -> None: ...")
    (tmp_path / "src" / "a.py").write_text("def a() -> None: ...")
    return ComposedPrompt(
        content="System prompt for exploratory review",
        fragments_used=["system-prompt"],
        total_tokens=500,
        repo_path=str(tmp_path),
    )
