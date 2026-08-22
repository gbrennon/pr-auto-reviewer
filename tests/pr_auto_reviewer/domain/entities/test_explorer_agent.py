"""Tests for the ExplorerAgent sub-agent."""

from typing import Any, cast

import pytest

from pr_auto_reviewer.domain.entities.explorer_agent import ExplorerAgent


class TestExplorerAgent:
    """Tests for the explorer sub-agent."""

    def test_role(self) -> None:
        assert ExplorerAgent().role == "explorer"

    def test_responsibility(self) -> None:
        assert ExplorerAgent().responsibility == (
            "prepare local clone to other sub agents can just review "
            "diff by installing and setting it up"
        )

    def test_behavior(self) -> None:
        assert ExplorerAgent().behavior == (
            "install application dependencies based in instructions "
            "(like md files) and setup pr to next sub agent review"
        )

    def test_immutability(self) -> None:
        with pytest.raises(AttributeError):
            cast(Any, ExplorerAgent()).behavior = "changed"