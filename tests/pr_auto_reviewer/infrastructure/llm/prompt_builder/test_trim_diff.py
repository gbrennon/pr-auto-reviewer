from ._helpers import *


class TestTrimDiff:
    def test_returns_unchanged_when_under_budget(self):
        diff = (
            "diff --git a/a.py b/a.py\n"
            "--- a/a.py\n"
            "+++ b/a.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = _trim_diff(diff, max_tokens=500)
        assert result == diff

    def test_truncates_large_diff_at_boundaries(self):
        diff = ""
        for i in range(3):
            diff += (
                f"diff --git a/file{i}.py b/file{i}.py\n"
                f"--- a/file{i}.py\n"
                f"+++ b/file{i}.py\n"
                f"@@ -1 +1 @@\n"
                f"-old{i}\n"
                f"+new{i}\n"
            )
        result = _trim_diff(diff, max_tokens=20)
        assert "diff --git" in result
        assert len(result) < len(diff)

