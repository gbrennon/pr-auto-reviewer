"""CloneUrlResolverPort — protocol for resolving clone URL templates."""

from typing import Protocol


class CloneUrlResolverPort(Protocol):
    """Resolves a clone URL for a given platform and repository.

    Implementations own the platform mode (HTTPS vs SSH) at construction
    time and expose a single ``resolve`` method that takes only the
    repository string.  The port is injected into ``LocalChangesetFetcher``
    so that the fetcher never needs to know about URL construction.
    """

    def resolve(self, repository: str) -> str:
        """Build the clone URL for *repository*.

        Args:
            repository: The ``owner/name`` string for the remote repo.

        Returns:
            A full clone URL (e.g. ``https://github.com/org/repo.git``
            or ``git@github.com:org/repo.git``).
        """
        ...
