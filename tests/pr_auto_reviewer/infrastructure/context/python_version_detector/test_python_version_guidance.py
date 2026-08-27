from ._helpers import *


class TestPythonVersionGuidance:

    def test_guidance_when_none_then_returns_none(self):
        assert PythonVersionDetector().guidance(None) is None

    def test_guidance_when_3_9_then_includes_modern_type_hints(self):
        g = PythonVersionDetector().guidance("3.9")
        assert g is not None
        assert "Python Version" in g
        assert "list[X]" in g
        assert "List[X]" in g

    def test_guidance_when_3_11_then_includes_modern_type_hints(self):
        g = PythonVersionDetector().guidance("3.11")
        assert g is not None
        assert "X | None" in g
        assert "Optional[X]" in g

    def test_guidance_when_3_7_then_returns_none(self):
        assert PythonVersionDetector().guidance("3.7") is None

    def test_guidance_when_3_8_then_returns_none(self):
        assert PythonVersionDetector().guidance("3.8") is None

    def test_guidance_when_malformed_version_then_returns_none(self):
        assert PythonVersionDetector().guidance("not.a.version") is None

