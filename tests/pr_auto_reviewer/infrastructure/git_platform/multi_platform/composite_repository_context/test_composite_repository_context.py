from ._helpers import *


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

