"""AppPaths — resolves the XDG base directories holding this application's files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar


class AppPaths:
    """Resolve per-application directories under the XDG base directories.

    Every accessor honors its ``XDG_*`` environment variable when set to a
    non-empty value and otherwise resolves the platform default home,
    always joined with the application name:

    - :meth:`config_dir` — user configuration (``$XDG_CONFIG_HOME``)
    - :meth:`state_dir` — review state and transcripts (``$XDG_STATE_HOME``)
    - :meth:`cache_dir` — derived caches such as verified tokens (``$XDG_CACHE_HOME``)

    Fallback resolution passes the application-name-bearing path through
    ``os.path.expanduser`` so test suites may redirect every artifact
    root by intercepting that single function.
    """

    _APP_NAME: ClassVar[str] = "pr-auto-reviewer"

    @classmethod
    def config_dir(cls) -> Path:
        """Return the directory holding the user configuration file."""
        return cls._xdg("XDG_CONFIG_HOME", ".config")

    @classmethod
    def state_dir(cls) -> Path:
        """Return the directory holding review state and transcripts."""
        return cls._xdg("XDG_STATE_HOME", ".local/state")

    @classmethod
    def cache_dir(cls) -> Path:
        """Return the directory holding derived caches."""
        return cls._xdg("XDG_CACHE_HOME", ".cache")

    @classmethod
    def _xdg(cls, env_var: str, fallback: str) -> Path:
        """Resolve one XDG base directory from *env_var* or *fallback*."""
        override = os.environ.get(env_var)
        if override:
            return Path(override) / cls._APP_NAME
        return Path(
            os.path.expanduser(os.path.join("~", fallback, cls._APP_NAME))
        )
