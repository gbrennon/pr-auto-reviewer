"""PromptBuilder — constructs the LLM prompt from a diff and repository context."""

from __future__ import annotations

import re
from pathlib import Path

import jinja2

from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext

_DIFF_CHUNK_RE = re.compile(r"(?=^diff --git )", re.MULTILINE)
_DELETED_FILE_RE = re.compile(r"^deleted file mode", re.MULTILINE)
_NEW_FILE_RE = re.compile(r"^new file mode", re.MULTILINE)
_DEVNULL_SRC_RE = re.compile(r"^--- /dev/null$", re.MULTILINE)
_DEVNULL_DST_RE = re.compile(r"^\+\+\+ /dev/null$", re.MULTILINE)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class PromptBuilder:
    """Build the prompt sent to the LLM from a diff + review context."""

    def __init__(self, template_dir: Path | None = None) -> None:
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir or _TEMPLATES_DIR)),
            keep_trailing_newline=True,
        )

    def _classify_chunk(self, chunk: str) -> str:
        """Return '[ADDED]', '[DELETED]', or '[MODIFIED]' for a diff chunk."""
        if _DELETED_FILE_RE.search(chunk) or _DEVNULL_DST_RE.search(chunk):
            return "[DELETED]"
        if _NEW_FILE_RE.search(chunk) or _DEVNULL_SRC_RE.search(chunk):
            return "[ADDED]"
        return "[MODIFIED]"

    def _annotate_diff(self, raw_diff: str) -> str:
        """Insert file-status markers into a unified diff.

        Each per-file chunk gets a header line like::

            [DELETED] .github/copilot-instructions.md -- already removed, skip.

        placed right after the ``diff --git`` line.
        """
        chunks = _DIFF_CHUNK_RE.split(raw_diff)
        annotated: list[str] = []

        for chunk in chunks:
            if not chunk.strip():
                continue

            lines = chunk.split("\n")
            header_line = lines[0] if lines else ""

            if not header_line.startswith("diff --git "):
                annotated.append(chunk)
                continue

            parts = header_line.split(" ")
            b_path = parts[3][2:] if len(parts) >= 4 else ""

            change_type = self._classify_chunk(chunk)

            if change_type == "[DELETED]":
                marker = (
                    f"[DELETED] {b_path} -- this file is being removed. "
                    f"Do NOT flag any issues in it."
                )
            elif change_type == "[ADDED]":
                marker = (
                    f"[ADDED] {b_path} -- this is a new file. "
                    f"Review its content for issues."
                )
            else:
                marker = (
                    f"[MODIFIED] {b_path} -- this file has been changed. "
                    f"Review only the added (+) lines and the context."
                )

            lines.insert(1, marker)
            annotated.append("\n".join(lines))

        return "\n".join(annotated)

    def build(self, diff: PullRequestDiff, context: RepositoryContext) -> str:
        template = self._env.get_template("review_prompt.j2")

        conventions = context.conventions or diff.conventions
        repo_structure = context.repository_structure or diff.repository_structure

        annotated_diff = self._annotate_diff(diff.diff_content)

        return template.render(
            architecture_hint=context.architecture_hint if context.architecture_hint else None,
            conventions=conventions if conventions else None,
            repository_structure=repo_structure if repo_structure else None,
            file_contents=diff.file_contents if diff.file_contents else None,
            annotated_diff=annotated_diff,
            pr_title=context.pr_title if context.pr_title else None,
            pr_description=context.pr_description if context.pr_description else None,
            commit_messages=diff.commit_messages if diff.commit_messages else None,
        )