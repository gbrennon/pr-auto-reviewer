"""Tests for SystemNotifier using monkeypatched subprocess."""

from pr_auto_reviewer.infrastructure.system_notifier import SystemNotifier


class TestSystemNotifier:
    def test_notify_calls_subprocess(self, monkeypatch):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)

        monkeypatch.setattr("subprocess.run", fake_run)
        notifier = SystemNotifier()
        notifier.notify("title", "message body")
        assert len(calls) == 1
        assert calls[0] == ["notify-send", "title", "message body"]

    def test_notify_error_calls_notify_with_context(self, monkeypatch):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)

        monkeypatch.setattr("subprocess.run", fake_run)
        notifier = SystemNotifier()
        notifier.notify_error("step1", ValueError("bad"))
        assert len(calls) == 1
        assert "ERROR" in calls[0][1]

    def test_notify_step_calls_notify_with_header(self, monkeypatch):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)

        monkeypatch.setattr("subprocess.run", fake_run)
        notifier = SystemNotifier()
        notifier.notify_step("Review Complete", "PR #42 done")
        assert len(calls) == 1
        assert "Review Complete" in calls[0][1]
