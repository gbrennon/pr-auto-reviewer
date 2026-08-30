"""CompositionRoot wiring tests."""

from unittest.mock import patch

import pytest

from pr_auto_reviewer.application.services.process_issue_commands_service import (
    ProcessIssueCommandsService,
)
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.domain.value_objects.git_credentials import GitCredentials
from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.presentation.composition_root import (
    ApplicationComponents,
    CompositionRoot,
)
from tests.fakes.fake_notifier import FakeNotifier


class TestCompositionRoot:

    def test_composition_root_exposes_application_components(self, _root):
        assert isinstance(_root.components, ApplicationComponents)

    def test_components_review_service_is_wired(self, _root):
        assert isinstance(
            _root.components.review_service, ReviewPullRequestService,
        )

    def test_components_process_commands_service_is_wired(self, _root):
        assert isinstance(
            _root.components.process_commands_service,
            ProcessIssueCommandsService,
        )

    def test_components_review_reader_is_not_none(self, _root):
        assert _root.components.review_reader is not None

    def test_components_pr_lister_is_not_none(self, _root):
        assert _root.components.pr_lister is not None

    def test_components_repo_lister_is_not_none(self, _root):
        assert _root.components.repo_lister is not None

    def test_components_review_item_parser_is_wired(self, _root):
        assert isinstance(
            _root.components.review_item_parser, ReviewItemParser,
        )

    def test_components_cli_runner_is_wired(self, _root):
        assert isinstance(_root.components.cli_runner, CliRunner)

    def test_container_is_exposed(self, _root):
        assert _root.container is not None

    def test_components_notifier_uses_injected_override(self, monkeypatch, _fake_config):
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.composition_root.composition_root.load_config",
            lambda: _fake_config,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.container._container.load_config",
            lambda: _fake_config,
        )
        fake_notifier = FakeNotifier()

        root = CompositionRoot(notifier=fake_notifier)

        assert root.components.notifier is fake_notifier

    def test_components_notifier_falls_back_to_container_notifier(self, _root):
        assert _root.components.notifier is not None

    def test_run_daemon_prompts_and_sets_credentials_before_start(self, monkeypatch, _fake_config):
        class FakeProvider:
            def __init__(self):
                self.calls = []
            def prompt(self, protocol, host):
                self.calls.append((protocol, host))
                return GitCredentials(protocol=protocol, username="alice", secret="tok")

        _fake_config.run_once = True
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.composition_root.composition_root.load_config",
            lambda: _fake_config,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.container._container.load_config",
            lambda: _fake_config,
        )
        provider = FakeProvider()

        root = CompositionRoot(credential_provider=provider)
        with patch("pr_auto_reviewer.presentation.composition_root.composition_root.PollingDaemon.start"):
            root.run_daemon()

        assert provider.calls == [("https", "codeberg.org")]
        creds = root.container.local_repository.credentials
        assert creds is not None
        assert creds.username == "alice"
        assert creds.protocol == "https"

    def test_run_daemon_prompts_ssh_when_clone_protocol_is_ssh(self, monkeypatch, _fake_config):
        from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol

        class FakeProvider:
            def __init__(self):
                self.calls = []
            def prompt(self, protocol, host):
                self.calls.append((protocol, host))
                return GitCredentials(protocol=protocol, username="alice")

        _fake_config.run_once = True
        _fake_config.clone_protocol = CloneProtocol.SSH
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.composition_root.composition_root.load_config",
            lambda: _fake_config,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.container._container.load_config",
            lambda: _fake_config,
        )
        provider = FakeProvider()

        root = CompositionRoot(credential_provider=provider)
        with patch("pr_auto_reviewer.presentation.composition_root.composition_root.PollingDaemon.start"):
            root.run_daemon()

        assert provider.calls == [("ssh", "codeberg.org")]
        creds = root.container.local_repository.credentials
        assert creds is not None
        assert creds.protocol == "ssh"

    def test_run_daemon_skips_credentials_when_provider_returns_none(self, monkeypatch, _fake_config):
        class NoneProvider:
            def __init__(self):
                self.calls = []
            def prompt(self, protocol, host):
                self.calls.append((protocol, host))

        _fake_config.run_once = True
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.composition_root.composition_root.load_config",
            lambda: _fake_config,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.container._container.load_config",
            lambda: _fake_config,
        )
        provider = NoneProvider()

        root = CompositionRoot(credential_provider=provider)
        with patch("pr_auto_reviewer.presentation.composition_root.composition_root.PollingDaemon.start"):
            root.run_daemon()

        assert provider.calls == [("https", "codeberg.org")]
        assert root.container.local_repository.credentials is None

    @pytest.fixture
    def _fake_config(self) -> Config:
        return Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fake-owner",
            forgejo_reviewer_token="fake-reviewer",
            forgejo_reviewer_username="fake-user",
            github_owner_token="fake-owner",
            github_reviewer_token="fake-reviewer",
            github_reviewer_username="fake-user",
            output_mode="terminal",
        )

    @pytest.fixture
    def _root(self, monkeypatch, _fake_config: Config):
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.composition_root.composition_root.load_config",
            lambda: _fake_config,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.container._container.load_config",
            lambda: _fake_config,
        )
        return CompositionRoot()
