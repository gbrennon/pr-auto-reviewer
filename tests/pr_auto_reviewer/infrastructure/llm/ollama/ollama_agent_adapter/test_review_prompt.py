from ._helpers import *


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

        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED
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
