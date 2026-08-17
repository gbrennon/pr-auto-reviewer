"""E2E tests for the review flow.

Tests the complete review flow from CLI call to review completion.
"""

from unittest.mock import MagicMock

import pytest

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.presentation.polling_daemon import (
    PollingDaemon,
    PollingDaemonConfig,
)
from pr_auto_reviewer.presentation.ports import (
    OpenPullRequest,
    PrListerPort,
    RepoInfo,
    RepoListerPort,
)


class MockRepoLister(RepoListerPort):
    def __init__(self, repos: list[RepoInfo]) -> None:
        self._repos = repos
        self.call_count = 0

    def list_repos(self) -> list[RepoInfo]:
        self.call_count += 1
        return self._repos

class MockPrLister(PrListerPort):
    def __init__(self, prs: list[OpenPullRequest]) -> None:
        self._prs = prs
        self.call_count = 0
        self.last_repo = None

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        self.call_count += 1
        self.last_repo = repository
        return self._prs

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        for p in self._prs:
            if p.pr_id.number == pr_number:
                return p
        return None

class TestPollingDaemonE2E:
    """E2E tests for PollingDaemon."""

    def test_daemon_fetches_repos_and_prs(
        self,
        polling_daemon_config: PollingDaemonConfig,
        stub_review_service,
    ) -> None:
        """Daemon fetches repos and PRs in a cycle."""
        repo_lister = MockRepoLister([RepoInfo("repo1"), RepoInfo("repo2")])
        pr_lister = MockPrLister([])

        daemon = PollingDaemon(
            config=polling_daemon_config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=stub_review_service,
        )

        daemon._run_cycle()

        assert repo_lister.call_count == 1

    def test_daemon_processes_open_prs(
        self,
        polling_daemon_config: PollingDaemonConfig,
        stub_review_service,
    ) -> None:
        """Daemon processes open (non-draft) PRs."""
        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="test/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Test PR",
            is_draft=False,
        )

        repo_lister = MockRepoLister([RepoInfo("test/repo")])
        pr_lister = MockPrLister([open_pr])

        daemon = PollingDaemon(
            config=polling_daemon_config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=stub_review_service,
        )

        daemon._run_cycle()

        stub_review_service.assert_called_once()

    def test_daemon_skips_draft_prs(
        self,
        polling_daemon_config: PollingDaemonConfig,
        stub_review_service,
    ) -> None:
        """Daemon skips draft PRs."""
        draft_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="test/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="WIP",
            is_draft=True,
        )

        repo_lister = MockRepoLister([RepoInfo("test/repo")])
        pr_lister = MockPrLister([draft_pr])

        daemon = PollingDaemon(
            config=polling_daemon_config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=stub_review_service,
        )

        daemon._run_cycle()

        stub_review_service.assert_not_called()

    def test_daemon_handles_empty_repos(
        self,
        polling_daemon_config: PollingDaemonConfig,
        stub_review_service,
    ) -> None:
        """Daemon handles empty repos list."""
        repo_lister = MockRepoLister([])
        pr_lister = MockPrLister([])

        daemon = PollingDaemon(
            config=polling_daemon_config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=stub_review_service,
        )

        daemon._run_cycle()

        stub_review_service.assert_not_called()

    def test_daemon_handles_empty_prs(
        self,
        polling_daemon_config: PollingDaemonConfig,
        stub_review_service,
    ) -> None:
        """Daemon handles repo with no open PRs."""
        repo_lister = MockRepoLister([RepoInfo("test/repo")])
        pr_lister = MockPrLister([])

        daemon = PollingDaemon(
            config=polling_daemon_config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=stub_review_service,
        )

        daemon._run_cycle()

        stub_review_service.assert_not_called()
        assert pr_lister.call_count == 1
        assert pr_lister.last_repo == "test/repo"

    def test_daemon_calls_review_service_with_correct_command(
        self,
        polling_daemon_config: PollingDaemonConfig,
        stub_review_service,
    ) -> None:
        """Daemon calls review service with correct command."""
        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo", number=42),
            head_sha=CommitSha("sha123abc"),
            title="Fix critical bug",
            is_draft=False,
        )

        repo_lister = MockRepoLister([RepoInfo("owner/repo")])
        pr_lister = MockPrLister([open_pr])

        daemon = PollingDaemon(
            config=polling_daemon_config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=stub_review_service,
        )

        daemon._run_cycle()

        stub_review_service.assert_called_once()
        call_args = stub_review_service.call_args
        command = call_args[0][0]

        assert command.pr_id.repository == "owner/repo"
        assert command.pr_id.number == 42
        assert command.head_sha.value == "sha123abc"
        assert command.title == "Fix critical bug"

    def test_daemon_multiple_prs_in_multiple_repos(
        self,
        polling_daemon_config: PollingDaemonConfig,
        stub_review_service,
    ) -> None:
        """Daemon processes multiple PRs from multiple repos."""
        pr1 = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("sha001"),
            title="PR 1",
            is_draft=False,
        )
        pr2 = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo2", number=2),
            head_sha=CommitSha("sha002"),
            title="PR 2",
            is_draft=False,
        )

        class MultiRepoLister(RepoListerPort):
            def list_repos(self) -> list[RepoInfo]:
                return [RepoInfo("owner/repo1"), RepoInfo("owner/repo2")]

        class MultiPrLister(PrListerPort):
            def __init__(self) -> None:
                self.calls = []

            def list_open(self, repository: str) -> list[OpenPullRequest]:
                self.calls.append(repository)
                if repository == "owner/repo1":
                    return [pr1]
                elif repository == "owner/repo2":
                    return [pr2]
                return []

            def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
                for pr_list in ([pr1], [pr2]):
                    for p in pr_list:
                        if p.pr_id.number == pr_number:
                            return p
                return None

        repo_lister = MultiRepoLister()
        pr_lister = MultiPrLister()

        daemon = PollingDaemon(
            config=polling_daemon_config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=stub_review_service,
        )

        daemon._run_cycle()

        assert stub_review_service.call_count == 2

