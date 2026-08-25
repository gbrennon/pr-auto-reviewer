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
from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
    CommandBusPort,
)
from pr_auto_reviewer.application.services.pr_identifier import (
    PRIdentifier,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.verify_findings_command import (
    VerifyFindingsCommand,
)
from pr_auto_reviewer.domain.messages.events.agent_exchange_event import (
    AgentExchangeEvent,
)
from pr_auto_reviewer.domain.value_objects.conversation_decision import (
    ConversationDecision,
)
from pr_auto_reviewer.domain.value_objects.conversation_guardrails import (
    ConversationGuardrails,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.sub_agent_role import SubAgentRole
from pr_auto_reviewer.infrastructure.templates.conversation_renderers import (
    ExploreBeforeResultsRenderer,
    VerifyEmptyResponseRenderer,
    VerifyInitialUserRenderer,
    VerifyUnparseableResponseRenderer,
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
        tool_factory: Callable[[Path, list[str], str], Any],
        command_bus: CommandBusPort | None = None,
        max_turns: int = _VERIFY_MAX_TURNS,
    ) -> None:
        self._chat_port = chat_port
        self._verify_prompt = verify_prompt
        self._tool_factory = tool_factory
        self._command_bus = command_bus
        self._max_turns = max_turns
        self._initial_user = VerifyInitialUserRenderer()
        self._empty_user = VerifyEmptyResponseRenderer()
        self._unparseable_user = VerifyUnparseableResponseRenderer()
        self._explore_before_results = ExploreBeforeResultsRenderer()

    def execute(self, command: VerifyFindingsCommand) -> list[ReviewItem]:
        """Drop synthetic findings, then LLM-verify every survivor.

        Verification covers all severities: the observed fabrication
        class publishes as minor findings that mechanical gates cannot
        refute (real snippets, wrong semantics), so severity is never a
        reason to skip semantic verification.  On verifier abort the
        fail-closed rule applies to blocking items only; non-blocking
        survivors pass through unverified rather than unpublished.
        """
        survivors = self._filter_synthetic_findings(
            list(command.items), command.repo_path,
        )
        if not survivors:
            logger.debug(
                "No findings survived the synthetic filter; "
                "verification skipped"
            )
            return []

        findings_text = self._format_findings_for_verification(
            survivors, command.repo_path
        )
        prompt = self._verify_prompt.replace("{findings}", findings_text)

        results, transcript = self._run_verification_transcript(
            system_prompt=prompt,
            repo_path=command.repo_path,
            changed_files=command.changed_files,
            base_sha=command.base_sha,
        )
        self._publish_exchange(
            command.repo_path, command.review_session, prompt, transcript,
        )

        if results is None:
            logger.warning(
                "Verification aborted; dropping all %d blocking "
                "findings as unverified",
                sum(1 for i in survivors if i.is_blocking),
            )
            return [i for i in survivors if not i.is_blocking]

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

        kept = [
            item
            for i, item in enumerate(survivors)
            if i in verified_indices
        ]

        dropped = len(survivors) - len(kept)
        if dropped:
            logger.info(
                "Verification dropped %d/%d findings as hallucinations",
                dropped,
                len(survivors),
            )

        return kept

    def _run_verification_conversation(
        self,
        system_prompt: str,
        repo_path: Path,
        changed_files: list[str],
        base_sha: str = "",
    ) -> list[dict[str, Any]] | None:
        """Run the verification conversation, returning only its results."""
        results, _transcript = self._run_verification_transcript(
            system_prompt=system_prompt,
            repo_path=repo_path,
            changed_files=changed_files,
            base_sha=base_sha,
        )
        return results

    def _run_verification_transcript(
        self,
        system_prompt: str,
        repo_path: Path,
        changed_files: list[str],
        base_sha: str = "",
    ) -> tuple[list[dict[str, Any]] | None, list[ConversationMessage]]:
        """Run the verification conversation, returning results and transcript."""
        tool_service = self._tool_factory(repo_path, changed_files, base_sha)

        messages: list[ConversationMessage] = [
            ConversationMessage(
                role="system", content=system_prompt
            ),
            self._initial_user.render(repo_path=repo_path),
        ]

        guardrails = ConversationGuardrails(
            max_turns=self._max_turns,
            max_empty_responses=_MAX_EMPTY_RESPONSES,
            max_unparseable_responses=_MAX_UNPARSEABLE_RESPONSES,
            exploration_required=True,
        )

        while guardrails.has_turns_remaining():
            guardrails = guardrails.advance_turn()
            logger.debug(
                "Verify turn %d/%d",
                guardrails.turn,
                guardrails.max_turns,
            )
            content = self._chat_port.send(messages)
            if not content:
                decision, guardrails = guardrails.record_empty_response()
                if decision == ConversationDecision.EXCEEDED_EMPTY:
                    logger.warning(
                        "Verification: %d consecutive empty responses; "
                        "aborting",
                        guardrails.consecutive_empty,
                    )
                    return None, messages
                logger.debug(
                    "Empty response at verify turn %d; reprompting",
                    guardrails.turn,
                )
                messages.append(self._empty_user.render())
                continue

            parsed = self._parse_verify_turn(content)
            if parsed is None:
                decision, guardrails = (
                    guardrails.record_unparseable_response()
                )
                if (
                    decision
                    == ConversationDecision.EXCEEDED_UNPARSEABLE
                ):
                    logger.warning(
                        "Verification: %d consecutive unparseable "
                        "responses; aborting",
                        guardrails.consecutive_unparseable,
                    )
                    return None, messages
                logger.debug(
                    "Unparseable response at verify turn %d; "
                    "reprompting",
                    guardrails.turn,
                )
                messages.append(self._unparseable_user.render())
                continue

            guardrails = guardrails.mark_consecutive_success()
            messages.append(ConversationMessage(
                role="assistant", content=content
            ))

            if isinstance(parsed, list):
                decision, guardrails = guardrails.judge_verdict()
                if decision == ConversationDecision.DEMAND_EXPLORATION:
                    logger.debug(
                        "Verifier produced results with no tool calls; "
                        "demanding exploration"
                    )
                    messages.append(
                        self._explore_before_results.render()
                    )
                    continue
                if (
                    decision
                    == ConversationDecision.REFUSED_EXPLORATION
                ):
                    logger.warning(
                        "Model refused exploration after %d "
                        "demand(s); aborting verification",
                        guardrails.demands_issued,
                    )
                    return None, messages
                logger.debug(
                    "Got verification results at turn %d",
                    guardrails.turn,
                )
                return parsed, messages

            guardrails = guardrails.record_tool_call()
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
            "Verification exceeded max turns (%d)", self._max_turns
        )
        return None, messages

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


    def _filter_synthetic_findings(
        self, items: list[ReviewItem], repo_path: Path,
    ) -> list[ReviewItem]:
        """Drop findings that are mechanically synthetic before LLM spend.

        Two gates, applied in order:

        **S4 — no-op fix**: ``current_code == suggested_fix`` verbatim.
        If the fix is byte-identical to the current code, the finding is
        fabricated — the model invented a problem with no real change.

        **S3 — snippet-existence**: ``current_code`` does not appear in
        the cited file.  When the file exists but the quoted snippet is
        absent, the model hallucinated the code it is "fixing."
        """
        survivors: list[ReviewItem] = []
        for item in items:
            current = item.current_code.strip()
            suggested = item.suggested_fix.strip()
            if current and current == suggested:
                logger.debug(
                    "S4 no-op gate: dropping finding %s — "
                    "current_code == suggested_fix",
                    item.id,
                )
                continue
            if item.file_path and current:
                full_path = repo_path / item.file_path
                if full_path.exists() and not self._snippet_matches_file(
                    current, full_path,
                ):
                    logger.debug(
                        "S3 snippet-existence gate: dropping finding %s — "
                        "current_code not found in %s",
                        item.id, item.file_path,
                    )
                    continue
            survivors.append(item)
        dropped = len(items) - len(survivors)
        if dropped:
            logger.info(
                "Synthetic-finding filter dropped %d/%d items before "
                "LLM verification",
                dropped, len(items),
            )
        return survivors

    def _snippet_matches_file(self, snippet: str, file_path: Path) -> bool:
        """Return whether *snippet* appears in *file_path*.

        Matching is an in-order subsequence test over stripped lines:
        every snippet line must appear in the file, in order, with
        possible gaps between matches. A snippet anchored to a real
        first line but carrying a fabricated body fails this gate.
        """
        try:
            file_text = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            return True
        snippet_lines = [
            ln.strip()
            for ln in snippet.split("\n")
            if ln.strip()
        ]
        if not snippet_lines:
            return True
        file_lines = iter(
            [ln.strip() for ln in file_text.split("\n")]
        )
        return all(
            any(snippet_line == file_line for file_line in file_lines)
            for snippet_line in snippet_lines
        )

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

    def _publish_exchange(
        self,
        repo_path: Path,
        review_session: str,
        system_prompt: str,
        transcript: list[ConversationMessage],
    ) -> None:
        """Emit the finished verification exchange for the transcript log."""
        if self._command_bus is None:
            return
        self._command_bus.dispatch(AgentExchangeEvent(
            role=SubAgentRole.VERIFIER,
            phase_name="Verify Findings",
            pr_identifier=PRIdentifier.derive(repo_path),
            review_session=review_session,
            messages=transcript,
        ))
