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
    item_id: str = "id-1",
    *,
    severity: ItemSeverity = ItemSeverity.MAJOR,
    category: IssueCategory = IssueCategory.BUG,
    file_path: str | None = "src/a.py",
    current_code: str = "bad",
    suggested_fix: str = "good",
) -> ReviewItem:
    return ReviewItem(
        id=item_id,
        severity=severity,
        category=category,
        file_path=file_path,
        description=f"finding {item_id}",
        line="42",
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

    def test_minor_items_are_llm_verified_and_kept_when_confirmed(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        items = [_item(1, severity=ItemSeverity.MINOR)]
        verifier = _verifier(mock_chat_port, mock_tool_factory, [
            json.dumps({"action": "read_file", "args": "src/a.py"}),
            json.dumps({
                "results": [
                    {"finding_index": 0, "verified": True, "reasoning": "ok"}
                ]
            }),
        ])
        mock_tool_factory.return_value.execute.return_value = {
            "status": "success", "data": {}
        }

        result = verifier.execute(
            VerifyFindingsCommand(
                items=items, repo_path=Path("."), changed_files=[],
                review_session="test-session",
            )
        )

        assert result == items

    def test_drops_blocking_when_verification_aborts_on_empty_responses(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        minor = _item(item_id="minor", severity=ItemSeverity.MINOR)
        blocking = _item(item_id="major")
        items = [minor, blocking]
        verifier = _verifier(
            mock_chat_port, mock_tool_factory, ["", "", ""]
        )

        result = verifier.execute(
            VerifyFindingsCommand(
                items=items, repo_path=Path("."), changed_files=[],
                review_session="test-session",
            )
        )

        assert result == [minor]

    def test_drops_blocking_when_verification_aborts_on_unparseable(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        minor = _item(item_id="minor", severity=ItemSeverity.MINOR)
        blocking = _item(item_id="major")
        items = [minor, blocking]
        verifier = _verifier(
            mock_chat_port, mock_tool_factory,
            ["garbage", "garbage", "garbage"],
        )

        result = verifier.execute(
            VerifyFindingsCommand(
                items=items, repo_path=Path("."), changed_files=[],
                review_session="test-session",
            )
        )

        assert result == [minor]

    def test_drops_refuted_and_keeps_verified_items(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        blocking = [
            _item(item_id="aa11", current_code="bad", suggested_fix="good"),
            _item(item_id="bb22", current_code="bad", suggested_fix="good"),
        ]
        minor = _item(item_id="cc33", severity=ItemSeverity.MINOR)
        verifier = _verifier(mock_chat_port, mock_tool_factory, [
            json.dumps({"action": "read_file", "args": "src/a.py"}),
            json.dumps({
                "results": [
                    {"finding_index": 0, "verified": True, "reasoning": "ok"},
                    {
                        "finding_index": 1,
                        "verified": False,
                        "reasoning": "refuted against source",
                    },
                    {"finding_index": 2, "verified": True, "reasoning": "ok"},
                ]
            }),
        ])
        mock_tool_factory.return_value.execute.return_value = {
            "status": "success", "data": {}
        }
        result = verifier.execute(
            VerifyFindingsCommand(
                items=blocking + [minor],
                repo_path=Path("."),
                changed_files=[],
                review_session="test-session",
            )
        )

        assert result == [blocking[0], minor]

    def test_refuted_minor_item_is_dropped_by_llm_verification(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        minor = _item(item_id="mn-9", severity=ItemSeverity.MINOR)
        verifier = _verifier(mock_chat_port, mock_tool_factory, [
            json.dumps({"action": "read_file", "args": "src/a.py"}),
            json.dumps({
                "results": [
                    {
                        "finding_index": 0,
                        "verified": False,
                        "reasoning": "docstring documents this behavior",
                    },
                ]
            }),
        ])
        mock_tool_factory.return_value.execute.return_value = {
            "status": "success", "data": {}
        }
        result = verifier.execute(
            VerifyFindingsCommand(
                items=[minor], repo_path=Path("."), changed_files=[],
                review_session="test-session",
            )
        )

        assert result == []

    def test_s4_noop_fix_dropped_before_llm_spend(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        items = [_item(item_id="id-1", current_code="same", suggested_fix="same")]
        verifier = _verifier(mock_chat_port, mock_tool_factory)
        result = verifier.execute(
            VerifyFindingsCommand(
                items=items, repo_path=Path("."), changed_files=[],
                review_session="test-session",
            )
        )

        assert result == []
        mock_chat_port.send.assert_not_called()

    def test_s4_noop_gate_applies_to_minor_items(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        minor_noop = _item(
            item_id="mn-1", severity=ItemSeverity.MINOR,
            current_code="same", suggested_fix="same",
        )
        verifier = _verifier(mock_chat_port, mock_tool_factory)
        result = verifier.execute(
            VerifyFindingsCommand(
                items=[minor_noop], repo_path=Path("."), changed_files=[],
                review_session="test-session",
            )
        )

        assert result == []
        mock_chat_port.send.assert_not_called()

    def test_s3_fabricated_snippet_gate_applies_to_minor_items(
        self, mock_chat_port, mock_tool_factory, tmp_path,
    ) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("def real():\n    pass\n")
        minor_fabricated = _item(
            item_id="mn-2", severity=ItemSeverity.MINOR,
            current_code="class Nonexistent:\n    pass",
            suggested_fix="class Fixed:\n    pass",
        )
        verifier = _verifier(mock_chat_port, mock_tool_factory)
        result = verifier.execute(
            VerifyFindingsCommand(
                items=[minor_fabricated], repo_path=tmp_path,
                changed_files=[], review_session="test-session",
            )
        )

        assert result == []
        mock_chat_port.send.assert_not_called()

    def test_s3_snippet_absent_from_cited_file_is_dropped_before_llm(
        self, mock_chat_port, mock_tool_factory, tmp_path,
    ) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("def real():\n    pass\n")
        fabricated = _item(
            item_id="fab-1",
            current_code="class Nonexistent:\n    pass",
            suggested_fix="class Fixed:\n    pass",
        )
        verifier = _verifier(mock_chat_port, mock_tool_factory)
        result = verifier.execute(
            VerifyFindingsCommand(
                items=[fabricated], repo_path=tmp_path, changed_files=[],
                review_session="test-session",
            )
        )

        assert result == []
        mock_chat_port.send.assert_not_called()

    def test_s3_real_anchor_with_fabricated_body_is_dropped(
        self, mock_chat_port, mock_tool_factory, tmp_path,
    ) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text(
            "class Real:\n    def method(self):\n        return 1\n"
        )
        anchored_fabrication = _item(
            item_id="fab-2",
            current_code="class Real:\n    INVENTED = True\n",
            suggested_fix="class Fixed:\n    pass",
        )
        verifier = _verifier(mock_chat_port, mock_tool_factory)
        result = verifier.execute(
            VerifyFindingsCommand(
                items=[anchored_fabrication], repo_path=tmp_path,
                changed_files=[], review_session="test-session",
            )
        )

        assert result == []
        mock_chat_port.send.assert_not_called()

    def test_s3_genuine_snippet_passes_through_to_verification(
        self, mock_chat_port, mock_tool_factory, tmp_path,
    ) -> None:
        snippet = "class Real:\n    def method(self):\n        return 1"
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text(snippet + "\n")
        genuine = _item(
            item_id="gen-1", current_code=snippet,
            suggested_fix=snippet.replace("return 1", "return 2"),
        )
        verifier = _verifier(mock_chat_port, mock_tool_factory, [
            json.dumps({"action": "read_file", "args": "src/a.py"}),
            json.dumps({
                "results": [
                    {"finding_index": 0, "verified": True, "reasoning": "ok"}
                ]
            }),
        ])
        mock_tool_factory.return_value.execute.return_value = {
            "status": "success", "data": {}
        }
        result = verifier.execute(
            VerifyFindingsCommand(
                items=[genuine], repo_path=tmp_path,
                changed_files=[], review_session="test-session",
            )
        )

        assert result == [genuine]

    def test_returns_all_when_everything_verified(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        items = [_item(item_id="id-1")]
        verifier = _verifier(mock_chat_port, mock_tool_factory, [
            json.dumps({"action": "read_file", "args": "src/a.py"}),
            json.dumps({
                "results": [
                    {"finding_index": 0, "verified": True, "reasoning": "ok"}
                ]
            }),
        ])
        mock_tool_factory.return_value.execute.return_value = {
            "status": "success", "data": {}
        }
        result = verifier.execute(
            VerifyFindingsCommand(
                items=items, repo_path=Path("."), changed_files=[],
                review_session="test-session",
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
            "", json.dumps({"action": "read_file", "args": "a.py"}),
            json.dumps({"results": []}),
        ]
        mock_tool_factory.return_value.execute.return_value = {
            "status": "success", "data": {}
        }
        verifier = _verifier(mock_chat_port, mock_tool_factory)

        results = verifier._run_verification_conversation(
            "prompt", Path("."), []
        )

        assert results == []

    def test_unparseable_response_reprompts_then_succeeds(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        mock_chat_port.send.side_effect = [
            "garbage",
            json.dumps({"action": "read_file", "args": "a.py"}),
            json.dumps({"results": []}),
        ]
        mock_tool_factory.return_value.execute.return_value = {
            "status": "success", "data": {}
        }
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

    def test_demands_exploration_when_results_without_tool_calls(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        mock_chat_port.send.side_effect = [
            json.dumps(
                {"results": [{"finding_index": 0, "verified": True}]}
            ),
            json.dumps({"action": "read_file", "args": "src/a.py"}),
            json.dumps(
                {"results": [{"finding_index": 0, "verified": True}]}
            ),
        ]
        mock_tool_factory.return_value.execute.return_value = {
            "status": "success", "data": {}
        }
        verifier = _verifier(mock_chat_port, mock_tool_factory)

        results = verifier._run_verification_conversation(
            "prompt", Path("."), []
        )

        assert results == [{"finding_index": 0, "verified": True}]
        assert mock_chat_port.send.call_count == 3

    def test_aborts_when_model_refuses_exploration(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        results_json = json.dumps(
            {"results": [{"finding_index": 0, "verified": True}]}
        )
        mock_chat_port.send.side_effect = [
            results_json, results_json, results_json,
        ]
        verifier = _verifier(mock_chat_port, mock_tool_factory)

        results = verifier._run_verification_conversation(
            "prompt", Path("."), []
        )

        assert results is None
        assert mock_chat_port.send.call_count == 3


class TestReproScenario:
    """Verifier rejects dangerous dunder-suggestion findings via run_snippet."""

    def test_refutes_dunder_new_suggestion_when_snippet_fails(
        self, tmp_path, mock_chat_port,
    ) -> None:
        from pr_auto_reviewer.infrastructure.llm.exploration_tool_service import (
            ExplorationToolService,
        )
        (tmp_path / "_port_level.py").write_text(
            "from enum import Enum\n"
            "class PortLevel(Enum):\n"
            '    DOMAIN = "domain"\n'
        )
        suggested_fix = (
            "class PortLevel(Enum):\n"
            "    def __new__(cls, value):\n"
            "        obj = object.__new__(cls)\n"
            '        obj._value_ = value\n'
            "        return obj\n"
            '    DOMAIN = "domain"\n'
        )
        item = _item(
            item_id="dangerous-dunder",
            file_path="_port_level.py",
            current_code="class PortLevel(Enum): ...",
            suggested_fix=suggested_fix,
        )
        run_snippet_args = (
            "import _port_level\n"
            "try:\n"
            "    from _port_level import PortLevel\n"
            "    print('PortLevel imported OK')\n"
            "except TypeError as e:\n"
            "    print(f'TypeError: {e}')\n"
        )
        mock_chat_port.send.side_effect = [
            json.dumps(
                {"action": "run_snippet", "args": run_snippet_args}
            ),
            json.dumps({
                "results": [
                    {
                        "finding_index": 0,
                        "verified": False,
                        "reasoning": "suggested_fix causes TypeError",
                    }
                ]
            }),
        ]

        def tool_factory(repo_path, changed_files, base_sha):
            return ExplorationToolService(str(repo_path), changed_files, base_sha)

        verifier = FindingVerifier(
            mock_chat_port, "verify {findings}", tool_factory
        )

        result = verifier.execute(
            VerifyFindingsCommand(
                items=[item],
                repo_path=tmp_path,
                changed_files=["_port_level.py"],
                review_session="repro-session",
            )
        )

        assert result == []


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
