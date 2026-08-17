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
class TestMVC:
    """Tests for MVC architecture detection across languages."""

    @pytest.fixture
    def detector(self) -> ArchitectureDetector:
        return ArchitectureDetector()

    def test_detects_mvc_standard(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects MVC architecture using standard folders."""
        ext = get_ext(lang)
        paths = [
            f"controllers/controller.{ext}",
            f"models/model.{ext}",
            f"views/view.{ext}",
        ]
        assert detector.detect(paths) == "mvc"

    def test_detects_mvc_with_routes(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects MVC architecture using handlers and routes."""
        ext = get_ext(lang)
        paths = [
            f"handlers/handler.{ext}",
            f"models/model.{ext}",
            f"views/template.{ext}",
            f"routes/api.{ext}",
        ]
        assert detector.detect(paths) == "mvc"
