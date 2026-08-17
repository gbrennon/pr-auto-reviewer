"""Tests for ArchitectureDetector."""

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


@pytest.mark.parametrize("lang", LANGUAGES)
class TestCQRS:
    """Tests for CQRS pattern detection across languages."""

    @pytest.fixture
    def detector(self) -> ArchitectureDetector:
        return ArchitectureDetector()

    def test_detects_cqrs_root_paths(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects CQRS pattern using root-level paths."""
        ext = get_ext(lang)
        paths = [
            f"commands/create.{ext}",
            f"queries/list.{ext}",
        ]
        assert detector.detect(paths) == "cqrs"

    def test_detects_cqrs_src_paths(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects CQRS pattern using src/ paths."""
        ext = get_ext(lang)
        paths = [
            f"src/commands/handler.{ext}",
            f"src/queries/handler.{ext}",
        ]
        assert detector.detect(paths) == "cqrs"
