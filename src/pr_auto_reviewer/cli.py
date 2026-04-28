"""CLI entry point for PR Auto Reviewer."""

import argparse
import sys
from typing import Optional

from .config import load_config
from .watch_prs import watch_prs
from .create_issues_from_pr import create_issues_from_pr
from .list_items import list_items
from .bootstrap import bootstrap
from .clean import clean
from .test_issue_creation import test_issue_creation
from .validate import main as validate
from .validate_pr import main as validate_pr


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="PR AI Auto-Reviewer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # watch-prs command
    watch_parser = subparsers.add_parser("watch-prs", help="Watch PRs for reviews")
    watch_parser.add_argument("-i", "--interval", type=int, default=60, help="Poll interval in seconds")
    watch_parser.add_argument("-r", "--repo", help="Watch specific repo")
    watch_parser.add_argument("--once", action="store_true", help="Run once and exit")
    watch_parser.add_argument("-p", "--pr", type=int, help="Force re-review specific PR")
    watch_parser.add_argument("--list-items", action="store_true", help="List review items")

    # create-issues command
    create_parser = subparsers.add_parser("create-issues", help="Create issues from PR")
    create_parser.add_argument("repo", help="Repository in format owner/repo")
    create_parser.add_argument("pr_number", nargs="?", help="PR number or --all")

    # list-items command
    list_parser = subparsers.add_parser("list-items", help="List review items")
    list_parser.add_argument("repo", help="Repository in format owner/repo")
    list_parser.add_argument("pr_number", type=int, help="PR number")

    # bootstrap command
    subparsers.add_parser("bootstrap", help="Bootstrap the application")

    # clean command
    subparsers.add_parser("clean", help="Clean state files")

    # test-issue-creation command
    test_parser = subparsers.add_parser("test-issue-creation", help="Test issue creation")
    test_parser.add_argument("repo", help="Repository in format owner/repo")
    test_parser.add_argument("pr_number", type=int, help="PR number")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Generate local code review from diff file")
    validate_parser.add_argument("-d", "--diff", required=True, help="Path to diff/patch file")
    validate_parser.add_argument("-o", "--output", help="Write review to file instead of stdout")
    validate_parser.add_argument("-r", "--repo", help="Local repo path to include file tree structure")
    validate_parser.add_argument("--model", help="Ollama model to use")

    # validate-pr command
    validate_pr_parser = subparsers.add_parser("validate-pr", help="Generate review from Codeberg PR")
    validate_pr_parser.add_argument("-r", "--repo", required=True, help="Repository in format owner/repo")
    validate_pr_parser.add_argument("-p", "--pr", required=True, help="PR number")
    validate_pr_parser.add_argument("-o", "--output", help="Write review to file instead of stdout")
    validate_pr_parser.add_argument("-b", "--branch", default="main", help="Branch to use for repo structure")
    validate_pr_parser.add_argument("--model", help="Ollama model to use")

    args = parser.parse_args()

    if args.command == "validate":
        old_argv = sys.argv
        sys.argv = ["validate"]
        if args.diff:
            sys.argv.extend(["-d", args.diff])
        if args.output:
            sys.argv.extend(["-o", args.output])
        if args.repo:
            sys.argv.extend(["-r", args.repo])
        if args.model:
            sys.argv.extend(["--model", args.model])
        try:
            sys.exit(validate())
        finally:
            sys.argv = old_argv
    elif args.command == "validate-pr":
        old_argv = sys.argv
        sys.argv = ["validate-pr"]
        if args.repo:
            sys.argv.extend(["-r", args.repo])
        if args.pr:
            sys.argv.extend(["-p", str(args.pr)])
        if args.output:
            sys.argv.extend(["-o", args.output])
        if args.branch:
            sys.argv.extend(["-b", args.branch])
        if args.model:
            sys.argv.extend(["--model", args.model])
        try:
            sys.exit(validate_pr())
        finally:
            sys.argv = old_argv

    try:
        load_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    if args.command == "watch-prs":
        watch_prs(
            interval=args.interval,
            repo_filter=args.repo,
            run_once=args.once,
            force_pr=args.pr,
            list_items=args.list_items,
        )
    elif args.command == "create-issues":
        create_issues_from_pr(args.repo, args.pr_number)
    elif args.command == "list-items":
        list_items(args.repo, args.pr_number)
    elif args.command == "bootstrap":
        bootstrap()
    elif args.command == "clean":
        clean()
    elif args.command == "test-issue-creation":
        test_issue_creation(args.repo, args.pr_number)


if __name__ == "__main__":
    main()