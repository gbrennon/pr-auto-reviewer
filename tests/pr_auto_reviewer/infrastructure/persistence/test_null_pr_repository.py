import pytest
from pr_auto_reviewer.infrastructure.persistence.null_pr_repository import (
    NullPullRequestRepository,
)
from pr_auto_reviewer.domain import (
    PullRequest, PullRequestId, CommitSha, CodeReview, ReviewVerdict,
)


class TestNullPullRequestRepository:

    @pytest.fixture
    def _repo(self):
        return NullPullRequestRepository()

    @pytest.fixture
    def _pr_id(self):
        return PullRequestId(repository="owner/repo", number=1)

    def test_find_always_returns_none(self, _repo, _pr_id):
        assert _repo.find(_pr_id) is None

    def test_find_returns_none_for_multiple_calls(self, _repo, _pr_id):
        _repo.find(_pr_id)
        _repo.find(_pr_id)
        assert _repo.find(_pr_id) is None

    def test_save_does_not_affect_find(self, _repo, _pr_id):
        pr = PullRequest(
            id=_pr_id, title="Test",
            head_sha=CommitSha(value="abc"),
        )
        _repo.save(pr)
        assert _repo.find(_pr_id) is None

    def test_save_multiple_prs_does_not_affect_find(self, _repo):
        _repo.save(PullRequest(
            id=PullRequestId(repository="o/r", number=1),
            title="PR 1", head_sha=CommitSha(value="abc"),
        ))
        _repo.save(PullRequest(
            id=PullRequestId(repository="o/r", number=2),
            title="PR 2", head_sha=CommitSha(value="abc"),
        ))
        _repo.save(PullRequest(
            id=PullRequestId(repository="o/r", number=3),
            title="PR 3", head_sha=CommitSha(value="abc"),
        ))
        _repo.save(PullRequest(
            id=PullRequestId(repository="o/r", number=4),
            title="PR 4", head_sha=CommitSha(value="abc"),
        ))
        _repo.save(PullRequest(
            id=PullRequestId(repository="o/r", number=5),
            title="PR 5", head_sha=CommitSha(value="abc"),
        ))
        assert _repo.find(PullRequestId(repository="o/r", number=1)) is None

    def test_save_does_not_raise(self, _repo):
        pr = PullRequest(
            id=PullRequestId(repository="o/r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )
        _repo.save(pr)

    def test_reset_is_noop(self, _repo, _pr_id):
        pr = PullRequest(
            id=_pr_id, title="Test",
            head_sha=CommitSha(value="abc"),
        )
        _repo.save(pr)
        _repo.reset()
        assert _repo.find(_pr_id) is None
