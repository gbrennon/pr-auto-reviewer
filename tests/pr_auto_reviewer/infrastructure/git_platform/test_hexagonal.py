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
class TestHexagonal:
    """Tests for hexagonal architecture detection across languages."""

    @pytest.fixture
    def detector(self) -> ArchitectureDetector:
        return ArchitectureDetector()

    def test_detects_hexagonal_src_paths(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects hexagonal architecture using src/ paths."""
        ext = get_ext(lang)
        paths = [f"src/domain/model.{ext}", f"src/application/service.{ext}"]
        assert detector.detect(paths) == "hexagonal"

    def test_detects_hexagonal_root_paths(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects hexagonal architecture using root-level paths."""
        ext = get_ext(lang)
        paths = [f"domain/entity.{ext}", f"adapters/repository.{ext}", f"ports/interface.{ext}"]
        assert detector.detect(paths) == "hexagonal"
