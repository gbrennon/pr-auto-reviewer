from ._helpers import *


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

