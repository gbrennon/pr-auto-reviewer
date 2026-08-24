"""Fake NotifierPort that records notifications for assertions."""

from pr_auto_reviewer.application.ports.outbound.notifier_port import NotifierPort


class FakeNotifier(NotifierPort):
    """Records every notification so tests can assert observable effects."""

    def __init__(self) -> None:
        self.successes: list[tuple[str, str]] = []
        self.errors: list[tuple[str, Exception]] = []

    def notify_success(self, context: str, detail: str = "") -> None:
        self.successes.append((context, detail))

    def notify_error(self, context: str, error: Exception) -> None:
        self.errors.append((context, error))
