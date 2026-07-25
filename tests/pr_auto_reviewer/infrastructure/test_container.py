import pytest
import os
from pathlib import Path
from pr_auto_reviewer.infrastructure.container import Container
from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


class TestContainer:

    @pytest.fixture(autouse=True)
    def _redirect_config_dir(self, tmp_path: Path, monkeypatch) -> None:
        config_root = tmp_path / ".config" / "pr-auto-reviewer"
        config_root.mkdir(parents=True, exist_ok=True)
        _real_expanduser = os.path.expanduser
        monkeypatch.setattr(
            os.path,
            "expanduser",
            lambda p, _real=_real_expanduser: str(config_root) if "pr-auto-reviewer" in p else _real(p),
        )
        monkeypatch.setattr(os, "makedirs", lambda *a, **kw: None)

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

    def test_container_creates_token_resolver_both_mode(self):
        """TokenResolver is injected into both github and forgejo clients
        in BOTH platform mode, with correct prefixes."""
        config = Config(
            env="test",
            platform_mode=GitProvider.BOTH,
            forgejo_owner_token="fj-own",
            forgejo_reviewer_token="fj-rev",
            forgejo_reviewer_username="fj-user",
            github_owner_token="gh-own",
            github_reviewer_token="gh-rev",
            github_reviewer_username="gh-user",
            output_mode="api",
        )
        container = Container(config)
        publisher = container.review_publisher

        gh_adapter = publisher._publishers["github"]
        assert gh_adapter._publishing._client._token_resolver is not None
        _token, source = gh_adapter._publishing._client._token_resolver.resolve_source(
            "OWNER", "test-org/repo"
        )
        assert source.startswith("GITHUB_")
        assert gh_adapter._publishing._owner_client._token_resolver is not None
        _token2, source2 = gh_adapter._publishing._owner_client._token_resolver.resolve_source(
            "OWNER", "test-org/repo"
        )
        assert source2.startswith("GITHUB_")

        fj_adapter = publisher._publishers["forgejo"]
        assert fj_adapter._publishing._client._token_resolver is not None
        _token3, source3 = fj_adapter._publishing._client._token_resolver.resolve_source(
            "OWNER", "test-org/repo"
        )
        assert source3.startswith("FORGEJO_")
        assert fj_adapter._publishing._owner_client._token_resolver is not None
        _token4, source4 = fj_adapter._publishing._owner_client._token_resolver.resolve_source(
            "OWNER", "test-org/repo"
        )
        assert source4.startswith("FORGEJO_")

    def test_container_creates_preflight_verifier_both_mode(self):
        """PreflightVerifier is injected into both client roles in BOTH
        platform mode."""
        config = Config(
            env="test",
            platform_mode=GitProvider.BOTH,
            forgejo_owner_token="fj-own",
            forgejo_reviewer_token="fj-rev",
            forgejo_reviewer_username="fj-user",
            github_owner_token="gh-own",
            github_reviewer_token="gh-rev",
            github_reviewer_username="gh-user",
            output_mode="api",
        )
        container = Container(config)
        publisher = container.review_publisher

        gh_adapter = publisher._publishers["github"]
        assert gh_adapter._publishing._client._preflight_verifier is not None
        assert gh_adapter._publishing._owner_client._preflight_verifier is not None

        fj_adapter = publisher._publishers["forgejo"]
        assert fj_adapter._publishing._client._preflight_verifier is not None
        assert fj_adapter._publishing._owner_client._preflight_verifier is not None

    def test_container_creates_token_resolver_single_platform(self):
        """TokenResolver is injected into http_client with correct prefix
        in single-platform mode."""
        config = Config(
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
        container = Container(config)
        assert container.http_client._token_resolver is not None
        _token, source = container.http_client._token_resolver.resolve_source(
            "OWNER", "test-org/repo"
        )
        assert source.startswith("FORGEJO_")
