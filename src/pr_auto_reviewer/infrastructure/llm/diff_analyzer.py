from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

class DiffAnalyzer:

    _DIFF_CHUNK_RE = re.compile(r"(?=^diff --git )", re.MULTILINE)
    _DIFF_FILE_PATH_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)
    _DIFF_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", re.MULTILINE)
    _DELETED_FILE_RE = re.compile(r"^deleted file mode", re.MULTILINE)
    _NEW_FILE_RE = re.compile(r"^new file mode", re.MULTILINE)
    _DEVNULL_SRC_RE = re.compile(r"^--- /dev/null$", re.MULTILINE)
    _DEVNULL_DST_RE = re.compile(r"^\+\+\+ /dev/null$", re.MULTILINE)

    def parse_diff_hunks(self, diff_content: str) -> dict[str, list[tuple[int, int]]]:
        hunks: dict[str, list[tuple[int, int]]] = {}
        current_file: str | None = None
        current_hunk_start: int | None = None
        current_hunk_line = 0
        in_hunk = False

        for line in diff_content.split("\n"):
            m_file = self._DIFF_FILE_PATH_RE.match(line)
            if m_file:
                current_file = m_file.group(2)
                if current_file == "/dev/null":
                    current_file = None
                current_hunk_start = None
                in_hunk = False
                continue

            m_hunk = self._DIFF_HUNK_RE.match(line)
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

    def extract_context_around_hunks(
        self,
        content: str,
        hunks: list[tuple[int, int]],
        context_lines: int = 5,
        max_chars: int = 3000,
    ) -> str:
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

    def classify_diff_chunk(self, chunk: str) -> str:
        if self._DELETED_FILE_RE.search(chunk) or self._DEVNULL_DST_RE.search(chunk):
            return "[DELETED]"
        if self._NEW_FILE_RE.search(chunk) or self._DEVNULL_SRC_RE.search(chunk):
            return "[ADDED]"
        return "[MODIFIED]"

    def annotate_diff_with_markers(self, raw_diff: str) -> str:
        logger.debug("Annotating diff with markers: %d chars", len(raw_diff))
        chunks = self._DIFF_CHUNK_RE.split(raw_diff)
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
            change_type = self.classify_diff_chunk(chunk)
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

    def trim_diff_by_file_boundaries(self, raw_diff: str, max_tokens: int) -> str:
        from pr_auto_reviewer.infrastructure.llm.prompt_budget import PromptBudget

        if PromptBudget.estimate_tokens(raw_diff) <= max_tokens:
            logger.debug("Diff fits within budget (%d tokens)", max_tokens)
            return raw_diff

        logger.debug(
            "Trimming diff: %d tokens estimated, budget=%d",
            PromptBudget.estimate_tokens(raw_diff), max_tokens,
        )

        chunks = self._DIFF_CHUNK_RE.split(raw_diff)
        if chunks and not chunks[0].strip():
            chunks.pop(0)

        def _priority(chunk: str) -> int:
            kind = self.classify_diff_chunk(chunk)
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

        logger.debug(
            "Trimmed diff: %d kept chunks, %d chars",
            len(kept), len(result),
        )
        return result

    def trim_file_contents_to_limits(
        self,
        file_contents: dict[str, str],
        diff_content: str,
        max_files: int = 10,
        max_chars_per_file: int = 3000,
    ) -> dict[str, str]:
        if not file_contents:
            return {}

        hunks = self.parse_diff_hunks(diff_content)
        trimmed: dict[str, str] = {}

        for file_path, content in file_contents.items():
            if len(trimmed) >= max_files:
                break
            file_hunks = hunks.get(file_path, [])
            if file_hunks:
                context = self.extract_context_around_hunks(
                    content, file_hunks, context_lines=5, max_chars=max_chars_per_file
                )
            else:
                context = content[:max_chars_per_file]
                if len(content) > max_chars_per_file:
                    context += f"\n... (file truncated, {len(content)} total chars)\n"
            if context.strip():
                trimmed[file_path] = context

        logger.debug(
            "Trimmed file contents: %d files (limited to %d files, %d chars/file)",
            len(trimmed), max_files, max_chars_per_file,
        )
        return trimmed

    def trim_repo_structure_to_lines(
        self, structure: str, max_lines: int = 100
    ) -> str:
        lines = structure.split("\n")
        if len(lines) <= max_lines:
            return structure
        return "\n".join(lines[:max_lines]) + (
            f"\n... ({len(lines) - max_lines} more entries omitted)\n"
        )
