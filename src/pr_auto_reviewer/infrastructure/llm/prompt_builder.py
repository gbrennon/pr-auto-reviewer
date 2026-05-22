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
7. ``static instructions`` — use compact template if configured
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

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




@dataclass
class PromptBudget:
    """Tracks token consumption for budget-aware prompt construction.

    Uses a rough heuristic of 1 token ≈ 4 characters. For production use
    with more accurate counting, integrate ``tiktoken``.
    """

    max_tokens: int
    _consumed: int = field(default=0, init=False, repr=False)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self._consumed)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimate: 1 token ≈ 4 characters."""
        return len(text) // 4

    def consume(self, text: str) -> int:
        """Mark *text* as consumed, return its estimated token count."""
        tokens = self.estimate_tokens(text)
        self._consumed += tokens
        return tokens

    def would_fit(self, text: str) -> bool:
        """Return True if *text* fits within the remaining budget."""
        return self._consumed + self.estimate_tokens(text) <= self.max_tokens

    def try_consume(self, text: str) -> bool:
        """Consume *text* if it fits; return True when consumed."""
        if self.would_fit(text):
            self.consume(text)
            return True
        return False




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
            if line.startswith("+") or line.startswith(" ") or line.startswith("-"):
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


# -- File-status markers (module-level) ---------------------------------------


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




class PromptBuilder:
    """Build the prompt sent to the LLM from a diff + review context.

    Parameters
    ----------
    template_dir:
        Directory containing Jinja2 templates. Defaults to ``templates/``.
    max_tokens:
        Soft cap on total prompt tokens. ``0`` = unlimited (legacy mode).
    max_file_chars:
        Maximum characters per file in the file-contents section.
    max_files:
        Maximum number of files to include in the file-contents section.
    max_structure_lines:
        Maximum lines in the repository-structure section.
    use_compact_template:
        Use ``review_prompt_compact.j2`` (~4 KB) instead of the full template.
    """

    def __init__(
        self,
        template_dir: Path | None = None,
        max_tokens: int = 0,
        max_file_chars: int = 3000,
        max_files: int = 10,
        max_structure_lines: int = 100,
        use_compact_template: bool = False,
    ) -> None:
        self._max_tokens = max_tokens
        self._max_file_chars = max_file_chars
        self._max_files = max_files
        self._max_structure_lines = max_structure_lines
        self._use_compact_template = use_compact_template
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir or _TEMPLATES_DIR)),
            keep_trailing_newline=True,
        )

    def build(self, diff: PullRequestDiff, context: RepositoryContext) -> str:
        """Build a prompt using token-budget-aware allocation.

        When ``self._max_tokens > 0``, sections are prioritised and
        trimmed to fit within the budget. In legacy mode (max_tokens=0),
        all sections are included as-is for backward compatibility.
        """
        template_name = (
            "review_prompt_compact.j2" if self._use_compact_template
            else "review_prompt.j2"
        )
        template = self._env.get_template(template_name)

        conventions = context.conventions or diff.conventions
        repo_structure = context.repository_structure or diff.repository_structure
        annotated_diff = _annotate_diff(diff.diff_content)

        # --- unlimited mode (legacy) ----------------------------------------
        if self._max_tokens <= 0:
            return template.render(
                architecture_hint=(
                    context.architecture_hint if context.architecture_hint else None
                ),
                conventions=conventions if conventions else None,
                repository_structure=repo_structure if repo_structure else None,
                file_contents=diff.file_contents if diff.file_contents else None,
                annotated_diff=annotated_diff,
                pr_title=context.pr_title if context.pr_title else None,
                pr_description=(
                    context.pr_description if context.pr_description else None
                ),
                commit_messages=(
                    diff.commit_messages if diff.commit_messages else None
                ),
            )

        budget = PromptBudget(max_tokens=self._max_tokens)

        budget.consume(context.pr_title or "")
        budget.consume(context.pr_description or "")
        for msg in (diff.commit_messages or []):
            budget.consume(msg)

        if budget.would_fit(annotated_diff):
            budget.consume(annotated_diff)
        else:
            allowed_diff_tokens = max(
                int(self._max_tokens * 0.6),
                self._max_tokens - budget._consumed - 500,
            )
            annotated_diff = _annotate_diff(
                _trim_diff(diff.diff_content, allowed_diff_tokens)
            )
            budget.consume(annotated_diff)

        # Priority 3: File contents (trimmed)
        file_contents = None
        if diff.file_contents and budget.remaining_tokens > 500:
            trimmed_fc = _trim_file_contents(
                diff.file_contents,
                diff.diff_content,
                max_files=self._max_files,
                max_chars_per_file=self._max_file_chars,
            )
            if trimmed_fc and budget.would_fit(str(trimmed_fc)):
                file_contents = trimmed_fc
                budget.consume(str(trimmed_fc))

        if conventions and budget.remaining_tokens > 200:
            budget.consume(conventions)

        if context.architecture_hint and budget.remaining_tokens > 100:
            budget.consume(context.architecture_hint)

        # Priority 6: Repo structure (trimmed)
        if repo_structure and budget.remaining_tokens > 200:
            trimmed_structure = _trim_repo_structure(
                repo_structure, self._max_structure_lines
            )
            if budget.would_fit(trimmed_structure):
                repo_structure = trimmed_structure
                budget.consume(trimmed_structure)
            else:
                repo_structure = None

        return template.render(
            architecture_hint=(
                context.architecture_hint if context.architecture_hint else None
            ),
            conventions=conventions if conventions else None,
            repository_structure=repo_structure if repo_structure else None,
            file_contents=file_contents,
            annotated_diff=annotated_diff,
            pr_title=context.pr_title if context.pr_title else None,
            pr_description=(
                context.pr_description if context.pr_description else None
            ),
            commit_messages=(
                diff.commit_messages if diff.commit_messages else None
            ),
        )
