from ._helpers import *


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
        verifier = FindingVerifierService(
            mock_chat_port, "verify {findings}", mock_tool_factory
        )

        results = verifier._run_verification_conversation(
            "prompt", Path("."), ["src/a.py"]
        )

        assert results == [{"finding_index": 0, "verified": True}]
        tool_service.execute.assert_called_once_with(
            "read_file", "src/a.py"
        )


    def test_markdown_fenced_tool_call_then_markdown_results(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        mock_chat_port.send.side_effect = [
            '```json\n{"action": "read_file", "args": "src/a.py"}\n```',
            '```json\n{"results": [{"finding_index": 0, "verified": true}]}\n```',
        ]
        tool_service = mock_tool_factory.return_value
        tool_service.execute.return_value = {"status": "success", "data": {}}
        verifier = FindingVerifierService(
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

