"""Behavioral tests for GithubReviewReader."""

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.github.review_reader import GithubReviewReader
from tests.fakes import FakeGitPlatformHttpClient


def _reader(paths: dict) -> GithubReviewReader:
    return GithubReviewReader(FakeGitPlatformHttpClient(paths))


PR = PullRequestId(repository="o/r", number=3)
PATH = "/repos/o/r/pulls/3/reviews"


class TestGithubReviewReader:
    """Exercises GithubReviewReader.get_latest_review across response shapes."""

    def test_get_latest_review_when_list_then_returns_latest_body(self) -> None:
        reader = _reader(
            {
                PATH: [
                    {"submitted_at": "2024-01-01T00:00:00Z", "body": "older"},
                    {"submitted_at": "2024-01-02T00:00:00Z", "body": "newer"},
                ]
            }
        )

        assert reader.get_latest_review(PR) == "newer"

    def test_get_latest_review_when_empty_list_then_returns_none(self) -> None:
        assert _reader({PATH: []}).get_latest_review(PR) is None

    def test_get_latest_review_when_list_review_without_body_then_returns_none(self) -> None:
        assert _reader({PATH: [{"submitted_at": "2024-01-01T00:00:00Z"}]}).get_latest_review(PR) is None

    def test_get_latest_review_when_dict_then_returns_body(self) -> None:
        assert _reader({PATH: {"body": "single"}}).get_latest_review(PR) == "single"

    def test_get_latest_review_when_scalar_then_returns_none(self) -> None:
        assert _reader({PATH: "plain"}).get_latest_review(PR) is None