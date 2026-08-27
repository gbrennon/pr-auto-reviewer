from ._helpers import *


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

