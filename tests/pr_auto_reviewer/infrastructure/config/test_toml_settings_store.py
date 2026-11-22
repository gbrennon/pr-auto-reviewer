"""Tests for TOML-backed non-secret application settings."""

from pathlib import Path

import pytest

from pr_auto_reviewer.infrastructure.config.toml_settings_store import (
    TomlSettingsStore,
)


class TestTomlSettingsStore:
    """Verify typed setting persistence and secret exclusion."""

    def test_settings_round_trip_preserves_types(self, tmp_path: Path) -> None:
        store = TomlSettingsStore(tmp_path / "settings.toml")

        store.set("poll_interval", 30)
        store.set("debug", True)
        store.set("platform_mode", "both")
        store.set("repos_allow_list", ["owner/repo", "other/repo"])

        reopened = TomlSettingsStore(tmp_path / "settings.toml")
        assert reopened.all() == {
            "debug": True,
            "platform_mode": "both",
            "poll_interval": 30,
            "repos_allow_list": ["owner/repo", "other/repo"],
        }

    def test_setting_can_be_deleted(self, tmp_path: Path) -> None:
        store = TomlSettingsStore(tmp_path / "settings.toml")
        store.set("debug", True)

        store.delete("debug")

        assert store.get("debug") is None
        assert store.all() == {}

    def test_token_keys_are_rejected(self, tmp_path: Path) -> None:
        store = TomlSettingsStore(tmp_path / "settings.toml")

        with pytest.raises(ValueError, match="secret"):
            store.set("GITHUB_MANAGER_TOKEN", "secret")
