"""Tests for the temporary legacy configuration migration script."""

import stat
import tomllib
from pathlib import Path

from pytest import MonkeyPatch

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
            environment={},
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
            environment={},
        ).run()

        assert result == {"settings": ("REPOS_ALLOW_LIST",), "secrets": ()}
        assert source.read_bytes() == original_source
        with (config_dir / "settings.toml").open("rb") as stream:
            assert tomllib.load(stream) == {
                "repositories": {
                    "allow_list": ["github:owner/repo", "forgejo:owner/other"],
                },
            }

    def test_migrates_inline_environment_when_source_is_missing(
        self, tmp_path: Path
    ) -> None:
        config_dir = tmp_path / "config-home"
        state_dir = tmp_path / "state-home"

        result = ConfigMigration(
            source=tmp_path / "missing.env",
            config_dir=config_dir,
            state_dir=state_dir,
            encryption_key="migration-key",
            environment={
                "PLATFORM_MODE": "github",
                "GITHUB_MANAGER_TOKEN": "inline-token",
                "PR_AUTO_REVIEWER_ENCRYPTION_KEY": "unlock-key",
            },
        ).run()

        assert result == {
            "settings": ("PLATFORM_MODE",),
            "secrets": ("GITHUB_MANAGER_TOKEN",),
        }
        assert TomlSettingsStore(config_dir / "settings.toml").get("platform.mode") == (
            "github"
        )
        secrets = EncryptedSqliteSecretStore(state_dir / "secrets.sqlite3", "migration-key")
        assert secrets.get("GITHUB_MANAGER_TOKEN") == "inline-token"
        assert secrets.get("PR_AUTO_REVIEWER_ENCRYPTION_KEY") is None

    def test_dotenv_values_take_precedence_over_inline_environment(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "config"
        source.write_text("GITHUB_MANAGER_TOKEN=file-token\n")

        ConfigMigration(
            source=source,
            config_dir=tmp_path / "config-home",
            state_dir=tmp_path / "state-home",
            encryption_key="migration-key",
            environment={"GITHUB_MANAGER_TOKEN": "inline-token"},
        ).run()

        secrets = EncryptedSqliteSecretStore(
            tmp_path / "state-home" / "secrets.sqlite3", "migration-key"
        )
        assert secrets.get("GITHUB_MANAGER_TOKEN") == "file-token"

    def test_main_reads_encryption_key_from_source_file(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        source = tmp_path / "config"
        source.write_text(
            "PR_AUTO_REVIEWER_ENCRYPTION_KEY=source-key\n"
            "GITHUB_MANAGER_TOKEN=source-token\n"
        )
        monkeypatch.delenv("PR_AUTO_REVIEWER_ENCRYPTION_KEY", raising=False)

        assert (
            ConfigMigration.from_cli(
                [
                    "--source",
                    str(source),
                    "--config-dir",
                    str(tmp_path / "config-home"),
                    "--state-dir",
                    str(tmp_path / "state-home"),
                ]
            ).main()
            == 0
        )
        environment_file = tmp_path / "config-home" / "environment"
        assert environment_file.read_text() == (
            "PR_AUTO_REVIEWER_ENCRYPTION_KEY=source-key\n"
        )
        assert stat.S_IMODE(environment_file.stat().st_mode) == 0o600
        secrets = EncryptedSqliteSecretStore(
            tmp_path / "state-home" / "secrets.sqlite3", "source-key"
        )
        assert secrets.get("GITHUB_MANAGER_TOKEN") == "source-token"
        assert secrets.get("PR_AUTO_REVIEWER_ENCRYPTION_KEY") is None

    def test_owner_token_alias_migrates_and_cleans_plaintext_toml(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "config"
        source.write_text("GITHUB_OWNER_TOKEN=owner-token\n")
        config_dir = tmp_path / "config-home"
        config_dir.mkdir()
        (config_dir / "settings.toml").write_text(
            'GITHUB_OWNER_TOKEN = "old-owner-token"\n'
        )

        result = ConfigMigration(
            source=source,
            config_dir=config_dir,
            state_dir=tmp_path / "state-home",
            encryption_key="migration-key",
            environment={},
        ).run()

        assert result["secrets"] == ("GITHUB_MANAGER_TOKEN",)
        assert "GITHUB_OWNER_TOKEN" not in (config_dir / "settings.toml").read_text()
        secrets = EncryptedSqliteSecretStore(
            tmp_path / "state-home" / "secrets.sqlite3", "migration-key"
        )
        assert secrets.get("GITHUB_MANAGER_TOKEN") == "owner-token"

    def test_ignores_unrecognized_legacy_keys(self, tmp_path: Path) -> None:
        source = tmp_path / "config"
        source.write_text(
            "LLM_BACKEND=llama_cpp\n"
            "PUBLISH_INCONCLUSIVE_REVIEW=true\n"
            "Select.NULL=\n"
            "PLATFORM_MODE=github\n"
        )
        config_dir = tmp_path / "config-home"
        config_dir.mkdir()
        (config_dir / "settings.toml").write_text(
            'LLM_BACKEND = "old"\n"Select.NULL" = ""\n'
        )
        result = ConfigMigration(
            source=source,
            config_dir=config_dir,
            state_dir=tmp_path / "state-home",
            encryption_key="migration-key",
            environment={},
        ).run()
        assert result == {"settings": ("PLATFORM_MODE",), "secrets": ()}
        assert "LLM_BACKEND" not in (config_dir / "settings.toml").read_text()
        assert "Select.NULL" not in (config_dir / "settings.toml").read_text()

    def test_run_wipes_existing_secret_database(self, tmp_path: Path) -> None:
        source = tmp_path / "config"
        source.write_text(
            "PLATFORM_MODE=github\n"
            "GITHUB_MANAGER_TOKEN=new-token\n"
        )
        state_dir = tmp_path / "state-home"
        old_store = EncryptedSqliteSecretStore(
            state_dir / "secrets.sqlite3", "migration-key"
        )
        old_store.set("GITHUB_MANAGER_TOKEN", "old-token")
        (state_dir / "state.sqlite3").write_bytes(b"old-state")

        ConfigMigration(
            source=source,
            config_dir=tmp_path / "config-home",
            state_dir=state_dir,
            encryption_key="migration-key",
            environment={},
        ).run()

        new_store = EncryptedSqliteSecretStore(
            state_dir / "secrets.sqlite3", "migration-key"
        )
        assert new_store.names() == ("GITHUB_MANAGER_TOKEN",)
        assert not (state_dir / "state.sqlite3").exists()

    def test_organization_owner_alias_migrates_to_manager(self, tmp_path: Path) -> None:
        source = tmp_path / "config"
        source.write_text("GITHUB_TOKEN_forging-blocks-org_OWNER=org-token\n")

        result = ConfigMigration(
            source=source,
            config_dir=tmp_path / "config-home",
            state_dir=tmp_path / "state-home",
            encryption_key="migration-key",
            environment={},
        ).run()

        assert result["secrets"] == ("GITHUB_TOKEN_forging-blocks-org_MANAGER",)
        secrets = EncryptedSqliteSecretStore(
            tmp_path / "state-home" / "secrets.sqlite3", "migration-key"
        )
        assert secrets.get("GITHUB_TOKEN_forging-blocks-org_MANAGER") == "org-token"
