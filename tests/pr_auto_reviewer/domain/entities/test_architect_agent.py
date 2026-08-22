"""Tests for the ArchitectAgent sub-agent."""

from typing import Any, cast

import pytest

from pr_auto_reviewer.domain.entities.architect_agent import ArchitectAgent


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