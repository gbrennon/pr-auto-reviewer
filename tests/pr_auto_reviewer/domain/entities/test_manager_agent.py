"""Tests for the ManagerAgent sub-agent."""

from typing import Any, cast

import pytest

from pr_auto_reviewer.domain.entities.manager_agent import ManagerAgent


class TestManagerAgent:
    """Tests for the manager sub-agent."""

    def test_role(self) -> None:
        assert ManagerAgent().role == "manager"

    def test_responsibility(self) -> None:
        assert ManagerAgent().responsibility == (
            "plan and separate tasks, assign them to sub agents like a "
            "software development team, and explain requirements and "
            "acceptance criteria to the advisor"
        )

    def test_behavior(self) -> None:
        assert ManagerAgent().behavior == (
            "assign refined tasks to sub agents, act at the start of "
            "the review and between phases, and own the technical "
            "context so sub agents never review the PR poorly"
        )

    def test_immutability(self) -> None:
        with pytest.raises(AttributeError):
            cast(Any, ManagerAgent()).behavior = "changed"