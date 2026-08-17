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
class TestLayered:
    """Tests for layered architecture detection across languages."""

    @pytest.fixture
    def detector(self) -> ArchitectureDetector:
        return ArchitectureDetector()

    def test_detects_layered_src_paths(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects layered architecture using src/ paths."""
        ext = get_ext(lang)
        paths = [
            f"src/domain/entity.{ext}",
            f"src/application/service.{ext}",
            f"src/infrastructure/persistence.{ext}",
            f"src/presentation/controller.{ext}",
        ]
        assert detector.detect(paths) == "layered"

    def test_detects_layered_root_paths(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects layered architecture using root-level paths."""
        ext = get_ext(lang)
        paths = [
            f"domain/model.{ext}",
            f"application/service.{ext}",
            f"infrastructure/adapter.{ext}",
            f"presentation/handler.{ext}",
        ]
        assert detector.detect(paths) == "layered"
