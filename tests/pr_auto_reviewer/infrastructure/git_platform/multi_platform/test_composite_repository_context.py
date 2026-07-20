"""Tests for CompositeRepositoryContext using stub port implementations."""

import pytest

from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_repository_context import (
    CompositeRepositoryContext,
)


class _StubRepositoryContext(RepositoryContextPort):
    """Stub context fetcher that records calls and returns canned data."""

    def __init__(self, repo_context: RepositoryContext) -> None:
        self.fetch_calls: list[PullRequestId] = []
        self.fetch_target_branches: list[str] = []
        self._repo_context = repo_context

    def fetch(self, pr_id: PullRequestId, target_branch: str = "") -> RepositoryContext:
        self.fetch_calls.append(pr_id)
        self.fetch_target_branches.append(target_branch)
        return self._repo_context

    def build_fragment_context(
        self,
        repo_context: RepositoryContext,
        file_paths: list[str],
        commit_messages: list[str] | None = None,
    ) -> tuple[str, str | None]:
        return ("fragment-content", "base-sha-abc")


class TestCompositeRepositoryContext:
    def test_fetch_routes_to_correct_platform(self):
        github_ctx = _StubRepositoryContext(
            RepositoryContext(architecture_hint="github-arch")
        )
        forgejo_ctx = _StubRepositoryContext(
            RepositoryContext(architecture_hint="forgejo-arch")
        )
        composite = CompositeRepositoryContext({
            "github": github_ctx,
            "forgejo": forgejo_ctx,
        })

        gh_result = composite.fetch(
            PullRequestId(repository="github:owner/repo", number=1)
        )
        fj_result = composite.fetch(
            PullRequestId(repository="codeberg:org/proj", number=2)
        )

        assert gh_result.architecture_hint == "github-arch"
        assert fj_result.architecture_hint == "forgejo-arch"
        assert len(github_ctx.fetch_calls) == 1
        assert len(forgejo_ctx.fetch_calls) == 1

    def test_fetch_defaults_to_forgejo_without_prefix(self):
        forgejo_ctx = _StubRepositoryContext(
            RepositoryContext(architecture_hint="forgejo-arch")
        )
        composite = CompositeRepositoryContext({"forgejo": forgejo_ctx})

        result = composite.fetch(
            PullRequestId(repository="owner/repo", number=1)
        )

        assert result.architecture_hint == "forgejo-arch"
        assert len(forgejo_ctx.fetch_calls) == 1
        assert forgejo_ctx.fetch_calls[0].repository == "owner/repo"

    def test_fetch_raises_for_unknown_platform(self):
        composite = CompositeRepositoryContext({})

        with pytest.raises(ValueError, match="No repository context for platform"):
            composite.fetch(
                PullRequestId(repository="unknown:owner/repo", number=1)
            )

    def test_build_fragment_context_delegates_to_forgejo(self):
        forgejo_ctx = _StubRepositoryContext(
            RepositoryContext(architecture_hint="forgejo-arch")
        )
        composite = CompositeRepositoryContext({"forgejo": forgejo_ctx})

        repo_ctx = RepositoryContext(architecture_hint="test-arch")
        result = composite.build_fragment_context(
            repo_ctx, ["a.py", "b.py"], ["fix: stuff"]
        )

        assert result[0] == "fragment-content"
        assert result[1] == "base-sha-abc"


class TestBranchThreading:
    """Verify target_branch flows from CompositeRepositoryContext.fetch()
    through to platform-specific adapters."""

    def test_target_branch_passthrough_to_platform(self):
        stub = _StubRepositoryContext(
            RepositoryContext(architecture_hint="test-arch")
        )
        composite = CompositeRepositoryContext({"forgejo": stub})

        result = composite.fetch(
            PullRequestId(repository="org/repo", number=3),
            target_branch="develop",
        )

        assert result.architecture_hint == "test-arch"
        assert len(stub.fetch_calls) == 1
        assert stub.fetch_target_branches == ["develop"]

    def test_target_branch_defaults_to_empty_string(self):
        stub = _StubRepositoryContext(
            RepositoryContext(architecture_hint="test-arch")
        )
        composite = CompositeRepositoryContext({"forgejo": stub})

        composite.fetch(PullRequestId(repository="org/repo", number=1))

        assert stub.fetch_target_branches == [""]
