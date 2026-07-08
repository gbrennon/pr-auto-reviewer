"""Tests for CompositeChangesetFetcher using real port implementations."""

import pytest

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_changeset_fetcher import (
    CompositeChangesetFetcher,
)
from tests.fixtures.composite_fixtures import RecordingChangesetFetcher


class TestCompositeChangesetFetcher:
    def test_fetch_routes_to_github_fetcher(self):
        github_fetcher = RecordingChangesetFetcher("github diff")
        forgejo_fetcher = RecordingChangesetFetcher("forgejo diff")
        composite = CompositeChangesetFetcher(github_fetcher, forgejo_fetcher)

        pr_id = PullRequestId(repository="github:owner/repo", number=1)
        sha = CommitSha("abc123")

        diff = composite.fetch(pr_id, sha)
        assert diff.diff_content == "github diff"
        assert len(github_fetcher.fetch_calls) == 1
        assert len(forgejo_fetcher.fetch_calls) == 0

    def test_fetch_routes_to_forgejo_fetcher(self):
        github_fetcher = RecordingChangesetFetcher("github diff")
        forgejo_fetcher = RecordingChangesetFetcher("forgejo diff")
        composite = CompositeChangesetFetcher(github_fetcher, forgejo_fetcher)

        pr_id = PullRequestId(repository="codeberg:org/proj", number=2)
        sha = CommitSha("def456")

        diff = composite.fetch(pr_id, sha)
        assert diff.diff_content == "forgejo diff"
        assert len(forgejo_fetcher.fetch_calls) == 1
        assert len(github_fetcher.fetch_calls) == 0

    def test_fetch_defaults_to_forgejo_without_prefix(self):
        github_fetcher = RecordingChangesetFetcher("github diff")
        forgejo_fetcher = RecordingChangesetFetcher("forgejo diff")
        composite = CompositeChangesetFetcher(github_fetcher, forgejo_fetcher)

        pr_id = PullRequestId(repository="owner/repo", number=1)
        sha = CommitSha("abc123")

        diff = composite.fetch(pr_id, sha)
        assert diff.diff_content == "forgejo diff"
        assert len(forgejo_fetcher.fetch_calls) == 1

    def test_fetch_raises_for_unknown_platform(self):
        github_fetcher = RecordingChangesetFetcher()
        forgejo_fetcher = RecordingChangesetFetcher()
        composite = CompositeChangesetFetcher(github_fetcher, forgejo_fetcher)

        pr_id = PullRequestId(repository="gitlab:owner/repo", number=1)
        sha = CommitSha("abc123")

        with pytest.raises(ValueError, match="Unknown platform"):
            composite.fetch(pr_id, sha)
