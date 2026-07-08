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

@pytest.mark.parametrize("lang", LANGUAGES)
class TestClean:
    """Tests for clean architecture detection across languages."""

    @pytest.fixture
    def detector(self) -> ArchitectureDetector:
        return ArchitectureDetector()

    def test_detects_clean_src_paths(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects clean architecture using src/ paths."""
        ext = get_ext(lang)
        paths = [
            f"src/domain/entity.{ext}",
            f"src/use_cases/interactor.{ext}",
            f"src/infrastructure/repository.{ext}",
        ]
        assert detector.detect(paths) == "clean"

    def test_detects_clean_root_paths(self, detector: ArchitectureDetector, lang: str) -> None:
        """Detects clean architecture using root-level paths."""
        ext = get_ext(lang)
        paths = [
            f"domain/model.{ext}",
            f"use_cases/service.{ext}",
            f"infrastructure/persistence.{ext}",
        ]
        assert detector.detect(paths) == "clean"

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

class TestReturnsUnknown:
    """Tests for unknown architecture detection."""

    @pytest.fixture
    def detector(self) -> ArchitectureDetector:
        return ArchitectureDetector()

    def test_returns_unknown_for_empty(self, detector: ArchitectureDetector) -> None:
        """Returns unknown for empty path list."""
        assert detector.detect([]) == "unknown"

    def test_returns_unknown_for_unrecognized(self, detector: ArchitectureDetector) -> None:
        """Returns unknown for unrecognized patterns."""
        paths = ["src/main.rs", "README.md", "src/utils/helper.go"]
        assert detector.detect(paths) == "unknown"

    def test_returns_unknown_for_partial_match(self, detector: ArchitectureDetector) -> None:
        """Returns unknown when only some markers present."""
        paths = ["src/domain/model.rs", "src/services/service.rs"]
        assert detector.detect(paths) == "unknown"

    def test_returns_unknown_for_no_src_folders(self, detector: ArchitectureDetector) -> None:
        """Returns unknown for typical Go project structure."""
        paths = ["main.go", "cmd/server/main.go", "internal/handler.go"]
        assert detector.detect(paths) == "unknown"