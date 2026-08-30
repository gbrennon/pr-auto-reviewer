"""GitCredentialProviderPort — protocol for obtaining git authentication."""

from typing import Protocol

from pr_auto_reviewer.domain.value_objects.git_credentials import GitCredentials


class GitCredentialProviderPort(Protocol):
    """Provides authentication data for cloning and fetching from a git host.

    Implementations return the credentials to use for the given protocol and
    host, or ``None`` when no credentials are available (for example when the
    user declines to authenticate or the session is non-interactive).
    """

    def prompt(self, protocol: str, host: str) -> GitCredentials | None:
        """Obtain credentials for *protocol* against *host*.

        Args:
            protocol: The git transport in use, ``ssh`` or ``https``.
            host: The git host (e.g. ``github.com`` or ``codeberg.org``).

        Returns:
            The credentials to use, or ``None`` if none are available.
        """
        ...
