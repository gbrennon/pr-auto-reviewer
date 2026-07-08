"""Tests for _is_installed helper."""

from pathlib import Path

from pr_auto_reviewer.infrastructure.config.config import _is_installed


class TestIsInstalled:
    def test_returns_true_when_no_env_file(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.config.config._get_repo_root",
            lambda: tmp_path,
        )
        assert _is_installed() is True

    def test_returns_false_when_env_file_exists(self, tmp_path: Path, monkeypatch):
        (tmp_path / ".env").touch()
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.config.config._get_repo_root",
            lambda: tmp_path,
        )
        assert _is_installed() is False
