"""Unit tests for FragmentRepository protocol."""

import inspect
from typing import Protocol

import pytest

from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment
from pr_auto_reviewer.application.ports.outbound.fragment_repository_port import (
    FragmentRepositoryPort as FragmentRepository,
)


class TestFragmentRepository:
    """Tests for FragmentRepository protocol interface."""

    def test_is_protocol(self) -> None:
        """FragmentRepository should be a Protocol (structural subtyping)."""
        assert issubclass(FragmentRepository, Protocol)

    def test_has_find_by_language_method(self) -> None:
        """FragmentRepository must define find_by_language method."""
        sig = inspect.signature(FragmentRepository.find_by_language)
        params = list(sig.parameters.keys())

        assert "language" in params
        assert sig.return_annotation == "list[PromptFragment]"

    def test_has_find_universal_method(self) -> None:
        """FragmentRepository must define find_universal method."""
        sig = inspect.signature(FragmentRepository.find_universal)
        params = list(sig.parameters.keys())

        # Only 'self' (no extra params)
        assert params == ["self"]
        assert sig.return_annotation == "list[PromptFragment]"

    def test_has_find_by_id_method(self) -> None:
        """FragmentRepository must define find_by_id method."""
        sig = inspect.signature(FragmentRepository.find_by_id)
        params = list(sig.parameters.keys())

        assert "fragment_id" in params

    @pytest.mark.parametrize(
        "method_name,expected_params",
        [
            ("find_by_language", ["self", "language"]),
            ("find_universal", ["self"]),
            ("find_by_id", ["self", "fragment_id"]),
        ],
    )
    def test_method_signatures(
        self, method_name: str, expected_params: list[str]
    ) -> None:
        """Protocol methods should have expected parameter lists."""
        method = getattr(FragmentRepository, method_name)

        # Skip abstract method wrappers
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert params == expected_params
