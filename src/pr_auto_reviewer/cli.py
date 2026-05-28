"""CLI entry point for PR Auto Reviewer."""

import argparse
import os
import sys

from .presentation.composition_root import bootstrap, run_daemon


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="PR AI Auto-Reviewer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # watch-prs command
    watch_parser = subparsers.add_parser("watch-prs", help="Watch PRs for reviews")
    watch_parser.add_argument("-i", "--interval", type=int, default=60, help="Poll interval in seconds")
    watch_parser.add_argument("-r", "--repo", help="Watch specific repo")
    watch_parser.add_argument("--once", action="store_true", help="Run once and exit")
    watch_parser.add_argument("-p", "--pr", "--force", type=int, dest="force_pr", help="Force re-review specific PR")
    watch_parser.add_argument("-v", "--verbose", action="store_true", help="Show debug logs")

    # review command
    review_parser = subparsers.add_parser("review", help="Review a specific PR")
    review_parser.add_argument("-r", "--repo", required=True, help="Repository in format owner/repo")
    review_parser.add_argument("-p", "--pr", required=True, type=int, help="PR number")
    review_parser.add_argument("--force", action="store_true", help="Force re-review even if already reviewed")
    review_parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed error information")

    # process-commands command
    process_cmd_parser = subparsers.add_parser("process-commands", help="Process issue commands for a PR")
    process_cmd_parser.add_argument("-r", "--repo", required=True, help="Repository in format owner/repo")
    process_cmd_parser.add_argument("-p", "--pr", required=True, type=int, help="PR number")
    process_cmd_parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed error information")

    # bootstrap command
    subparsers.add_parser("bootstrap", help="Bootstrap the application")

    # clean command
    subparsers.add_parser("clean", help="Clean state files")

    # list-items command
    list_items_parser = subparsers.add_parser("list-items", help="List review items for a PR")
    list_items_parser.add_argument("-r", "--repo", required=True, help="Repository in format owner/repo")
    list_items_parser.add_argument("-p", "--pr", required=True, type=int, help="PR number")
    list_items_parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed error information")

    args = parser.parse_args()

    if args.command == "watch-prs":
        if args.interval != 60:
            os.environ["POLL_INTERVAL"] = str(args.interval)
        if args.repo:
            os.environ["REPOS_FILTER"] = args.repo
        if args.force_pr:
            os.environ["FORCE_PR"] = str(args.force_pr)
        if args.once:
            os.environ["RUN_ONCE"] = "true"
        if args.verbose:
            os.environ["DEBUG"] = "1"
        components = bootstrap()
        run_daemon(components)
    elif args.command == "review":
        if args.verbose:
            os.environ["DEBUG"] = "1"
        components = bootstrap()
        review_argv = [sys.argv[0], "review", "--repo", args.repo, "--pr", str(args.pr)]
        if args.force:
            review_argv.append("--force")
        if args.verbose:
            review_argv.append("--verbose")
        sys.exit(components.cli_runner.run(review_argv))
    elif args.command == "process-commands":
        if args.verbose:
            os.environ["DEBUG"] = "1"
        components = bootstrap()
        process_argv = [sys.argv[0], "process-commands", "--repo", args.repo, "--pr", str(args.pr)]
        if args.verbose:
            process_argv.append("--verbose")
        sys.exit(components.cli_runner.run(process_argv))
    elif args.command == "bootstrap":
        bootstrap()
    elif args.command == "clean":
        components = bootstrap()
        components.cli_runner.run([sys.argv[0], "clean"])
    elif args.command == "list-items":
        if args.verbose:
            os.environ["DEBUG"] = "1"
        components = bootstrap()
        list_argv = [sys.argv[0], "list-items", "--repo", args.repo, "--pr", str(args.pr)]
        if args.verbose:
            list_argv.append("--verbose")
        sys.exit(components.cli_runner.run(list_argv))


if __name__ == "__main__":
    main()
