"""Tests for the ReviewerAgent sub-agent."""

from typing import Any, cast

import pytest

from pr_auto_reviewer.domain.entities.reviewer_agent import ReviewerAgent


class TestReviewerAgent:
    """Tests for the reviewer sub-agent."""

    def test_role(self) -> None:
        assert ReviewerAgent().role == "reviewer"

    def test_responsibility(self) -> None:
        assert ReviewerAgent().responsibility == (
            "join review output of sub agents and so the final verdict "
            "and output"
        )

    def test_behavior(self) -> None:
        assert ReviewerAgent().behavior == (
            "read output of other sub agents and prepare the final "
            "turn verdict"
        )

    def test_immutability(self) -> None:
        with pytest.raises(AttributeError):
            cast(Any, ReviewerAgent()).role = "changed"