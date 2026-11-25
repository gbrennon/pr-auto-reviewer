"""Command execution port for Forgejo CLI adapters."""

from __future__ import annotations

from typing import Protocol


class CommandRunner(Protocol):
    """Run an authenticated command and return stdout."""

    def run(self, command: list[str], input_text: str | None = None) -> str:
        """Execute a command."""
        ...
