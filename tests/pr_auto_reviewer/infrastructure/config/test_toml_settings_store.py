"""Tests for TOML-backed non-secret application settings."""

from pathlib import Path

import pytest

from pr_auto_reviewer.infrastructure.config.toml_settings_store import (
    TomlSettingsStore,
)


class TestTomlSettingsStore:
    """Verify typed setting persistence and secret exclusion."""

    def test_settings_round_trip_uses_grouped_paths_and_legacy_aliases(
        self, tmp_path: Path
    ) -> None:
        store = TomlSettingsStore(tmp_path / "settings.toml")

        store.set("poll_interval", 30)
        store.set("platform.mode", "both")
        store.set("REPOS_ALLOW_LIST", ["owner/repo", "other/repo"])

        reopened = TomlSettingsStore(tmp_path / "settings.toml")
        assert reopened.all() == {
            "daemon.poll_interval": 30,
            "platform.mode": "both",
            "repositories.allow_list": ["owner/repo", "other/repo"],
        }
        assert reopened.get("POLL_INTERVAL") == 30
        assert reopened.get("platform_mode") == "both"
        assert reopened.get("repos_allow_list") == ["owner/repo", "other/repo"]

        document = (tmp_path / "settings.toml").read_text(encoding="utf-8")
        assert "[daemon]" in document
        assert "[platform]" in document
        assert "[repositories]" in document
        assert "poll_interval = 30" in document
        assert "platform_mode" not in document

    def test_grouped_writes_preserve_auth_and_repository_tables(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "settings.toml"
        path.write_text(
            '[auth.defaults]\nmanager_profile = "manager"\n\n'
            '[repositories."codeberg.org/acme/widget"]\n'
            'manager_profile = "repo-manager"\n',
            encoding="utf-8",
        )
        store = TomlSettingsStore(path)

        store.set("platform.mode", "github")

        reopened = TomlSettingsStore(path)
        document = reopened._document()
        assert document["auth"] == {"defaults": {"manager_profile": "manager"}}
        assert document["repositories"] == {
            "codeberg.org/acme/widget": {"manager_profile": "repo-manager"}
        }
        assert reopened.get("platform.mode") == "github"

    def test_grouped_setting_can_be_deleted_through_legacy_alias(
        self, tmp_path: Path
    ) -> None:
        store = TomlSettingsStore(tmp_path / "settings.toml")
        store.set("platform.mode", "both")

        store.delete("PLATFORM_MODE")

        assert store.get("platform.mode") is None
        assert store.all() == {}

    def test_token_keys_are_rejected(self, tmp_path: Path) -> None:
        store = TomlSettingsStore(tmp_path / "settings.toml")

        with pytest.raises(ValueError, match="secret"):
            store.set("GITHUB_MANAGER_TOKEN", "secret")

    def test_setting_can_be_deleted(self, tmp_path: Path) -> None:
        store = TomlSettingsStore(tmp_path / "settings.toml")
        store.set("debug", True)

        store.delete("debug")

        assert store.get("debug") is None
        assert store.all() == {}
