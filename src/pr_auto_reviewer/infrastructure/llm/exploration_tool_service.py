"""ExplorationToolService — executes file read, search, list, and git operations against a cloned repo."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from pr_auto_reviewer.domain.agent.tool_call import ToolCall
from pr_auto_reviewer.domain.agent.tool_result import ToolResult
logger = logging.getLogger(__name__)

_MAX_FILE_BYTES = 100 * 1024
_MAX_SEARCH_HITS = 50
_MAX_DIR_ENTRIES = 200
_GIT_READONLY_SUBCOMMANDS = frozenset({
    "diff",
    "log",
    "show",
    "branch",
    "status",
    "blame",
    "rev-parse",
    "rev-list",
    "ls-tree",
    "cat-file",
    "for-each-ref",
    "ls-files",
})


class ExplorationToolService:
    """Executes tool calls from the LLM against the cloned repository.

    All operations are sandboxed to the repo root — path traversal is blocked.
    Results are JSON-serializable dicts suitable for injection into chat messages.
    """

    def __init__(self, repo_path: Path | str, changed_files: list[str] | None = None) -> None:
        if not repo_path:
            raise ValueError("repo_path cannot be empty")
        resolved = Path(repo_path).resolve()
        if not resolved.is_dir():
            raise ValueError(f"repo_path is not a directory: {repo_path}")
        self._repo_root = resolved
        self._changed_files = changed_files or []

    def execute(self, operation: str, args: str | dict[str, str]) -> dict[str, Any]:
        """Dispatch an operation by name.

        Args:
        operations: read_file, search_codebase, list_directory, run_git, get_changed_files
            args: Operation-specific arguments string, or a dict with a single key
                mapping to the argument value (normalized here).

        Returns:
            A dict with status and result/error fields.
        """
        if isinstance(args, dict):
            args = next(iter(args.values()), "")
        if operation == "read_file":
            return self.read_file(args)
        if operation == "search_codebase":
            return self.search_codebase(args)
        if operation == "list_directory":
            return self.list_directory(args)
        if operation == "run_git":
            return self.run_git(args)
        if operation == "get_changed_files":
            return self.get_changed_files()
        return {"status": "error", "error": f"Unknown operation: {operation}"}

    def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a ``ToolCall`` and return a ``ToolResult``.

        Delegates to the existing ``execute()`` method, mapping the
        dict return value to a ``ToolResult``.
        """
        operation = tool_call.tool_name
        args = tool_call.arguments.get("args", "")
        result = self.execute(operation, args)
        return ToolResult(
            status=result.get("status", "error"),
            data=result if result.get("status") == "ok" else None,
            error=result.get("error"),
        )

    def read_file(self, args: str) -> dict[str, Any]:
        """Read a file (or line range) relative to the repo root.

        Args: ``<relative_path> [L1-L50]`` — path is required, optional line range.
        """
        path_str, start_line, end_line = self._parse_read_args(args)
        resolved = self._resolve_safe(path_str)
        if resolved is None:
            return {"status": "error", "error": f"Path traversal blocked: {path_str}"}
        if not resolved.is_file():
            return {"status": "error", "error": f"File not found: {path_str}"}
        if resolved.stat().st_size > _MAX_FILE_BYTES:
            return {
                "status": "error",
                "error": f"File exceeds {_MAX_FILE_BYTES} byte limit",
            }
        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return {"status": "error", "error": "Binary file — cannot read as text"}
        if start_line is not None:
            lines = content.splitlines()
            end = min(end_line or len(lines), len(lines))
            if start_line < 1 or start_line > len(lines):
                return {
                    "status": "error",
                    "error": f"Line {start_line} out of range (file has {len(lines)} lines)",
                }
            content = "\n".join(lines[start_line - 1 : end])
        return {
            "status": "ok",
            "path": path_str,
            "content": content,
        }

    def search_codebase(self, args: str) -> dict[str, Any]:
        """Search for a pattern in the repo using ``grep -rn``.

        Args: ``<pattern>`` — regex or literal text to search for.
        """
        pattern = args.strip()
        if not pattern:
            return {"status": "error", "error": "Empty search pattern"}
        try:
            result = subprocess.run(
                ["grep", "-rn", "-e", pattern, "."],
                capture_output=True,
                text=True,
                cwd=str(self._repo_root),
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Search timed out"}
        lines = result.stdout.splitlines()
        if len(lines) > _MAX_SEARCH_HITS:
            lines = lines[:_MAX_SEARCH_HITS]
            truncated = True
        else:
            truncated = False
        hits = []
        for line in lines:
            parts = line.split(":", 2)
            if len(parts) == 3:
                hits.append({
                    "file": parts[0],
                    "line": int(parts[1]),
                    "text": parts[2],
                })
        return {
            "status": "ok",
            "pattern": pattern,
            "hits": hits,
            "truncated": truncated,
        }

    def list_directory(self, args: str) -> dict[str, Any]:
        """List entries in a directory relative to the repo root.

        Args: ``<relative_path>`` — directory to list (use ``.`` for root).
        """
        path_str = args.strip() or "."
        resolved = self._resolve_safe(path_str)
        if resolved is None:
            return {"status": "error", "error": f"Path traversal blocked: {path_str}"}
        if not resolved.is_dir():
            return {"status": "error", "error": f"Not a directory: {path_str}"}
        entries = []
        try:
            for entry in sorted(resolved.iterdir()):
                if len(entries) >= _MAX_DIR_ENTRIES:
                    break
                entry_type = "dir" if entry.is_dir() else "file"
                entries.append({
                    "name": entry.name,
                    "type": entry_type,
                })
        except PermissionError:
            return {"status": "error", "error": f"Permission denied: {path_str}"}
        return {
            "status": "ok",
            "path": path_str,
            "entries": entries,
            "truncated": len(entries) >= _MAX_DIR_ENTRIES,
        }

    def run_git(self, args: str) -> dict[str, Any]:
        """Execute a read-only git subcommand against the repo.

        Args: ``<subcommand> [args...]`` — subcommand must be in the whitelist.
        """
        tokens = args.strip().split()
        if not tokens:
            return {"status": "error", "error": "Empty git args"}
        subcommand = tokens[0]
        if subcommand not in _GIT_READONLY_SUBCOMMANDS:
            return {
                "status": "error",
                "error": f"Git subcommand '{subcommand}' is not allowed. "
                f"Allowed: {', '.join(sorted(_GIT_READONLY_SUBCOMMANDS))}",
            }
        try:
            result = subprocess.run(
                ["git", subcommand, *tokens[1:]],
                capture_output=True,
                text=True,
                cwd=str(self._repo_root),
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Git command timed out"}
        if result.returncode != 0:
            return {
                "status": "error",
                "error": result.stderr.strip() or f"git {subcommand} failed",
            }
        return {
            "status": "ok",
            "subcommand": subcommand,
            "output": result.stdout,
        }

    def get_changed_files(self) -> dict[str, Any]:
        """Return the list of files modified in the PR under review.

        Returns:
            A dict with status ``ok`` and a ``files`` list of
            repo-relative paths, or ``files`` may be empty.
        """
        return {"status": "ok", "files": list(self._changed_files)}

    def _resolve_safe(self, relative_path: str) -> Path | None:
        """Resolve a path against the repo root, blocking escapes.

        Accepts both relative paths (``src/foo.py``) and absolute paths
        that sit inside the repo root (common when the LLM echoes the
        repo path it was given).

        Returns ``None`` if the path escapes the repo root.
        """
        stripped = relative_path.strip()
        if os.path.isabs(stripped):
            candidate = Path(stripped).resolve()
        else:
            candidate = (self._repo_root / stripped.lstrip("/")).resolve()
        try:
            candidate.relative_to(self._repo_root)
        except ValueError:
            return None
        return candidate

    @staticmethod
    def _parse_read_args(args: str) -> tuple[str, int | None, int | None]:
        """Parse the read_file argument string.

        Returns: ``(path, start_line | None, end_line | None)``.
        """
        match = re.match(r"^(\S+)\s+(L?)(\d+)(?:-L?(\d+))?$", args.strip())
        if match:
            path = match.group(1)
            start = int(match.group(3))
            end_str = match.group(4)
            end = int(end_str) if end_str else None
            return path, start, end
        return args.strip(), None, None
