"""Shared helpers, fixtures, and imports for the split test modules."""

from __future__ import annotations

from typing import Any

from pr_auto_reviewer.infrastructure.git_platform.practices.python.pep_store import (
    PepStore,
)

_SAMPLE_PEPS: dict[str, dict[str, Any]] = {
    "8": {
        "number": 8,
        "title": "Style Guide for Python Code",
        "status": "Active",
        "type": "Process",
        "topic": "style",
        "python_version": None,
        "url": "https://peps.python.org/pep-0008/",
    },
    "484": {
        "number": 484,
        "title": "Type Hints",
        "status": "Final",
        "type": "Standards Track",
        "topic": "typing",
        "python_version": "3.5",
        "url": "https://peps.python.org/pep-0484/",
    },
    "526": {
        "number": 526,
        "title": "Syntax for Variable Annotations",
        "status": "Final",
        "type": "Standards Track",
        "topic": "typing",
        "python_version": "3.6",
        "url": "https://peps.python.org/pep-0526/",
    },
    "557": {
        "number": 557,
        "title": "Data Classes",
        "status": "Final",
        "type": "Standards Track",
        "topic": "typing",
        "python_version": "3.7",
        "url": "https://peps.python.org/pep-0557/",
    },
    "572": {
        "number": 572,
        "title": "Assignment Expressions",
        "status": "Final",
        "type": "Standards Track",
        "topic": "syntax",
        "python_version": "3.8",
        "url": "https://peps.python.org/pep-0572/",
    },
    "585": {
        "number": 585,
        "title": "Type Hinting Generics In Standard Collections",
        "status": "Final",
        "type": "Standards Track",
        "topic": "typing",
        "python_version": "3.9",
        "url": "https://peps.python.org/pep-0585/",
    },
    "604": {
        "number": 604,
        "title": "Allow writing union types as X | Y",
        "status": "Final",
        "type": "Standards Track",
        "topic": "typing",
        "python_version": "3.10",
        "url": "https://peps.python.org/pep-0604/",
    },
    "634": {
        "number": 634,
        "title": "Structural Pattern Matching",
        "status": "Final",
        "type": "Standards Track",
        "topic": "syntax",
        "python_version": "3.10",
        "url": "https://peps.python.org/pep-0634/",
    },
    "3": {
        "number": 3,
        "title": "Withdrawn PEP",
        "status": "Withdrawn",
        "type": "Process",
        "topic": "process",
        "python_version": None,
        "url": "https://peps.python.org/pep-0003/",
    },
    "5": {
        "number": 5,
        "title": "Rejected PEP",
        "status": "Rejected",
        "type": "Standards Track",
        "topic": "syntax",
        "python_version": "3.8",
        "url": "https://peps.python.org/pep-0005/",
    },
    "10": {
        "number": 10,
        "title": "Empty topic PEP",
        "status": "Active",
        "type": "Process",
        "topic": "",
        "python_version": None,
        "url": "https://peps.python.org/pep-0010/",
    },
    "11": {
        "number": 11,
        "title": "Release PEP",
        "status": "Active",
        "type": "Process",
        "topic": "release",
        "python_version": "3.12",
        "url": "https://peps.python.org/pep-0011/",
    },
    "12": {
        "number": 12,
        "title": "Draft Standards Track",
        "status": "Draft",
        "type": "Standards Track",
        "topic": "syntax",
        "python_version": "3.12",
        "url": "https://peps.python.org/pep-0012/",
    },
    "274": {
        "number": 274,
        "title": "Dict Comprehensions",
        "status": "Final",
        "type": "Standards Track",
        "topic": "syntax",
        "python_version": "2.7, 3.0",
        "url": "https://peps.python.org/pep-0274/",
    },
}


def _make_store(peps: dict[str, Any] | None = None) -> PepStore:
    if peps is None:
        peps = dict(_SAMPLE_PEPS)

    def fake_get(url: str) -> dict[str, Any]:
        return peps

    return PepStore(http_get=fake_get)


__all__ = ['_SAMPLE_PEPS', 'Any', 'PepStore', '_make_store', 'annotations']
