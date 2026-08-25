from ._helpers import *


class TestTrimFileContents:
    def test_returns_empty_for_empty_input(self):
        assert _trim_file_contents({}, "") == {}

    def test_limits_number_of_files(self):
        contents = {f"f{i}.py": f"content{i}" for i in range(20)}
        result = _trim_file_contents(contents, "", max_files=3)
        assert len(result) <= 3

    def test_extracts_context_around_hunks(self):
        file_contents = {
            "main.py": "\n".join(
                f"line {i}" for i in range(1, 101)
            )
        }
        diff = (
            "diff --git a/main.py b/main.py\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -50,3 +50,4 @@\n"
            " line 50\n"
            " line 51\n"
            "-line 52\n"
            "+line 52 modified\n"
            " line 53\n"
        )
        result = _trim_file_contents(file_contents, diff, max_chars_per_file=5000)
        assert "main.py" in result
        content = result["main.py"]
        assert "line 50" in content
        assert "line 53" in content

