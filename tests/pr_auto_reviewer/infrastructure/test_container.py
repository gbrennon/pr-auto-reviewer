import pytest
from pr_auto_reviewer.infrastructure.container import Container
from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


class TestContainer:

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
    def _container(self, monkeypatch, _fake_config: Config):
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.container.load_config",
            lambda: _fake_config,
        )
        return Container(_fake_config)

    @pytest.mark.parametrize("attr", [
        "config",
        "pr_repository",
        "changeset_fetcher",
        "repository_context",
        "llm_review",
        "review_publisher",
        "review_reader",
        "comment_reader",
        "comment_publisher",
        "issue_tracker",
        "command_bus",
        "repo_lister",
        "pr_lister",
    ])
    def test_container_provides_non_null_instance(
        self, _container, attr,
    ):
        assert getattr(_container, attr) is not None
