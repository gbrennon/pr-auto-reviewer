"""Tests for PollingDaemonConfig."""

import pytest

from pr_auto_reviewer.presentation.polling_daemon.polling_daemon_config import (
    PollingDaemonConfig,
)

class TestPollingDaemonConfig:
    """Tests for PollingDaemonConfig dataclass."""

    def test_creation(self) -> None:
        """Creates PollingDaemonConfig with all fields."""
        config = PollingDaemonConfig(
            poll_interval_seconds=30,
            repos_filter="owner/",
            run_once=True,
        )

        assert config.poll_interval_seconds == 30
        assert config.repos_filter == "owner/"
        assert config.run_once is True

    def test_default_values(self) -> None:
        """Creates PollingDaemonConfig with default values."""
        config = PollingDaemonConfig(
            poll_interval_seconds=60,
            repos_filter=None,
            run_once=False,
        )

        assert config.poll_interval_seconds == 60
        assert config.repos_filter is None
        assert config.run_once is False

    def test_is_immutable(self) -> None:
        """PollingDaemonConfig is immutable (frozen=True)."""
        config = PollingDaemonConfig(
            poll_interval_seconds=60,
            repos_filter=None,
            run_once=False,
        )

        with pytest.raises(AttributeError):
            config.poll_interval_seconds = 30