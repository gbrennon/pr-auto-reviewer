from dataclasses import replace

from ._helpers import *


class TestFindingVerifierExecute:
    """Behaviour of FindingVerifierService.execute(command) -> list[ReviewItem]."""

    def test_minor_items_are_llm_verified_and_kept_when_confirmed(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        items = [_item("1", severity=ItemSeverity.MINOR)]
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

    def test_marks_prior_finding_resolved_from_verifier_status(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        prior = _item(item_id="prior")
        verifier = _verifier(mock_chat_port, mock_tool_factory, [
            json.dumps({"action": "read_file", "args": "src/a.py"}),
            json.dumps({
                "results": [
                    {
                        "finding_index": 0,
                        "verified": False,
                        "status": "resolved",
                    },
                ]
            }),
        ])
        mock_tool_factory.return_value.execute.return_value = {
            "status": "success", "data": {}
        }

        result = verifier.execute(
            VerifyFindingsCommand(
                items=[], repo_path=Path("."), changed_files=[],
                review_session="test-session", prior_items=[prior],
            )
        )

        assert result == [replace(prior, status="resolved")]

    def test_keeps_prior_finding_open_when_verification_aborts(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        prior = _item(item_id="prior")
        verifier = _verifier(mock_chat_port, mock_tool_factory, ["", "", ""])

        result = verifier.execute(
            VerifyFindingsCommand(
                items=[], repo_path=Path("."), changed_files=[],
                review_session="test-session", prior_items=[prior],
            )
        )

        assert result == [prior]

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

    def test_all_dropped_by_filter_still_publishes_audit_transcript(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        """The S3/S4 drop path must leave a visible 05-verifier trail."""
        from unittest.mock import MagicMock

        from pr_auto_reviewer.domain.messages.events.agent_exchange_event import (
            AgentExchangeEvent,
        )

        no_op = _item(
            item_id="no-op", current_code="same", suggested_fix="same",
        )
        command_bus = MagicMock()
        verifier = FindingVerifierService(
            mock_chat_port, "verify {findings}", mock_tool_factory,
            command_bus=command_bus,
        )

        result = verifier.execute(
            VerifyFindingsCommand(
                items=[no_op], repo_path=Path("."), changed_files=["src/a.py"],
                review_session="test-session",
            )
        )

        assert result == []
        mock_chat_port.send.assert_not_called()
        published = [
            c.args[0]
            for c in command_bus.dispatch.call_args_list
            if c.args and isinstance(c.args[0], AgentExchangeEvent)
        ]
        assert published, "expected a verifier transcript exchange"
        transcript_text = "\n".join(
            message.content for message in published[0].messages
        )
        assert "synthetic-finding" in transcript_text

