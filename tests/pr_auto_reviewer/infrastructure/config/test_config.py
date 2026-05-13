"""Tests for configuration module."""

import os
from pathlib import Path

import pytest

from pr_auto_reviewer.infrastructure.config import config as config_module
from pr_auto_reviewer.infrastructure.config.config import (
    _is_installed,
    _normalize_platform_api_url,
    load_config,
)


class _FakePath:
    """A Path replacement that always evaluates to a given tmp_path."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def __call__(self, *args, **kwargs) -> Path:
        return self._root


class TestIsInstalled:
    """Tests for _is_installed detection."""

    def test_returns_true_when_no_env_file(self, tmp_path: Path, monkeypatch) -> None:
        """Detects installed mode when .env doesn't exist."""
        monkeypatch.setattr(config_module, "_get_repo_root", lambda: tmp_path)
        assert _is_installed() is True

    def test_returns_false_when_env_file_exists(self, tmp_path: Path, monkeypatch) -> None:
        """Detects development mode when .env exists."""
        env_file = tmp_path / ".env"
        env_file.touch()
        monkeypatch.setattr(config_module, "_get_repo_root", lambda: tmp_path)
        assert _is_installed() is False


class TestNormalizePlatformApiUrl:
    """Tests for _normalize_platform_api_url."""

    def test_adds_suffix_when_missing(self):
        """Adds /api/v1 when not present."""
        assert _normalize_platform_api_url("https://codeberg.org") == "https://codeberg.org/api/v1"

    def test_keeps_suffix_when_present(self):
        """Keeps URL unchanged when /api/v1 already present."""
        assert _normalize_platform_api_url("https://codeberg.org/api/v1") == "https://codeberg.org/api/v1"

    def test_handles_trailing_slash(self):
        """Adds /api/v1 when URL has trailing slash."""
        assert _normalize_platform_api_url("https://codeberg.org/") == "https://codeberg.org//api/v1"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_dev_mode_uses_env_first(self, tmp_path: Path, monkeypatch) -> None:
        """In development mode, .env is loaded before user config."""
        env_file = tmp_path / ".env"
        env_file.write_text("PLATFORM_TOKEN=dev_token\n")

        user_config = tmp_path / "config"
        user_config.write_text("PLATFORM_TOKEN=user_token\n")

        monkeypatch.setattr(config_module, "Path", _FakePath(tmp_path))
        monkeypatch.setattr(config_module.os.path, "expanduser", lambda *a: str(user_config))
        for key in list(os.environ):
            monkeypatch.delenv(key, raising=False)

        config = load_config()
        assert config.platform_token == "user_token"

    def test_prod_mode_uses_user_config_first(self, tmp_path: Path, monkeypatch) -> None:
        """In production mode, user config is loaded before .env."""
        env_file = tmp_path / ".env"
        env_file.write_text("PLATFORM_TOKEN=dev_token\n")

        user_config = tmp_path / "config"
        user_config.write_text("PLATFORM_TOKEN=user_token\n")

        monkeypatch.setattr(config_module, "Path", _FakePath(tmp_path))
        monkeypatch.setattr(config_module.os.path, "expanduser", lambda *a: str(user_config))
        for key in list(os.environ):
            monkeypatch.delenv(key, raising=False)

        config = load_config()
        assert config.platform_token == "user_token"
        assert config.env == "production"

    def test_explicit_env_overrides_auto_detect(self, tmp_path: Path, monkeypatch) -> None:
        """Explicit ENV variable overrides auto-detection."""
        env_file = tmp_path / ".env"
        env_file.touch()

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setattr(config_module, "Path", _FakePath(tmp_path))

        config = load_config()
        assert config.env == "production"
