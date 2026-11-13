from __future__ import annotations

from pathlib import Path

from pr_auto_reviewer.infrastructure.config.config_dataclass import Config
from pr_auto_reviewer.infrastructure.config.sha_config_reloader import (
    ShaConfigReloader,
)


class ConfigLoaderStubFake:
    """Config loader fake returning incremented configs on each load."""

    def __init__(self, base_interval: int = 60) -> None:
        self.configs: list[Config] = [
            Config(env="production", poll_interval=base_interval + 1),
            Config(env="production", poll_interval=base_interval + 2),
        ]

    def load(self) -> Config:
        return self.configs[0]


class TestShaConfigReloader:
    """Verifies that config is only reloaded when its file hash changes."""

    def test_returns_current_config_when_hash_is_unchanged(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config"
        cfg_file.write_text("POLL_INTERVAL=60\n")
        loader = ConfigLoaderStubFake()
        reloader = ShaConfigReloader(cfg_file, loader)

        reloaded = reloader.check_for_reload()

        assert reloaded is not None
        assert reloaded.poll_interval == 61

    def test_reloads_when_file_content_changes(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config"
        cfg_file.write_text("POLL_INTERVAL=60\n")
        loader = ConfigLoaderStubFake()
        reloader = ShaConfigReloader(cfg_file, loader)

        cfg_file.write_text("POLL_INTERVAL=120\n")
        reloaded = reloader.check_for_reload()

        assert reloaded is not None
        assert reloaded.poll_interval == 61

    def test_subsequent_call_without_change_reads_current_config(
        self, tmp_path: Path,
    ) -> None:
        cfg_file = tmp_path / "config"
        cfg_file.write_text("POLL_INTERVAL=60\n")
        loader = ConfigLoaderStubFake()
        reloader = ShaConfigReloader(cfg_file, loader)
        cfg_file.write_text("POLL_INTERVAL=120\n")
        reloader.check_for_reload()

        reloaded_again = reloader.check_for_reload()

        assert reloaded_again is not None
        assert reloaded_again.poll_interval == 61
