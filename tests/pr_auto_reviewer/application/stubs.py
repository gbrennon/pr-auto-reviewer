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

    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        self.find_calls.append(pr_id)
        return self._pr

    def save(self, pr: PullRequest) -> None:
        self.save_calls.append(pr)
        self._pr = pr


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

    def fetch(self, pr_id: PullRequestId) -> RepositoryContext:
        self.fetch_calls.append(pr_id)
        return self._ctx


class StubLlmReview(LlmReviewPort):
    def __init__(self, review: CodeReview) -> None:
        self._review = review
        self.review_calls: list[tuple[PullRequestDiff, RepositoryContext]] = []

    def review(self, diff: PullRequestDiff, ctx: RepositoryContext) -> CodeReview:
        self.review_calls.append((diff, ctx))
        return self._review


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
