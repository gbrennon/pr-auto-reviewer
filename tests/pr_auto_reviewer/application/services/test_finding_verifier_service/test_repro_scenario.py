from ._helpers import *


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

        verifier = FindingVerifierService(
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

