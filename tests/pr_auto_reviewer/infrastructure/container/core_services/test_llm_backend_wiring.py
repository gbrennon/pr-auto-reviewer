"""Tests for LLM backend selection in core services wiring."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
)
from pr_auto_reviewer.infrastructure.llm.llm_agent_adapter import (
    LlmAgentAdapter,
)
from pr_auto_reviewer.infrastructure.llm.openai_compatible_chat_client import (
    OpenAiCompatibleChatClient,
)

from ._helpers import *


class TestLlmBackendWiring:
    def test_wire_core_services_with_llama_cpp_backend(
        self, forgejo_config: Config, repo_context: RepositoryContextPort, tmp_path: Path
    ) -> None:
        cfg = replace(forgejo_config, llm_backend="llama_cpp")
        services = wire_core_services(cfg, repo_context, _config_dir=tmp_path)

        assert isinstance(
            services.conversation_service._chat_port, OpenAiCompatibleChatClient
        )
        assert isinstance(services.llm_review, LlmAgentAdapter)

    def test_wire_core_services_with_ollama_backend(
        self, forgejo_config: Config, repo_context: RepositoryContextPort, tmp_path: Path
    ) -> None:
        cfg = replace(forgejo_config, llm_backend="ollama")
        services = wire_core_services(cfg, repo_context, _config_dir=tmp_path)

        assert isinstance(
            services.conversation_service._chat_port, OpenAiCompatibleChatClient
        )
        assert isinstance(services.llm_review, LlmAgentAdapter)

    def test_wire_core_services_with_auto_backend(
        self,
        monkeypatch: pytest.MonkeyPatch,
        forgejo_config: Config,
        repo_context: RepositoryContextPort,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.backend_detector.BackendDetector.detect",
            lambda _self: "llama_cpp",
        )
        cfg = replace(forgejo_config, llm_backend="auto")
        services = wire_core_services(cfg, repo_context, _config_dir=tmp_path)

        assert isinstance(
            services.conversation_service._chat_port, LlamaCppChatClient
        )
