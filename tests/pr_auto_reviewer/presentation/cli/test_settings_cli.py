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

        assert snapshot.values == (("poll_interval", "30"),)
        assert "legacy-secret" not in repr(snapshot)

    def test_snapshot_exposes_values_but_never_secret_values(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)
        cli.run(["set", "poll_interval", "30"])
        cli.run(["set", "GITHUB_MANAGER_TOKEN", "secret-value"])

        snapshot = cli.snapshot()

        assert snapshot.values == (("poll_interval", "30"),)
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

        assert snapshot.values == (("poll_interval", "30"),)
        assert snapshot.secret_names == ()
        assert snapshot.secret_error == "PR_AUTO_REVIEWER_ENCRYPTION_KEY is required"

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

    def test_non_secret_setting_can_be_written_and_read(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = self._cli(monkeypatch, tmp_path)

        assert cli.run(["set", "poll_interval", "30"]) == 0
        capsys.readouterr()

        assert cli.run(["get", "poll_interval"]) == 0
        assert capsys.readouterr().out.strip() == "30"

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
        assert "debug = true" in output
        assert "FORGEJO_MANAGER_TOKEN = <secret>" in output
        assert "secret" not in output.replace("FORGEJO_MANAGER_TOKEN = <secret>", "")

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