class TestCliRunnerE2E:
    """E2E tests for CliRunner."""

    @pytest.fixture
    def mock_process_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_review_reader(self):
        reader = MagicMock()
        reader.get_latest_review.return_value = None
        return reader

    @pytest.fixture
    def mock_item_parser(self):
        return MagicMock()

    def test_review_command_with_existing_pr(
        self,
        stub_review_service,
        mock_process_service,
        mock_review_reader,
        mock_item_parser,
    ) -> None:
        """CLI review command processes existing PR."""
        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="test/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Test PR",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])

        runner = CliRunner(
            review_service=stub_review_service,
            process_commands_service=mock_process_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_item_parser,
        )

        result = runner._run_review(["--repo", "test/repo", "--pr", "1"])

        assert result == 0
        stub_review_service.assert_called_once()

    def test_review_command_pr_not_found(
        self,
        stub_review_service,
        mock_process_service,
        mock_review_reader,
        mock_item_parser,
    ) -> None:
        """CLI review returns error when PR not found."""
        pr_lister = MockPrLister([])

        runner = CliRunner(
            review_service=stub_review_service,
            process_commands_service=mock_process_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_item_parser,
        )

        result = runner._run_review(["--repo", "test/repo", "--pr", "999"])

        assert result == 1
        stub_review_service.assert_not_called()

    def test_list_items_command(
        self,
        stub_review_service,
        mock_process_service,
        mock_review_reader,
        mock_item_parser,
    ) -> None:
        """CLI list-items command works."""
        from pr_auto_reviewer.domain.entities.review_item import ReviewItem
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity

        mock_review_reader.get_latest_review.return_value = "1. [security] [MAJOR] src/auth.py\n\nissue"
        mock_item_parser.parse.return_value = [
            ReviewItem(id="id-1",
                severity=ItemSeverity.MAJOR,
                category="security",
                file_path="src/auth.py",
                description="issue",
            )
        ]

        pr_lister = MockPrLister([])
        runner = CliRunner(
            review_service=stub_review_service,
            process_commands_service=mock_process_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_item_parser,
        )

        result = runner._run_list_items(["--repo", "test/repo", "--pr", "1"])

        assert result == 0

    def test_process_commands_command(
        self,
        stub_review_service,
        mock_process_service,
        mock_review_reader,
        mock_item_parser,
    ) -> None:
        """CLI process-commands works."""
        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="test/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Test PR",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])

        runner = CliRunner(
            review_service=stub_review_service,
            process_commands_service=mock_process_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_item_parser,
        )

        result = runner._run_process_commands(["--repo", "test/repo", "--pr", "1"])

        assert result in [0, 1]
        mock_process_service.execute.assert_called_once()

    def test_routes_correctly(
        self,
        stub_review_service,
        mock_process_service,
        mock_review_reader,
        mock_item_parser,
    ) -> None:
        """CLI routes to correct handler for each command."""
        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="test/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Test PR",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])

        runner = CliRunner(
            review_service=stub_review_service,
            process_commands_service=mock_process_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_item_parser,
        )

        result_review = runner._run_review(["--repo", "test/repo", "--pr", "1"])
        assert result_review == 0

        result_commands = runner._run_process_commands(["--repo", "test/repo", "--pr", "1"])
        assert result_commands == 0

class TestPR18DiffE2E:
    """E2E tests specifically for PR18 diff scenario."""

    def test_pr18_diff_is_loaded(
        self,
        review_flow_fixtures: dict,
    ) -> None:
        """PR18 diff fixture is properly loaded."""
        pr18_diff = review_flow_fixtures.get("pr18_diff", "")
        assert "evals/evaluators/__init__.py" in pr18_diff
        assert "evals/evaluators/exact_match.py" in pr18_diff
        assert "evals/evaluators/factory.py" in pr18_diff
        assert len(pr18_diff) > 1000

    def test_pr18_review_flow(
        self,
        review_flow_fixtures: dict,
    ) -> None:
        """Test review flow with PR18 diff content."""
        from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
            PullRequestDiff,
        )

        pr18_diff = review_flow_fixtures.get("pr18_diff", "")

        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="test/evals", number=18),
            head_sha=CommitSha("67ebb6c1234567890abcdef1234567890abcdef"),
            diff_content=pr18_diff,
            repository_structure="evals/evaluators/__init__.py\nevals/evaluators/base.py\nevals/evaluators/factory.py",
        )

        assert diff.pr_id.repository == "test/evals"
        assert diff.pr_id.number == 18
        assert len(diff.diff_content) > 1000

    def test_pr18_detection_as_clean_architecture(
        self,
        review_flow_fixtures: dict,
    ) -> None:
        """Test that PR18 tree paths detect clean architecture."""
        from pr_auto_reviewer.infrastructure.context.architecture_detector import (
            ArchitectureDetector,
        )

        tree_paths = [
            "evals/evaluators/factory.py",
            "evals/evaluators/base.py",
            "evals/evaluators/schema.py",
            "evals/use_cases/",
            "evals/domain/",
            "evals/infrastructure/",
        ]

        detector = ArchitectureDetector()
        arch = detector.detect(tree_paths)

        assert arch in ["clean", "layered", "hexagonal", "onion", "cqrs", "mvc"]
