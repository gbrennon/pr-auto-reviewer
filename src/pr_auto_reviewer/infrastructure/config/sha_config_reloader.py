"""ShaConfigReloader — reloads configuration only when file hash changes."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from pr_auto_reviewer.infrastructure.config.config_dataclass import Config
from pr_auto_reviewer.presentation.ports.config_reloader_port import (
    ConfigReloaderPort,
)

logger = logging.getLogger(__name__)


class ShaConfigReloader(ConfigReloaderPort):
    """Tracks configuration file SHA256 and delegates reload on modification."""

    def __init__(self, config_path: Path, config_loader: Any) -> None:
        self._config_path = config_path
        self._config_loader = config_loader
        self._state: dict[str, str] = {
            "hash": self._compute_hash(config_path),
        }

    @staticmethod
    def _compute_hash(path: Path) -> str:
        if not path.is_file():
            return ""
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return ""

    def check_for_reload(self) -> Config:
        """Read current configuration settings for the next daemon loop."""
        new_hash = self._compute_hash(self._config_path)
        state_dict = self._state
        current_hash = state_dict.get("hash", "")
        if new_hash != current_hash:
            state_dict["hash"] = new_hash
            logger.info(
                "Config file change detected (%s -> %s), reloading configuration",
                current_hash[:8] or "(empty)",
                new_hash[:8],
            )
        return self._config_loader.load()
