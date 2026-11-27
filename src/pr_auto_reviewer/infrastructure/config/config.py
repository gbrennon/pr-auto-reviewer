"""ConfigLoader — loads application configuration with correct environment precedence."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dotenv import dotenv_values

from pr_auto_reviewer.infrastructure.config.advisor_granularity import (
    AdvisorGranularity,
)
from pr_auto_reviewer.infrastructure.config.auth_configuration import (
    AuthConfigParser,
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
from pr_auto_reviewer.infrastructure.config.settings_key_mapping import (
    flatten_settings,
)
from pr_auto_reviewer.infrastructure.config.toml_settings_store import (
    TomlSettingsStore,
)
from pr_auto_reviewer.infrastructure.persistence.sqlite_persistence import (
    LEGACY_STORAGE_ENCRYPTION_KEY,
    EncryptedSqliteSecretStore,
    SqliteStorageKeyMigrator,
)

logger = logging.getLogger(__name__)

_COMMAND_LINE_KEYS = {
    "PLATFORM_MODE", "FORGEJO_MODE", "PLATFORM_TRANSPORT",
    "REVIEW_OUTPUT", "DEBUG", "PROMPT_MODE",
    "LLM_HOST", "LLM_MODEL",
    "POLL_INTERVAL", "MAX_PROMPT_TOKENS",
    "MAX_FILE_CHARS", "MAX_FILES", "MAX_STRUCTURE_LINES",
    "USE_COMPACT_TEMPLATE", "USE_STRICT_FRAGMENT_SELECTION",
    "LLM_TIMEOUT",
    "LLM_MAX_RETRIES", "LLM_MAX_TURNS", "LLM_CALL_BUDGET", "MAX_CONTEXT_TOKENS",
    "ADVISOR_GRANULARITY",
    "GITHUB_API_URL", "GITHUB_REVIEW_MODE",
    "FORGEJO_API_URL", "FORGEJO_HOST",
    "GITHUB_MANAGER_TOKEN", "GITHUB_REVIEWER_TOKEN",
    "GITHUB_REVIEWER_USERNAME", "FORGEJO_MANAGER_TOKEN",
    "FORGEJO_REVIEWER_TOKEN", "FORGEJO_REVIEWER_USERNAME",
    "PR_AUTO_REVIEWER_ENCRYPTION_KEY",
    "RUN_ONCE", "REPOS_FILTER", "REPOS_ALLOW_LIST", "FORCE_PR",
    "CLONE_PROTOCOL", "REVIEW_MAX_RETRIES", "REVIEW_MAX_TRIES",
    "REMOTE_FAILURE_THRESHOLD", "REMOTE_FAILURE_INTERVAL_SECONDS",
    "REMOTE_FAILURE_INTERVAL_INCREMENT_SECONDS",
    "REMOTE_FAILURE_QUARANTINE_SECONDS",
}

_TOKEN_OVERRIDE_PREFIXES = ("GITHUB_TOKEN_", "FORGEJO_TOKEN_")

_CONFIG_KEYS = list(_COMMAND_LINE_KEYS) + [
    "GITHUB_API_URL",
    "GITHUB_MANAGER_TOKEN", "GITHUB_REVIEWER_TOKEN",
    "GITHUB_REVIEWER_USERNAME", "GITHUB_REVIEW_MODE",
    "FORGEJO_API_URL", "FORGEJO_HOST",
    "FORGEJO_MANAGER_TOKEN", "FORGEJO_REVIEWER_TOKEN",
    "FORGEJO_REVIEWER_USERNAME",
]

_SECRET_CONFIG_KEYS = frozenset({
    "GITHUB_MANAGER_TOKEN", "GITHUB_REVIEWER_TOKEN",
    "GITHUB_REVIEWER_USERNAME", "FORGEJO_MANAGER_TOKEN",
    "FORGEJO_REVIEWER_TOKEN", "FORGEJO_REVIEWER_USERNAME",
})

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
        runtime_keys = _COMMAND_LINE_KEYS | {
            key for key in os.environ
            if key.startswith(_TOKEN_OVERRIDE_PREFIXES)
        }
        for key in runtime_keys:
            if key in os.environ:
                values[key] = os.environ[key]

    def _load_toml_document(self) -> dict[str, object]:
        settings = TomlSettingsStore(AppPaths.config_dir() / "settings.toml")
        return settings._document()

    def _load_toml_values(self, document: dict[str, object]) -> dict[str, str]:
        return {
            name: json.dumps(value) if isinstance(value, list) else str(value)
            for name, value in flatten_settings(document).items()
            if not TomlSettingsStore.is_secret_name(name)
        }

    def _load_encrypted_secret_values(
        self, configured_values: dict[str, str],
    ) -> dict[str, str]:
        key = os.environ.get("PR_AUTO_REVIEWER_ENCRYPTION_KEY", "").strip()
        if not key:
            key = configured_values.get(
                "PR_AUTO_REVIEWER_ENCRYPTION_KEY", "",
            ).strip()
        if not key:
            return {}
        SqliteStorageKeyMigrator(
            AppPaths.state_dir() / "secrets.sqlite3",
            key,
            LEGACY_STORAGE_ENCRYPTION_KEY,
        ).migrate()
        store = EncryptedSqliteSecretStore(
            AppPaths.state_dir() / "secrets.sqlite3", key,
        )
        return {
            name: value
            for name in store.names()
            if self._is_supported_secret_name(name)
            and (value := store.get(name)) is not None
        }

    @staticmethod
    def _is_supported_secret_name(name: str) -> bool:
        return name in _SECRET_CONFIG_KEYS or name.startswith(
            _TOKEN_OVERRIDE_PREFIXES
        )

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

    @staticmethod
    def _load_remote_failure_settings(
        values: dict[str, str],
    ) -> tuple[int, float, float, float]:
        return (
            int(values.pop("REMOTE_FAILURE_THRESHOLD", "3")),
            float(values.pop("REMOTE_FAILURE_INTERVAL_SECONDS", "60")),
            float(
                values.pop(
                    "REMOTE_FAILURE_INTERVAL_INCREMENT_SECONDS", "60",
                )
            ),
            float(values.pop("REMOTE_FAILURE_QUARANTINE_SECONDS", "3600")),
        )

    def _load_production(self, config_path: str) -> Config:
        toml_document = self._load_toml_document()
        values = self._load_toml_values(toml_document)
        auth_configuration = AuthConfigParser().parse(toml_document)
        configured_values: dict[str, str] = {}
        if Path(config_path).exists():
            configured_values = self._load_values(Path(config_path))
            logger.info("Loading production config from %s", config_path)
        else:
            logger.warning(
                "Production config not found at %s; using defaults.",
                config_path,
            )
        values.update(configured_values)
        values.update(self._load_encrypted_secret_values(configured_values))
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
        (
            remote_failure_threshold,
            remote_failure_interval_seconds,
            remote_failure_interval_increment_seconds,
            remote_failure_quarantine_seconds,
        ) = self._load_remote_failure_settings(values)
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
            remote_failure_threshold=remote_failure_threshold,
            remote_failure_interval_seconds=remote_failure_interval_seconds,
            remote_failure_interval_increment_seconds=(
                remote_failure_interval_increment_seconds
            ),
            remote_failure_quarantine_seconds=remote_failure_quarantine_seconds,
            auth_configuration=auth_configuration,
        )

    def _load_development(
        self, user_config_path: str, repo_env_path: Path, env: str
    ) -> Config:
        toml_document = self._load_toml_document()
        values: dict[str, str] = self._load_toml_values(toml_document)
        auth_configuration = AuthConfigParser().parse(toml_document)
        configured_values: dict[str, str] = {}

        user_cfg = Path(user_config_path)
        if user_cfg.exists():
            logger.info(
                "Loading dev user config from %s", user_config_path
            )
            configured_values.update(self._load_values(user_cfg))

        if repo_env_path.exists():
            logger.info("Loading dev .env from %s", repo_env_path)
            configured_values.update(self._load_values(repo_env_path))

        values.update(configured_values)
        values.update(self._load_encrypted_secret_values(configured_values))
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
        (
            remote_failure_threshold,
            remote_failure_interval_seconds,
            remote_failure_interval_increment_seconds,
            remote_failure_quarantine_seconds,
        ) = self._load_remote_failure_settings(values)
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
            remote_failure_threshold=remote_failure_threshold,
            remote_failure_interval_seconds=remote_failure_interval_seconds,
            remote_failure_interval_increment_seconds=(
                remote_failure_interval_increment_seconds
            ),
            remote_failure_quarantine_seconds=remote_failure_quarantine_seconds,
            auth_configuration=auth_configuration,
        )

def load_config() -> Config:
    return ConfigLoader().load()
