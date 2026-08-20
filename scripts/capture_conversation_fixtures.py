"""Capture real-world review conversations into reusable JSON fixtures.

Reads the markdown conversation logs under
``~/.config/pr-auto-reviewer/conversations/`` (one nested directory per PR)
and emits one JSON fixture per phase plus a manifest, optionally extracting
the final ``--- JSON ---`` review payload from captured terminal outputs.

Usage:

.. code-block:: bash

    uv run python -m scripts.capture_conversation_fixtures \
        --logs-dir ~/.config/pr-auto-reviewer/conversations \
        --out-dir tests/fixtures/conversations \
        [--pr gbrennon_pr-auto-reviewer_146]

The emitted fixtures feed the behavior tests in
``tests/e2e/test_captured_review_no_defaults.py``; point the case registry
at them after capture.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, ClassVar


class ConversationLogParser:
    """Parse one MarkdownConversationLogger log file into structured data."""

    _HEADER_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        ("agent: ", "agent_role"),
        ("phase: ", "phase_name"),
        ("pr: ", "pr"),
        ("model: ", "model"),
        ("turns: ", "turns_line"),
    ]

    _SECTION_RE = re.compile(r"^(?:#+\s*)?(Sent|Received) — ([^—]+) \((.+)\)$")
    _TURN_RE = re.compile(r"^## Turn (\d+)$")
    _TS_RE = re.compile(r"^## 20\d{6}_\d{6}$")

    def parse_file(self, path: Path) -> dict[str, Any]:
        """Parse *path* and return a phase fixture dict."""
        path = Path(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        meta: dict[str, str] = {}
        messages: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        turn = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                stripped = stripped[1:].strip()
            lower = stripped.lower()
            matched = False
            for prefix, key in self._HEADER_PATTERNS:
                if lower.startswith(prefix):
                    meta[key] = stripped.split(" ", 1)[1].strip()
                    matched = True
                    break
            if matched:
                continue
            if self._TS_RE.match(stripped):
                meta["timestamp"] = stripped[2:].strip()
                continue
            turn_match = self._TURN_RE.match(stripped)
            if turn_match:
                turn = int(turn_match.group(1))
                continue
            section_match = self._SECTION_RE.match(stripped)
            if section_match:
                direction, kind, role = section_match.groups()
                current = {
                    "turn": turn,
                    "direction": direction.lower(),
                    "kind": kind.strip().lower(),
                    "role": role.strip(),
                    "content": "",
                }
                messages.append(current)
                continue
            if current is not None:
                current["content"] += ("" if not current["content"] else "\n") + line

        verdict, items_count, turns = "", 0, 0
        if meta.get("turns_line"):
            match = re.match(
                r"(\d+)\s*\|\s*verdict:\s*([^\|]+)\s*\|\s*items:\s*(\d+)",
                meta["turns_line"],
                re.IGNORECASE,
            )
            if match:
                turns = int(match.group(1))
                verdict = match.group(2).strip()
                items_count = int(match.group(3))

        parsed_messages = [self._parse_message(m) for m in messages]
        return {
            "source_file": str(path),
            "pr": meta.get("pr", ""),
            "phase_name": meta.get("phase_name", path.stem),
            "agent_role": meta.get("agent_role", "unknown"),
            "model": meta.get("model", ""),
            "timestamp": meta.get("timestamp", ""),
            "turns": turns,
            "llm_verdict": verdict,
            "items_count": items_count,
            "messages": parsed_messages,
        }

    def _parse_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Return a message with embedded JSON payloads parsed when possible."""
        content = message["content"].strip()
        parsed: Any = None
        if message["kind"] in ("answer", "tool call", "tool result"):
            parsed = self._extract_json(content)
        return {
            "turn": message["turn"],
            "direction": message["direction"],
            "kind": message["kind"],
            "role": message["role"],
            "content_length": len(content),
            "content_preview": content[:2000],
            "json": parsed,
        }

    def _extract_json(self, text: str) -> Any:
        """Parse the first JSON object/array found in *text*, else None."""
        cleaned = text.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        for open_char, close_char in (("{", "}"), ("[", "]")):
            start = cleaned.find(open_char)
            if start == -1:
                continue
            depth = 0
            in_string = False
            for idx in range(start, len(cleaned)):
                ch = cleaned[idx]
                if ch == '"':
                    in_string = not in_string
                if in_string:
                    continue
                if ch == open_char:
                    depth += 1
                elif ch == close_char:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(cleaned[start : idx + 1])
                        except json.JSONDecodeError:
                            return None
        return None


