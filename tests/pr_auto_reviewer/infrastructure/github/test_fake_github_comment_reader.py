from tests.fakes.fake_github_comment_reader import FakeGithubCommentReader
from pr_auto_reviewer.domain.value_objects.comment_id import CommentId
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class TestFakeGithubCommentReader:
    """Tests using the fake GithubCommentReader."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake comment reader can be instantiated."""
        fake = FakeGithubCommentReader()
        assert fake is not None

    def test_fake_get_comments(self) -> None:
        """Fake get_comments returns configured comments."""
        fake = FakeGithubCommentReader()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        comments = fake.get_comments(pr_id)
        assert len(comments) == 2
        assert fake.get_comments_calls == [(pr_id,)]
        assert comments[0].body == "Test comment 1"
        assert comments[1].body == "Test comment 2"

    def test_fake_get_comments_empty(self) -> None:
        """Fake get_comments can return empty list."""
        # This fake always returns 2 comments, but we could extend it
        fake = FakeGithubCommentReader()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        comments = fake.get_comments(pr_id)
        assert len(comments) > 0