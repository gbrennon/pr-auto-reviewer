"""ConfigLoader — loads application configuration with correct environment precedence."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from pr_auto_reviewer.infrastructure.config.config_builder import ConfigBuilder
from pr_auto_reviewer.infrastructure.config.config_dataclass import Config
from pr_auto_reviewer.infrastructure.config.environment_detector import (
    EnvironmentDetector,
)
from pr_auto_reviewer.infrastructure.config.repo_root import RepoRoot

logger = logging.getLogger(__name__)

_CONFIG_KEYS = [
    "PLATFORM_MODE", "FORGEJO_MODE",
    "GITHUB_API_URL", "GITHUB_OWNER_TOKEN", "GITHUB_REVIEWER_TOKEN",
    "GITHUB_REVIEWER_USERNAME", "GITHUB_REVIEW_MODE",
    "FORGEJO_API_URL", "FORGEJO_HOST", "FORGEJO_OWNER_TOKEN",
    "FORGEJO_REVIEWER_TOKEN", "FORGEJO_REVIEWER_USERNAME",
    "LLM_HOST", "OLLAMA_HOST", "LLM_MODEL", "OLLAMA_MODEL",
    "REVIEW_OUTPUT", "POLL_INTERVAL", "DEBUG",
    "MAX_PROMPT_TOKENS", "MAX_FILE_CHARS", "MAX_FILES",
    "MAX_STRUCTURE_LINES", "USE_COMPACT_TEMPLATE",
    "USE_STRICT_FRAGMENT_SELECTION", "OLLAMA_TIMEOUT",
    "PROMPT_MODE",
]


class ConfigLoader:
    """Loads configuration with correct precedence for each environment.

    **Production** (installed via ``make install``):
        Reads *only* from ``~/.config/pr-auto-reviewer/config``.
        Environment variables are **ignored entirely**.

    **Development** (repo with ``.env`` file):
        Command-line env vars (e.g. ``make review-force PLATFORM_MODE=github``)
        override ``.env``, which overrides ``~/.config/pr-auto-reviewer/config``.
    """

    def __init__(self) -> None:
        self._detector = EnvironmentDetector()
        self._builder = ConfigBuilder()

    def load(self) -> Config:
        repo_root = RepoRoot.path()
        env = self._detector.detect()

        user_config_path = os.path.expanduser("~/.config/pr-auto-reviewer/config")
        repo_env_path = repo_root / ".env"

        if env == "production":
            return self._load_production(user_config_path)

        return self._load_development(user_config_path, repo_env_path, env)

    def _load_production(self, config_path: str) -> Config:
        if Path(config_path).exists():
            values = dotenv_values(config_path)
            logger.info("Loading production config from %s", config_path)
        else:
            logger.warning(
                "Production config not found at %s; using defaults.", config_path
            )
            values = {}
        return self._builder.build(values, env_name="production")

    def _load_development(
        self, user_config_path: str, repo_env_path: Path, env: str
    ) -> Config:
        _pre_existing = {
            k: os.environ[k] for k in _CONFIG_KEYS if k in os.environ
        }

        user_cfg = Path(user_config_path)
        if user_cfg.exists():
            logger.info("Loading dev user config from %s", user_config_path)
            load_dotenv(user_cfg, override=False)

        if repo_env_path.exists():
            logger.info("Loading dev .env from %s", repo_env_path)
            load_dotenv(repo_env_path, override=True)

        for k, v in _pre_existing.items():
            os.environ[k] = v

        values = {k: os.environ.get(k, "") for k in _CONFIG_KEYS}
        return self._builder.build(values, env_name=env)


def load_config() -> Config:
    """Backward-compatible entry point.  Delegates to ``ConfigLoader``."""
    return ConfigLoader().load()