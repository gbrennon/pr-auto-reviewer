"""Tests for FindingVerifier application service."""

import json
from pathlib import Path

from pr_auto_reviewer.application.services.finding_verifier import FindingVerifier
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.verify_findings_command import (
    VerifyFindingsCommand,
)
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity


def _item(
    number: int,
    *,
    severity: ItemSeverity = ItemSeverity.MAJOR,
    category: IssueCategory = IssueCategory.BUG,
    file_path: str | None = "src/a.py",
    current_code: str = "bad",
    suggested_fix: str = "good",
    id_: str = "",
) -> ReviewItem:
    return ReviewItem(
        number=number,
        severity=severity,
        category=category,
        file_path=file_path,
        description=f"finding {number}",
        line="42",
        id=id_ or f"id{number}",
        current_code=current_code,
        suggested_fix=suggested_fix,
    )


def _verifier(
    mock_chat_port, mock_tool_factory, responses: list[str] | None = None,
) -> FindingVerifier:
    if responses is not None:
        mock_chat_port.send.side_effect = responses
    return FindingVerifier(
        mock_chat_port, "verify {findings}", mock_tool_factory
    )


class TestFindingVerifierExecute:
    """Behaviour of FindingVerifier.execute(command) -> list[ReviewItem]."""

    def test_returns_all_items_when_none_blocking(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        items = [_item(1, severity=ItemSeverity.MINOR)]
        verifier = _verifier(mock_chat_port, mock_tool_factory)

        result = verifier.execute(
            VerifyFindingsCommand(
                items=items, repo_path=Path("."), changed_files=[]
            )
        )

        assert result == items

    def test_preserves_all_when_verification_aborts_on_empty_responses(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        items = [_item(1)]
        verifier = _verifier(
            mock_chat_port, mock_tool_factory, ["", "", ""]
        )

        result = verifier.execute(
            VerifyFindingsCommand(
                items=items, repo_path=Path("."), changed_files=[]
            )
        )

        assert result == items

    def test_preserves_all_when_verification_aborts_on_unparseable(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        items = [_item(1)]
        verifier = _verifier(
            mock_chat_port, mock_tool_factory,
            ["garbage", "garbage", "garbage"],
        )

        result = verifier.execute(
            VerifyFindingsCommand(
                items=items, repo_path=Path("."), changed_files=[]
            )
        )

        assert result == items

    def test_drops_refuted_and_keeps_verified_items(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        blocking = [
            _item(1, id_="aa11", current_code="bad", suggested_fix="good"),
            _item(2, id_="bb22", current_code="bad", suggested_fix="good"),
        ]
        minor = _item(3, severity=ItemSeverity.MINOR, id_="cc33")
        verifier = _verifier(mock_chat_port, mock_tool_factory, [
            json.dumps({
                "results": [
                    {"finding_index": 0, "verified": True, "reasoning": "ok"},
                    {
                        "finding_index": 1,
                        "verified": False,
                        "reasoning": "refuted against source",
                    },
                ]
            })
        ])

        result = verifier.execute(
            VerifyFindingsCommand(
                items=blocking + [minor],
                repo_path=Path("."),
                changed_files=[],
            )
        )

        assert result == [minor, blocking[0]]

    def test_drops_verified_item_whose_code_matches_fix(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        items = [_item(1, current_code="same", suggested_fix="same")]
        verifier = _verifier(mock_chat_port, mock_tool_factory, [
            json.dumps({
                "results": [
                    {"finding_index": 0, "verified": True, "reasoning": "ok"}
                ]
            })
        ])

        result = verifier.execute(
            VerifyFindingsCommand(
                items=items, repo_path=Path("."), changed_files=[]
            )
        )

        assert result == []

    def test_returns_all_when_everything_verified(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        items = [_item(1)]
        verifier = _verifier(mock_chat_port, mock_tool_factory, [
            json.dumps({
                "results": [
                    {"finding_index": 0, "verified": True, "reasoning": "ok"}
                ]
            })
        ])

        result = verifier.execute(
            VerifyFindingsCommand(
                items=items, repo_path=Path("."), changed_files=[]
            )
        )

        assert result == items


class TestRunVerificationConversation:
    """Multi-turn agentic loop with tools, retries, and abort paths."""

    def test_tool_call_then_results(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        mock_chat_port.send.side_effect = [
            json.dumps({"action": "read_file", "args": "src/a.py"}),
            json.dumps({"results": [{"finding_index": 0, "verified": True}]}),
        ]
        tool_service = mock_tool_factory.return_value
        tool_service.execute.return_value = {"status": "success", "data": {}}
        verifier = FindingVerifier(
            mock_chat_port, "verify {findings}", mock_tool_factory
        )

        results = verifier._run_verification_conversation(
            "prompt", Path("."), ["src/a.py"]
        )

        assert results == [{"finding_index": 0, "verified": True}]
        tool_service.execute.assert_called_once_with(
            "read_file", "src/a.py"
        )

    def test_empty_response_reprompts_then_succeeds(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        mock_chat_port.send.side_effect = [
            "", json.dumps({"results": []})
        ]
        verifier = _verifier(mock_chat_port, mock_tool_factory)

        results = verifier._run_verification_conversation(
            "prompt", Path("."), []
        )

        assert results == []

    def test_unparseable_response_reprompts_then_succeeds(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        mock_chat_port.send.side_effect = [
            "garbage", json.dumps({"results": []})
        ]
        verifier = _verifier(mock_chat_port, mock_tool_factory)

        results = verifier._run_verification_conversation(
            "prompt", Path("."), []
        )

        assert results == []

    def test_max_turns_exceeded_returns_none(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        mock_chat_port.send.side_effect = [
            json.dumps({"action": "read_file", "args": "a.py"})
        ] * 5
        mock_tool_factory.return_value.execute.return_value = {
            "status": "success", "data": {}
        }
        verifier = _verifier(mock_chat_port, mock_tool_factory)

        results = verifier._run_verification_conversation(
            "prompt", Path("."), []
        )

        assert results is None


class TestParseVerifyTurn:
    """Parsing a verification turn into results, tool call, or None."""

    def _verifier(self, mock_chat_port, mock_tool_factory) -> FindingVerifier:
        return FindingVerifier(
            mock_chat_port, "verify {findings}", mock_tool_factory
        )

    def test_returns_results_list(self, mock_chat_port, mock_tool_factory) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn('{"results": [{"finding_index": 1}]}') == [
            {"finding_index": 1}
        ]

    def test_returns_action_dict(self, mock_chat_port, mock_tool_factory) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn('{"action": "read_file"}') == {
            "action": "read_file"
        }

    def test_returns_none_for_non_dict_json(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn("[1, 2]") is None

    def test_returns_none_when_no_results_or_action(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn('{"foo": 1}') is None

    def test_delegates_to_prose_when_not_json(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn("narrative prose") is None


class TestParseVerifyProse:
    """Parsing narrative prose into per-finding verification results."""

    def _verifier(self, mock_chat_port, mock_tool_factory) -> FindingVerifier:
        return FindingVerifier(
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


class TestFormatFindingsForVerification:
    """Rendering blocking findings with surrounding context."""

    def test_formats_existing_missing_and_unknown_files(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        repo = tmp_path / "repo"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "a.py").write_text("def f(): pass\n")
        verifier = FindingVerifier(
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


class TestExtractFileContext:
    """Surrounding-context extraction for a code snippet."""

    def _verifier(self, mock_chat_port, mock_tool_factory) -> FindingVerifier:
        return FindingVerifier(
            mock_chat_port, "verify {findings}", mock_tool_factory
        )

    def test_returns_error_message_when_file_unreadable(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(tmp_path / "missing.txt", "x")

        assert text == "(file could not be read)"

    def test_returns_head_when_snippet_empty(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        path = tmp_path / "a.txt"
        path.write_text("line1\nline2\n")

        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(path, "")

        assert text == "line1\nline2\n"

    def test_returns_head_when_snippet_blank(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        path = tmp_path / "a.txt"
        path.write_text("content")

        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(path, "   \n ")

        assert text == "content"

    def test_returns_window_around_exact_line(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        path = tmp_path / "a.txt"
        path.write_text("\n".join(f"line{i}" for i in range(100)))

        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(path, "line50")

        assert "line50" in text
        assert "line39" not in text
        assert "line99" in text

    def test_falls_back_to_substring_match(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        path = tmp_path / "a.txt"
        path.write_text("alpha\nbeta gamma\nomega\n")

        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(path, "gamma")

        assert "beta gamma" in text

    def test_returns_head_when_no_match(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        path = tmp_path / "a.txt"
        path.write_text("alpha\nbeta\n")

        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(path, "zeta")

        assert text == "alpha\nbeta\n"
