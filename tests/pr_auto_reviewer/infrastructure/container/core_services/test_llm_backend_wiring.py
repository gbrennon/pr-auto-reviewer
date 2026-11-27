"""Tests for the single OpenAI-compatible LLM wiring path."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from pr_auto_reviewer.infrastructure.llm.llm_agent_adapter import LlmAgentAdapter
from pr_auto_reviewer.infrastructure.llm.openai_compatible_chat_client import (
    OpenAiCompatibleChatClient,
)

from ._helpers import *


class TestLlmClientWiring:
    """Verify core services always use the OpenAI-compatible client."""

    def test_wire_core_services_with_openai_compatible_client(
        self,
        forgejo_config: Config,
        repo_context: RepositoryContextPort,
        tmp_path: Path,
    ) -> None:
        services = wire_core_services(forgejo_config, repo_context, _config_dir=tmp_path)

        assert isinstance(
            services.conversation_service._chat_port, OpenAiCompatibleChatClient
        )
        assert isinstance(services.llm_review, LlmAgentAdapter)

    def test_wire_core_services_with_configured_model(
        self,
        forgejo_config: Config,
        repo_context: RepositoryContextPort,
        tmp_path: Path,
    ) -> None:
        configured = replace(forgejo_config, llm_model="configured-model")

        services = wire_core_services(configured, repo_context, _config_dir=tmp_path)

        assert isinstance(services.llm_review, LlmAgentAdapter)
        assert services.llm_review._resolve_model() == "configured-model"
