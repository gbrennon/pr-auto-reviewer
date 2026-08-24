"""Tests for the AdvisorAgent sub-agent."""

from typing import Any, cast

import pytest

from pr_auto_reviewer.domain.entities.advisor_agent import AdvisorAgent


class TestAdvisorAgent:
    """Tests for the advisor sub-agent."""

    def test_role(self) -> None:
        assert AdvisorAgent().role == "advisor"

    def test_responsibility(self) -> None:
        assert AdvisorAgent().responsibility == (
            "prevent other sub agents from being side-tracked and "
            "keep every phase focused on its assigned task"
        )

    def test_behavior(self) -> None:
        assert AdvisorAgent().behavior == (
            "watch sub agents actions, grade them on focus, interrupt "
            "drift with feedback, and resend the original prompt when a "
            "sub agent goes off-task"
        )

    def test_immutability(self) -> None:
        with pytest.raises(AttributeError):
            cast(Any, AdvisorAgent()).role = "changed"

    def test_equality_same_role(self) -> None:
        assert AdvisorAgent() == AdvisorAgent()