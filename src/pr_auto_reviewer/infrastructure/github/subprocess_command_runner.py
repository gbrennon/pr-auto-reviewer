"""Subprocess implementation for GitHub CLI commands."""

from __future__ import annotations

import subprocess


class SubprocessCommandRunner:
    """Run commands through the local process environment."""

    def run(self, command: list[str], input_text: str | None = None) -> str:
        """Execute a command and raise when the CLI reports failure."""
        result = subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "GitHub CLI command failed")
        return result.stdout
