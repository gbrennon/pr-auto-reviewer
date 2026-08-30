"""InteractiveGitCredentialPrompter — asks the user for git credentials."""

from __future__ import annotations

import getpass
import sys

from pr_auto_reviewer.domain.value_objects.git_credentials import GitCredentials


class InteractiveGitCredentialPrompter:
    """Prompts for git credentials interactively on stdin/tty.

    Only prompts when standard input is a TTY, so non-interactive runs
    (cron, systemd, CI) are never blocked by a hanging prompt. When not a TTY
    or when the user provides no secret it returns ``None`` rather than
    raising, so a missing credential does not crash the daemon.
    """

    def __init__(
        self,
        input_fn=input,
        prompt_fn=getpass.getpass,
        isatty_fn=None,
    ) -> None:
        self._input = input_fn
        self._prompt = prompt_fn
        self._isatty = isatty_fn

    def prompt(self, protocol: str, host: str) -> GitCredentials | None:
        """Interactively obtain credentials for *protocol* on *host*.

        Prints the protocol and host explicitly before asking for the username
        and secret so the user knows exactly what is being authenticated.
        Returns ``None`` when the session is non-interactive or no secret is
        supplied.
        """
        if self._isatty is not None and not self._isatty():
            return None
        if self._isatty is None and not sys.stdin.isatty():
            return None

        print(f"Authentication required for {host} over {protocol}.")
        username = self._input(f"Username for {host} ({protocol}): ").strip()
        secret = self._prompt(f"Password/token for {username} ({protocol}): ")
        print(f"Authenticating to {host} as {username!r} via {protocol}.")

        if not username or not secret:
            return None
        return GitCredentials(protocol=protocol, username=username, secret=secret)
