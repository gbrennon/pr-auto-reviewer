from ._helpers import *


class TestParseVerifyProse:
    """Parsing narrative prose into per-finding verification results."""

    def _verifier(self, mock_chat_port, mock_tool_factory) -> FindingVerifierService:
        return FindingVerifierService(
            mock_chat_port, "verify {findings}", mock_tool_factory
        )

    def test_parses_verified_finding_line(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        result = self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_prose("- Finding 1: confirmed in source")

        assert result == [
            {
                "finding_index": 1,
                "verified": True,
                "reasoning": "confirmed in source",
            }
        ]

    def test_multiple_lines_with_mixed_verdicts(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        content = (
            "Finding 1: confirmed\n"
            "Finding 2: refuted because not found\n"
            "Finding 3: unable to verify claim\n"
            "Finding 4: doesn't exist in the tree\n"
            "Finding 5: hallucinated\n"
            "Finding 6: cannot verify without more context\n"
            "Finding 7: not found anywhere\n"
        )
        result = self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_prose(content)

        assert result is not None
        assert [r["finding_index"] for r in result if r["verified"]] == [1]
        assert [
            r["finding_index"] for r in result if not r["verified"]
        ] == [2, 3, 4, 5, 6, 7]

    def test_returns_none_without_finding_lines(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_prose("no findings here") is None

