from ._helpers import *


class TestLocalRepositoryContextBuildFragmentContext:
    """Tests for LocalRepositoryContext.build_fragment_context()."""

    def test_build_fragment_context_returns_language_and_serialized(self) -> None:
        """Returns a (language, serialized_context) tuple."""
        repo = FakeLocalRepository()
        ctx = LocalRepositoryContext(repo)
        repo_ctx = RepositoryContext(
            architecture_hint="hexagonal",
            conventions="# Rules",
            repository_structure="src/main.py\nsrc/utils.py",
        )

        language, serialized = ctx.build_fragment_context(
            repo_ctx, file_paths=["src/main.py", "src/utils.py"],
        )

        assert isinstance(language, str)
        assert language != ""
        assert serialized is not None
        assert "hexagonal" in serialized

    def test_build_fragment_context_includes_commit_messages(self) -> None:
        """Commit messages are included in the serialized context."""
        repo = FakeLocalRepository()
        ctx = LocalRepositoryContext(repo)
        repo_ctx = RepositoryContext(
            architecture_hint="layered",
            repository_structure="src/main.py",
        )

        _language, serialized = ctx.build_fragment_context(
            repo_ctx,
            file_paths=["src/main.py"],
            commit_messages=["feat: add login", "fix: typo"],
        )

        assert serialized is not None
        assert "feat: add login" in serialized
        assert "fix: typo" in serialized

    def test_build_fragment_context_defaults_python_version(self) -> None:
        """When language is python and no version is set, defaults to 3.9."""
        repo = FakeLocalRepository()
        ctx = LocalRepositoryContext(repo)
        repo_ctx = RepositoryContext(
            architecture_hint="hexagonal",
            repository_structure="src/main.py",
        )

        _language, serialized = ctx.build_fragment_context(
            repo_ctx, file_paths=["src/main.py"],
        )

        assert serialized is not None
        assert "Python 3.9" in serialized

    def test_build_fragment_context_respects_explicit_python_version(self) -> None:
        """When python_version is explicitly set, it is used."""
        repo = FakeLocalRepository()
        ctx = LocalRepositoryContext(repo)
        repo_ctx = RepositoryContext(
            architecture_hint="hexagonal",
            repository_structure="src/main.py",
            python_version="3.12",
        )

        _language, serialized = ctx.build_fragment_context(
            repo_ctx, file_paths=["src/main.py"],
        )
        assert serialized is not None
        assert "Python 3.12" in serialized

