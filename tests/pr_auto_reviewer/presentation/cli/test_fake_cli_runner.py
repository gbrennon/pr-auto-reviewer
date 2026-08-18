"""Tests for CliRunner using fake."""

from __future__ import annotations

import pytest

from tests.fakes.fake_cli_runner import FakeCliRunner, FakeCliRunnerWithResult


class TestFakeCliRunner:
    """Tests using the fake CliRunner."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake CliRunner can be instantiated."""
        fake = FakeCliRunner()
        assert fake is not None

    def test_fake_run_tracks_call(self) -> None:
        """Fake run tracks the argv call."""
        fake = FakeCliRunner()
        fake.run(["review", "pr/1"])
        assert len(fake.run_calls) == 1
        assert fake.run_calls[0] == ["review", "pr/1"]

    def test_fake_run_with_result(self) -> None:
        """Fake run can return a configurable result."""
        fake = FakeCliRunnerWithResult(review_result=42)
        result = fake.run()
        assert result == 42