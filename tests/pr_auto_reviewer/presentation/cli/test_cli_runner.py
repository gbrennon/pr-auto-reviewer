"""Tests for CliRunner."""

from unittest.mock import MagicMock, patch

import pytest

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.presentation.ports import OpenPullRequest, PrListerPort


class MockPrLister(PrListerPort):
    def __init__(self, prs: list[OpenPullRequest]) -> None:
        self._prs = prs
        self.list_open_call_count = 0
        self.get_pr_call_count = 0

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        self.list_open_call_count += 1
        return self._prs
    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        self.get_pr_call_count += 1
        for p in self._prs:
            if p.pr_id.number == pr_number:
                return p
        return None
class TestCliRunner:
    """Tests for CliRunner class."""

    @pytest.fixture
    def mock_review_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_process_commands_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_review_reader(self) -> MagicMock:
        reader = MagicMock()
        reader.get_latest_review.return_value = None
        return reader

    @pytest.fixture
    def mock_review_item_parser(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def runner(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> CliRunner:
        pr_lister = MockPrLister([])
        return CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

    def test_creation(self, runner: CliRunner) -> None:
        """Creates CliRunner with all dependencies."""
        assert runner is not None

    def test_run_routes_to_review(self, runner: CliRunner) -> None:
        """Routes review command correctly."""
        with patch.object(runner, "_run_review", return_value=0) as mock:
            result = runner.run(["cli", "review"])
            assert result == 0
            mock.assert_called_once()

    def test_run_routes_to_process_commands(self, runner: CliRunner) -> None:
        """Routes process-commands command correctly."""
        with patch.object(runner, "_run_process_commands", return_value=0) as mock:
            result = runner.run(["cli", "process-commands"])
            assert result == 0
            mock.assert_called_once()

    def test_run_routes_to_list_items(self, runner: CliRunner) -> None:
        """Routes list-items command correctly."""
        with patch.object(runner, "_run_list_items", return_value=0) as mock:
            result = runner.run(["cli", "list-items"])
            assert result == 0
            mock.assert_called_once()

    def test_run_review_pr_found(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Successfully processes review when PR exists."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        result = runner._run_review(["--repo", "owner/repo", "--pr", "1"])

        assert result == 0
        mock_review_service.execute.assert_called_once()

    def test_run_review_success_message(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Prints success message after review."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        with patch("builtins.print") as mock_print:
            runner._run_review(["--repo", "owner/repo", "--pr", "1"])
            mock_print.assert_any_call("Review posted for PR #1")

    def test_run_review_pr_not_found(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Returns error when PR not found."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        pr_lister = MockPrLister([])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        result = runner._run_review(["--repo", "owner/repo", "--pr", "999"])

        assert result == 1

    def test_run_list_items_no_review(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Returns error when no review found."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        pr_lister = MockPrLister([])
        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        result = runner._run_list_items(["--repo", "owner/repo", "--pr", "1"])

        assert result == 1

    def test_run_list_items_with_items(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Lists items when review exists."""
        from pr_auto_reviewer.domain.entities.review_item import ReviewItem
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        mock_review_reader.get_latest_review.return_value = "1. [security] [MAJOR] src/auth.py\n\nvulnerability"

        mock_items = [
            ReviewItem(id="id-1",
                severity=ItemSeverity.MAJOR,
                category="security",
                file_path="src/auth.py",
                description="vulnerability",
            )
        ]
        mock_review_item_parser.parse.return_value = mock_items
        pr_lister = MockPrLister([])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        result = runner._run_list_items(["--repo", "owner/repo", "--pr", "1"])

        assert result == 0

    def test_run_list_items_no_items(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Returns 0 when no actionable items found."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        mock_review_reader.get_latest_review.return_value = "Some review content"
        mock_review_item_parser.parse.return_value = []
        pr_lister = MockPrLister([])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        result = runner._run_list_items(["--repo", "owner/repo", "--pr", "1"])

        assert result == 0

    def test_run_review_error_handling(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Handles exceptions during review."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])
        mock_review_service.execute.side_effect = RuntimeError("test error")

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        result = runner._run_review(["--repo", "owner/repo", "--pr", "1"])

        assert result == 1

    def test_run_process_commands_pr_not_found(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Returns error when PR not found."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        pr_lister = MockPrLister([])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        result = runner._run_process_commands(["--repo", "owner/repo", "--pr", "999"])

        assert result == 1

    def test_verbose_review_prints_pr_details(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Verbose mode prints PR details before executing review."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        with patch("builtins.print") as mock_print:
            runner._run_review(
                ["--repo", "owner/repo", "--pr", "1", "--verbose"]
            )
            mock_print.assert_any_call(
                "[verbose] Fetching PR #1 from repository 'owner/repo'..."
            )
            mock_print.assert_any_call(
                "[verbose] PR #1 found (title='Fix bug', head_sha='abc123')"
            )
            mock_print.assert_any_call("[verbose] Submitting review...")

    def test_verbose_review_prints_traceback(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Verbose mode prints traceback on review errors."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])
        mock_review_service.execute.side_effect = RuntimeError("test error")

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        with patch("traceback.print_exc") as mock_tb:
            result = runner._run_review(
                ["--repo", "owner/repo", "--pr", "1", "--verbose"]
            )
            assert result == 1
            mock_tb.assert_called_once()

    def test_verbose_process_commands_prints_pr_details(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Verbose mode prints PR details before processing commands."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        with patch("builtins.print") as mock_print:
            runner._run_process_commands(
                ["--repo", "owner/repo", "--pr", "1", "--verbose"]
            )
            mock_print.assert_any_call(
                "[verbose] Fetching PR #1 from repository 'owner/repo'..."
            )
            mock_print.assert_any_call(
                "[verbose] PR #1 found (title='Fix bug', head_sha='abc123')"
            )
            mock_print.assert_any_call("[verbose] Processing issue commands...")

    def test_verbose_process_commands_prints_traceback(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Verbose mode prints traceback on process-commands errors."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])
        mock_process_commands_service.execute.side_effect = RuntimeError("test error")

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        with patch("traceback.print_exc") as mock_tb:
            result = runner._run_process_commands(
                ["--repo", "owner/repo", "--pr", "1", "--verbose"]
            )
            assert result == 1
            mock_tb.assert_called_once()

    def test_verbose_list_items_prints_raw_body(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Verbose mode prints raw review body for list-items."""
        from pr_auto_reviewer.domain.entities.review_item import ReviewItem
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        raw_body = "1. [security] [MAJOR] src/auth.py\n\nvulnerability"
        mock_review_reader.get_latest_review.return_value = raw_body

        mock_items = [
            ReviewItem(id="id-1",
                severity=ItemSeverity.MAJOR,
                category="security",
                file_path="src/auth.py",
                description="vulnerability",
            )
        ]
        mock_review_item_parser.parse.return_value = mock_items
        pr_lister = MockPrLister([])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        with patch("builtins.print") as mock_print:
            runner._run_list_items(
                ["--repo", "owner/repo", "--pr", "1", "--verbose"]
            )
            mock_print.assert_any_call(
                "[verbose] Fetching review for PR #1 "
                "from repository 'owner/repo'..."
            )
            mock_print.assert_any_call("[verbose] Raw review body:")
            mock_print.assert_any_call(raw_body)

    def test_verbose_not_enabled_by_default(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Verbose output is not printed when flag is absent."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        with patch("builtins.print") as mock_print:
            runner._run_review(["--repo", "owner/repo", "--pr", "1"])

        verbose_calls = [
            c for c in mock_print.call_args_list
            if "[verbose]" in str(c)
        ]
        assert len(verbose_calls) == 0

    def test_run_review_reuses_open_prs_on_invalid_pr(
        self,
        mock_review_service: MagicMock,
        mock_process_commands_service: MagicMock,
        mock_review_reader: MagicMock,
        mock_review_item_parser: MagicMock,
    ) -> None:
        """Invalid PR number reuses cached open_prs — no duplicate list_open (Bug 2 fix)."""
        from pr_auto_reviewer.presentation.cli.runner import CliRunner

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        pr_lister = MockPrLister([open_pr])

        runner = CliRunner(
            review_service=mock_review_service,
            process_commands_service=mock_process_commands_service,
            review_reader=mock_review_reader,
            pr_lister=pr_lister,
            review_item_parser=mock_review_item_parser,
        )

        result = runner._run_review(["--repo", "owner/repo", "--pr", "99"])

        assert result == 1  # error exit code
        assert pr_lister.list_open_call_count == 1, (
            f"Expected 1 list_open call, got {pr_lister.list_open_call_count}"
        )
        assert pr_lister.get_pr_call_count == 0, (
            f"Expected 0 get_pr calls (cached list should be sufficient), "
            f"got {pr_lister.get_pr_call_count}"
        )
