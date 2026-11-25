"""Canonical paths for grouped TOML application settings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class SettingKey:
    """Describe one persisted setting and its legacy environment alias."""

    legacy_name: str
    path: tuple[str, ...]

    @property
    def canonical_name(self) -> str:
        """Return the dotted TOML/CLI name for this setting."""
        return ".".join(self.path)


_SETTING_DEFINITIONS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("PLATFORM_MODE", ("platform", "mode"), ("FORGEJO_MODE",)),
    ("PLATFORM_TRANSPORT", ("platform", "transport"), ()),
    ("GITHUB_API_URL", ("platform", "github", "api_url"), ()),
    ("GITHUB_REVIEW_MODE", ("platform", "github", "review_mode"), ()),
    ("FORGEJO_API_URL", ("platform", "forgejo", "api_url"), ()),
    ("FORGEJO_HOST", ("platform", "forgejo", "host"), ()),
    ("LLM_HOST", ("llm", "host"), ()),
    ("LLM_MODEL", ("llm", "model"), ()),
    ("LLM_TIMEOUT", ("llm", "timeout"), ()),
    ("MAX_CONTEXT_TOKENS", ("llm", "context_tokens"), ()),
    ("LLM_MAX_RETRIES", ("llm", "max_retries"), ()),
    ("LLM_MAX_TURNS", ("llm", "max_turns"), ()),
    ("LLM_CALL_BUDGET", ("llm", "call_budget"), ()),
    ("POLL_INTERVAL", ("daemon", "poll_interval"), ()),
    ("RUN_ONCE", ("daemon", "run_once"), ()),
    ("DEBUG", ("daemon", "debug"), ()),
    ("REVIEW_MAX_CONVERSATIONS", ("review", "max_conversations"), ()),
    ("REVIEW_MAX_RETRIES", ("review", "max_retries"), ()),
    ("REVIEW_MAX_TRIES", ("review", "max_tries"), ()),
    ("ADVISOR_MAX_BLOCKS", ("advisor", "max_blocks"), ()),
    ("ADVISOR_GRANULARITY", ("advisor", "granularity"), ()),
    ("REVIEW_OUTPUT", ("output", "mode"), ()),
    ("PROMPT_MODE", ("prompt", "mode"), ()),
    ("MAX_PROMPT_TOKENS", ("prompt", "max_tokens"), ()),
    ("MAX_FILE_CHARS", ("prompt", "max_file_chars"), ()),
    ("MAX_FILES", ("prompt", "max_files"), ()),
    ("MAX_STRUCTURE_LINES", ("prompt", "max_structure_lines"), ()),
    ("USE_COMPACT_TEMPLATE", ("prompt", "compact_template"), ()),
    (
        "USE_STRICT_FRAGMENT_SELECTION",
        ("prompt", "strict_fragment_selection"),
        (),
    ),
    ("REPOS_FILTER", ("repositories", "filter"), ()),
    ("REPOS_ALLOW_LIST", ("repositories", "allow_list"), ()),
    ("FORCE_PR", ("repositories", "force_pr"), ()),
    ("CLONE_PROTOCOL", ("repositories", "clone_protocol"), ()),
    (
        "LOCAL_CLONE_BASE_DIR",
        ("repositories", "local_clone_base_dir"),
        (),
    ),
    ("REMOTE_FAILURE_THRESHOLD", ("resilience", "failure_threshold"), ()),
    (
        "REMOTE_FAILURE_INTERVAL_SECONDS",
        ("resilience", "interval_seconds"),
        (),
    ),
    (
        "REMOTE_FAILURE_INTERVAL_INCREMENT_SECONDS",
        ("resilience", "interval_increment_seconds"),
        (),
    ),
    (
        "REMOTE_FAILURE_QUARANTINE_SECONDS",
        ("resilience", "quarantine_seconds"),
        (),
    ),
    ("REQUESTS_CA_BUNDLE", ("network", "ca_bundle"), ("CA_BUNDLE",)),
    ("TUI_NAVIGATION_MODE", ("tui", "navigation_mode"), ()),
)

SETTING_KEYS: Final[tuple[SettingKey, ...]] = tuple(
    SettingKey(legacy_name, path) for legacy_name, path, _aliases in _SETTING_DEFINITIONS
)

_BY_ALIAS: Final[dict[str, SettingKey]] = {}
for _legacy_name, _path, _aliases in _SETTING_DEFINITIONS:
    _key = SettingKey(_legacy_name, _path)
    for _alias in (_legacy_name, *_aliases):
        _BY_ALIAS[_alias.casefold()] = _key
    _BY_ALIAS[_key.canonical_name] = _key

_BY_PATH: Final[dict[tuple[str, ...], SettingKey]] = {
    key.path: key for key in SETTING_KEYS
}
_MISSING = object()


def setting_key(name: str) -> SettingKey | None:
    """Resolve a canonical dotted or legacy environment setting name."""
    cleaned = name.strip()
    if not cleaned:
        return None
    direct = _BY_ALIAS.get(cleaned.casefold())
    if direct is not None:
        return direct
    path = tuple(part.strip().casefold() for part in cleaned.split("."))
    return _BY_PATH.get(path)


def canonical_name(name: str) -> str:
    """Return the canonical dotted name when known, otherwise ``name``."""
    key = setting_key(name)
    return key.canonical_name if key is not None else name


def legacy_name(name: str) -> str:
    """Return the legacy environment name when known, otherwise ``name``."""
    key = setting_key(name)
    return key.legacy_name if key is not None else name


def _nested_value(document: Mapping[str, object], path: tuple[str, ...]) -> object:
    value: object = document
    for part in path:
        if not isinstance(value, Mapping) or part not in value:
            return _MISSING
        value = value[part]
    return value


def flatten_settings(document: Mapping[str, object]) -> dict[str, object]:
    """Flatten grouped and legacy settings to legacy environment names.

    Grouped values take precedence over a duplicate flat-root value. Structured
    authentication and repository assignment tables are intentionally omitted.
    """
    values: dict[str, object] = {}
    for name, value in document.items():
        if isinstance(value, Mapping):
            continue
        key = setting_key(str(name))
        values[key.legacy_name if key else str(name).upper()] = value
    for key in SETTING_KEYS:
        value = _nested_value(document, key.path)
        if value is not _MISSING and not isinstance(value, Mapping):
            values[key.legacy_name] = value
    return values


def canonical_settings(document: Mapping[str, object]) -> dict[str, object]:
    """Flatten settings for display using canonical dotted names."""
    values: dict[str, object] = {}
    for name, value in document.items():
        if isinstance(value, Mapping):
            continue
        values[canonical_name(str(name))] = value
    for key in SETTING_KEYS:
        value = _nested_value(document, key.path)
        if value is not _MISSING and not isinstance(value, Mapping):
            values[key.canonical_name] = value
    return values


def aliases_for(key: SettingKey) -> tuple[str, ...]:
    """Return legacy root aliases that should be removed on canonical writes."""
    for legacy_name, _path, aliases in _SETTING_DEFINITIONS:
        if legacy_name == key.legacy_name:
            return (legacy_name, *aliases)
    return (key.legacy_name,)
