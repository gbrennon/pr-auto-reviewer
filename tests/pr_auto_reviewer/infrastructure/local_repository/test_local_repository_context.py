"""Tests for LocalRepositoryContext using FakeLocalRepository."""

from pathlib import Path


from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.local_repository.local_repository_context import (
    LocalRepositoryContext,
)
from tests.fakes.local_repository_fakes import FakeLocalRepository


class TestLocalRepositoryContextFetch:
    """Tests for LocalRepositoryContext.fetch()."""

    def test_fetch_with_no_clone_path_returns_defaults(self) -> None:
        """When no clone path is available, fetch returns a context with defaults."""
        repo = FakeLocalRepository(last_clone_path_return=None)
        ctx = LocalRepositoryContext(repo)

        result = ctx.fetch(PullRequestId(repository="owner/repo", number=1))

        assert result.architecture_hint == "unknown"
        assert result.conventions is None
        assert result.repository_structure is None
        assert result.python_version is None

    def test_fetch_with_clone_path_returns_populated_context(self) -> None:
        """When a clone path is available, fetch returns a populated context."""
        repo = FakeLocalRepository(
            last_clone_path_return=Path("/tmp/clone/repo"),
            list_tree_return=["src/main.py", "src/utils.py", "README.md"],
        )
        ctx = LocalRepositoryContext(repo)

        result = ctx.fetch(PullRequestId(repository="owner/repo", number=1))

        assert result.repository_structure is not None
        assert "src/main.py" in result.repository_structure

    def test_fetch_calls_list_tree_with_correct_ref(self) -> None:
        """list_tree is called with the repo path and target_branch ref."""
        repo = FakeLocalRepository(
            last_clone_path_return=Path("/tmp/clone/repo"),
        )
        ctx = LocalRepositoryContext(repo)

        ctx.fetch(PullRequestId(repository="owner/repo", number=1), target_branch="main")

        assert len(repo.list_tree_calls) == 1
        args, kwargs = repo.list_tree_calls[0]
        assert args[0] == Path("/tmp/clone/repo")
        assert kwargs["ref"] == "main"

    def test_fetch_defaults_ref_to_head_when_no_target_branch(self) -> None:
        """When target_branch is empty, list_tree uses HEAD as ref."""
        repo = FakeLocalRepository(
            last_clone_path_return=Path("/tmp/clone/repo"),
        )
        ctx = LocalRepositoryContext(repo)

        ctx.fetch(PullRequestId(repository="owner/repo", number=1))

        _, kwargs = repo.list_tree_calls[0]
        assert kwargs["ref"] == "HEAD"

    def test_fetch_gracefully_handles_list_tree_failure(self) -> None:
        """When list_tree raises, fetch returns defaults without crashing."""
        repo = FakeLocalRepository(
            last_clone_path_return=Path("/tmp/clone/repo"),
            list_tree_return=RuntimeError("git failed"),
        )
        ctx = LocalRepositoryContext(repo)

        result = ctx.fetch(PullRequestId(repository="owner/repo", number=1))

        assert result.architecture_hint == "unknown"
        assert result.repository_structure is None

    def test_fetch_reads_conventions_file_when_present(self) -> None:
        """When CONVENTIONS.md is in the tree, its content is read."""
        repo = FakeLocalRepository(
            last_clone_path_return=Path("/tmp/clone/repo"),
            list_tree_return=["src/main.py", "CONVENTIONS.md"],
            read_file_return="# Project Conventions\n- Use tabs",
        )
        ctx = LocalRepositoryContext(repo)

        result = ctx.fetch(PullRequestId(repository="owner/repo", number=1))

        assert result.conventions == "# Project Conventions\n- Use tabs"
        assert len(repo.read_file_calls) == 1

    def test_fetch_reads_architecture_file_when_present(self) -> None:
        """When ARCHITECTURE.md is in the tree, its content is read."""
        repo = FakeLocalRepository(
            last_clone_path_return=Path("/tmp/clone/repo"),
            list_tree_return=["src/main.py", "ARCHITECTURE.md"],
            read_file_return="# Architecture\nHexagonal",
        )
        ctx = LocalRepositoryContext(repo)

        result = ctx.fetch(PullRequestId(repository="owner/repo", number=1))

        assert result.conventions == "# Architecture\nHexagonal"

    def test_fetch_skips_conventions_read_on_failure(self) -> None:
        """When reading a conventions file raises, it is skipped gracefully."""
        repo = FakeLocalRepository(
            last_clone_path_return=Path("/tmp/clone/repo"),
            list_tree_return=["src/main.py", "CONVENTIONS.md"],
            read_file_return=RuntimeError("permission denied"),
        )
        ctx = LocalRepositoryContext(repo)

        result = ctx.fetch(PullRequestId(repository="owner/repo", number=1))

        assert result.conventions is None

    def test_fetch_no_conventions_file_returns_none(self) -> None:
        """When no conventions file is in the tree, conventions is None."""
        repo = FakeLocalRepository(
            last_clone_path_return=Path("/tmp/clone/repo"),
            list_tree_return=["src/main.py", "src/utils.py"],
        )
        ctx = LocalRepositoryContext(repo)

        result = ctx.fetch(PullRequestId(repository="owner/repo", number=1))

        assert result.conventions is None
        assert len(repo.read_file_calls) == 0


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
