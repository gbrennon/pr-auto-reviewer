"""Tests for loading persistent TOML settings into Config."""

from pathlib import Path

from pr_auto_reviewer.infrastructure.config import TomlSettingsStore, load_config


class TestConfigTomlIntegration:
    """Verify TOML settings participate in application configuration."""

    def test_toml_settings_are_loaded_when_no_environment_override(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        store = TomlSettingsStore(tmp_path / "config" / "pr-auto-reviewer" / "settings.toml")
        store.set("poll_interval", 17)
        store.set("platform_mode", "github")

        config = load_config()

        assert config.poll_interval == 17
        assert config.platform_mode.value == "github"
