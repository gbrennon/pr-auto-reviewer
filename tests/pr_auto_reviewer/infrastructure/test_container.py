import pytest
from pr_auto_reviewer.infrastructure.container import Container


class TestContainer:

    @pytest.fixture
    def _container(self):
        return Container()

    @pytest.mark.parametrize("attr", [
        "config",
        "http_client",
        "reviewer_client",
        "pr_repository",
        "changeset_fetcher",
        "repository_context",
        "llm_review",
        "review_publisher",
        "review_reader",
        "comment_reader",
        "comment_publisher",
        "issue_tracker",
        "command_bus",
        "repo_lister",
        "pr_lister",
    ])
    def test_container_provides_non_null_instance(
        self, _container, attr,
    ):
        assert getattr(_container, attr) is not None
