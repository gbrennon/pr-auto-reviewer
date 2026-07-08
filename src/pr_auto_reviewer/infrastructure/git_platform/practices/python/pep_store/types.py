from __future__ import annotations

from typing import TypedDict

class PepEntry(TypedDict, total=False):
    number: int
    title: str
    status: str
    type: str
    topic: str
    python_version: str | None
    url: str

_TYPE_PRIORITY: dict[str, int] = {
    "Standards Track": 3,
    "Process": 1,
}

_EXCLUDED_STATUSES: frozenset[str] = frozenset(
    {"Rejected", "Withdrawn", "Informational"}
)

_EXCLUDED_TOPICS: frozenset[str] = frozenset({"release"})

_MAX_PEPS = 15
