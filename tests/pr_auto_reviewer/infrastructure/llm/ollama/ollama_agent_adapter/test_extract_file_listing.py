from ._helpers import *


class TestExtractFileListing:
    """Exercises the diff-section path extractor."""

    def test_extract_when_diff_section_then_paths(self) -> None:
        content = (
            "## Diff\n\n"
            "--- a/src/app.py\n"
            "+++ b/src/main.py\n"
            "+++ b/foo/bar.txt\n"
        )
        adapter = _adapter()

        assert adapter._extract_file_listing(content) == [
            "foo/bar.txt",
            "src/app.py",
            "src/main.py",
        ]

    def test_extract_when_dev_null_then_skipped(self) -> None:
        content = "## Diff\n--- /dev/null\n+++ b/new.py\n"
        adapter = _adapter()

        assert adapter._extract_file_listing(content) == ["new.py"]

    def test_extract_when_no_diff_section_then_empty(self) -> None:
        assert _adapter()._extract_file_listing("plain content") == []

    def test_extract_when_prefixes_without_slashes_then_kept(self) -> None:
        content = "## Diff\n--- a/readme.md\n+++ b/generated.yaml\n"
        adapter = _adapter()

        assert adapter._extract_file_listing(content) == ["generated.yaml", "readme.md"]

