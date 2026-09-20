"""End-to-end tests for CLI entry point (service commands)."""

from unittest.mock import call, patch

import pytest

from pr_auto_reviewer.cli import SERVICE_NAME, main


class TestCliServiceCommands:
    """E2E tests for pr-auto-reviewer service subcommands."""

    @pytest.mark.parametrize(
        "command,expected_action",
        [
            ("start", "start"),
            ("stop", "stop"),
            ("status", "status"),
            ("restart", "restart"),
        ],
    )
    def test_systemctl_command_dispatches_correct_action(
        self, command: str, expected_action: str
    ) -> None:
        with (
            patch("sys.argv", ["pr-auto-reviewer", command]),
            patch.dict("os.environ", {"SSH_AUTH_SOCK": "/run/user/1000/agent.sock"}),
            patch("subprocess.run") as mock_run,
        ):
            main()

        expected_calls = []
        if command in {"start", "restart"}:
            expected_calls.append(
                call(
                    ["systemctl", "--user", "import-environment", "SSH_AUTH_SOCK"],
                    check=False,
                )
            )
        expected_calls.append(
            call(["systemctl", "--user", expected_action, SERVICE_NAME], check=False)
        )
        assert mock_run.call_args_list == expected_calls

    def test_logs_command_dispatches_journalctl(self) -> None:
        with (
            patch("sys.argv", ["pr-auto-reviewer", "logs"]),
            patch("subprocess.run") as mock_run,
        ):
            main()

        mock_run.assert_called_once_with(
            ["journalctl", "--user", "-u", SERVICE_NAME, "-f"], check=False
        )

    def test_help_flag_shows_service_commands(self) -> None:
        with patch("sys.argv", ["pr-auto-reviewer", "--help"]), pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
