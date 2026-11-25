from __future__ import annotations

from unittest.mock import patch

from pr_auto_reviewer.presentation.composition_root._shared import status_snapshot
from pr_auto_reviewer.application.dtos.daemon_status_snapshot import (
    DaemonStatusSnapshot,
)

class TestStatusProvider:
    def test_shared_provider_returns_composition_snapshot(self) -> None:
        expected = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=("owner/repo",),
            capabilities=(),
        )

        with patch(
            "pr_auto_reviewer.presentation.composition_root._shared.CompositionRoot"
        ) as root_type:
            root_type.return_value.status_snapshot.return_value = expected

            result = status_snapshot()

        assert result == expected
