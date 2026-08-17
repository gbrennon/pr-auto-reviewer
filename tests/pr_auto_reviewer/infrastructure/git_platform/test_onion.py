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
class TestOnion:
    """Tests for onion architecture detection across languages."""

    @pytest.fixture
    def detector(self) -> ArchitectureDetector:
        return ArchitectureDetector()

    def test_detects_onion_src_paths(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects onion architecture using src/ paths."""
        ext = get_ext(lang)
        paths = [
            f"src/core/domain.{ext}",
            f"src/application/service.{ext}",
            f"src/infrastructure/adapter.{ext}",
        ]
        assert detector.detect(paths) == "onion"

    def test_detects_onion_root_paths(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects onion architecture using root-level paths."""
        ext = get_ext(lang)
        paths = [
            f"core/entity.{ext}",
            f"application/use_case.{ext}",
            f"infrastructure/repository.{ext}",
        ]
        assert detector.detect(paths) == "onion"
