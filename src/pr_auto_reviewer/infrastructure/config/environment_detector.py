"""Detects whether the application is running in production or development."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.config.repo_root import RepoRoot


class EnvironmentDetector:
    """Determines the runtime environment.

    Args:
        environ: Environment dict to read ``ENV`` from.  Defaults to
            ``os.environ``.
    """

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        import os
        self._environ = environ if environ is not None else os.environ

    def detect(self) -> str:
        env = self._environ.get("ENV", "").strip()
        if env:
            return env
        return "production" if self._is_installed() else "development"

    def is_installed(self) -> bool:
        return self._is_installed()

    @classmethod
    def _is_installed(cls) -> bool:
        return not (RepoRoot.path() / ".env").exists()