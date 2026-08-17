"""FindingVerifier — verify blocking findings against source code via agentic conversation."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pr_auto_reviewer.application.ports.inbound.verify_findings_use_case import (
    VerifyFindingsUseCase,
)
from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.domain.agent.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.verify_findings_command import (
    VerifyFindingsCommand,
)

logger = logging.getLogger(__name__)

_VERIFY_MAX_TURNS = 5
_MAX_EMPTY_RESPONSES = 3
_MAX_UNPARSEABLE_RESPONSES = 3

_FINDING_RESULT_LINE = re.compile(
    r"(?:- |#### )?\*?\*?(?:Finding|Item)\s*(\d+)\*?\*?\s*[:—-]\s*(.+)",
    re.IGNORECASE,
)


class FindingVerifier(VerifyFindingsUseCase):
    """Verify CRITICAL/MAJOR findings against actual source code.

    Runs a separate multi-turn agentic conversation where the LLM reads
    files, searches for symbols, and confirms or rejects each finding.
    Unverified findings are dropped as hallucinations.
    """

    def __init__(
        self,
        chat_port: AgentChatPort,
        verify_prompt: str,
        tool_factory: Callable[[Path, list[str]], Any],
    ) -> None:
        self._chat_port = chat_port
        self._verify_prompt = verify_prompt
        self._tool_factory = tool_factory

    def execute(self, command: VerifyFindingsCommand) -> list[ReviewItem]:
        """Verify blocking findings, returning only those confirmed by the LLM."""
        blocking = [
            i for i in command.items if i.is_blocking
        ]
        if not blocking:
            return list(command.items)

        findings_text = self._format_findings_for_verification(
            blocking, command.repo_path
        )
        prompt = self._verify_prompt.replace("{findings}", findings_text)

        results = self._run_verification_conversation(
            system_prompt=prompt,
            repo_path=command.repo_path,
            changed_files=command.changed_files,
        )

        if results is None:
            logger.warning(
                "Verification failed to produce results; preserving all "
                "%d blocking findings",
                len(blocking),
            )
            return list(command.items)

        verified_indices: set[int] = set()
        for r in results:
            idx = r.get("finding_index")
            verified = r.get("verified", False)
            if verified and isinstance(idx, int):
                verified_indices.add(idx)
            else:
                logger.debug(
                    "Verifier refuted finding: verified=%s idx=%s reasoning=%s",
                    verified,
                    idx,
                    r.get("reasoning", "")[:120],
                )

        verified_blocking: list[ReviewItem] = []
        for i, item in enumerate(blocking):
            if i not in verified_indices:
                continue
            item_current = item.current_code.strip()
            item_suggested = item.suggested_fix.strip()
            if item_current == item_suggested and item_current:
                logger.debug(
                    "Item %d: current_code == suggested_fix; "
                    "treating as unverified",
                    item.number,
                )
                continue
            verified_blocking.append(item)

        dropped = len(blocking) - len(verified_blocking)
        if dropped == 0:
            return list(command.items)

        logger.info(
            "Verification dropped %d/%d blocking findings as hallucinations",
            dropped,
            len(blocking),
        )

        non_blocking = [
            i for i in command.items if not i.is_blocking
        ]
        return non_blocking + verified_blocking

    def _run_verification_conversation(
        self,
        system_prompt: str,
        repo_path: Path,
        changed_files: list[str],
    ) -> list[dict[str, Any]] | None:
        """Run a multi-turn verification conversation with tool access."""
        tool_service = self._tool_factory(repo_path, changed_files)

        messages: list[ConversationMessage] = [
            ConversationMessage(
                role="system", content=system_prompt
            ),
            ConversationMessage(
                role="user",
                content=(
                    f"Repository path: {repo_path}\n\n"
                    "Verify each finding above against the ACTUAL source code. "
                    "Use read_file to inspect files, search_codebase to locate "
                    "symbols, and list_directory to explore the repository. "
                    "You have access to read_file, search_codebase, "
                    "list_directory, run_git, and get_changed_files tools.\n\n"
                    "For tool calls, respond with a JSON object containing "
                    "'action' and 'args' keys.\n"
                    "When verification is complete, respond with a JSON object "
                    "containing a 'results' array."
                ),
            ),
        ]

        empty_consecutive = 0
        unparseable_consecutive = 0
        for turn in range(_VERIFY_MAX_TURNS):
            logger.debug(
                "Verify turn %d/%d", turn + 1, _VERIFY_MAX_TURNS
            )
            content = self._chat_port.send(messages)
            if not content:
                empty_consecutive += 1
                if empty_consecutive >= _MAX_EMPTY_RESPONSES:
                    logger.warning(
                        "Verification: %d consecutive empty responses; "
                        "aborting",
                        empty_consecutive,
                    )
                    return None
                logger.debug(
                    "Empty response at verify turn %d; reprompting",
                    turn + 1,
                )
                messages.append(ConversationMessage(
                    role="user",
                    content=(
                        "Your previous response was empty. Please verify "
                        "each finding and respond with a JSON object "
                        "containing a 'results' array."
                    ),
                ))
                continue

            empty_consecutive = 0

            parsed = self._parse_verify_turn(content)
            if parsed is None:
                unparseable_consecutive += 1
                if (
                    unparseable_consecutive
                    >= _MAX_UNPARSEABLE_RESPONSES
                ):
                    logger.warning(
                        "Verification: %d consecutive unparseable "
                        "responses; aborting",
                        unparseable_consecutive,
                    )
                    return None
                logger.debug(
                    "Unparseable response at verify turn %d; reprompting",
                    turn + 1,
                )
                messages.append(ConversationMessage(
                    role="user",
                    content=(
                        "Your previous response was not valid JSON. "
                        "Please respond with a JSON object containing "
                        "either 'action' and 'args' for tool calls, "
                        "or 'results' for your verification results."
                    ),
                ))
                continue
            unparseable_consecutive = 0

            messages.append(ConversationMessage(
                role="assistant", content=content
            ))

            if isinstance(parsed, list):
                logger.debug(
                    "Got verification results at turn %d", turn + 1
                )
                return parsed

            action = parsed["action"]
            args = parsed.get("args", "")
            logger.debug(
                "Verify tool call — action=%s args=%s",
                action,
                str(args)[:200],
            )
            result = tool_service.execute(action, args)
            result_json = json.dumps(result)
            logger.debug(
                "Tool result (%d chars): %s",
                len(result_json),
                result_json[:300],
            )
            messages.append(ConversationMessage(
                role="user",
                content=result_json,
            ))

        logger.warning(
            "Verification exceeded max turns (%d)", _VERIFY_MAX_TURNS
        )
        return None

    def _parse_verify_turn(
        self, content: str
    ) -> list[dict[str, Any]] | dict[str, str] | None:
        """Parse a verification conversation turn into results or a tool-call dict."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return self._parse_verify_prose(content)

        if not isinstance(data, dict):
            return None

        if "results" in data and isinstance(data["results"], list):
            return data["results"]

        if "action" in data and isinstance(data["action"], str):
            return data

        return None

    def _parse_verify_prose(
        self, content: str
    ) -> list[dict[str, Any]] | None:
        """Parse verification results from narrative prose instead of JSON."""
        results: list[dict[str, Any]] = []
        for match in _FINDING_RESULT_LINE.finditer(content):
            idx_str = match.group(1)
            rest = match.group(2).strip().lower()
            verified = not any(
                kw in rest
                for kw in (
                    "refuted",
                    "not found",
                    "doesn't exist",
                    "hallucinated",
                    "cannot verify",
                    "unable to",
                )
            )
            finding_index = int(idx_str)
            results.append(
                {
                    "finding_index": finding_index,
                    "verified": verified,
                    "reasoning": match.group(2).strip()[:200],
                }
            )
        return results if results else None

    def _format_findings_for_verification(
        self, items: list[ReviewItem], repo_path: Path
    ) -> str:
        """Format blocking findings with surrounding file context for verification."""
        parts: list[str] = []
        repo_root = repo_path

        for i, item in enumerate(items):
            file_content = ""
            if item.file_path:
                full_path = repo_root / item.file_path
                if full_path.exists():
                    file_content = self._extract_file_context(
                        full_path, item.current_code
                    )

            parts.append(
                f"## Finding {i}\n\n"
                f"- **File:** `{item.file_path or '(unknown)'}`\n"
                f"- **Severity:** {item.severity.value}\n"
                f"- **Category:** {item.category.value}\n"
                f"- **Description:** {item.description}\n"
                f"- **Current code:**\n```\n{item.current_code}\n```\n"
                f"- **Suggested fix:**\n```\n{item.suggested_fix}\n```\n"
                f"- **File content (surrounding context):**\n```\n{file_content}\n```\n"
            )

        return "\n\n".join(parts)

    def _extract_file_context(
        self, file_path: Path, snippet: str
    ) -> str:
        """Extract surrounding context from a file around a matching code snippet."""
        try:
            file_text = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            return "(file could not be read)"

        if not snippet or not snippet.strip():
            return file_text[:2000]

        snippet_lines = [
            ln.strip()
            for ln in snippet.strip().split("\n")
            if ln.strip()
        ]

        file_lines = file_text.split("\n")
        first_snippet_line = snippet_lines[0]

        match_line = None
        for idx, line in enumerate(file_lines):
            if line.strip() == first_snippet_line:
                match_line = idx
                break

        if match_line is None:
            for idx, line in enumerate(file_lines):
                if first_snippet_line in line.strip():
                    match_line = idx
                    break

        if match_line is None:
            return file_text[:2000]

        window_start = max(0, match_line - 10)
        window_end = min(len(file_lines), match_line + 50)
        return "\n".join(file_lines[window_start:window_end])
