"""ConfigLoader — loads application configuration with correct environment precedence."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import dotenv_values

from pr_auto_reviewer.infrastructure.config.config_builder import ConfigBuilder
from pr_auto_reviewer.infrastructure.config.config_dataclass import Config
from pr_auto_reviewer.infrastructure.config.environment_detector import (
    EnvironmentDetector,
)
from pr_auto_reviewer.infrastructure.config.repo_root import RepoRoot

logger = logging.getLogger(__name__)

_COMMAND_LINE_KEYS = {
    "PLATFORM_MODE", "FORGEJO_MODE",
    "REVIEW_OUTPUT", "DEBUG", "PROMPT_MODE",
    "LLM_HOST", "LLM_MODEL", "OLLAMA_HOST", "OLLAMA_MODEL",
    "POLL_INTERVAL", "MAX_PROMPT_TOKENS",
    "MAX_FILE_CHARS", "MAX_FILES", "MAX_STRUCTURE_LINES",
    "USE_COMPACT_TEMPLATE", "USE_STRICT_FRAGMENT_SELECTION",
    "OLLAMA_TIMEOUT",
    "LLM_MAX_RETRIES",
    "GITHUB_API_URL", "GITHUB_REVIEW_MODE",
    "FORGEJO_API_URL", "FORGEJO_HOST",
    "RUN_ONCE", "REPOS_FILTER", "FORCE_PR",
    "CLONE_PROTOCOL",
}

_CONFIG_KEYS = list(_COMMAND_LINE_KEYS) + [
    "GITHUB_API_URL",
    "GITHUB_OWNER_TOKEN", "GITHUB_REVIEWER_TOKEN",
    "GITHUB_REVIEWER_USERNAME", "GITHUB_REVIEW_MODE",
    "FORGEJO_API_URL", "FORGEJO_HOST",
    "FORGEJO_OWNER_TOKEN", "FORGEJO_REVIEWER_TOKEN",
    "FORGEJO_REVIEWER_USERNAME",
]



class ConfigLoader:
    """Loads configuration with correct precedence for each environment.

    **Production** (installed via ``make install``):
        Reads *only* from ``~/.config/pr-auto-reviewer/config``.
        Token values come exclusively from that file.

    **Development** (repo with ``.env`` file):
        ``.env`` overrides ``~/.config/pr-auto-reviewer/config``.
        Token values always come from ``.env`` (or user config if not set).

    In **both** environments, command-line env vars from ``make`` or
    direct export override non-token settings like ``PLATFORM_MODE``,
    ``REVIEW_OUTPUT``, ``DEBUG``, etc.
    """

    def __init__(self) -> None:
        self._detector = EnvironmentDetector()
        self._builder = ConfigBuilder()

    @staticmethod
    def _merge_command_line_env(values: dict[str, str]) -> None:
        for key in _COMMAND_LINE_KEYS:
            if key in os.environ:
                values[key] = os.environ[key]

    def _load_production(self, config_path: str) -> Config:
        if Path(config_path).exists():
            values = dotenv_values(config_path)
            logger.info("Loading production config from %s", config_path)
        else:
            logger.warning(
                "Production config not found at %s; using defaults.",
                config_path,
            )
            values = {}
        self._merge_command_line_env(values)
        llm_max_retries = int(values.pop("LLM_MAX_RETRIES", 5))
        return self._builder.build(values, env_name="production", llm_max_retries=llm_max_retries)

    def _load_development(
        self, user_config_path: str, repo_env_path: Path, env: str
    ) -> Config:
        values: dict[str, str] = {}

        user_cfg = Path(user_config_path)
        if user_cfg.exists():
            logger.info(
                "Loading dev user config from %s", user_config_path
            )
            values.update(dotenv_values(user_cfg))

        if repo_env_path.exists():
            logger.info("Loading dev .env from %s", repo_env_path)
            values.update(dotenv_values(repo_env_path))

        self._merge_command_line_env(values)

        llm_max_retries = int(values.pop("LLM_MAX_RETRIES", 5))
        return self._builder.build(values, env_name=env, llm_max_retries=llm_max_retries)

    def load(self) -> Config:
        repo_root = RepoRoot.path()
        env = self._detector.detect()

        user_config_path = os.path.expanduser(
            "~/.config/pr-auto-reviewer/config"
        )
        repo_env_path = repo_root / ".env"

        if env == "production":
            return self._load_production(user_config_path)

        return self._load_development(user_config_path, repo_env_path, env)


def load_config() -> Config:
    return ConfigLoader().load()
