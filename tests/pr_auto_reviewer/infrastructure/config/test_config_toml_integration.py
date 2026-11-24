"""Tests for loading persistent TOML settings into Config."""

from pathlib import Path

from pr_auto_reviewer.infrastructure.config import TomlSettingsStore, load_config


class TestConfigTomlIntegration:
    """Verify TOML settings participate in application configuration."""

    def test_grouped_toml_settings_are_loaded_when_no_environment_override(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        store = TomlSettingsStore(tmp_path / "config" / "pr-auto-reviewer" / "settings.toml")
        store.set("daemon.poll_interval", 17)
        store.set("platform.mode", "github")

        config = load_config()

        assert config.poll_interval == 17
        assert config.platform_mode.value == "github"

    def test_legacy_flat_toml_settings_remain_compatible(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        settings_path = tmp_path / "config" / "pr-auto-reviewer" / "settings.toml"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            'POLL_INTERVAL = 19\nPLATFORM_MODE = "github"\n',
            encoding="utf-8",
        )

        config = load_config()

        assert config.poll_interval == 19
        assert config.platform_mode.value == "github"

    def test_grouped_repository_settings_coexist_with_auth_tables(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        path = tmp_path / "config" / "pr-auto-reviewer" / "settings.toml"
        path.parent.mkdir(parents=True)
        path.write_text(
            '[repositories]\n'
            'allow_list = ["github:owner/repo"]\n\n'
            '[repositories."github.com/owner/repo"]\n'
            'manager_profile = "manager"\n',
            encoding="utf-8",
        )

        config = load_config()

        assert config.repos_allow_list == ("github:owner/repo",)
        assert config.auth_configuration.for_repository("github.com/owner/repo").manager_profile == (
            "manager"
        )

    def test_toml_allow_list_array_loads_as_immutable_tuple(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        store = TomlSettingsStore(tmp_path / "config" / "pr-auto-reviewer" / "settings.toml")
        store.set("REPOS_ALLOW_LIST", ["github:owner/repo", "forgejo:owner/other"])

        config = load_config()

        assert config.repos_allow_list == (
            "github:owner/repo",
            "forgejo:owner/other",
        )

    def test_toml_allow_list_legacy_string_is_normalized(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        store = TomlSettingsStore(tmp_path / "config" / "pr-auto-reviewer" / "settings.toml")
        store.set("REPOS_ALLOW_LIST", "github:owner/repo, forgejo:owner/other")

        config = load_config()

        assert config.repos_allow_list == (
            "github:owner/repo",
            "forgejo:owner/other",
        )
