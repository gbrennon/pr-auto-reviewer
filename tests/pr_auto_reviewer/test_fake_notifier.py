"""Tests for the FakeNotifier test double."""

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from tests.fakes.fake_notifier import FakeNotifier


class TestFakeNotifier:
    def test_notify_success_records_context_and_detail(self):
        notifier = FakeNotifier()

        notifier.notify_success("Review complete", "PR #42 in my/repo")

        assert notifier.successes == [("Review complete", "PR #42 in my/repo")]

    def test_notify_success_records_empty_detail_when_absent(self):
        notifier = FakeNotifier()

        notifier.notify_success("Review complete")

        assert notifier.successes == [("Review complete", "")]

    def test_notify_error_records_context_and_error(self):
        notifier = FakeNotifier()
        error = LlmUnavailableError("ollama down")

        notifier.notify_error("step1", error)

        assert notifier.errors == [("step1", error)]

    def test_multiple_notifications_recorded_in_order(self):
        notifier = FakeNotifier()

        notifier.notify_success("first")
        notifier.notify_error("second", ValueError("bad"))
        notifier.notify_success("third", "detail")

        assert [context for context, _ in notifier.successes] == ["first", "third"]
        assert [context for context, _ in notifier.errors] == ["second"]
