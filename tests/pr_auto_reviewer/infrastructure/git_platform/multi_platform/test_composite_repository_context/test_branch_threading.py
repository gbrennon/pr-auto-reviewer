from ._helpers import *


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

