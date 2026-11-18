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
            "GITHUB_OWNER_TOKEN=sometoken\n"
            "GITHUB_TOKEN_org_OWNER=sometoken\n"
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
        assert result["secrets"] == ("GITHUB_OWNER_TOKEN", "GITHUB_TOKEN_org_OWNER")
        assert source.read_text() == (
            "PLATFORM_MODE=both\n"
            "USE_STRICT_FRAGMENT_SELECTION=False\n"
            "GITHUB_OWNER_TOKEN=sometoken\n"
            "GITHUB_TOKEN_org_OWNER=sometoken\n"
        )
        with (config_dir / "settings.toml").open("rb") as stream:
            assert tomllib.load(stream) == {
                "PLATFORM_MODE": "both",
                "USE_STRICT_FRAGMENT_SELECTION": False,
            }
        assert TomlSettingsStore(config_dir / "settings.toml").all() == {
            "PLATFORM_MODE": "both",
            "USE_STRICT_FRAGMENT_SELECTION": False,
        }
        secrets = EncryptedSqliteSecretStore(state_dir / "secrets.sqlite3", "migration-key")
        assert secrets.get("GITHUB_OWNER_TOKEN") == "sometoken"
        assert secrets.get("GITHUB_TOKEN_org_OWNER") == "sometoken"
