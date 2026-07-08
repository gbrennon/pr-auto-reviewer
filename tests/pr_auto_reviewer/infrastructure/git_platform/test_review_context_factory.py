"""Behavioural tests for ReviewContextFactory — wired with real stubs."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.compose_review_prompt_port import (
    ComposeReviewPromptPort,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.context.review_context_factory import (
    ReviewContextFactory,
)
from tests.pr_auto_reviewer.application.stubs import StubRepositoryContext

class _SpyComposeReviewPrompt(ComposeReviewPromptPort):

    def __init__(self) -> None:
        self.execute_calls: list[ReviewContext] = []
        self._default = ComposedPrompt(
            content="Review this please.", fragments_used=["f1"], total_tokens=10,
        )

    def execute(self, context: ReviewContext) -> ComposedPrompt:
        self.execute_calls.append(context)
        return self._default

def _make_pr_id() -> PullRequestId:
    return PullRequestId(repository="test/repo", number=7)

_DEFAULT_FILE_CONTENTS = {"src/main.py": "def foo(): pass\n"}

def _make_diff(
    *, diff_content: str = "+def foo(): pass\n",
    file_contents: dict[str, str] | None = None,
    commit_messages: list[str] | None = None,
) -> PullRequestDiff:
    if file_contents is None:
        file_contents = _DEFAULT_FILE_CONTENTS
    if commit_messages is None:
        commit_messages = []
    return PullRequestDiff(
        pr_id=_make_pr_id(),
        head_sha=CommitSha(value="abc12345"),
        diff_content=diff_content,
        file_contents=file_contents,
        commit_messages=commit_messages,
    )

class TestReviewContextFactoryBuild:

    def test_returns_composed_prompt_from_compose_port(self) -> None:
        repo_ctx = StubRepositoryContext()
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)

        result = factory.build(_make_pr_id(), _make_diff())

        assert isinstance(result, ComposedPrompt)
        assert result.content == "Review this please."
        assert result.fragments_used == ["f1"]

    def test_fetches_repository_context_with_correct_pr_id(self) -> None:
        repo_ctx = StubRepositoryContext()
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)
        pr_id = _make_pr_id()

        factory.build(pr_id, _make_diff())

        assert repo_ctx.fetch_calls == [pr_id]

    def test_merges_pr_title_into_repository_context(self) -> None:
        repo_ctx = StubRepositoryContext()
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)

        factory.build(_make_pr_id(), _make_diff(), pr_title="My PR Title")

        merged_ctx, _files, _msgs = repo_ctx.build_fragment_context_calls[0]
        assert merged_ctx.pr_title == "My PR Title"

    def test_merges_pr_description_into_repository_context(self) -> None:
        repo_ctx = StubRepositoryContext()
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)

        factory.build(_make_pr_id(), _make_diff(), pr_description="Fixes bug #42")

        merged_ctx, _files, _msgs = repo_ctx.build_fragment_context_calls[0]
        assert merged_ctx.pr_description == "Fixes bug #42"

    def test_passes_commit_messages_to_build_fragment_context(self) -> None:
        repo_ctx = StubRepositoryContext()
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)
        msgs = ["fix: correct off-by-one", "refactor: extract helper"]

        factory.build(_make_pr_id(), _make_diff(commit_messages=msgs))

        _ctx, _files, received_msgs = repo_ctx.build_fragment_context_calls[0]
        assert received_msgs == msgs

    def test_passes_none_for_empty_commit_messages(self) -> None:
        repo_ctx = StubRepositoryContext()
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)

        factory.build(_make_pr_id(), _make_diff(commit_messages=[]))

        _ctx, _files, received_msgs = repo_ctx.build_fragment_context_calls[0]
        assert received_msgs is None

    def test_builds_review_context_with_correct_diff_content(self) -> None:
        repo_ctx = StubRepositoryContext()
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)

        factory.build(_make_pr_id(), _make_diff(diff_content="+def bar():\n    pass\n"))

        rctx = compose.execute_calls[0]
        assert rctx.diff == "+def bar():\n    pass\n"

    def test_builds_review_context_with_sorted_file_paths(self) -> None:
        repo_ctx = StubRepositoryContext()
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)

        factory.build(_make_pr_id(), _make_diff(file_contents={
            "z.py": "", "a.py": "", "m.py": "",
        }))

        rctx = compose.execute_calls[0]
        assert rctx.file_paths == ["a.py", "m.py", "z.py"]

    def test_builds_review_context_with_language_from_repository_context(self) -> None:
        repo_ctx = StubRepositoryContext()
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)

        factory.build(_make_pr_id(), _make_diff())

        rctx = compose.execute_calls[0]
        assert rctx.language == "python"

    def test_builds_review_context_with_serialized_repository_context(self) -> None:
        repo_ctx = StubRepositoryContext(
            ctx=RepositoryContext(architecture_hint="hexagonal", conventions="Use types"),
        )
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)

        factory.build(_make_pr_id(), _make_diff())

        rctx = compose.execute_calls[0]
        assert rctx.repository_context is not None
        assert "hexagonal" in rctx.repository_context
        assert "Use types" in rctx.repository_context

    def test_build_without_title_and_description_does_not_crash(self) -> None:
        """When pr_title and pr_description are omitted (None), the build must succeed."""
        repo_ctx = StubRepositoryContext()
        compose = _SpyComposeReviewPrompt()
        factory = ReviewContextFactory(repo_ctx, compose)

        result = factory.build(_make_pr_id(), _make_diff())

        assert isinstance(result, ComposedPrompt)
        assert compose.execute_calls[0].diff == "+def foo(): pass\n"

