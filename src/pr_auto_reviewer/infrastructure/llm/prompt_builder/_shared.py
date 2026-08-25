"""PromptBuilder — constructs the LLM prompt from a diff and repository context.

Supports token-budget-aware construction to prevent oversized prompts
that exceed the LLM context window. When the total estimated token count
exceeds the configured ``max_tokens``, lower-priority sections are trimmed
or dropped in this order (highest priority first):

1. ``diff`` — always kept, truncated at whole-file boundaries if needed
2. ``pr context`` — title, description, commit messages (tiny, always kept)
3. ``file contents`` — trimmed per-file and count-limited
4. ``conventions`` — kept as-is
5. ``architecture hint`` — kept as-is
6. ``repo structure`` — trimmed to max line count
7. ``static instructions`` — use compact template if configured"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext

_DIFF_CHUNK_RE = re.compile(r"(?=^diff --git )", re.MULTILINE)


_DIFF_FILE_PATH_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)


_DIFF_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", re.MULTILINE)


_DELETED_FILE_RE = re.compile(r"^deleted file mode", re.MULTILINE)


_NEW_FILE_RE = re.compile(r"^new file mode", re.MULTILINE)


_DEVNULL_SRC_RE = re.compile(r"^--- /dev/null$", re.MULTILINE)


_DEVNULL_DST_RE = re.compile(r"^\+\+\+ /dev/null$", re.MULTILINE)


_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _parse_diff_hunks(diff_content: str) -> dict[str, list[tuple[int, int]]]:
    """Parse unified diff to extract per-file hunk line ranges.

    Returns ``{file_path: [(start_line_1based, line_count), ...]}``.
    """
    hunks: dict[str, list[tuple[int, int]]] = {}
    current_file: str | None = None
    current_hunk_start: int | None = None
    current_hunk_line = 0
    in_hunk = False

    for line in diff_content.split("\n"):
        m_file = _DIFF_FILE_PATH_RE.match(line)
        if m_file:
            current_file = m_file.group(2)
            if current_file == "/dev/null":
                current_file = None
            current_hunk_start = None
            in_hunk = False
            continue

        m_hunk = _DIFF_HUNK_RE.match(line)
        if m_hunk and current_file:
            current_hunk_start = int(m_hunk.group(1))
            current_hunk_line = current_hunk_start
            in_hunk = True
            continue

        if in_hunk and current_file and current_hunk_start is not None:
            if line.startswith(("+", " ", "-")):
                current_hunk_line += 1
            elif line.startswith("\\"):
                continue
            else:
                count = current_hunk_line - current_hunk_start
                if count > 0:
                    hunks.setdefault(current_file, []).append(
                        (current_hunk_start, count)
                    )
                current_hunk_start = None
                in_hunk = False

    if in_hunk and current_file and current_hunk_start is not None:
        count = current_hunk_line - current_hunk_start
        if count > 0:
            hunks.setdefault(current_file, []).append((current_hunk_start, count))

    return hunks


def _extract_surrounding_context(
    content: str,
    hunks: list[tuple[int, int]],
    context_lines: int = 5,
    max_chars: int = 3000,
) -> str:
    """Extract lines around each hunk from *content*, capped at *max_chars*."""
    all_lines = content.split("\n")
    selected: set[int] = set()

    for start, count in hunks:
        zero_based = start - 1
        begin = max(0, zero_based - context_lines)
        end = min(len(all_lines), zero_based + count + context_lines)
        for idx in range(begin, end):
            selected.add(idx)

    if not selected:
        return ""

    sorted_idx = sorted(selected)
    out_lines: list[str] = []
    char_count = 0
    prev = -2
    for idx in sorted_idx:
        if idx != prev + 1:
            out_lines.append("...")
            char_count += 4
        line = f"{idx + 1:>6}: {all_lines[idx]}"
        out_lines.append(line)
        char_count += len(line) + 1
        if char_count > max_chars:
            out_lines.append(
                f"... (truncated, showing {idx}/{len(all_lines)} lines)"
            )
            break
        prev = idx

    return "\n".join(out_lines)


def _classify_chunk(chunk: str) -> str:
    """Return '[ADDED]', '[DELETED]', or '[MODIFIED]' for a diff chunk."""
    if _DELETED_FILE_RE.search(chunk) or _DEVNULL_DST_RE.search(chunk):
        return "[DELETED]"
    if _NEW_FILE_RE.search(chunk) or _DEVNULL_SRC_RE.search(chunk):
        return "[ADDED]"
    return "[MODIFIED]"


def _annotate_diff(raw_diff: str) -> str:
    """Insert file-status markers into a unified diff."""
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
        change_type = _classify_chunk(chunk)
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


def _trim_diff(raw_diff: str, max_tokens: int) -> str:
    """Truncate diff at ``diff --git`` boundaries to fit *max_tokens*.

    Keeps whole per-file chunks in priority order:
    ``[ADDED]`` > ``[MODIFIED]`` > ``[DELETED]``.
    """

    from .prompt_budget import PromptBudget
    if PromptBudget.estimate_tokens(raw_diff) <= max_tokens:
        return raw_diff

    chunks = _DIFF_CHUNK_RE.split(raw_diff)
    if chunks and not chunks[0].strip():
        chunks.pop(0)

    def _priority(chunk: str) -> int:
        kind = _classify_chunk(chunk)
        return {"[ADDED]": 0, "[MODIFIED]": 1, "[DELETED]": 2}.get(kind, 3)

    sorted_chunks = sorted(chunks, key=_priority)
    budget = PromptBudget(max_tokens=max_tokens)
    kept: list[str] = []

    for chunk in sorted_chunks:
        full = "diff --git " + chunk if kept else chunk
        if budget.would_fit(full):
            budget.consume(full)
            kept.append(full)
        else:
            break

    result = "".join(kept).rstrip() + "\n"
    if len(result) < 50:
        first_chunk = chunks[0]
        result = first_chunk[:max_tokens * 4] + "\n... (diff truncated)\n"

    return result


def _trim_file_contents(
    file_contents: dict[str, str],
    diff_content: str,
    max_files: int = 10,
    max_chars_per_file: int = 3000,
) -> dict[str, str]:
    """Trim file contents to fit within size limits.

    1. Limits the *number* of files to *max_files*.
    2. Replaces full-file content with context around diff hunks.
    3. Caps each file's content at *max_chars_per_file*.
    """
    if not file_contents:
        return {}

    hunks = _parse_diff_hunks(diff_content)
    trimmed: dict[str, str] = {}

    for file_path, content in file_contents.items():
        if len(trimmed) >= max_files:
            break
        file_hunks = hunks.get(file_path, [])
        if file_hunks:
            context = _extract_surrounding_context(
                content, file_hunks, context_lines=5, max_chars=max_chars_per_file
            )
        else:
            context = content[:max_chars_per_file]
            if len(content) > max_chars_per_file:
                context += f"\n... (file truncated, {len(content)} total chars)\n"
        if context.strip():
            trimmed[file_path] = context

    return trimmed


def _trim_repo_structure(structure: str, max_lines: int = 100) -> str:
    """Truncate repository structure listing to *max_lines* lines."""
    lines = structure.split("\n")
    if len(lines) <= max_lines:
        return structure
    return "\n".join(lines[:max_lines]) + (
        f"\n... ({len(lines) - max_lines} more entries omitted)\n"
    )


__all__ = ['_DELETED_FILE_RE', '_DEVNULL_DST_RE', '_DEVNULL_SRC_RE', '_DIFF_CHUNK_RE', '_DIFF_FILE_PATH_RE', '_DIFF_HUNK_RE', '_NEW_FILE_RE', '_TEMPLATES_DIR', 'IssueCategory', 'ItemSeverity', 'Path', 'PullRequestDiff', 'RepositoryContext', '_annotate_diff', '_classify_chunk', '_extract_surrounding_context', '_parse_diff_hunks', '_trim_diff', '_trim_file_contents', '_trim_repo_structure', 'annotations', 'dataclass', 'field', 'jinja2', 're']
