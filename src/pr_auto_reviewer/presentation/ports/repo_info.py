"""RepoInfo — repository identity with last-push timestamp."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepoInfo:
    """A repository's identity and last-push timestamp.

    ``pushed_at`` is an ISO-8601 string from the platform's ``/user/repos``
    endpoint, or ``None`` when the field is missing.
    """

    full_name: str
    pushed_at: str | None = None
