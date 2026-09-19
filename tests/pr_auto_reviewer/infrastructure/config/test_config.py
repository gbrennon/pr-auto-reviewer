"""Tests for load_config using captured fixture data."""

from pathlib import Path

import pytest

from pr_auto_reviewer.infrastructure.config.advisor_granularity import (
    AdvisorGranularity,
)


class TestLoadConfig:

    def test_defaults_when_no_env_vars(self):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        cfg = load_config()
        assert cfg.env == "production"
        assert cfg.platform_mode.value == "forgejo"
        assert cfg.fragments_dir == ""

    def test_env_dev_when_env_file_exists(self, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        (tmp_path / ".env").touch()
        cfg = load_config()
        assert cfg.env == "development"

    def test_explicit_env_overrides_detection(self, monkeypatch):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        monkeypatch.setenv("ENV", "staging")
        cfg = load_config()
        assert cfg.env == "staging"

    def test_platform_mode_github(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("PLATFORM_MODE", "github")
        cfg = load_config()
        assert cfg.platform_mode.value == "github"

    def test_platform_mode_both(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("PLATFORM_MODE", "both")
        cfg = load_config()
        assert cfg.platform_mode.value == "both"

    def test_clone_protocol_defaults_to_https(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        cfg = load_config()
        assert cfg.clone_protocol is CloneProtocol.HTTPS

    def test_clone_protocol_from_env(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("CLONE_PROTOCOL", "ssh")
        cfg = load_config()
        assert cfg.clone_protocol is CloneProtocol.SSH

    def test_clone_protocol_normalizes_case_and_aliases(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("CLONE_PROTOCOL", "git")
        cfg = load_config()
        assert cfg.clone_protocol is CloneProtocol.SSH

    def test_forgejo_mode_env_var_fallback(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("FORGEJO_MODE", "forgejo")
        cfg = load_config()
        assert cfg.platform_mode.value == "forgejo"

    def test_llm_settings(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("LLM_HOST", "http://llm:8080")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        cfg = load_config()
        assert cfg.llm_host == "http://llm:8080"
        assert cfg.llm_model == "gpt-4"

    def test_llm_timeout_from_env(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("LLM_TIMEOUT", "321")
        cfg = load_config()
        assert cfg.llm_timeout == 321

    def test_llm_model_none_when_empty(self):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        cfg = load_config()
        assert cfg.llm_model is None

    def test_output_mode_file_with_path(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("REVIEW_OUTPUT", "file:/tmp/out.md")
        cfg = load_config()
        assert cfg.output_mode == "terminal"
        assert cfg.output_path == "/tmp/out.md"

    def test_output_mode_file_empty_path(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("REVIEW_OUTPUT", "file:")
        cfg = load_config()
        assert cfg.output_mode == "terminal"
        assert cfg.output_path is None

    def test_debug_enabled(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("DEBUG", "1")
        cfg = load_config()
        assert cfg.debug is True

    def test_numeric_settings(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("POLL_INTERVAL", "30")
        monkeypatch.setenv("MAX_PROMPT_TOKENS", "4096")
        monkeypatch.setenv("MAX_FILE_CHARS", "2000")
        monkeypatch.setenv("MAX_FILES", "5")
        monkeypatch.setenv("MAX_STRUCTURE_LINES", "50")
        monkeypatch.setenv("LLM_MAX_RETRIES", "3")
        cfg = load_config()
        assert cfg.poll_interval == 30
        assert cfg.max_prompt_tokens == 4096
        assert cfg.max_file_chars == 2000
        assert cfg.max_files == 5
        assert cfg.max_structure_lines == 50
        assert cfg.llm_max_retries == 3
    def test_use_compact_template_true(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("USE_COMPACT_TEMPLATE", "true")
        cfg = load_config()
        assert cfg.use_compact_template is True

    def test_use_strict_fragment_selection_true(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("USE_STRICT_FRAGMENT_SELECTION", "true")
        cfg = load_config()
        assert cfg.use_strict_fragment_selection is True

    def test_review_max_tries_from_env(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("REVIEW_MAX_TRIES", "4")
        cfg = load_config()
        assert cfg.review_max_tries == 4

    def test_review_max_tries_defaults_to_two(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        cfg = load_config()
        assert cfg.review_max_tries == 2


    def test_github_settings(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)

        token_values = {
            "GITHUB_API_URL": "https://github.example.com",
            "GITHUB_OWNER_TOKEN": "gh_owner",
            "GITHUB_REVIEWER_TOKEN": "gh_reviewer",
            "GITHUB_REVIEWER_USERNAME": "bot",
            "GITHUB_REVIEW_MODE": "informal",
        }
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.config.config.dotenv_values",
            lambda path: token_values if ".env" in str(path) else {},
        )
        monkeypatch.setenv("GITHUB_API_URL", "https://github.example.com")

        cfg = load_config()
        assert cfg.github_api_url == "https://github.example.com"
        assert cfg.github_owner_token == "gh_owner"
        assert cfg.github_reviewer_token == "gh_reviewer"
        assert cfg.github_reviewer_username == "bot"
        assert cfg.github_review_mode == "informal"

    def test_forgejo_settings_with_host_fallback(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("FORGEJO_HOST", "https://git.example.com")

        token_values = {
            "FORGEJO_OWNER_TOKEN": "fj_owner",
            "FORGEJO_REVIEWER_TOKEN": "fj_reviewer",
            "FORGEJO_REVIEWER_USERNAME": "fj_bot",
        }
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.config.config.dotenv_values",
            lambda path: token_values if ".env" in str(path) else {},
        )

        cfg = load_config()
        assert cfg.forgejo_api_url == "https://git.example.com/api/v1"
        assert cfg.forgejo_owner_token == "fj_owner"
        assert cfg.forgejo_reviewer_token == "fj_reviewer"
        assert cfg.forgejo_reviewer_username == "fj_bot"


    def test_load_production_parses_hyphenated_org_token_overrides(
        self, monkeypatch, tmp_path: Path
    ):
        """_load_production reads from a config file parsed by dotenv_values,
        which accepts hyphenated keys that systemd's EnvironmentFile= would
        reject.  Verify they reach Config.org_token_overrides intact."""
        from pr_auto_reviewer.infrastructure.config.config import load_config

        # Ensure Path.exists returns True so _load_production actually
        # calls dotenv_values (the real ~/.config/… path won't exist in CI).
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.config.config.Path.exists",
            lambda self: True,
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.config.config.dotenv_values",
            lambda path: {
                "GITHUB_TOKEN_forging-blocks-org_OWNER": "ghp_org_owner",
                "GITHUB_TOKEN_forging-blocks-org_REVIEWER": "ghp_org_reviewer",
                "GITHUB_TOKEN_forging-blocks-org_REVIEWER_USERNAME": "org-reviewer-bot",
                "FORGEJO_TOKEN_my-other-org_OWNER": "fj_owner_token",
            },
        )

        cfg = load_config()

        gh_overrides = cfg.org_token_overrides.github
        assert "forging-blocks-org" in gh_overrides
        entry = gh_overrides["forging-blocks-org"]
        assert entry.owner_token == "ghp_org_owner"
        assert entry.reviewer_token == "ghp_org_reviewer"
        assert entry.reviewer_username == "org-reviewer-bot"

        fj_overrides = cfg.org_token_overrides.forgejo
        assert "my-other-org" in fj_overrides
        assert fj_overrides["my-other-org"].owner_token == "fj_owner_token"
    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch, tmp_path: Path):
        """Prevent real .env and env vars from leaking into tests."""
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.config.repo_root.RepoRoot.path",
            classmethod(lambda cls: tmp_path),
        )
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.config.config.dotenv_values",
            lambda path: {},
        )
        for var in [
            "ENV",
            "PLATFORM_MODE",
            "FORGEJO_MODE",
            "FORGEJO_API_URL",
            "FORGEJO_HOST",
            "GITHUB_API_URL",
            "GITHUB_OWNER_TOKEN",
            "GITHUB_REVIEWER_TOKEN",
            "GITHUB_REVIEWER_USERNAME",
            "GITHUB_REVIEW_MODE",
            "FORGEJO_OWNER_TOKEN",
            "FORGEJO_REVIEWER_TOKEN",
            "FORGEJO_REVIEWER_USERNAME",
            "LLM_HOST",
            "LLM_MODEL",
            "LLM_TIMEOUT",
            "REVIEW_OUTPUT",
            "POLL_INTERVAL",
            "DEBUG",
            "MAX_PROMPT_TOKENS",
            "MAX_FILE_CHARS",
            "MAX_FILES",
            "USE_COMPACT_TEMPLATE",
            "USE_STRICT_FRAGMENT_SELECTION",
            "MAX_STRUCTURE_LINES",
            "PROMPT_MODE",
            "LLM_MAX_RETRIES",
            "RUN_ONCE",
            "REPOS_FILTER",
            "REPOS_ALLOW_LIST",
            "FORCE_PR",
        ]:
            monkeypatch.delenv(var, raising=False)

    def _enter_dev_mode(self, tmp_path: Path) -> None:
        """Create .env so load_config detects development mode."""
        (tmp_path / ".env").touch()

    def test_llm_call_budget_and_advisor_granularity(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("LLM_CALL_BUDGET", "42")
        monkeypatch.setenv("ADVISOR_GRANULARITY", "turn")
        cfg = load_config()
        assert cfg.llm_call_budget == 42
        assert cfg.advisor_granularity is AdvisorGranularity.TURN

    def test_advisor_granularity_defaults_to_phase(self):
        from pr_auto_reviewer.infrastructure.config.config_builder import (
            ConfigBuilder,
        )

        cfg = ConfigBuilder().build({}, env_name="test")
        assert cfg.llm_call_budget == 300
        assert cfg.advisor_granularity is AdvisorGranularity.PHASE

    def test_invalid_advisor_granularity_is_rejected(self):
        from pr_auto_reviewer.infrastructure.config.config_builder import (
            ConfigBuilder,
        )

        with pytest.raises(ValueError):
            ConfigBuilder().build(
                {}, env_name="test", advisor_granularity="every-other-turn"
            )

    def test_repos_allow_list_parsed_from_comma_separated_source(self):
        from pr_auto_reviewer.infrastructure.config.config_builder import (
            ConfigBuilder,
        )

        cfg = ConfigBuilder().build(
            {"REPOS_ALLOW_LIST": "owner/a, owner/b"}, env_name="test"
        )
        assert cfg.repos_allow_list == ("owner/a", "owner/b")

    def test_repos_allow_list_defaults_to_empty_tuple(self):
        from pr_auto_reviewer.infrastructure.config.config_builder import (
            ConfigBuilder,
        )

        cfg = ConfigBuilder().build({}, env_name="test")
        assert cfg.repos_allow_list == ()

    def test_repos_allow_list_newline_form_matches_comma_form(self):
        from pr_auto_reviewer.infrastructure.config.config_builder import (
            ConfigBuilder,
        )

        cfg = ConfigBuilder().build(
            {"REPOS_ALLOW_LIST": "owner/a\nowner/b"}, env_name="test"
        )
        assert cfg.repos_allow_list == ("owner/a", "owner/b")

    def test_repos_allow_list_from_env_in_dev_mode(self, monkeypatch, tmp_path: Path):
        from pr_auto_reviewer.infrastructure.config.config import load_config

        self._enter_dev_mode(tmp_path)
        monkeypatch.setenv("REPOS_ALLOW_LIST", "owner/a")
        cfg = load_config()
        assert cfg.repos_allow_list == ("owner/a",)
