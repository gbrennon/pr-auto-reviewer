"""ConfigReloaderPort — protocol for polling daemon configuration reload checks."""

from __future__ import annotations

from typing import Protocol

from pr_auto_reviewer.infrastructure.config.config_dataclass import Config


class ConfigReloaderPort(Protocol):
    """Checks whether the configuration source changed and returns reloaded config."""

    def check_for_reload(self) -> Config:
        """Read current settings for the next polling loop."""
        ...
