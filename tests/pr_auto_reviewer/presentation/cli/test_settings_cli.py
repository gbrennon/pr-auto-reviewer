"""Tests for settings and encrypted credential CLI operations."""

from pathlib import Path

import pytest

from pr_auto_reviewer.presentation.cli.settings_cli import SettingsCli


class TestSettingsCli:
    """Verify CLI behavior at the settings boundary."""

    def test_snapshot_hides_secret_values_even_if_legacy_settings_contain_them(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)
        cli._settings().set("poll_interval", 30)
        (tmp_path / "config" / "pr-auto-reviewer" / "settings.toml").write_text(
            'poll_interval = 30\nGITHUB_MANAGER_TOKEN = "legacy-secret"\n', encoding="utf-8",
        )

        snapshot = cli.snapshot()

        assert snapshot.values == (("daemon.poll_interval", "30"),)
        assert "legacy-secret" not in repr(snapshot)

    def test_snapshot_exposes_values_but_never_secret_values(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)
        cli.run(["set", "poll_interval", "30"])
        cli.run(["set", "GITHUB_MANAGER_TOKEN", "secret-value"])

        snapshot = cli.snapshot()

        assert snapshot.values == (("daemon.poll_interval", "30"),)
        assert snapshot.secret_names == ("GITHUB_MANAGER_TOKEN",)
        assert "secret-value" not in repr(snapshot)

    def test_snapshot_without_encryption_key_keeps_non_secret_settings_available(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        monkeypatch.delenv("PR_AUTO_REVIEWER_ENCRYPTION_KEY", raising=False)
        cli = SettingsCli()
        cli.write("poll_interval", "30")

        snapshot = cli.snapshot()

        assert snapshot.values == (("daemon.poll_interval", "30"),)
        assert snapshot.secret_names == ()
        assert snapshot.secret_error == "PR_AUTO_REVIEWER_ENCRYPTION_KEY is required"

    def test_snapshot_reports_key_that_cannot_decrypt_persisted_secrets(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)
        cli.write("GITHUB_MANAGER_TOKEN", "secret-value")
        monkeypatch.setenv("PR_AUTO_REVIEWER_ENCRYPTION_KEY", "wrong-key")

        snapshot = cli.snapshot()

        assert snapshot.secret_names == ()
        assert snapshot.secret_error == (
            "Configured encryption key could not decrypt persisted data; "
            "verify the key or check for corrupted storage"
        )

    def test_write_and_unset_settings_without_reading_secrets(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)

        cli.write("poll_interval", "45")
        cli.write("GITHUB_MANAGER_TOKEN", "secret-value")
        cli.unset("poll_interval")

        snapshot = cli.snapshot()
        assert snapshot.values == ()
        assert snapshot.secret_names == ("GITHUB_MANAGER_TOKEN",)

    @staticmethod
    def _cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SettingsCli:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        monkeypatch.setenv("PR_AUTO_REVIEWER_ENCRYPTION_KEY", "test-key")
        return SettingsCli()

    def test_navigation_mode_defaults_to_arrows_and_accepts_configured_mode(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)
        assert cli.navigation_mode() == "arrows"
        cli.write("TUI_NAVIGATION_MODE", "vim")
        assert cli.navigation_mode() == "vim"

    def test_non_secret_setting_can_be_written_and_read(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)

        assert cli.run(["set", "poll_interval", "30"]) == 0
        capsys.readouterr()

        assert cli.run(["get", "poll_interval"]) == 0
        assert capsys.readouterr().out.strip() == "30"
        assert cli.run(["set", "platform.mode", "github"]) == 0
        assert cli._settings().get("PLATFORM_MODE") == "github"
        assert cli._settings().get("daemon.poll_interval") == 30

    def test_add_and_remove_repository_manage_allow_list_and_role_tokens(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)

        cli.add_repository("github:acme/widget", "manager", "reviewer")

        assert cli._settings().get("REPOS_ALLOW_LIST") == ["github:acme/widget"]
        assert cli.snapshot().secret_names == (
            "GITHUB_TOKEN_acme_MANAGER",
            "GITHUB_TOKEN_acme_REVIEWER",
        )
        cli.remove_repository("github:acme/widget")
        assert cli._settings().get("REPOS_ALLOW_LIST") == []

    def test_repo_add_command_prompts_for_write_only_role_tokens(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)
        tokens = iter(("manager", "reviewer"))
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.cli.settings_cli.getpass.getpass",
            lambda _prompt: next(tokens),
        )

        assert cli.run(["repo-add", "forgejo:acme/widget"]) == 0

        assert cli._settings().get("REPOS_ALLOW_LIST") == ["forgejo:acme/widget"]
        assert "Added repository forgejo:acme/widget" in capsys.readouterr().out

    def test_secret_can_be_overwritten_but_not_read(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)

        assert cli.run(["set", "GITHUB_MANAGER_TOKEN", "first"]) == 0
        assert cli.run(["set", "GITHUB_MANAGER_TOKEN", "second"]) == 0
        assert cli.run(["get", "GITHUB_MANAGER_TOKEN"]) == 2

        assert "cannot read secret" in capsys.readouterr().err

    def test_list_displays_setting_values_and_secret_names_only(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)
        cli.run(["set", "debug", "true"])
        cli.run(["set", "FORGEJO_MANAGER_TOKEN", "secret"])
        capsys.readouterr()

        assert cli.run(["list"]) == 0

        output = capsys.readouterr().out
        assert "daemon.debug = true" in output
        assert "FORGEJO_MANAGER_TOKEN = <secret>" in output
        assert "secret" not in output.replace("FORGEJO_MANAGER_TOKEN = <secret>", "")

    def test_list_reports_key_that_cannot_decrypt_persisted_secrets(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)
        cli.run(["set", "FORGEJO_MANAGER_TOKEN", "secret"])
        capsys.readouterr()
        monkeypatch.setenv("PR_AUTO_REVIEWER_ENCRYPTION_KEY", "wrong-key")

        assert cli.run(["list"]) == 2
        assert "could not decrypt persisted data" in capsys.readouterr().err

    def test_secret_setup_uses_key_from_user_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        config_home = tmp_path / "config"
        config_dir = config_home / "pr-auto-reviewer"
        config_dir.mkdir(parents=True)
        (config_dir / "config").write_text(
            "PR_AUTO_REVIEWER_ENCRYPTION_KEY=test-key\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        monkeypatch.delenv("PR_AUTO_REVIEWER_ENCRYPTION_KEY", raising=False)
        cli = SettingsCli()

        assert cli.run(["set", "FORGEJO_MANAGER_TOKEN", "secret"]) == 0
        capsys.readouterr()

        assert cli.run(["list"]) == 0
        assert "FORGEJO_MANAGER_TOKEN = <secret>" in capsys.readouterr().out

    def test_encryption_key_setup_writes_user_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        config_home = tmp_path / "config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        monkeypatch.delenv("PR_AUTO_REVIEWER_ENCRYPTION_KEY", raising=False)
        monkeypatch.setattr(
            "pr_auto_reviewer.presentation.cli.settings_cli.getpass.getpass",
            lambda prompt: "defined-key",
        )
        cli = SettingsCli()

        assert cli.run(["set-encryption-key"]) == 0

        config_path = config_home / "pr-auto-reviewer" / "config"
        assert "PR_AUTO_REVIEWER_ENCRYPTION_KEY=defined-key\n" in (
            config_path.read_text(encoding="utf-8")
        )
        assert "defined-key" not in capsys.readouterr().out

    def test_generic_allow_list_set_get_list_and_snapshot_use_json_array_values(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)

        assert cli.run(
            [
                "set",
                "REPOS_ALLOW_LIST",
                "github:owner/repo, forgejo:owner/other\nforgejo:owner/third",
            ]
        ) == 0
        capsys.readouterr()

        assert cli._settings().get("REPOS_ALLOW_LIST") == [
            "github:owner/repo",
            "forgejo:owner/other",
            "forgejo:owner/third",
        ]
        snapshot = cli.snapshot()
        assert (
            "repositories.allow_list",
            '["github:owner/repo", "forgejo:owner/other", "forgejo:owner/third"]',
        ) in snapshot.values
        assert cli.run(["get", "REPOS_ALLOW_LIST"]) == 0
        assert capsys.readouterr().out.strip() == (
            '["github:owner/repo", "forgejo:owner/other", "forgejo:owner/third"]'
        )
        assert cli.run(["list"]) == 0
        assert (
            "repositories.allow_list = [\"github:owner/repo\", \"forgejo:owner/other\", \"forgejo:owner/third\"]"
            in capsys.readouterr().out
        )

    def test_old_string_allow_list_is_canonicalized_for_cli_output(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)
        cli._settings().set(
            "REPOS_ALLOW_LIST",
            r"github:owner/repo\nforgejo:owner/other",
        )

        snapshot = cli.snapshot()

        assert (
            "repositories.allow_list",
            '["github:owner/repo", "forgejo:owner/other"]',
        ) in snapshot.values
        assert cli.run(["get", "REPOS_ALLOW_LIST"]) == 0
        assert capsys.readouterr().out.strip() == (
            '["github:owner/repo", "forgejo:owner/other"]'
        )
        assert cli.run(["list"]) == 0
        assert (
            "repositories.allow_list = [\"github:owner/repo\", \"forgejo:owner/other\"]"
            in capsys.readouterr().out
        )
