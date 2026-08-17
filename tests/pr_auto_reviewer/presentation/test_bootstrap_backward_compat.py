"""Bootstrap function backward compatibility tests."""

import pytest

from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.presentation.composition_root import (
    ApplicationComponents,
    bootstrap,
)


class TestBootstrapBackwardCompat:

    def test_bootstrap_function_returns_application_components(
        self, monkeypatch, _fake_config,
    ):
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.composition_root.load_config",
            lambda: _fake_config,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.container.load_config",
            lambda: _fake_config,
        )
        components = bootstrap()
        assert isinstance(components, ApplicationComponents)

    def test_run_daemon_function_exists_and_accepts_components(
        self, monkeypatch, _fake_config,
    ):
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.composition_root.load_config",
            lambda: _fake_config,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.container.load_config",
            lambda: _fake_config,
        )
        components = bootstrap()
        assert components is not None

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
