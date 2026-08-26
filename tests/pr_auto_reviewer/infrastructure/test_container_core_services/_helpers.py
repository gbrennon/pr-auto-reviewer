"""Shared helpers, fixtures, and imports for the split test modules."""

from __future__ import annotations

import pytest

from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.config.advisor_granularity import (
    AdvisorGranularity,
)
from pr_auto_reviewer.infrastructure.container._core_services import (
    CoreServices,
    wire_core_services,
)
from pr_auto_reviewer.infrastructure.container._platform_adapters import (
    wire_platform_adapters,
)
from pr_auto_reviewer.infrastructure.container._platform_clients import (
    wire_platform_clients,
)
from pr_auto_reviewer.infrastructure.context.review_context_factory import (
    ReviewContextFactory,
)
from pr_auto_reviewer.infrastructure.fragments.file_system_fragment_repository import (
    FileSystemFragmentRepository,
)
from pr_auto_reviewer.infrastructure.fragments.jinja2_renderer import (
    Jinja2Renderer,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.infrastructure.local_repository.local_git_repository import (
    LocalGitRepository,
)
from pr_auto_reviewer.infrastructure.notifier.linux_notifier import (
    LinuxNotifier,
)
from pr_auto_reviewer.infrastructure.persistence.json_file_pr_repository import (
    JsonFilePullRequestRepository,
)

CORE_SERVICES_INSTANCE_TYPES = [
    ("pr_repository", JsonFilePullRequestRepository),
    ("command_bus", InMemoryCommandBus),
    ("notifier", LinuxNotifier),
    ("fragment_repository", FileSystemFragmentRepository),
    ("fragment_renderer", Jinja2Renderer),
    ("review_context_factory", ReviewContextFactory),
    ("review_plan", ReviewPlan),
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


__all__ = ['CORE_SERVICES_INSTANCE_TYPES', 'AdvisorGranularity', 'Config', 'CoreServices', 'FileSystemFragmentRepository', 'GitProvider', 'InMemoryCommandBus', 'Jinja2Renderer', 'JsonFilePullRequestRepository', 'LinuxNotifier', 'LocalGitRepository', 'ReviewContextFactory', 'ReviewPlan', 'annotations', 'forgejo_config', 'local_repository', 'pytest', 'repo_context', 'wire_core_services', 'wire_platform_adapters', 'wire_platform_clients']
