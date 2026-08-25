from ._helpers import *


class TestFormatFindingsForVerification:
    """Rendering blocking findings with surrounding context."""

    def test_formats_existing_missing_and_unknown_files(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        repo = tmp_path / "repo"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "a.py").write_text("def f(): pass\n")
        verifier = FindingVerifierService(
            mock_chat_port, "verify {findings}", mock_tool_factory
        )
        items = [
            _item(1, file_path="src/a.py"),
            _item(2, file_path="src/missing.py"),
            _item(3, file_path=None),
        ]

        text = verifier._format_findings_for_verification(items, repo)

        assert "## Finding 0" in text
        assert "src/a.py" in text
        assert "src/missing.py" in text
        assert "(unknown)" in text
        assert "def f(): pass" in text

