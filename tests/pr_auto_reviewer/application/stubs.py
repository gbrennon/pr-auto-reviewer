"""Test stubs implementing outbound ports for application-layer tests.

Each stub implements a real Protocol, accepts controlled data,
and tracks invocations with plain lists — no MagicMock.
"""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.pull_request_repository import (
    PullRequestRepository,
)
from pr_auto_reviewer.application.ports.outbound.changeset_fetcher_port import (
    ChangesetFetcherPort,
)
from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
)
from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.application.ports.outbound.compose_review_prompt_port import (
    ComposeReviewPromptPort,
)
from pr_auto_reviewer.application.ports.outbound.review_context_factory_port import (
    ReviewContextFactoryPort,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext
from pr_auto_reviewer.application.ports.outbound.review_reader_port import (
    ReviewReaderPort,
)
from pr_auto_reviewer.application.ports.outbound.comment_reader_port import (
    CommentReaderPort,
)
from pr_auto_reviewer.application.ports.outbound.comment_publisher_port import (
    CommentPublisherPort,
)
from pr_auto_reviewer.application.ports.outbound.issue_tracker_port import (
    IssueTrackerPort,
)
from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext

class StubPullRequestRepository(PullRequestRepository):
    """Controlled PR persistence: returns a fixed PR and records calls."""

    def __init__(self, initial: PullRequest | None = None) -> None:
        self._pr = initial
        self.find_calls: list[PullRequestId] = []
        self.save_calls: list[PullRequest] = []
        self.reset_calls: int = 0

    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        self.find_calls.append(pr_id)
        return self._pr

    def save(self, pr: PullRequest) -> None:
        self.save_calls.append(pr)
        self._pr = pr

    def reset(self) -> None:
        self.reset_calls += 1
        self._pr = None

class StubChangesetFetcher(ChangesetFetcherPort):
    """Returns a fixed PullRequestDiff, tracks call count."""

    def __init__(self, diff: PullRequestDiff) -> None:
        self._diff = diff
        self.fetch_calls: list[tuple[PullRequestId, CommitSha]] = []

    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        self.fetch_calls.append((pr_id, sha))
        return self._diff

class StubRepositoryContext(RepositoryContextPort):
    def __init__(self, ctx: RepositoryContext | None = None) -> None:
        self._ctx = ctx or RepositoryContext(architecture_hint="")
        self.fetch_calls: list[PullRequestId] = []
        self.build_fragment_context_calls: list[
            tuple[RepositoryContext, list[str]]
        ] = []

    def fetch(self, pr_id: PullRequestId) -> RepositoryContext:
        self.fetch_calls.append(pr_id)
        return self._ctx

    def build_fragment_context(
        self,
        repo_context: RepositoryContext,
        file_paths: list[str],
        commit_messages: list[str] | None = None,
    ) -> tuple[str, str | None]:
        self.build_fragment_context_calls.append(
            (repo_context, file_paths, commit_messages)
        )
        language = "python"
        parts: list[str] = []
        if repo_context.architecture_hint:
            parts.append(f"## Architecture: {repo_context.architecture_hint}")
        if repo_context.conventions:
            parts.append(f"## Conventions\n{repo_context.conventions}")
        if repo_context.pr_title:
            parts.append(f"## PR Title\n{repo_context.pr_title}")
        if repo_context.pr_description:
            parts.append(f"## PR Description\n{repo_context.pr_description}")
        if commit_messages:
            messages = "\n".join(f"- {msg}" for msg in commit_messages)
            parts.append(f"## Commit Messages\n{messages}")
        serialized = "\n\n".join(parts) if parts else None
        return language, serialized

class StubLlmReview(LlmReviewPort):
    def __init__(self, review: CodeReview) -> None:
        self._review = review
        self.review_calls: list[tuple[PullRequestDiff, RepositoryContext]] = []
        self.review_prompt_calls: list = []

    def review(self, diff: PullRequestDiff, ctx: RepositoryContext) -> CodeReview:
        self.review_calls.append((diff, ctx))
        return self._review

    def review_prompt(self, prompt) -> CodeReview:
        self.review_prompt_calls.append(prompt)
        return self._review

class StubComposeReviewPrompt(ComposeReviewPromptPort):
    def __init__(self, prompt: ComposedPrompt | None = None) -> None:
        self._prompt = prompt or ComposedPrompt(
            content="You are a code reviewer.\n\nReview this diff:\n+code",
            fragments_used=["solid", "python-errors"],
            total_tokens=100,
        )
        self.execute_calls: list[ReviewContext] = []

    def execute(self, context: ReviewContext) -> ComposedPrompt:
        self.execute_calls.append(context)
        return self._prompt

class StubReviewContextFactory(ReviewContextFactoryPort):
    def __init__(self, prompt: ComposedPrompt | None = None) -> None:
        self._prompt = prompt
        self.build_calls: list = []

    def build(
        self,
        pr_id: PullRequestId,
        diff: PullRequestDiff,
        pr_title: str | None = None,
        pr_description: str | None = None,
    ) -> ComposedPrompt:
        self.build_calls.append((pr_id, diff, pr_title, pr_description))
        if self._prompt is not None:
            return self._prompt
        parts = [
            "You are a Senior Principal Software Engineer and Code Reviewer.",
            "",
            "Review the following diff and report issues as JSON:",
            "",
            "```diff",
            diff.diff_content,
            "```",
        ]
        if pr_title:
            parts.insert(2, f"PR Title: {pr_title}")
        if pr_description:
            parts.insert(3, f"PR Description: {pr_description}")
        content = "\n".join(parts)
        return ComposedPrompt(
            content=content,
            fragments_used=["solid", "python-errors"],
            total_tokens=len(content) // 4,
        )

class StubReviewPublisher(ReviewPublisherPort):
    def __init__(self) -> None:
        self.publish_calls: list[tuple[PullRequestId, CodeReview]] = []

    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None:
        self.publish_calls.append((pr_id, review))

class StubReviewReader(ReviewReaderPort):
    def __init__(self, body: str | None = None) -> None:
        self._body = body
        self.get_latest_review_calls: list[PullRequestId] = []

    def get_latest_review(self, pr_id: PullRequestId) -> str | None:
        self.get_latest_review_calls.append(pr_id)
        return self._body

class StubCommentReader(CommentReaderPort):
    def __init__(self, comments: list[PrComment] | None = None) -> None:
        self._comments = comments or []
        self.get_comments_calls: list[PullRequestId] = []

    def get_comments(self, pr_id: PullRequestId) -> list[PrComment]:
        self.get_comments_calls.append(pr_id)
        return list(self._comments)

class StubCommentPublisher(CommentPublisherPort):
    def __init__(self) -> None:
        self.post_calls: list[tuple[PullRequestId, str]] = []

    def post(self, pr_id: PullRequestId, body: str) -> None:
        self.post_calls.append((pr_id, body))

class StubIssueTracker(IssueTrackerPort):
    def __init__(self, issues_to_return: list[Issue] | None = None) -> None:
        self._issues = issues_to_return or []
        self._next = 0
        self.create_calls: list[tuple[str, str, str]] = []

    def create(self, repository: str, title: str, body: str) -> Issue:
        self.create_calls.append((repository, title, body))
        if self._next < len(self._issues):
            issue = self._issues[self._next]
            self._next += 1
            return issue
        return Issue(
            id=999, repository=repository, title=title, body=body,
            source_pr_id=PullRequestId(repository=repository, number=1),
            source_item_number=0,
        )
