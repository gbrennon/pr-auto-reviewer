"""Tests for LinuxNotifier using injected fake callable."""

import pytest

from pr_auto_reviewer.infrastructure.notifier.linux_notifier import LinuxNotifier


@pytest.fixture
def fake_run_command():
    """Fixture that records calls to a fake subprocess.run."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

    fake_run.calls = calls
    return fake_run


class TestLinuxNotifier:
    def test_notify_success_calls_notify_send(self, fake_run_command):
        notifier = LinuxNotifier(run_command=fake_run_command)
        notifier.notify_success("Review complete", "PR #42 in my/repo")
        assert len(fake_run_command.calls) == 1
        assert fake_run_command.calls[0] == [
            "notify-send",
            "pr-auto-reviewer: Review complete",
            "PR #42 in my/repo",
        ]

    def test_notify_error_calls_notify_send_with_context(self, fake_run_command):
        notifier = LinuxNotifier(run_command=fake_run_command)
        notifier.notify_error("step1", ValueError("bad"))
        assert len(fake_run_command.calls) == 1
        assert fake_run_command.calls[0][0] == "notify-send"
        assert "ERROR" in fake_run_command.calls[0][1]
        assert "step1: bad" in fake_run_command.calls[0][2]
