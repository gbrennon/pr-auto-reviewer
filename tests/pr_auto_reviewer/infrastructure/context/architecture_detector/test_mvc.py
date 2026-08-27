from ._helpers import *


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

