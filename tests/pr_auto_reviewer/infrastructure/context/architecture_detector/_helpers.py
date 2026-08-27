"""Shared helpers, fixtures, and imports for the split test modules."""

import pytest

from pr_auto_reviewer.infrastructure.context.architecture_detector import (
    ArchitectureDetector,
)

LANGUAGES = [
    "golang",
    "python",
    "scala",
    "java",
    "typescript",
    "rust",
]


EXTENSIONS = {
    "golang": "go",
    "python": "py",
    "scala": "scala",
    "java": "java",
    "typescript": "ts",
    "rust": "rs",
}


def get_ext(lang: str) -> str:
    return EXTENSIONS.get(lang, "txt")


__all__ = ['EXTENSIONS', 'LANGUAGES', 'ArchitectureDetector', 'get_ext', 'pytest']
