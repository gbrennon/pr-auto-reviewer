"""Unit tests for PromptRenderer protocol."""

import inspect
from typing import Protocol

import pytest

from pr_auto_reviewer.application.ports.outbound.prompt_renderer_port import (
    PromptRendererPort as PromptRenderer,
)


class TestPromptRenderer:
    """Tests for PromptRenderer protocol interface."""

    def test_is_protocol(self) -> None:
        """PromptRenderer should be a Protocol (structural subtyping)."""
        assert issubclass(PromptRenderer, Protocol)

    def test_has_render_method(self) -> None:
        """PromptRenderer must define a render method."""
        sig = inspect.signature(PromptRenderer.render)
        params = list(sig.parameters.keys())

        assert "template" in params
        assert "variables" in params
        assert sig.return_annotation == "str"

    @pytest.mark.parametrize(
        "method_name,expected_params",
        [
            ("render", ["self", "template", "variables"]),
        ],
    )
    def test_method_signatures(
        self, method_name: str, expected_params: list[str]
    ) -> None:
        """Protocol methods should have expected parameter lists."""
        method = getattr(PromptRenderer, method_name)

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert params == expected_params
