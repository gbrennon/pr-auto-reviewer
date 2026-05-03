"""CliRunner - CLI entry point with subcommands."""

from __future__ import annotations

import argparse
import logging

from pr_auto_reviewer.application.commands.process_issue_commands_command import (
    ProcessIssueCommandsCommand,
)
from pr_auto_reviewer.application.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.application.ports.inbound.process_issue_commands_use_case import (
    ProcessIssueCommandsUseCase,
)
from pr_auto_reviewer.application.ports.inbound.review_pull_request_use_case import (
    ReviewPullRequestUseCase,
)
from pr_auto_reviewer.application.ports.outbound.review_reader_port import ReviewReaderPort
from pr_auto_reviewer.domain.exceptions.pull_request_not_found_error import (
    PullRequestNotFoundError,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.presentation.ports import PrListerPort

logger = logging.getLogger(__name__)


class CliRunner:
    """CLI runner with subcommands for manual operations."""

    def __init__(
        self,
        review_service: ReviewPullRequestUseCase,
        process_commands_service: ProcessIssueCommandsUseCase,
        review_reader: ReviewReaderPort,
        pr_lister: PrListerPort,
        review_item_parser: ReviewItemParser,
    ) -> None:
        self._review_service = review_service
        self._process_commands_service = process_commands_service
        self._review_reader = review_reader
        self._pr_lister = pr_lister
        self._review_item_parser = review_item_parser

    def run(self, argv: list[str]) -> int:
        """Run the CLI with the given arguments."""
        parser = argparse.ArgumentParser(prog="pr-auto-reviewer")
        subparsers = parser.add_subparsers(dest="command", required=True)

        subparsers.add_parser("review", help="Force review a specific PR")
        subparsers.add_parser(
            "process-commands", help="Process issue commands for a PR"
        )
        subparsers.add_parser("list-items", help="List review items for a PR")

        args = parser.parse_args(argv[1:])

        if args.command == "review":
            return self._run_review(argv[2:])
        elif args.command == "process-commands":
            return self._run_process_commands(argv[2:])
        elif args.command == "list-items":
            return self._run_list_items(argv[2:])
        else:
            parser.print_help()
            return 1

    def _run_review(self, argv: list[str]) -> int:
        parser = argparse.ArgumentParser(prog="pr-auto-reviewer review")
        parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
        parser.add_argument("--pr", required=True, type=int, help="PR number")
        args = parser.parse_args(argv)

        open_prs = self._pr_lister.list_open(args.repo)
        pr = next((p for p in open_prs if p.pr_id.number == args.pr), None)

        if pr is None:
            print(f"Error: PR #{args.pr} not found or not open in {args.repo}")
            return 1

        command = ReviewPullRequestCommand(
            pr_id=pr.pr_id,
            head_sha=pr.head_sha,
            title=pr.title,
        )

        try:
            self._review_service.execute(command)
            print(f"Review posted for PR #{args.pr}")
            return 0
        except Exception as e:
            print(f"Error: {e}")
            return 1

    def _run_process_commands(self, argv: list[str]) -> int:
        parser = argparse.ArgumentParser(prog="pr-auto-reviewer process-commands")
        parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
        parser.add_argument("--pr", required=True, type=int, help="PR number")
        args = parser.parse_args(argv)

        pr_id = PullRequestId(repository=args.repo, number=args.pr)

        open_prs = self._pr_lister.list_open(args.repo)
        pr = next((p for p in open_prs if p.pr_id.number == args.pr), None)

        if pr is None:
            print(f"Error: PR #{args.pr} not found in local state")
            return 1

        command = ProcessIssueCommandsCommand(pr_id=pr_id, head_sha=pr.head_sha)

        try:
            self._process_commands_service.execute(command)
            print("Command processing complete")
            return 0
        except PullRequestNotFoundError:
            print("Error: PR not in local state")
            return 1
        except Exception as e:
            print(f"Error: {e}")
            return 1

    def _run_list_items(self, argv: list[str]) -> int:
        parser = argparse.ArgumentParser(prog="pr-auto-reviewer list-items")
        parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
        parser.add_argument("--pr", required=True, type=int, help="PR number")
        args = parser.parse_args(argv)

        pr_id = PullRequestId(repository=args.repo, number=args.pr)

        raw_body = self._review_reader.get_latest_review(pr_id)
        if raw_body is None:
            print(f"No review found for PR #{args.pr}")
            return 1

        items = self._review_item_parser.parse(raw_body)
        if not items:
            print("No actionable items found")
            return 0

        print(f"{'#':<4} | {'Severity':<10} | {'Category':<12} | {'File':<30} | Description")
        print("-" * 100)
        for item in items:
            file_path = item.file_path or ""
            print(
                f"{item.number:<4} | {item.severity.value.upper():<10} | "
                f"{item.category:<12} | {file_path:<30} | {item.description}"
            )

        return 0