class FinalReviewExtractor:
    """Extract the ``--- JSON ---`` payload from a captured terminal output."""

    def extract(self, text: str) -> dict[str, Any] | None:
        """Return the JSON block after ``--- JSON ---``, or None."""
        marker = "--- JSON ---"
        if marker not in text:
            return None
        section = text.split(marker, 1)[1]
        section = re.split(r"\n=+", section, 1)[0].strip()
        try:
            payload = json.loads(section)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None


class ConversationFixtureCapture:
    """Walk conversation logs and write JSON fixtures + a manifest."""

    def __init__(self, logs_dir: Path, out_dir: Path) -> None:
        self._logs_dir = logs_dir
        self._out_dir = out_dir
        self._parser = ConversationLogParser()
        self._final_extractor = FinalReviewExtractor()

    def run(self, pr_filter: str | None = None) -> list[dict[str, Any]]:
        """Capture all logs (optionally filtered by *pr_filter*) into fixtures."""
        self._out_dir.mkdir(parents=True, exist_ok=True)
        manifest: list[dict[str, Any]] = []
        for log_file in sorted(self._logs_dir.rglob("*.md")):
            if pr_filter and pr_filter not in str(log_file.parent):
                continue
            fixture = self._parser.parse_file(log_file)
            pr_dir = self._out_dir / log_file.parent.name
            pr_dir.mkdir(parents=True, exist_ok=True)
            stem = log_file.stem
            target = pr_dir / f"{stem}.json"
            target.write_text(
                json.dumps(fixture, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            manifest.append({
                "case_id": f"{log_file.parent.name}/{stem}",
                "pr": fixture["pr"],
                "phase_name": fixture["phase_name"],
                "verdict": fixture["llm_verdict"],
                "turns": fixture["turns"],
                "items_count": fixture["items_count"],
                "fixture": str(target),
            })
            self._extract_terminal_payloads(pr_dir, log_file.parent, stem)
        manifest_path = self._out_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return manifest

    def _extract_terminal_payloads(self, pr_dir: Path, logs_pr_dir: Path, stem: str) -> None:
        """Extract a ``--- JSON ---`` payload from sibling .txt/.out files."""
        candidates = sorted(logs_pr_dir.glob("*.txt")) + sorted(logs_pr_dir.glob("*.out"))
        for sibling in candidates:
            payload = self._final_extractor.extract(
                sibling.read_text(encoding="utf-8", errors="replace")
            )
            if payload is not None:
                (pr_dir / f"final_review_{stem}.json").write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )


def main(argv: list[str] | None = None) -> int:
    """Run the capture from CLI arguments."""
    argv = argv if argv is not None else sys.argv[1:]
    args: dict[str, str] = {}
    for i in range(0, len(argv) - 1, 2):
        args[argv[i]] = argv[i + 1]
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0

    default_logs = Path.home() / ".config" / "pr-auto-reviewer" / "conversations"
    logs_dir = Path(args.get("--logs-dir", str(default_logs)))
    out_dir = Path(args.get("--out-dir", "tests/fixtures/conversations"))
    pr_filter = args.get("--pr")

    if not logs_dir.is_dir():
        print(f"Logs dir not found: {logs_dir}", file=sys.stderr)
        return 1

    capture = ConversationFixtureCapture(logs_dir, out_dir)
    manifest = capture.run(pr_filter=pr_filter)
    print(f"Captured {len(manifest)} phase fixtures into {out_dir}")
    print(f"Manifest: {out_dir / 'manifest.json'}")
    for entry in manifest[:20]:
        print(
            f"  {entry['case_id']}  verdict={entry['verdict']}"
            f" turns={entry['turns']} items={entry['items_count']}"
        )
    if len(manifest) > 20:
        print(f"  ... {len(manifest) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())