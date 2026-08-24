"""Tests for the SubAgent abstract contract."""

import pytest

from pr_auto_reviewer.domain.entities.advisor_agent import AdvisorAgent
from pr_auto_reviewer.domain.entities.sub_agent import SubAgent


class TestSubAgent:
    """Tests for the abstract SubAgent contract."""

    def test_cannot_instantiate_abstract_sub_agent(self) -> None:
        with pytest.raises(TypeError):
            type("IncompleteSubAgent", (SubAgent,), {})()

    def test_describe_combines_role_responsibility_and_behavior(self) -> None:
        agent = AdvisorAgent()
        assert agent.describe() == (
            "advisor: prevent other sub agents from being side-tracked "
            "and keep every phase focused on its assigned task — watch "
            "sub agents actions, grade them on focus, interrupt drift "
            "with feedback, and resend the original prompt when a sub "
            "agent goes off-task"
        )