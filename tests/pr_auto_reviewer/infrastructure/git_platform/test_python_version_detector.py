from pr_auto_reviewer.infrastructure.git_platform.python_version_detector import (
    PythonVersionDetector,
)


class TestPythonVersionDetector:

    def test_detect_when_has_pyproject_then_returns_3_9(self):
        d = PythonVersionDetector()
        assert d.detect(["pyproject.toml", "src/main.py"]) == "3.9"

    def test_detect_when_has_setup_cfg_without_pyproject_then_returns_3_7(self):
        d = PythonVersionDetector()
        assert d.detect(["setup.cfg", "src/app.py"]) == "3.7"

    def test_detect_when_has_dot_python_version_then_returns_3_7(self):
        d = PythonVersionDetector()
        assert d.detect([".python-version", "src/lib.py"]) == "3.7"

    def test_detect_when_has_setup_py_then_returns_3_7(self):
        d = PythonVersionDetector()
        assert d.detect(["setup.py", "pkg/module.py"]) == "3.7"

    def test_detect_when_no_python_files_then_returns_none(self):
        d = PythonVersionDetector()
        assert d.detect(["main.go", "lib.rs"]) is None

    def test_detect_when_empty_paths_then_returns_none(self):
        d = PythonVersionDetector()
        assert d.detect([]) is None


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
