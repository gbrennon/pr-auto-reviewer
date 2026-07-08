"""Integration tests for FileSystemFragmentRepository — REAL files, NO mocks."""

from pathlib import Path

import pytest

from pr_auto_reviewer.infrastructure.fragments.repositories import (
    FileSystemFragmentRepository,
)

class TestFileSystemFragmentRepository:
    """Integration tests using real fragment files from disk."""

    @pytest.fixture
    def fixtures_dir(self) -> Path:
        """Path to the real test fragments directory."""
        return (
            Path(__file__).parent.parent.parent.parent / "fixtures" / "fragments"
        )

    @pytest.fixture
    def repository(
        self, fixtures_dir: Path,
    ) -> FileSystemFragmentRepository:
        """Create repository pointing to real test fixture files."""
        return FileSystemFragmentRepository(base_path=fixtures_dir)

    def test_creates_repository_with_valid_path(
        self, fixtures_dir: Path,
    ) -> None:
        """Repository should initialize with an existing base path."""
        repo = FileSystemFragmentRepository(base_path=fixtures_dir)

        assert repo.base_path == fixtures_dir

    def test_rejects_nonexistent_path(self) -> None:
        """Repository should raise ValueError for non-existent base path."""
        with pytest.raises(ValueError, match="base_path does not exist"):
            FileSystemFragmentRepository(base_path=Path("/nonexistent/path"))

    def test_rejects_file_as_base_path(self, fixtures_dir: Path) -> None:
        """Repository should reject a file path (requires directory)."""
        some_file = fixtures_dir / "python" / "error-handling.md"

        with pytest.raises(ValueError, match="must be a directory"):
            FileSystemFragmentRepository(base_path=some_file)

    def test_finds_fragments_by_language(
        self, repository: FileSystemFragmentRepository,
    ) -> None:
        """Repository should load all fragments for a given language."""
        fragments = repository.find_by_language("python")

        assert len(fragments) == 1
        assert fragments[0].id == "python-error-handling"
        assert fragments[0].language == "python"
        assert fragments[0].priority == 80
        assert fragments[0].category == "error-handling"
        assert "Python Error Handling" in fragments[0].content

    def test_finds_multiple_fragments_for_language(
        self,
        repository: FileSystemFragmentRepository,
        fixtures_dir: Path,
    ) -> None:
        """Repository should load all fragments when multiple exist."""
        second = fixtures_dir / "python" / "idioms.md"
        second.write_text(
            "---\n"
            "id: python-idioms\n"
            "language: python\n"
            "priority: 70\n"
            "category: idioms\n"
            "---\n\n"
            "# Python Idioms\n\n"
            "Use list comprehensions over map/filter.\n"
        )

        try:
            fragments = repository.find_by_language("python")

            assert len(fragments) == 2
            ids = {f.id for f in fragments}
            assert ids == {"python-error-handling", "python-idioms"}
            assert fragments[0].id == "python-error-handling"
            assert fragments[1].id == "python-idioms"
        finally:
            second.unlink()

    def test_returns_empty_list_for_unknown_language(
        self, repository: FileSystemFragmentRepository,
    ) -> None:
        """Repository should return empty list when language dir is missing."""
        fragments = repository.find_by_language("pascal")

        assert fragments == []

    def test_finds_go_fragments(
        self, repository: FileSystemFragmentRepository,
    ) -> None:
        """Repository should load Go fragments correctly."""
        fragments = repository.find_by_language("go")

        assert len(fragments) == 1
        assert fragments[0].id == "go-concurrency"
        assert fragments[0].language == "go"
        assert fragments[0].priority == 85
        assert "Go Concurrency" in fragments[0].content

    def test_finds_universal_fragments(
        self, repository: FileSystemFragmentRepository,
    ) -> None:
        """Repository should load language-agnostic universal fragments."""
        fragments = repository.find_universal()

        assert len(fragments) == 1
        assert fragments[0].id == "solid-principles"
        assert fragments[0].language is None

    def test_finds_fragment_by_id(
        self, repository: FileSystemFragmentRepository,
    ) -> None:
        """Repository should find a specific fragment by ID."""
        fragment = repository.find_by_id("python-error-handling")

        assert fragment is not None
        assert fragment.id == "python-error-handling"
        assert fragment.language == "python"

    def test_finds_universal_fragment_by_id(
        self, repository: FileSystemFragmentRepository,
    ) -> None:
        """Repository should find universal fragments by ID."""
        fragment = repository.find_by_id("solid-principles")

        assert fragment is not None
        assert fragment.id == "solid-principles"
        assert fragment.is_universal()

    def test_returns_none_for_nonexistent_id(
        self, repository: FileSystemFragmentRepository,
    ) -> None:
        """Repository should return None when ID does not exist."""
        fragment = repository.find_by_id("nonexistent-id")

        assert fragment is None

    def test_handles_malformed_yaml_gracefully(
        self,
        repository: FileSystemFragmentRepository,
        fixtures_dir: Path,
    ) -> None:
        """Repository should skip files with malformed YAML (no crash)."""
        bad_file = fixtures_dir / "python" / "malformed.md"
        bad_file.write_text(
            "---\n"
            "id: malformed\n"
            "this is not valid yaml: [\n"
            "---\n\n"
            "Content here\n"
        )

        try:
            fragments = repository.find_by_language("python")

            assert all(f.id != "malformed" for f in fragments)
            assert any(f.id == "python-error-handling" for f in fragments)
        finally:
            bad_file.unlink()

    def test_handles_missing_required_fields(
        self,
        repository: FileSystemFragmentRepository,
        fixtures_dir: Path,
    ) -> None:
        """Repository should skip fragments missing the required 'id' field."""
        incomplete = fixtures_dir / "python" / "incomplete.md"
        incomplete.write_text(
            "---\n"
            "language: python\n"
            "---\n\n"
            "Content without ID\n"
        )

        try:
            fragments = repository.find_by_language("python")

            assert all(f.id != "" for f in fragments)
            assert len(fragments) >= 1
        finally:
            incomplete.unlink()

    def test_skips_non_markdown_files(
        self,
        repository: FileSystemFragmentRepository,
        fixtures_dir: Path,
    ) -> None:
        """Repository should only process .md files."""
        txt_file = fixtures_dir / "python" / "notes.txt"
        txt_file.write_text("not a fragment")

        try:
            fragments = repository.find_by_language("python")

            assert len(fragments) == 1
        finally:
            txt_file.unlink()

    def test_handles_file_without_yaml_front_matter(
        self,
        repository: FileSystemFragmentRepository,
        fixtures_dir: Path,
    ) -> None:
        """Repository should skip .md files that lack YAML front matter."""
        no_yaml = fixtures_dir / "python" / "no-frontmatter.md"
        no_yaml.write_text("# Just markdown\n\nNo front matter here.\n")

        try:
            fragments = repository.find_by_language("python")

            assert len(fragments) == 1
            assert fragments[0].id == "python-error-handling"
        finally:
            no_yaml.unlink()

    def test_returns_fragments_sorted_by_priority_descending(
        self,
        repository: FileSystemFragmentRepository,
        fixtures_dir: Path,
    ) -> None:
        """Repository should sort fragments by priority (highest first)."""
        low = fixtures_dir / "python" / "low-prio.md"
        low.write_text(
            "---\n"
            "id: python-low\n"
            "language: python\n"
            "priority: 10\n"
            "category: test\n"
            "---\n\n"
            "# Low priority\n"
        )

        try:
            fragments = repository.find_by_language("python")

            assert len(fragments) == 2
            assert fragments[0].priority >= fragments[1].priority
        finally:
            low.unlink()

    def test_returns_empty_list_when_no_universal_dir(
        self, tmp_path: Path,
    ) -> None:
        """Repository should return [] when universal/ dir is missing."""
        repo = FileSystemFragmentRepository(base_path=tmp_path)

        fragments = repo.find_universal()

        assert fragments == []
