"""Fake ``PromptRendererPort`` implementation for test use.

Records ``render`` calls and supports configurable return values
and failure injection, so tests never need ``unittest.mock.Mock``.
"""

from __future__ import annotations


class FakePromptRenderer:
    """Fake that implements ``PromptRendererPort``.

    Stores every ``(template, variables)`` pair passed to ``render()``
    in ``render_calls`` and returns a pre-configured value (or raises
    a pre-configured exception).
    """

    def __init__(
        self,
        return_value: str = "",
        raise_on_render: Exception | None = None,
    ) -> None:
        self.return_value = return_value
        self.raise_on_render = raise_on_render
        self.render_calls: list[tuple[str, dict[str, str]]] = []

    @property
    def called(self) -> bool:
        """``True`` when ``render()`` was called at least once."""
        return len(self.render_calls) > 0

    @property
    def call_count(self) -> int:
        """How many times ``render()`` was called."""
        return len(self.render_calls)

    @property
    def call_args(self) -> tuple[tuple[str, dict[str, str]]] | None:
        """The ``(template, variables)`` from the most recent call."""
        if not self.render_calls:
            return None
        return (self.render_calls[-1],)

    def render(self, template: str, variables: dict[str, str]) -> str:
        self.render_calls.append((template, variables))
        if self.raise_on_render is not None:
            raise self.raise_on_render
        return self.return_value