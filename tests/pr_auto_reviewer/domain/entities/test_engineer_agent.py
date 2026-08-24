"""Tests for the EngineerAgent sub-agent."""

from typing import Any, cast

import pytest

from pr_auto_reviewer.domain.entities.engineer_agent import EngineerAgent


class TestEngineerAgent:
    """Tests for the engineer sub-agent."""

    def test_role(self) -> None:
        assert EngineerAgent().role == "engineer"

    def test_responsibility(self) -> None:
        assert EngineerAgent().responsibility == (
            "exercise the changes searching for bugs and improvements; "
            "analyze code quality, test coverage, principles; and "
            "suggest good practices that match the project's existing "
            "approach"
        )

    def test_behavior(self) -> None:
        assert EngineerAgent().behavior == (
            "think about what the project is doing and which approach "
            "was already introduced; never suggest something extremely "
            "new; prefer clean, decoupled code"
        )

    def test_immutability(self) -> None:
        with pytest.raises(AttributeError):
            cast(Any, EngineerAgent()).responsibility = "changed"