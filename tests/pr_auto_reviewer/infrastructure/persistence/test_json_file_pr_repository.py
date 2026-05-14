"""Tests for JsonFilePullRequestRepository — persistence adapter TDD.

Covers:
- find / save round-trip
- missing key → None
- atomic writes (tmp + os.replace)
- RepositoryCorruptedError on malformed JSON
- full aggregate serialization (reviews, items, processed_comment_ids)
"""

import json
import os
from pathlib import Path

import pytest

from pr_auto_reviewer.domain import (
    PullRequest,
    PullRequestId,
    CommitSha,
    CodeReview,
    ReviewVerdict,
    ReviewItem,
    ItemSeverity,
    CommentId,
)
from pr_auto_reviewer.domain.exceptions import RepositoryCorruptedError
from pr_auto_reviewer.infrastructure.persistence.json_file_pr_repository import (
    JsonFilePullRequestRepository,
)


class TestJsonFilePullRequestRepository:
    """Complex TDD test suite for the JSON file persistence adapter."""

    @staticmethod
    def _repo(tmp_path: Path) -> JsonFilePullRequestRepository:
        return JsonFilePullRequestRepository(tmp_path / "state.json")

    @staticmethod
    def _pr(
        repo: str = "owner/repo",
        number: int = 42,
        title: str = "Fix login bug",
        sha: str = "abc1234",
        is_draft: bool = False,
        reviews: tuple[CodeReview, ...] = (),
        processed_comment_ids: frozenset[CommentId] = frozenset(),
    ) -> PullRequest:
        return PullRequest(
            id=PullRequestId(repository=repo, number=number),
            title=title,
            head_sha=CommitSha(value=sha),
            is_draft=is_draft,
            reviews=reviews,
            processed_comment_ids=processed_comment_ids,
        )

    @staticmethod
    def _review(
        verdict: ReviewVerdict = ReviewVerdict.CHANGES_REQUESTED,
        summary: str = "Security issue found",
        model_used: str = "code-review",
        items: list[ReviewItem] | None = None,
    ) -> CodeReview:
        return CodeReview(
            verdict=verdict,
            summary=summary,
            model_used=model_used,
            items=items or [],
        )

    @staticmethod
    def _item(
        number: int = 1,
        severity: ItemSeverity = ItemSeverity.MAJOR,
        category: str = "security",
        file_path: str = "src/auth.py",
        description: str = "Missing input validation",
    ) -> ReviewItem:
        return ReviewItem(
            number=number,
            severity=severity,
            category=category,
            file_path=file_path,
            description=description,
        )

    # ------------------------------------------------------------------
    # find — missing file / missing key
    # ------------------------------------------------------------------
    def test_find_returns_none_when_file_does_not_exist(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        result = repo.find(PullRequestId(repository="owner/repo", number=1))
        assert result is None

    def test_find_returns_none_when_key_missing(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        repo.save(self._pr(repo="owner/repo", number=1))
        result = repo.find(PullRequestId(repository="owner/repo", number=99))
        assert result is None

    # ------------------------------------------------------------------
    # save + find round-trip — minimal aggregate
    # ------------------------------------------------------------------
    def test_save_and_find_minimal_pr(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        pr = self._pr()
        repo.save(pr)
        found = repo.find(pr.id)
        assert found is not None
        assert found.id == pr.id
        assert found.title == pr.title
        assert found.head_sha == pr.head_sha
        assert found.is_draft is False
        assert found.reviews == ()
        assert found.processed_comment_ids == frozenset()

    # ------------------------------------------------------------------
    # save + find round-trip — full aggregate with reviews & comments
    # ------------------------------------------------------------------
    def test_save_and_find_full_aggregate(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        review = self._review(
            verdict=ReviewVerdict.APPROVED,
            summary="LGTM",
            model_used="llama3",
            items=[
                self._item(number=1, severity=ItemSeverity.CRITICAL),
                self._item(
                    number=2,
                    severity=ItemSeverity.MINOR,
                    category="style",
                    file_path="src/main.py",
                    description="Trailing whitespace",
                ),
            ],
        )
        pr = self._pr(
            is_draft=True,
            reviews=(review,),
            processed_comment_ids=frozenset({CommentId("101"), CommentId("204")}),
        )
        repo.save(pr)
        found = repo.find(pr.id)
        assert found is not None
        assert found.is_draft is True
        assert len(found.reviews) == 1
        saved_review = found.reviews[0]
        assert saved_review.verdict == ReviewVerdict.APPROVED
        assert saved_review.summary == "LGTM"
        assert saved_review.model_used == "llama3"
        assert len(saved_review.items) == 2
        assert saved_review.items[0].severity == ItemSeverity.CRITICAL
        assert saved_review.items[1].file_path == "src/main.py"
        assert found.processed_comment_ids == frozenset(
            {CommentId("101"), CommentId("204")}
        )

    # ------------------------------------------------------------------
    # Atomic write — no partial files left behind
    # ------------------------------------------------------------------
    def test_atomic_write_leaves_no_tmp_files(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        repo.save(self._pr())
        tmp_files = list(tmp_path.glob("*.tmp*"))
        assert tmp_files == []

    def test_atomic_write_replaces_existing_file(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        pr1 = self._pr(number=1, title="First")
        pr2 = self._pr(number=2, title="Second")
        repo.save(pr1)
        repo.save(pr2)
        assert repo.find(pr1.id) is not None
        assert repo.find(pr2.id) is not None
        data = json.loads((tmp_path / "state.json").read_text())
        assert len(data["reviewed"]) == 2

    # ------------------------------------------------------------------
    # RepositoryCorruptedError on malformed JSON
    # ------------------------------------------------------------------
    def test_find_raises_on_malformed_json(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text("not json at all {{{", encoding="utf-8")
        repo = JsonFilePullRequestRepository(state_file)
        with pytest.raises(RepositoryCorruptedError):
            repo.find(PullRequestId(repository="owner/repo", number=1))

    def test_find_raises_on_json_decode_error(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text('{"reviewed": {"broken": ', encoding="utf-8")
        repo = JsonFilePullRequestRepository(state_file)
        with pytest.raises(RepositoryCorruptedError):
            repo.find(PullRequestId(repository="owner/repo", number=1))

    # ------------------------------------------------------------------
    # Multiple PRs isolation
    # ------------------------------------------------------------------
    def test_multiple_prs_do_not_clobber_each_other(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        pr_a = self._pr(repo="owner/a", number=1, title="A")
        pr_b = self._pr(repo="owner/b", number=2, title="B", sha="def567")
        repo.save(pr_a)
        repo.save(pr_b)
        found_a = repo.find(pr_a.id)
        found_b = repo.find(pr_b.id)
        assert found_a is not None and found_a.title == "A"
        assert found_b is not None and found_b.title == "B"

    # ------------------------------------------------------------------
    # Update existing PR (immutable aggregate — new version saved)
    # ------------------------------------------------------------------
    def test_update_existing_pr_overwrites_previous(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        pr = self._pr(number=1, title="Old", sha="s1")
        repo.save(pr)
        updated = pr.add_review(
            self._review(verdict=ReviewVerdict.COMMENTED, summary="Reviewed"),
            CommitSha(value="s2"),
        )
        repo.save(updated)
        found = repo.find(pr.id)
        assert found is not None
        assert found.head_sha == CommitSha(value="s2")
        assert len(found.reviews) == 1

    # ------------------------------------------------------------------
    # File schema validation (internal structure)
    # ------------------------------------------------------------------
    def test_file_schema_matches_spec(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        review = self._review(
            items=[self._item(number=1, severity=ItemSeverity.MAJOR)],
        )
        pr = self._pr(
            reviews=(review,),
            processed_comment_ids=frozenset({CommentId("42")}),
        )
        repo.save(pr)
        raw = json.loads((tmp_path / "state.json").read_text())
        assert "reviewed" in raw
        entry = raw["reviewed"]["owner/repo/42"]
        assert entry["title"] == "Fix login bug"
        assert entry["head_sha"] == "abc1234"
        assert entry["is_draft"] is False
        assert entry["reviews"][0]["verdict"] == "changes_requested"
        assert entry["reviews"][0]["items"][0]["severity"] == "major"
        assert entry["processed_comment_ids"] == ["42"]

    # ------------------------------------------------------------------
    # OSError during read → RepositoryCorruptedError
    # ------------------------------------------------------------------
    def test_find_raises_on_os_error(self, tmp_path: Path, monkeypatch) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text('{"reviewed": {}}', encoding="utf-8")
        repo = JsonFilePullRequestRepository(state_file)

        def _bad_open(*args, **kwargs):
            raise OSError("disk failure")

        monkeypatch.setattr("builtins.open", _bad_open)
        with pytest.raises(RepositoryCorruptedError):
            repo.find(PullRequestId(repository="owner/repo", number=1))

    # ------------------------------------------------------------------
    # OSError during write propagates and cleans up tmp file
    # ------------------------------------------------------------------
    def test_save_cleans_up_tmp_on_write_failure(self, tmp_path: Path, monkeypatch) -> None:
        repo = self._repo(tmp_path)
        call_count = {"n": 0}

        original_fdopen = os.fdopen

        def _failing_fdopen(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise OSError("write failure")
            return original_fdopen(*args, **kwargs)

        monkeypatch.setattr(os, "fdopen", _failing_fdopen)
        with pytest.raises(OSError):
            repo.save(self._pr())
        # tmp file should have been removed
        assert list(tmp_path.glob("*.tmp*")) == []
