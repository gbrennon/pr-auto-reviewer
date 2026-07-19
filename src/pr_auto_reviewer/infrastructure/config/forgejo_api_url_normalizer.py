"""Normalizes Forgejo API base URLs."""

from __future__ import annotations


class ForgejoApiUrlNormalizer:
    """Ensures a Forgejo host URL ends with ``/api/v1``."""

    @classmethod
    def normalize(cls, url: str) -> str:
        if url.endswith("/api/v1"):
            return url
        return url.rstrip("/") + "/api/v1"
