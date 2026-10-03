from pathlib import Path
from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.agent_conversation_service import (
    AgentConversationService,
)
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.turn_kind import TurnKind
from pr_auto_reviewer.domain.value_objects.turn_parse_result import TurnParseResult


class TestCitationGrounding:
    """Praise and suggestion file citations are validated against the repo."""

    @staticmethod
    def _result_with_citations(
        metadata: dict, repo_path: Path,
    ) -> PhaseResult:
        service = AgentConversationService(
            chat_port=MagicMock(), command_bus=MagicMock(), max_turns=10,
        )
        parsed = TurnParseResult(
            kind=TurnKind.VERDICT, raw_items=[], metadata=metadata,
        )
        return service._build_phase_result(
            parsed, repo_path=repo_path, changed_files=[],
        )

    def test_praise_citing_nonexistent_file_is_dropped(
        self, tmp_path,
    ) -> None:
        result = self._result_with_citations({
            "verdict": "approved",
            "praise": [
                {
                    "file": "adapters/shallow_inbound.py",
                    "description": "great adapter",
                },
            ],
        }, repo_path=tmp_path)

        assert result.llm_praise == []

    def test_praise_citing_real_file_survives(self, tmp_path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("x = 1\n")
        result = self._result_with_citations({
            "verdict": "approved",
            "praise": [
                {
                    "file": "src/a.py",
                    "description": "clean module",
                },
            ],
        }, repo_path=tmp_path)

        assert len(result.llm_praise) == 1
        assert result.llm_praise[0]["file"] == "src/a.py"

    def test_suggestion_with_nonexistent_path_is_dropped(
        self, tmp_path,
    ) -> None:
        result = self._result_with_citations({
            "verdict": "approved",
            "suggestions": [
                {
                    "file": "ports/app_inbound.py",
                    "description": "add explicit interface definitions",
                },
            ],
        }, repo_path=tmp_path)

        assert result.llm_suggestions == []

    def test_praise_citing_existing_file_outside_repo_is_dropped(
        self, tmp_path,
    ) -> None:
        outside = tmp_path.parent / (
            "outside-" + tmp_path.name
        )
        outside.mkdir()
        (outside / "secret.py").write_text("x = 1\n")

        result = self._result_with_citations({
            "verdict": "approved",
            "praise": [
                {
                    "file": str(outside / "secret.py"),
                    "description": "great module",
                },
            ],
        }, repo_path=tmp_path)

        assert result.llm_praise == []

    def test_praise_citing_parent_escape_path_is_dropped(
        self, tmp_path,
    ) -> None:
        (tmp_path.parent / "escape-target.py").write_text("x = 1\n")

        result = self._result_with_citations({
            "verdict": "approved",
            "praise": [
                {
                    "file": "../escape-target.py",
                    "description": "great module",
                },
            ],
        }, repo_path=tmp_path)

        assert result.llm_praise == []
