"""Tests for the sub-agent domain model."""

from typing import Any, cast

import pytest

from pr_auto_reviewer.domain.agent import (
    AdvisorAgent,
    ArchitectAgent,
    EngineerAgent,
    ExplorerAgent,
    ManagerAgent,
    ReviewerAgent,
    SubAgent,
)


class TestSubAgentContract:
    """Tests for the abstract SubAgent contract."""

    def test_cannot_instantiate_abstract_sub_agent(self) -> None:
        with pytest.raises(TypeError):
            type("IncompleteSubAgent", (SubAgent,), {})()

    def test_describe_combines_role_responsibility_and_behavior(self) -> None:
        agent = AdvisorAgent()
        assert agent.describe() == (
            "advisor: remember focus of tasks interacting with other "
            "sub agents — send message to other sub agents with "
            "feedback, prose and remind agents what they should focus"
        )


class TestAdvisorAgent:
    """Tests for the advisor sub-agent."""

    def test_role(self) -> None:
        assert AdvisorAgent().role == "advisor"

    def test_responsibility(self) -> None:
        assert AdvisorAgent().responsibility == (
            "remember focus of tasks interacting with other sub agents"
        )

    def test_behavior(self) -> None:
        assert AdvisorAgent().behavior == (
            "send message to other sub agents with feedback, prose and "
            "remind agents what they should focus"
        )

    def test_immutability(self) -> None:
        with pytest.raises(AttributeError):
            cast(Any, AdvisorAgent()).role = "changed"

    def test_equality_same_role(self) -> None:
        assert AdvisorAgent() == AdvisorAgent()


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


class TestEngineerAgent:
    """Tests for the engineer sub-agent."""

    def test_role(self) -> None:
        assert EngineerAgent().role == "engineer"

    def test_responsibility(self) -> None:
        assert EngineerAgent().responsibility == (
            "exercise changes searching for bugs by using modifications"
        )

    def test_behavior(self) -> None:
        assert EngineerAgent().behavior == (
            "read code to search for software engineering misses and "
            "it can spawn repl to exercise code"
        )

    def test_immutability(self) -> None:
        with pytest.raises(AttributeError):
            cast(Any, EngineerAgent()).responsibility = "changed"


class TestArchitectAgent:
    """Tests for the architect sub-agent."""

    def test_role(self) -> None:
        assert ArchitectAgent().role == "architect"

    def test_responsibility(self) -> None:
        assert ArchitectAgent().responsibility == (
            "enforce architecture good practices and search for "
            "software architecture misses"
        )

    def test_behavior(self) -> None:
        assert ArchitectAgent().behavior == (
            "read source code to identify misses, violations, "
            "coupling, poor implementations"
        )

    def test_immutability(self) -> None:
        with pytest.raises(AttributeError):
            cast(Any, ArchitectAgent()).behavior = "changed"


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


class TestManagerAgent:
    """Tests for the manager sub-agent."""

    def test_role(self) -> None:
        assert ManagerAgent().role == "manager"

    def test_responsibility(self) -> None:
        assert ManagerAgent().responsibility == (
            "orchestrate sub agents in the review workflow"
        )

    def test_behavior(self) -> None:
        assert ManagerAgent().behavior == (
            "communicate and track other sub agents work"
        )

    def test_immutability(self) -> None:
        with pytest.raises(AttributeError):
            cast(Any, ManagerAgent()).behavior = "changed"
