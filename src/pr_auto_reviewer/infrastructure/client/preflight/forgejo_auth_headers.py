"""Forgejo/Codeberg auth headers — ``token`` prefix, no extra headers."""

from __future__ import annotations


class ForgejoAuthHeaders:
    def auth_header(self, token: str) -> dict[str, str]:
        return {"Authorization": f"token {token}"}

    def write_access_extra_headers(self) -> dict[str, str]:
        return {}