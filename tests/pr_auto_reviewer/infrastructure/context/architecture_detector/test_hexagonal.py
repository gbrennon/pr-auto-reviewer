from ._helpers import *


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

