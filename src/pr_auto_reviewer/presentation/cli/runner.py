"""CliRunner - CLI entry point with subcommands."""

from __future__ import annotations

import argparse
import logging
import sys

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
from pr_auto_reviewer.application.ports.outbound.pull_request_repository import (
    PullRequestRepository,
)
from pr_auto_reviewer.application.ports.outbound.review_reader_port import ReviewReaderPort
from pr_auto_reviewer.application.ports.outbound.token_verifier_port import (
    TokenVerifierPort,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.exceptions.pull_request_not_found_error import (
    PullRequestNotFoundError,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.presentation.ports import PrListerPort
from pr_auto_reviewer.application.ports.outbound.notifier_port import NotifierPort

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
        pr_repository: PullRequestRepository | None = None,
        notifier: NotifierPort | None = None,
        token_verifier: TokenVerifierPort | None = None,
        output_mode: str = "forgejo",
    ) -> None:
        self._review_service = review_service
        self._process_commands_service = process_commands_service
        self._review_reader = review_reader
        self._pr_lister = pr_lister
        self._review_item_parser = review_item_parser
        self._pr_repository = pr_repository
        self._notifier = notifier
        self._token_verifier = token_verifier
        self._output_mode = output_mode

    def run(self, argv: list[str]) -> int:
        """Run the CLI with the given arguments."""
        parser = argparse.ArgumentParser(prog="pr-auto-reviewer")
        subparsers = parser.add_subparsers(dest="command", required=True)

        subparsers.add_parser("review", help="Force review a specific PR")
        subparsers.add_parser(
            "process-commands", help="Process issue commands for a PR"
        )
        subparsers.add_parser("list-items", help="List review items for a PR")
        subparsers.add_parser("clean", help="Reset all reviewed-PR tracking state")

        args, _unknown = parser.parse_known_args(argv[1:])

        if args.command == "review":
            return self._run_review(argv[2:])
        elif args.command == "process-commands":
            return self._run_process_commands(argv[2:])
        elif args.command == "list-items":
            return self._run_list_items(argv[2:])
        elif args.command == "clean":
            return self._run_clean()
        else:
            parser.print_help()
            return 1

    def _run_review(self, argv: list[str]) -> int:
        parser = argparse.ArgumentParser(prog="pr-auto-reviewer review")
        parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
        parser.add_argument("--pr", required=True, type=int, help="PR number")
        parser.add_argument(
            "-v", "--verbose", action="store_true", help="Enable debug output"
        )
        parser.add_argument(
            "--force", action="store_true", help="Force re-review even if already reviewed"
        )
        args = parser.parse_args(argv)

        force_mode = args.force or self._output_mode == "terminal"

        if self._token_verifier:
            verify_id = PullRequestId(repository=args.repo, number=args.pr)
            self._token_verifier.verify(verify_id)

        if args.verbose:
            print(
                f"[verbose] Fetching PR #{args.pr} from repository '{args.repo}'..."
            )

        if force_mode:
            # Force/terminal mode: fetch PR directly regardless of state (open/closed/merged)
            pr = self._pr_lister.get_pr(args.repo, args.pr)
            if args.verbose and pr:
                print(f"[verbose] Force-fetching PR #{args.pr} (state-agnostic, found: {pr is not None})")
        else:
            open_prs = self._pr_lister.list_open(args.repo)
            pr = next((p for p in open_prs if p.pr_id.number == args.pr), None)

        if pr is None:
            reason = "not found or not open" if not force_mode else "not found"
            print(f"Error: PR #{args.pr} {reason} in {args.repo}")
            if args.verbose and not force_mode:
                open_prs = self._pr_lister.list_open(args.repo)
                if open_prs:
                    listed = ", ".join(f"#{p.pr_id.number}" for p in open_prs)
                    print(f"[verbose] {len(open_prs)} open PR(s) found: {listed}")
                else:
                    print(f"[verbose] No open PRs found in {args.repo}")
            return 1

        if args.verbose:
            print(
                f"[verbose] PR #{pr.pr_id.number} found "
                f"(title='{pr.title}', head_sha='{pr.head_sha}')"
            )
            print("[verbose] Submitting review...")

        command = ReviewPullRequestCommand(
            pr_id=pr.pr_id,
            head_sha=pr.head_sha,
            title=pr.title,
            description=pr.description,
            force=args.force,
            updated_at=pr.updated_at,
            target_branch=pr.target_branch,
        )

        try:
            self._review_service.execute(command)
            print(f"Review posted for PR #{args.pr}")
            if self._notifier:
                self._notifier.notify_success("Review complete", f"PR #{args.pr} in {args.repo}")
            return 0
        except LlmUnavailableError as e:
            print("Error: LLM host unreachable — cancelling review")
            if self._notifier:
                self._notifier.notify_error(
                    f"LLM unavailable for PR #{command.pr_id.number}", e)
            if args.verbose:
                import traceback

                traceback.print_exc()
            return 1
        except Exception as e:
            print(f"Error: {e}")
            if self._notifier:
                self._notifier.notify_error(f"Review failed for PR #{command.pr_id.number}", e)
            if args.verbose:
                import traceback

                traceback.print_exc()
            return 1

    def _run_process_commands(self, argv: list[str]) -> int:
        parser = argparse.ArgumentParser(prog="pr-auto-reviewer process-commands")
        parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
        parser.add_argument("--pr", required=True, type=int, help="PR number")
        parser.add_argument(
            "-v", "--verbose", action="store_true", help="Enable debug output"
        )
        args = parser.parse_args(argv)

        pr_id = PullRequestId(repository=args.repo, number=args.pr)

        if args.verbose:
            print(
                f"[verbose] Fetching PR #{args.pr} from repository '{args.repo}'..."
            )

        open_prs = self._pr_lister.list_open(args.repo)
        pr = next((p for p in open_prs if p.pr_id.number == args.pr), None)

        if pr is None:
            print(f"Error: PR #{args.pr} not found in local state")
            if args.verbose:
                if open_prs:
                    listed = ", ".join(f"#{p.pr_id.number}" for p in open_prs)
                    print(f"[verbose] {len(open_prs)} open PR(s) found: {listed}")
                else:
                    print(f"[verbose] No open PRs found in {args.repo}")
            return 1

        if args.verbose:
            print(
                f"[verbose] PR #{pr.pr_id.number} found "
                f"(title='{pr.title}', head_sha='{pr.head_sha}')"
            )
            print("[verbose] Processing issue commands...")

        command = ProcessIssueCommandsCommand(pr_id=pr_id, head_sha=pr.head_sha)

        try:
            self._process_commands_service.execute(command)
            print("Command processing complete")
            return 0
        except PullRequestNotFoundError:
            print("Error: PR not in local state")
            return 1
        except LlmUnavailableError as e:
            print("Error: LLM host unreachable — cancelling command processing")
            if self._notifier:
                self._notifier.notify_error(
                    f"LLM unavailable for PR #{args.pr}", e)
            if args.verbose:
                import traceback

                traceback.print_exc()
            return 1
        except Exception as e:
            print(f"Error: {e}")
            if self._notifier:
                self._notifier.notify_error(f"Command processing failed for PR #{args.pr}", e)
            if args.verbose:
                import traceback

                traceback.print_exc()
            return 1

    def _run_list_items(self, argv: list[str]) -> int:
        parser = argparse.ArgumentParser(prog="pr-auto-reviewer list-items")
        parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
        parser.add_argument("--pr", required=True, type=int, help="PR number")
        parser.add_argument(
            "-v", "--verbose", action="store_true", help="Enable debug output"
        )
        args = parser.parse_args(argv)

        pr_id = PullRequestId(repository=args.repo, number=args.pr)

        if args.verbose:
            print(
                f"[verbose] Fetching review for PR #{args.pr} "
                f"from repository '{args.repo}'..."
            )

        raw_body = self._review_reader.get_latest_review(pr_id)
        if raw_body is None:
            print(f"No review found for PR #{args.pr}")
            return 1

        if args.verbose:
            print("[verbose] Raw review body:")
            print("---")
            print(raw_body)
            print("---")

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

    def _run_clean(self) -> int:
        """Reset all reviewed-PR tracking state."""
        if self._pr_repository is None:
            print("Error: persistence is disabled (terminal mode); nothing to clean")
            return 1
        self._pr_repository.reset()
        print("Review state cleaned. All PRs will be treated as new.")
        return 0


def main() -> None:
    """Standalone entry point for the inner CLI runner."""
    from pr_auto_reviewer.presentation.composition_root import bootstrap

    components = bootstrap()
    sys.exit(components.cli_runner.run(sys.argv))


if __name__ == "__main__":
    main()
