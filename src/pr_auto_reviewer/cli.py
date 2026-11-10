"""CLI entry point for PR Auto Reviewer."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Any

from .presentation.composition_root import bootstrap, run_daemon, show_status

SERVICE_NAME = "pr-auto-reviewer.service"


class CommandLineInterface:
    """Dispatches command-line arguments to presentation services."""

    def run(self, argv: list[str] | None = None) -> None:
        """Parse arguments and dispatch the selected command."""
        parser = self._build_parser()
        args = parser.parse_args(argv)
        self._dispatch(args)

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="PR AI Auto-Reviewer")
        subparsers = parser.add_subparsers(dest="command", required=True)
        self._add_service_parsers(subparsers)
        self._add_action_parsers(subparsers)
        return parser

    def _add_service_parsers(self, subparsers: Any) -> None:
        subparsers.add_parser("start", help="Start the systemd service")
        subparsers.add_parser("stop", help="Stop the systemd service")
        subparsers.add_parser("status", help="Show live daemon status")
        subparsers.add_parser("logs", help="Follow service logs")
        subparsers.add_parser("restart", help="Restart the service")
        subparsers.add_parser("bootstrap", help="Bootstrap the application")
        subparsers.add_parser("clean", help="Clean state files")
        subparsers.add_parser(
            "list-allowed-repositories",
            help="List repositories permitted by the allowlist",
        )

    def _add_action_parsers(self, subparsers: Any) -> None:
        watch_parser = subparsers.add_parser("watch-prs", help="Watch PRs for reviews")
        watch_parser.add_argument("-i", "--interval", type=int, default=60)
        watch_parser.add_argument("-r", "--repo", help="Watch specific repo")
        watch_parser.add_argument("--once", action="store_true")
        watch_parser.add_argument("-p", "--pr", "--force", type=int, dest="force_pr")
        watch_parser.add_argument("-v", "--verbose", action="store_true")

        review_parser = subparsers.add_parser("review", help="Review a specific PR")
        review_parser.add_argument("-r", "--repo", required=True)
        review_parser.add_argument("-p", "--pr", required=True, type=int)
        review_parser.add_argument("--force", action="store_true")
        review_parser.add_argument("-v", "--verbose", action="store_true")

        process_parser = subparsers.add_parser("process-commands", help="Process issue commands")
        process_parser.add_argument("-r", "--repo", required=True)
        process_parser.add_argument("-p", "--pr", required=True, type=int)
        process_parser.add_argument("-v", "--verbose", action="store_true")

        items_parser = subparsers.add_parser("list-items", help="List review items")
        items_parser.add_argument("-r", "--repo", required=True)
        items_parser.add_argument("-p", "--pr", required=True, type=int)
        items_parser.add_argument("-v", "--verbose", action="store_true")

    def _dispatch(self, args: argparse.Namespace) -> None:
        if self._handle_lifecycle(args.command):
            return
        if args.command == "watch-prs":
            self._handle_watch(args)
            return
        self._handle_runner_command(args)

    def _handle_lifecycle(self, command: str) -> bool:
        if command in {"start", "stop", "restart"}:
            self._run_systemctl(command)
            return True
        if command == "status":
            print(show_status())
            return True
        if command == "logs":
            self._run_journalctl()
            return True
        if command == "bootstrap":
            bootstrap()
            return True
        return False

    @staticmethod
    def _set_env_if_truthy(key: str, val: str | None) -> None:
        if val:
            os.environ[key] = val

    @classmethod
    def _apply_watch_env(cls, args: argparse.Namespace) -> None:
        if args.interval != 60:
            os.environ["POLL_INTERVAL"] = str(args.interval)
        os.environ["RUN_ONCE"] = "true" if args.once else "false"
        cls._set_env_if_truthy("REPOS_FILTER", args.repo)
        cls._set_env_if_truthy("FORCE_PR", str(args.force_pr) if args.force_pr else None)
        cls._set_env_if_truthy("DEBUG", "1" if args.verbose else None)

    def _handle_watch(self, args: argparse.Namespace) -> None:
        self._apply_watch_env(args)
        components = bootstrap()
        run_daemon(components)

    @staticmethod
    def _build_runner_argv(args: argparse.Namespace) -> list[str]:
        cmd_argv = [sys.argv[0], args.command]
        repo = getattr(args, "repo", None)
        if repo:
            cmd_argv.extend(["--repo", repo])
        pr = getattr(args, "pr", None)
        if pr:
            cmd_argv.extend(["--pr", str(pr)])
        if getattr(args, "force", False):
            cmd_argv.append("--force")
        if getattr(args, "verbose", False):
            cmd_argv.append("--verbose")
        return cmd_argv

    def _handle_runner_command(self, args: argparse.Namespace) -> None:
        if getattr(args, "verbose", False):
            os.environ["DEBUG"] = "1"
        components = bootstrap()
        cmd_argv = self._build_runner_argv(args)
        sys.exit(components.cli_runner.run(cmd_argv))

    @staticmethod
    def _run_systemctl(action: str) -> None:
        if action in {"start", "restart"} and os.environ.get("SSH_AUTH_SOCK"):
            subprocess.run(
                ["systemctl", "--user", "import-environment", "SSH_AUTH_SOCK"],
                check=False,
            )
        subprocess.run(["systemctl", "--user", action, SERVICE_NAME], check=False)

    @staticmethod
    def _run_journalctl() -> None:
        subprocess.run(["journalctl", "--user", "-u", SERVICE_NAME, "-f"], check=False)


def main() -> None:
    """Main CLI entry point."""
    CommandLineInterface().run()


if __name__ == "__main__":
    main()
