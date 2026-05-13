import pytest
from pr_auto_reviewer.domain import RepositoryContext


class TestRepositoryContext:
    """Tests for RepositoryContext value object."""

    def test_creation_with_all_fields(self) -> None:
        ctx = RepositoryContext(
            architecture_hint="hexagonal",
            conventions="# Project Conventions",
            repository_structure="src/\n  main.py",
        )
        assert ctx.architecture_hint == "hexagonal"
        assert ctx.conventions == "# Project Conventions"
        assert ctx.repository_structure == "src/\n  main.py"

    def test_creation_minimal(self) -> None:
        ctx = RepositoryContext(architecture_hint="unknown")
        assert ctx.architecture_hint == "unknown"
        assert ctx.conventions is None
        assert ctx.repository_structure is None

    def test_equality_same(self) -> None:
        a = RepositoryContext(architecture_hint="hexagonal")
        b = RepositoryContext(architecture_hint="hexagonal")
        assert a == b

    def test_equality_different_hint(self) -> None:
        a = RepositoryContext(architecture_hint="hexagonal")
        b = RepositoryContext(architecture_hint="mvc")
        assert a != b

    def test_equality_different_conventions(self) -> None:
        a = RepositoryContext(architecture_hint="hexagonal", conventions="A")
        b = RepositoryContext(architecture_hint="hexagonal", conventions="B")
        assert a != b

    def test_immutability(self) -> None:
        ctx = RepositoryContext(architecture_hint="hexagonal")
        with pytest.raises(Exception):
            ctx.architecture_hint = "changed"  # type: ignore[misc]

    def test_hash_consistency(self) -> None:
        ctx = RepositoryContext(architecture_hint="hexagonal", conventions="test")
        assert hash(ctx) == hash(ctx)
