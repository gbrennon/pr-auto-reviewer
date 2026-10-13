"""ConfigLoader — loads application configuration with correct environment precedence."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import dotenv_values

from pr_auto_reviewer.infrastructure.config.advisor_granularity import (
    AdvisorGranularity,
)
from pr_auto_reviewer.infrastructure.config.app_paths import (
    AppPaths,
)
from pr_auto_reviewer.infrastructure.config.config_builder_composition import (
    ConfigBuilderComposition,
)
from pr_auto_reviewer.infrastructure.config.config_dataclass import Config
from pr_auto_reviewer.infrastructure.config.environment_detector import (
    EnvironmentDetector,
)
from pr_auto_reviewer.infrastructure.config.repo_root import RepoRoot

logger = logging.getLogger(__name__)

_COMMAND_LINE_KEYS = {
    "PLATFORM_MODE", "FORGEJO_MODE",
    "REVIEW_OUTPUT", "DEBUG", "PROMPT_MODE",
    "LLM_HOST", "LLM_MODEL",
    "POLL_INTERVAL", "MAX_PROMPT_TOKENS",
    "MAX_FILE_CHARS", "MAX_FILES", "MAX_STRUCTURE_LINES",
    "USE_COMPACT_TEMPLATE", "USE_STRICT_FRAGMENT_SELECTION",
    "LLM_TIMEOUT",
    "LLM_MAX_RETRIES", "LLM_MAX_TURNS", "LLM_CALL_BUDGET", "ADVISOR_GRANULARITY",
    "GITHUB_API_URL", "GITHUB_REVIEW_MODE",
    "FORGEJO_API_URL", "FORGEJO_HOST",
    "RUN_ONCE", "REPOS_FILTER", "REPOS_ALLOW_LIST", "FORCE_PR",
    "CLONE_PROTOCOL", "REVIEW_MAX_RETRIES", "REVIEW_MAX_TRIES",
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
        Reads *only* from ``<XDG_CONFIG_HOME>/pr-auto-reviewer/config``.
        Token values come exclusively from that file.

    **Development** (repo with ``.env`` file):
        ``.env`` overrides ``<XDG_CONFIG_HOME>/pr-auto-reviewer/config``.
        Token values always come from ``.env`` (or user config if not set).

    In **both** environments, command-line env vars from ``make`` or
    direct export override non-token settings like ``PLATFORM_MODE``,
    ``REVIEW_OUTPUT``, ``DEBUG``, etc.
    """

    def __init__(self) -> None:
        self._detector = EnvironmentDetector()
        self._builder = ConfigBuilderComposition().compose()

    def load(self) -> Config:
        repo_root = RepoRoot.path()
        env = self._detector.detect()

        user_config_path = str(AppPaths.config_dir() / "config")
        repo_env_path = repo_root / ".env"

        if env == "production":
            return self._load_production(user_config_path)

        return self._load_development(user_config_path, repo_env_path, env)

    def _merge_command_line_env(self, values: dict[str, str]) -> None:
        for key in _COMMAND_LINE_KEYS:
            if key in os.environ:
                values[key] = os.environ[key]

    def _load_values(self, path: Path) -> dict[str, str]:
        return {
            key: value
            for key, value in dotenv_values(path).items()
            if value is not None
        }

    def _apply_runtime_environment(self, values: dict[str, str]) -> None:
        bundle = values.get("REQUESTS_CA_BUNDLE", "").strip()
        if bundle:
            os.environ["REQUESTS_CA_BUNDLE"] = bundle

    def _load_production(self, config_path: str) -> Config:
        if Path(config_path).exists():
            values = self._load_values(Path(config_path))
            logger.info("Loading production config from %s", config_path)
        else:
            logger.warning(
                "Production config not found at %s; using defaults.",
                config_path,
            )
            values = {}
        self._merge_command_line_env(values)
        self._apply_runtime_environment(values)
        llm_max_retries = int(values.pop("LLM_MAX_RETRIES", 5))
        llm_max_turns = int(values.pop("LLM_MAX_TURNS", 10))

        advisor_max_blocks = int(values.pop("ADVISOR_MAX_BLOCKS", 2))
        review_max_conversations = int(
            values.pop("REVIEW_MAX_CONVERSATIONS", 48)
        )
        review_max_tries = int(values.pop("REVIEW_MAX_TRIES", 2))
        llm_call_budget = int(values.pop("LLM_CALL_BUDGET", 300))
        advisor_granularity = AdvisorGranularity.parse(
            values.pop("ADVISOR_GRANULARITY", AdvisorGranularity.PHASE.value)
        )
        return self._builder.build(
            values,
            env_name="production",
            llm_max_retries=llm_max_retries,
            llm_max_turns=llm_max_turns,
            advisor_max_blocks=advisor_max_blocks,
            review_max_conversations=review_max_conversations,
            review_max_tries=review_max_tries,
            llm_call_budget=llm_call_budget,
            advisor_granularity=advisor_granularity,
        )

    def _load_development(
        self, user_config_path: str, repo_env_path: Path, env: str
    ) -> Config:
        values: dict[str, str] = {}

        user_cfg = Path(user_config_path)
        if user_cfg.exists():
            logger.info(
                "Loading dev user config from %s", user_config_path
            )
            values.update(self._load_values(user_cfg))

        if repo_env_path.exists():
            logger.info("Loading dev .env from %s", repo_env_path)
            values.update(self._load_values(repo_env_path))

        self._merge_command_line_env(values)
        self._apply_runtime_environment(values)
        llm_max_retries = int(values.pop("LLM_MAX_RETRIES", 5))
        llm_max_turns = int(values.pop("LLM_MAX_TURNS", 10))
        advisor_max_blocks = int(values.pop("ADVISOR_MAX_BLOCKS", 2))
        review_max_conversations = int(
            values.pop("REVIEW_MAX_CONVERSATIONS", 48)
        )
        review_max_tries = int(values.pop("REVIEW_MAX_TRIES", 2))
        llm_call_budget = int(values.pop("LLM_CALL_BUDGET", 300))
        advisor_granularity = AdvisorGranularity.parse(
            values.pop("ADVISOR_GRANULARITY", AdvisorGranularity.PHASE.value)
        )
        return self._builder.build(
            values,
            env_name=env,
            llm_max_retries=llm_max_retries,
            llm_max_turns=llm_max_turns,
            advisor_max_blocks=advisor_max_blocks,
            review_max_conversations=review_max_conversations,
            review_max_tries=review_max_tries,
            llm_call_budget=llm_call_budget,
            advisor_granularity=advisor_granularity,
        )

def load_config() -> Config:
    return ConfigLoader().load()
