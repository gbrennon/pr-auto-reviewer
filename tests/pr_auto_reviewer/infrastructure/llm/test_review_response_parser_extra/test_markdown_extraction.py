from ._helpers import *


class TestMarkdownExtraction:
    """Exercises markdown section extraction helpers."""

    def test_extract_summary_when_section_then_text(self) -> None:
        assert (
            ReviewResponseParser()._extract_summary_md("## Summary\noverview text")
            == "overview text"
        )

    def test_extract_summary_when_absent_then_empty(self) -> None:
        assert ReviewResponseParser()._extract_summary_md("no summary") == ""

    def test_extract_reason_when_bold_then_text(self) -> None:
        assert (
            ReviewResponseParser()._extract_reason_md("**Reason:** alpha")
            == "alpha"
        )

    def test_extract_reason_when_plain_then_text(self) -> None:
        assert ReviewResponseParser()._extract_reason_md("Reason: beta") == "beta"

    def test_extract_reason_when_absent_then_empty(self) -> None:
        assert ReviewResponseParser()._extract_reason_md("nothing") == ""

    def test_extract_first_paragraph_when_long_then_returned(self) -> None:
        text = "A sufficiently long opening paragraph about the change.\n## Verdict\nx"

        assert ReviewResponseParser()._extract_first_paragraph(text) is not None

    def test_extract_first_paragraph_when_verdict_preamble_then_none(self) -> None:
        text = "verdict approved\n## Summary\nx"

        assert ReviewResponseParser()._extract_first_paragraph(text) is None

    def test_extract_first_paragraph_when_short_then_none(self) -> None:
        assert ReviewResponseParser()._extract_first_paragraph("short\n## Verdict\nx") is None

    def test_extract_first_paragraph_when_absent_then_none(self) -> None:
        assert ReviewResponseParser()._extract_first_paragraph("plain") is None

    def test_extract_line_range_when_range_then_dash_form(self) -> None:
        assert ReviewResponseParser()._extract_line_range("lines 5-10") == "5-10"

    def test_extract_line_range_when_to_form_then_dash(self) -> None:
        assert ReviewResponseParser()._extract_line_range("5 to 10") == "5-10"

    def test_extract_line_range_when_file_line_then_single(self) -> None:
        assert ReviewResponseParser()._extract_line_range("src/app.py:12") == "12"

    def test_extract_line_range_when_absent_then_empty(self) -> None:
        assert ReviewResponseParser()._extract_line_range("no reference") == ""

