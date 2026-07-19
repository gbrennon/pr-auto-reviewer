"""GitHub auth headers — Bearer token + Accept header for write checks."""

from __future__ import annotations


class GitHubAuthHeaders:
    def auth_header(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def write_access_extra_headers(self) -> dict[str, str]:
        return {"Accept": "application/vnd.github+json"}
