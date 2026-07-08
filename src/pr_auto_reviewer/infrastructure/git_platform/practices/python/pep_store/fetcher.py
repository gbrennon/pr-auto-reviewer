from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .types import PepEntry

logger = logging.getLogger(__name__)

def _default_http_get(url: str) -> dict[str, Any]:
    import requests

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()

class PepFetcher:
    def __init__(
        self,
        url: str,
        http_get: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self._url = url
        self._http_get = http_get or _default_http_get
        self._cache: list[PepEntry] | None = None

    def fetch(self) -> list[PepEntry]:
        if self._cache is not None:
            return self._cache
        logger.info("Fetching PEPs from %s", self._url)
        try:
            raw = self._http_get(self._url)
        except Exception:
            logger.warning("Failed to fetch PEPs", exc_info=True)
            self._cache = []
            return self._cache
        self._cache = [
            entry
            for entry in raw.values()
            if isinstance(entry, dict) and "number" in entry
        ]
        logger.info("Fetched %d PEPs", len(self._cache))
        return self._cache
