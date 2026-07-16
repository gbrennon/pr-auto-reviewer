"""Tests for EnvironmentDetector.is_installed."""

from pathlib import Path

from pr_auto_reviewer.infrastructure.config.environment_detector import (
    EnvironmentDetector,
)


class TestEnvironmentDetectorIsInstalled:
    def test_returns_true_when_no_env_file(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.config.repo_root.RepoRoot.path",
            classmethod(lambda cls: tmp_path),
        )
        detector = EnvironmentDetector()
        assert detector.is_installed() is True

    def test_returns_false_when_env_file_exists(self, tmp_path: Path, monkeypatch):
        (tmp_path / ".env").touch()
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.config.repo_root.RepoRoot.path",
            classmethod(lambda cls: tmp_path),
        )
        detector = EnvironmentDetector()
        assert detector.is_installed() is False
