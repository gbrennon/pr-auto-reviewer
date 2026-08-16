"""Behavior tests for wire_core_services() — verifies CoreServices
dataclass is populated with the correct service instances for a given config."""

from __future__ import annotations

import pytest

from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.container._core_services import (
    CoreServices,
    wire_core_services,
)
from pr_auto_reviewer.infrastructure.container._platform_clients import (
    wire_platform_clients,
)
from pr_auto_reviewer.infrastructure.container._platform_adapters import (
    wire_platform_adapters,
)
from pr_auto_reviewer.infrastructure.persistence.json_file_pr_repository import (
    JsonFilePullRequestRepository,
)
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_exploratory_chat_adapter import (
    OllamaExploratoryChatAdapter,
)
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.notifier.linux_notifier import (
    LinuxNotifier,
)
from pr_auto_reviewer.infrastructure.fragments.file_system_fragment_repository import (
    FileSystemFragmentRepository,
)
from pr_auto_reviewer.infrastructure.fragments.jinja2_renderer import (
    Jinja2Renderer,
)
from pr_auto_reviewer.infrastructure.context.review_context_factory import (
    ReviewContextFactory,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.infrastructure.local_repository.local_git_repository import (
    LocalGitRepository,
)

CORE_SERVICES_INSTANCE_TYPES = [
    ("pr_repository", JsonFilePullRequestRepository),
    ("command_bus", InMemoryCommandBus),
    ("notifier", LinuxNotifier),
    ("fragment_repository", FileSystemFragmentRepository),
    ("fragment_renderer", Jinja2Renderer),
    ("review_context_factory", ReviewContextFactory),
]


@pytest.fixture
def forgejo_config() -> Config:
    return Config(
        env="test",
        platform_mode=GitProvider.FORGEJO,
        forgejo_owner_token="fj-own",
        forgejo_reviewer_token="fj-rev",
        forgejo_reviewer_username="fj-bot",
    )


@pytest.fixture
def local_repository(tmp_path):
    return LocalGitRepository(tmp_path)


@pytest.fixture
def repo_context(forgejo_config: Config, local_repository):
    """A real RepositoryContextPort instance from the adapter wiring."""
    clients = wire_platform_clients(forgejo_config)
    adapters = wire_platform_adapters(
        forgejo_config, clients, is_terminal=False, local_repository=local_repository
    )
    return adapters.repository_context


class TestWireCoreServices:
    """Behaviour of wire_core_services(config, repository_context)."""

    @pytest.mark.parametrize("attr,expected_type", CORE_SERVICES_INSTANCE_TYPES)
    def test_core_services_instance_types(
        self,
        forgejo_config: Config,
        repo_context,
        attr: str,
        expected_type,
    ) -> None:
        result = wire_core_services(forgejo_config, repo_context)
        assert isinstance(getattr(result, attr), expected_type)

    def test_returns_core_services(
        self,
        forgejo_config: Config,
        repo_context,
    ) -> None:
        result = wire_core_services(forgejo_config, repo_context)
        assert isinstance(result, CoreServices)

    def test_all_fields_non_null(
        self,
        forgejo_config: Config,
        repo_context,
    ) -> None:
        result = wire_core_services(forgejo_config, repo_context)

        for attr in [
            "pr_repository",
            "llm_review",
            "command_bus",
            "notifier",
            "fragment_repository",
            "fragment_renderer",
            "review_context_factory",
        ]:
            assert getattr(result, attr) is not None, f"{attr} is None"

    def test_llm_review_uses_config_llm_host(
        self,
        repo_context,
    ) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            llm_host="http://custom-llm:9999",
        )

        result = wire_core_services(config, repo_context)

        assert result.llm_review._chat_client._host == "http://custom-llm:9999"

    def test_llm_review_uses_config_llm_model(
        self,
        repo_context,
    ) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            llm_model="custom-model:v2",
        )

        result = wire_core_services(config, repo_context)

        assert result.llm_review._chat_client._model == "custom-model:v2"

    def test_llm_review_defaults_to_code_review_when_no_model(
        self,
        forgejo_config: Config,
        repo_context,
    ) -> None:
        result = wire_core_services(forgejo_config, repo_context)

        assert result.llm_review._chat_client._model == "code-review:latest"

    def test_llm_review_uses_config_ollama_timeout(
        self,
        repo_context,
    ) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            ollama_timeout=300,
        )

        result = wire_core_services(config, repo_context)

        assert result.llm_review._chat_client._timeout == 300

    def test_fragment_max_tokens_is_none_when_not_in_config(
        self,
        forgejo_config: Config,
        repo_context,
    ) -> None:
        result = wire_core_services(forgejo_config, repo_context)

        assert result.fragment_max_tokens is None

    def test_fragment_max_tokens_flows_from_config(
        self,
        repo_context,
    ) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
        )
        config.fragment_max_tokens = 4096

        result = wire_core_services(config, repo_context)

        assert result.fragment_max_tokens == 4096

    def test_review_context_factory_uses_provided_repository_context(
        self,
        forgejo_config: Config,
        repo_context,
    ) -> None:
        result = wire_core_services(forgejo_config, repo_context)

        assert result.review_context_factory._repository_context is repo_context

    def test_max_prompt_tokens_zero_means_default_chars(
        self,
        forgejo_config: Config,
        repo_context,
    ) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            max_prompt_tokens=0,
        )

        result = wire_core_services(config, repo_context)

        assert (
            result.review_context_factory._compose_review_prompt._max_total_chars
            == 60_000
        )

    def test_max_prompt_tokens_non_zero_uses_formula(
        self,
        repo_context,
    ) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            max_prompt_tokens=500,
        )

        result = wire_core_services(config, repo_context)

        assert (
            result.review_context_factory._compose_review_prompt._max_total_chars
            == 2000
        )

    def test_strict_selection_false_by_default(
        self,
        forgejo_config: Config,
        repo_context,
    ) -> None:
        result = wire_core_services(forgejo_config, repo_context)

        assert (
            result.review_context_factory._compose_review_prompt._strict_selection
            is False
        )

    def test_strict_selection_true_when_config_set(
        self,
        forgejo_config: Config,
        repo_context,
    ) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            use_strict_fragment_selection=True,
        )

        result = wire_core_services(config, repo_context)

        assert (
            result.review_context_factory._compose_review_prompt._strict_selection
            is True
        )

    def test_custom_fragments_dir_is_used(
        self,
        forgejo_config: Config,
        repo_context,
        tmp_path,
    ) -> None:
        custom_dir = tmp_path / "custom" / "fragments"
        custom_dir.mkdir(parents=True)

        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            fragments_dir=str(custom_dir),
        )

        result = wire_core_services(config, repo_context)

        assert isinstance(result.fragment_repository, FileSystemFragmentRepository)
        assert result.fragment_repository.base_path == custom_dir

    def test_pr_repository_state_file_is_in_config_dir(
        self,
        forgejo_config: Config,
        repo_context,
        tmp_path,
    ) -> None:
        result = wire_core_services(forgejo_config, repo_context, _config_dir=tmp_path)

        assert isinstance(result.pr_repository, JsonFilePullRequestRepository)
        state_path = result.pr_repository._file_path
        assert str(state_path).startswith(str(tmp_path))
        assert str(state_path).endswith("state.json")
