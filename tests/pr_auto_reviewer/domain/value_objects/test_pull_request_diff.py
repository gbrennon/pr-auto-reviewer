from dataclasses import FrozenInstanceError

import pytest

from pr_auto_reviewer.domain import (
    CommitSha,
    PullRequestDiff,
    PullRequestId,
)


class TestPullRequestDiff:
    """Tests for PullRequestDiff value object."""

    def test_creation_with_all_fields(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        sha = CommitSha(value="abc123")
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=sha,
            diff_content="diff --git a/file b/file\n+foo\n-bar",
            file_contents={"src/main.py": "print('hello')"},
            repository_structure="src/\n  main.py",
            conventions="# Project Conventions\n...",
        )
        assert diff.pr_id == pr_id
        assert diff.head_sha == sha
        assert diff.diff_content == "diff --git a/file b/file\n+foo\n-bar"
        assert diff.file_contents == {"src/main.py": "print('hello')"}
        assert diff.repository_structure == "src/\n  main.py"
        assert diff.conventions == "# Project Conventions\n..."

    def test_creation_minimal(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=1)
        sha = CommitSha(value="abc")
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=sha,
            diff_content="",
        )
        assert diff.file_contents == {}
        assert diff.repository_structure is None
        assert diff.conventions is None

    def test_equality_same_values(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=1)
        sha = CommitSha(value="abc")
        a = PullRequestDiff(pr_id=pr_id, head_sha=sha, diff_content="diff")
        b = PullRequestDiff(pr_id=pr_id, head_sha=sha, diff_content="diff")
        assert a == b

    def test_equality_different_sha(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=1)
        a = PullRequestDiff(
            pr_id=pr_id, head_sha=CommitSha(value="abc"), diff_content="diff"
        )
        b = PullRequestDiff(
            pr_id=pr_id, head_sha=CommitSha(value="def"), diff_content="diff"
        )
        assert a != b

    def test_immutability(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=1)
        diff = PullRequestDiff(
            pr_id=pr_id, head_sha=CommitSha(value="abc"), diff_content="diff"
        )
        with pytest.raises(FrozenInstanceError):
            setattr(diff, "diff_content", "changed")

    def test_hash_consistency(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=1)
        sha = CommitSha(value="abc")
        diff = PullRequestDiff(pr_id=pr_id, head_sha=sha, diff_content="diff")
        with pytest.raises(TypeError, match="unhashable"):
            hash(diff)


class TestChangedPaths:
    """Tests for paths extracted from diff headers."""

    def test_includes_modified_and_deleted_paths(self) -> None:
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha(value="abc"),
            diff_content=(
                "diff --git a/old.py b/old.py\n"
                "deleted file mode 100644\n"
                "--- a/old.py\n"
                "+++ /dev/null\n"
                "diff --git a/changed.py b/changed.py\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n"
            ),
        )

        assert diff.changed_paths == ["changed.py", "old.py"]

    def test_sorts_and_deduplicates_paths(self) -> None:
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha(value="abc"),
            diff_content=(
                "diff --git a/z.py b/z.py\n"
                "diff --git a/a.py b/a.py\n"
                "diff --git a/z.py b/z.py\n"
            ),
        )

        assert diff.changed_paths == ["a.py", "z.py"]

    @pytest.mark.parametrize("diff_content", ["", "header without a diff path\n"])
    def test_returns_empty_for_content_without_diff_headers(
        self, diff_content: str,
    ) -> None:
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha(value="abc"),
            diff_content=diff_content,
        )

        assert diff.changed_paths == []
