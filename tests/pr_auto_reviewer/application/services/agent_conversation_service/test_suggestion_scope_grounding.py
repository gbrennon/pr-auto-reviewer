from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.agent_conversation_service import (
    AgentConversationService,
)
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.turn_kind import TurnKind
from pr_auto_reviewer.domain.value_objects.turn_parse_result import TurnParseResult


class TestSuggestionScopeGrounding:
    """Suggestion citations require safe targets and changed-file evidence."""

    @staticmethod
    def _result_with_suggestions(
        metadata: dict[str, Any],
        repo_path: Path,
        changed_files: list[str],
    ) -> PhaseResult:
        service = AgentConversationService(
            chat_port=MagicMock(), command_bus=MagicMock(), max_turns=10,
        )
        parsed = TurnParseResult(
            kind=TurnKind.VERDICT, raw_items=[], metadata=metadata,
        )
        return service._build_phase_result(
            parsed, repo_path=repo_path, changed_files=changed_files,
        )

    def test_changed_file_suggestion_survives(self, tmp_path: Path) -> None:
        changed_file = tmp_path / "pyproject.toml"
        changed_file.write_text("[project]\n")

        result = self._result_with_suggestions(
            {
                "verdict": "approved",
                "suggestions": [
                    {
                        "file": "pyproject.toml",
                        "description": "Keep the project metadata in this file.",
                    },
                ],
            },
            tmp_path,
            ["pyproject.toml"],
        )

        assert result.llm_suggestions[0]["file"] == "pyproject.toml"

    def test_related_unchanged_file_suggestion_survives(self, tmp_path: Path) -> None:
        changed_file = tmp_path / "pyproject.toml"
        changed_file.write_text("[project]\n")
        target_file = tmp_path / "src" / "config.py"
        target_file.parent.mkdir()
        target_file.write_text("CONFIG = {}\n")

        result = self._result_with_suggestions(
            {
                "verdict": "approved",
                "suggestions": [
                    {
                        "file": "src/config.py",
                        "description": (
                            "The pyproject.toml configuration is loaded by this "
                            "module; centralize the settings boundary."
                        ),
                    },
                ],
            },
            tmp_path,
            ["pyproject.toml"],
        )

        assert result.llm_suggestions[0]["file"] == "src/config.py"

    def test_unrelated_unchanged_file_suggestion_is_dropped(
        self, tmp_path: Path,
    ) -> None:
        changed_file = tmp_path / "pyproject.toml"
        changed_file.write_text("[project]\n")
        target_file = tmp_path / "src" / "config.py"
        target_file.parent.mkdir()
        target_file.write_text("CONFIG = {}\n")

        result = self._result_with_suggestions(
            {
                "verdict": "approved",
                "suggestions": [
                    {
                        "file": "src/config.py",
                        "description": "Centralize the settings boundary.",
                    },
                ],
            },
            tmp_path,
            ["pyproject.toml"],
        )

        assert result.llm_suggestions == []

    def test_fileless_repository_wide_suggestion_survives(
        self, tmp_path: Path,
    ) -> None:
        result = self._result_with_suggestions(
            {
                "verdict": "approved",
                "suggestions": [
                    {
                        "file": "",
                        "description": (
                            "Adopt one dependency direction across the repository."
                        ),
                    },
                ],
            },
            tmp_path,
            ["pyproject.toml"],
        )

        assert result.llm_suggestions[0]["file"] == ""

    def test_nonexistent_suggestion_target_is_dropped(self, tmp_path: Path) -> None:
        result = self._result_with_suggestions(
            {
                "verdict": "approved",
                "suggestions": [
                    {
                        "file": "src/missing.py",
                        "description": "The pyproject.toml configuration is related.",
                    },
                ],
            },
            tmp_path,
            ["pyproject.toml"],
        )

        assert result.llm_suggestions == []

    def test_outside_suggestion_target_is_dropped(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / ("outside-" + tmp_path.name)
        outside.mkdir()
        outside_file = outside / "secret.py"
        outside_file.write_text("x = 1\n")

        result = self._result_with_suggestions(
            {
                "verdict": "approved",
                "suggestions": [
                    {
                        "file": str(outside_file),
                        "description": "The pyproject.toml configuration is related.",
                    },
                ],
            },
            tmp_path,
            ["pyproject.toml"],
        )

        assert result.llm_suggestions == []

    def test_parent_escape_suggestion_target_is_dropped(self, tmp_path: Path) -> None:
        escape_target = tmp_path.parent / "escape-target.py"
        escape_target.write_text("x = 1\n")

        result = self._result_with_suggestions(
            {
                "verdict": "approved",
                "suggestions": [
                    {
                        "file": "../escape-target.py",
                        "description": "The pyproject.toml configuration is related.",
                    },
                ],
            },
            tmp_path,
            ["pyproject.toml"],
        )

        assert result.llm_suggestions == []
