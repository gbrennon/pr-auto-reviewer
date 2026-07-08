from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .fetcher import PepFetcher
from .filter import PepFilter
from .formatter import PepFormatter
from .matcher import PepMatcher
from .ranker import PepRanker
from .types import PepEntry, _MAX_PEPS

class PepStore:
    def __init__(
        self,
        peps_api_url: str = "https://peps.python.org/api/peps.json",
        *,
        http_get: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self._fetcher = PepFetcher(peps_api_url, http_get=http_get)
        self._filter = PepFilter()
        self._matcher = PepMatcher()
        self._ranker = PepRanker()
        self._formatter = PepFormatter()

    def guidance(self, python_version: str) -> str | None:
        try:
            target = self._matcher.parse_version(python_version)
        except (ValueError, TypeError):
            return None

        candidates: list[tuple[int, PepEntry]] = []

        for pep in self._fetcher.fetch():
            if not self._filter.is_relevant(pep):
                continue
            if not self._matcher.applies(pep.get("python_version"), target):
                continue
            score = self._ranker.score(pep, target)
            candidates.append((score, pep))

        candidates.sort(key=lambda item: item[0], reverse=True)
        selected = [pep for _score, pep in candidates[:_MAX_PEPS]]

        if not selected:
            return None
        return self._formatter.format(selected, python_version)
