"""CompositionRoot wiring tests."""

from unittest.mock import patch

import pytest

from pr_auto_reviewer.application.dtos.list_allowed_repositories_request import (
    ListAllowedRepositoriesRequest,
)
from pr_auto_reviewer.application.ports.inbound.review_pull_request_port import (
    ReviewPullRequestPort,
)
from pr_auto_reviewer.application.services.process_issue_commands_service import (
    ProcessIssueCommandsService,
)
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.git_credentials import GitCredentials
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.presentation.composition_root import (
    ApplicationComponents,
    CompositionRoot,
)
from pr_auto_reviewer.presentation.ports import OpenPullRequest, PrListerPort
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

    def test_components_list_allowed_repositories_is_wired(self, _root):
        response = _root.components.list_allowed_repositories.execute(
            ListAllowedRepositoriesRequest()
        )

        assert response.allows_every_repository is True

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

        root = CompositionRoot(
            credential_provider=provider,
            notifier=FakeNotifier(),
        )
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

        root = CompositionRoot(
            credential_provider=provider,
            notifier=FakeNotifier(),
        )
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

        root = CompositionRoot(
            credential_provider=provider,
            notifier=FakeNotifier(),
        )
        with patch("pr_auto_reviewer.presentation.composition_root.composition_root.PollingDaemon.start"):
            root.run_daemon()

        assert provider.calls == [("https", "codeberg.org")]
        assert root.container.local_repository.credentials is None

    def test_run_daemon_injects_configured_allow_list_into_daemon(
        self, monkeypatch, _fake_config
    ):
        captured: dict = {}

        class RecordingPollingDaemon:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def start(self):
                pass

        class NoneProvider:
            def prompt(self, protocol, host):
                return None

        _fake_config.run_once = True
        _fake_config.repos_allow_list = ("owner/only-this",)
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.composition_root.composition_root.load_config",
            lambda: _fake_config,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.container._container.load_config",
            lambda: _fake_config,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.composition_root.composition_root.PollingDaemon",
            RecordingPollingDaemon,
        )

        root = CompositionRoot(
            credential_provider=NoneProvider(),
            notifier=FakeNotifier(),
        )
        root.run_daemon()

        injected_allow_list = captured["repository_allow_list"]
        assert injected_allow_list.allows("owner/only-this") is True
        assert injected_allow_list.allows("owner/other") is False
        assert captured["config"].repos_allow_list == ("owner/only-this",)

    def test_cli_runner_reviews_repository_absent_from_allow_list(
        self, monkeypatch, _fake_config
    ):
        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/not-allowed", number=1),
            head_sha=CommitSha("abc1234"),
            title="Fix bug",
            is_draft=False,
        )

        class RecordingPrLister(PrListerPort):
            def __init__(self):
                self.queried_repos: list[str] = []

            def list_open(self, repository):
                self.queried_repos.append(repository)
                return [open_pr]

            def get_pr(self, repository, pr_number):
                self.queried_repos.append(repository)
                return open_pr

        class RecordingReviewService(ReviewPullRequestPort):
            def __init__(self):
                self.commands: list = []

            def execute(self, command):
                self.commands.append(command)
                return True

        _fake_config.output_mode = "terminal"
        _fake_config.repos_allow_list = ("owner/only-this",)
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.composition_root.composition_root.load_config",
            lambda: _fake_config,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.container._container.load_config",
            lambda: _fake_config,
        )

        root = CompositionRoot(notifier=FakeNotifier())
        cli_runner = root.components.cli_runner
        recording_pr_lister = RecordingPrLister()
        recording_review = RecordingReviewService()
        cli_runner._pr_lister = recording_pr_lister
        cli_runner._review_service = recording_review

        result = cli_runner._run_review(
            ["--repo", "owner/not-allowed", "--pr", "1"]
        )

        assert result == 0
        assert recording_pr_lister.queried_repos == ["owner/not-allowed"]
        assert len(recording_review.commands) == 1

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
        return CompositionRoot(notifier=FakeNotifier())
