"""Tests for the temporary legacy configuration migration script."""

import tomllib
from pathlib import Path

from scripts.migrate_config import ConfigMigration
from pr_auto_reviewer.infrastructure.config.toml_settings_store import TomlSettingsStore
from pr_auto_reviewer.infrastructure.persistence.encrypted_sqlite_secret_store import (
    EncryptedSqliteSecretStore,
)


class TestConfigMigration:
    """Verify migration preserves the legacy file and separates values."""

    def test_migrates_settings_and_secrets_without_changing_source(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "config"
        source.write_text(
            "PLATFORM_MODE=both\n"
            "USE_STRICT_FRAGMENT_SELECTION=False\n"
            "GITHUB_MANAGER_TOKEN=sometoken\n"
            "GITHUB_TOKEN_org_MANAGER=sometoken\n"
        )
        config_dir = tmp_path / "config-home"
        state_dir = tmp_path / "state-home"

        result = ConfigMigration(
            source=source,
            config_dir=config_dir,
            state_dir=state_dir,
            encryption_key="migration-key",
        ).run()

        assert result["settings"] == ("PLATFORM_MODE", "USE_STRICT_FRAGMENT_SELECTION")
        assert result["secrets"] == ("GITHUB_MANAGER_TOKEN", "GITHUB_TOKEN_org_MANAGER")
        assert source.read_text() == (
            "PLATFORM_MODE=both\n"
            "USE_STRICT_FRAGMENT_SELECTION=False\n"
            "GITHUB_MANAGER_TOKEN=sometoken\n"
            "GITHUB_TOKEN_org_MANAGER=sometoken\n"
        )
        with (config_dir / "settings.toml").open("rb") as stream:
            assert tomllib.load(stream) == {
                "platform": {"mode": "both"},
                "prompt": {"strict_fragment_selection": False},
            }
        assert TomlSettingsStore(config_dir / "settings.toml").all() == {
            "platform.mode": "both",
            "prompt.strict_fragment_selection": False,
        }
        secrets = EncryptedSqliteSecretStore(state_dir / "secrets.sqlite3", "migration-key")
        assert secrets.get("GITHUB_MANAGER_TOKEN") == "sometoken"
        assert secrets.get("GITHUB_TOKEN_org_MANAGER") == "sometoken"

    def test_migrates_allow_list_to_toml_array_without_mutating_source(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "config"
        source.write_bytes(
            b"REPOS_ALLOW_LIST=github:owner/repo, forgejo:owner/other\r\n"
        )
        original_source = source.read_bytes()
        config_dir = tmp_path / "config-home"
        state_dir = tmp_path / "state-home"

        result = ConfigMigration(
            source=source,
            config_dir=config_dir,
            state_dir=state_dir,
            encryption_key="migration-key",
        ).run()

        assert result == {"settings": ("REPOS_ALLOW_LIST",), "secrets": ()}
        assert source.read_bytes() == original_source
        with (config_dir / "settings.toml").open("rb") as stream:
            assert tomllib.load(stream) == {
                "repositories": {
                    "allow_list": ["github:owner/repo", "forgejo:owner/other"],
                },
            }
