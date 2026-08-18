"""Behavioral tests for OllamaAgentAdapter."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from pr_auto_reviewer.domain.agent.review_plan import ReviewPlan
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
    ComposedPrompt,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_agent_adapter import (
    OllamaAgentAdapter,
)
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_chat_client import (
    OllamaChatClient,
)


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.command: RunMultiPhaseReviewCommand | None = None

    def execute(self, command: RunMultiPhaseReviewCommand) -> CodeReview:
        self.command = command
        return CodeReview(
            verdict=ReviewVerdict.COMMENTED,
            reason="ran",
            summary="",
            items=[],
            suggestions=[],
            praise=[],
            model_used="code-review:latest",
        )


def _adapter(orchestrator=None) -> OllamaAgentAdapter:
    chat_client = cast(OllamaChatClient, SimpleNamespace(_model="code-review:latest"))
    plan = ReviewPlan(phases=(), methodology="m")
    return OllamaAgentAdapter(chat_client, orchestrator or _FakeOrchestrator(), plan)


class TestExtractFileListing:
    """Exercises the diff-section path extractor."""

    def test_extract_when_diff_section_then_paths(self) -> None:
        content = (
            "## Diff\n\n"
            "--- a/src/app.py\n"
            "+++ b/src/main.py\n"
            "+++ b/foo/bar.txt\n"
        )
        adapter = _adapter()

        assert adapter._extract_file_listing(content) == [
            "foo/bar.txt",
            "src/app.py",
            "src/main.py",
        ]

    def test_extract_when_dev_null_then_skipped(self) -> None:
        content = "## Diff\n--- /dev/null\n+++ b/new.py\n"
        adapter = _adapter()

        assert adapter._extract_file_listing(content) == ["new.py"]

    def test_extract_when_no_diff_section_then_empty(self) -> None:
        assert _adapter()._extract_file_listing("plain content") == []

    def test_extract_when_prefixes_without_slashes_then_kept(self) -> None:
        content = "## Diff\n--- a/readme.md\n+++ b/generated.yaml\n"
        adapter = _adapter()

        assert adapter._extract_file_listing(content) == ["generated.yaml", "readme.md"]


class TestReviewPrompt:
    """Exercises the staged multi-phase orchestration."""

    def test_review_when_called_then_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            _adapter().review(object(), object())

    def test_review_prompt_when_missing_repo_path_then_raises(self) -> None:
        prompt = ComposedPrompt(content="x", fragments_used=[], total_tokens=1)

        with pytest.raises(ValueError):
            _adapter().review_prompt(prompt)

    def test_review_prompt_when_repo_then_builds_command(self) -> None:
        orchestrator = _FakeOrchestrator()
        adapter = _adapter(orchestrator)
        prompt = ComposedPrompt(
            content="## Diff\n--- a/src/a.py\n+++ b/src/b.py\n",
            fragments_used=[],
            total_tokens=1,
            repo_path="/tmp/repo",
        )

        review = adapter.review_prompt(prompt)

        assert review.verdict == ReviewVerdict.COMMENTED
        assert isinstance(orchestrator.command, RunMultiPhaseReviewCommand)
        assert orchestrator.command.repo_path == Path("/tmp/repo")
        assert orchestrator.command.changed_files == ["src/a.py", "src/b.py"]
        assert orchestrator.command.model == "code-review:latest"

    def test_review_prompt_when_whitespace_repo_path_then_raises(self) -> None:
        prompt = ComposedPrompt(
            content="x", fragments_used=[], total_tokens=1, repo_path="   "
        )

        with pytest.raises(ValueError):
            _adapter().review_prompt(prompt)