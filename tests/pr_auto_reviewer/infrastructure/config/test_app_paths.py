"""Tests for AppPaths XDG directory resolution."""

from pathlib import Path

from pr_auto_reviewer.infrastructure.config.app_paths import AppPaths


class TestAppPaths:
    """Behaviour of AppPaths directory accessors."""

    def test_state_dir_when_xdg_state_home_set_returns_env_dir(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

        assert AppPaths.state_dir() == tmp_path / "pr-auto-reviewer"

    def test_cache_dir_when_xdg_cache_home_set_returns_env_dir(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

        assert AppPaths.cache_dir() == tmp_path / "pr-auto-reviewer"

    def test_config_dir_when_xdg_config_home_set_returns_env_dir(
        self, monkeypatch, tmp_path: Path
    ):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

        assert AppPaths.config_dir() == tmp_path / "pr-auto-reviewer"

    def test_state_dir_when_xdg_unset_falls_back_to_local_state(
        self, monkeypatch
    ):
        monkeypatch.delenv("XDG_STATE_HOME", raising=False)

        assert str(AppPaths.state_dir()).endswith(".local/state/pr-auto-reviewer")

    def test_cache_dir_when_xdg_unset_falls_back_to_cache(self, monkeypatch):
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

        assert str(AppPaths.cache_dir()).endswith(".cache/pr-auto-reviewer")

    def test_config_dir_when_xdg_unset_falls_back_to_config(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        assert str(AppPaths.config_dir()).endswith(".config/pr-auto-reviewer")
