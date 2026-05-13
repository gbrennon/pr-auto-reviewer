import pytest
from pr_auto_reviewer.domain import (
    PullRequestDiff,
    PullRequestId,
    CommitSha,
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
        with pytest.raises(Exception):
            diff.diff_content = "changed"  # type: ignore[misc]

    def test_hash_consistency(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=1)
        sha = CommitSha(value="abc")
        diff = PullRequestDiff(pr_id=pr_id, head_sha=sha, diff_content="diff")
        # dict[str, str] makes the frozen dataclass unhashable by default
        with pytest.raises(TypeError, match="unhashable"):
            hash(diff)
