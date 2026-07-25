"""Staged multi-phase code review via Ollama chat API with exploration tools."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

from pr_auto_reviewer.application.ports.outbound.llm_review_port import (
    LlmReviewPort,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
    ComposedPrompt,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import (
    ReviewVerdict,
)
from pr_auto_reviewer.infrastructure.llm.exploration_tool_service import (
    ExplorationToolService,
)
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)

logger = logging.getLogger(__name__)

_PHASE_PROMPT_DIR = (
    Path(__file__).resolve().parent.parent
    / "fragments"
    / "content"
    / "universal"
)

_PHASES: list[tuple[str, str]] = [
    ("bug-hunt-diff", "Bug Hunt — Diff"),
    ("bug-hunt-branch", "Bug Hunt — Branch"),
    ("architecture-review", "Architecture Review"),
]


class OllamaExploratoryChatAdapter(LlmReviewPort):
    """Staged multi-phase review using Ollama's chat API with exploration tools.

    Runs three phases in sequence:
    1. bug-hunt-diff — static diff analysis
    2. bug-hunt-branch — runtime-aware branch analysis with run_git access
    3. architecture-review — cross-file design and pattern review

    Findings from earlier phases are injected into later prompts via
    ``__PREVIOUS_FINDINGS__`` markers.
    """

    _MAX_TURNS = 10
    _MAX_EMPTY_RESPONSES = 3
    _MAX_UNPARSEABLE_RESPONSES = 3
    _FINDINGS_MARKER = "__PREVIOUS_FINDINGS__"

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        ollama_timeout: int = 120,
        max_retries: int = 5,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = ollama_timeout
        self._max_retries = max_retries
        self._parser = ReviewResponseParser()

    def review_prompt(self, composed: ComposedPrompt) -> CodeReview:
        """Run all review phases against the composed prompt's repository."""
        repo_path = composed.repo_path
        if not repo_path or not repo_path.strip():
            raise ValueError(
                "repo_path is required for staged multi-phase review"
            )
        return self._run_phases(repo_path.strip())

    def review(self, diff: object, context: object) -> CodeReview:
        """Not used in production; raises NotImplementedError."""
        raise NotImplementedError(
            "Use review_prompt(ComposedPrompt) for staged multi-phase review"
        )

    @classmethod
    def _load_phase_prompt(cls, phase_id: str) -> str:
        """Load a phase prompt markdown file, stripping YAML frontmatter."""
        path = _PHASE_PROMPT_DIR / f"{phase_id}.md"
        raw = path.read_text()
        return ReviewResponseParser.strip_frontmatter(raw)

    def _run_phases(self, repo_path: str) -> CodeReview:
        """Orchestrate all review phases, merging results."""
        all_items: list[ReviewItem] = []
        previous_findings: str = ""

        for phase_id, phase_name in _PHASES:
            logger.info("Starting phase: %s", phase_name)
            phase_prompt = self._load_phase_prompt(phase_id)

            if self._FINDINGS_MARKER in phase_prompt:
                phase_prompt = phase_prompt.replace(
                    self._FINDINGS_MARKER,
                    previous_findings or "No findings from prior phases.",
                )

            tool_service = ExplorationToolService(repo_path)
            phase_items = self._run_conversation(
                system_prompt=phase_prompt,
                repo_path=repo_path,
                tool_service=tool_service,
            )
            all_items.extend(phase_items)
            previous_findings = json.dumps(
                [
                    {
                        "file": item.file_path,
                        "severity": str(item.severity),
                        "category": str(item.category),
                        "description": item.description,
                    }
                    for item in all_items
                ],
                indent=2,
            )
            logger.info(
                "Phase %s complete: %d findings (total: %d)",
                phase_name,
                len(phase_items),
                len(all_items),
            )

        if not all_items:
            return CodeReview(
                verdict=ReviewVerdict.APPROVED,
                reason="No issues found across all review phases.",
                model_used=self._model,
            )

        return self._merge_items(all_items)

    def _run_conversation(
        self,
        system_prompt: str,
        repo_path: str,
        tool_service: ExplorationToolService,
    ) -> list[ReviewItem]:
        """Run a single-phase multi-turn conversation with tool access."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Repository path: {repo_path}\n\n"
                    "You have access to read_file, search_codebase, "
                    "list_directory, and run_git tools.\n"
                    "When you have completed your review for this phase, "
                    'respond with a JSON object containing "verdict" and '
                    '"items" keys.\n'
                    "For tool calls, respond with a JSON object containing "
                    '"action" and "args" keys.'
                ),
            },
        ]

        empty_consecutive = 0
        unparseable_consecutive = 0
        for turn in range(self._MAX_TURNS):
            logger.debug("Turn %d/%d", turn + 1, self._MAX_TURNS)
            content = self._stream_chat(messages)
            if not content:
                empty_consecutive += 1
                if empty_consecutive >= self._MAX_EMPTY_RESPONSES:
                    raise LlmUnavailableError(
                        f"LLM returned empty response {empty_consecutive} "
                        f"consecutive times at turn {turn + 1}"
                    )
                logger.debug(
                    "Empty response at turn %d; reprompting",
                    turn + 1,
                )
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous response was empty. Please continue "
                        "your analysis or provide your review findings as "
                        'a JSON object with "verdict" and "items" keys.'
                    ),
                })
                continue

            empty_consecutive = 0

            parsed = self._parse_turn(content)
            if parsed is None:
                unparseable_consecutive += 1
                if unparseable_consecutive >= self._MAX_UNPARSEABLE_RESPONSES:
                    raise LlmUnavailableError(
                        f"LLM returned unparseable response "
                        f"{unparseable_consecutive} consecutive times "
                        f"at turn {turn + 1}"
                    )
                logger.debug(
                    "Unparseable response at turn %d; reprompting",
                    turn + 1,
                )
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous response was not valid JSON. Please "
                        "respond with a JSON object containing either "
                        "'action' and 'args' for tool calls, or 'verdict' "
                        "and 'items' for your final review findings."
                    ),
                })
                continue
            unparseable_consecutive = 0

            messages.append({"role": "assistant", "content": content})

            if isinstance(parsed, list):
                logger.debug("Got verdict at turn %d", turn + 1)
                return parsed

            result = tool_service.execute(
                parsed["action"], parsed.get("args", "")
            )
            messages.append({
                "role": "user",
                "content": json.dumps(result),
            })

        raise LlmUnavailableError(
            f"Phase exceeded max turns ({self._MAX_TURNS}) without a verdict"
        )

    def _merge_items(self, items: list[ReviewItem]) -> CodeReview:
        """Deduplicate and merge items across phases into a CodeReview."""
        seen: set[tuple[str, str, str, str]] = set()
        merged: list[ReviewItem] = []

        for item in items:
            key = (
                item.file_path or "",
                str(item.severity),
                str(item.category),
                item.description,
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)

        for i, item in enumerate(merged, 1):
            object.__setattr__(item, "number", i)

        has_blocking = any(item.severity.is_blocking for item in merged)
        verdict = (
            ReviewVerdict.CHANGES_REQUESTED
            if has_blocking
            else ReviewVerdict.APPROVED
        )

        return CodeReview(
            verdict=verdict,
            reason=(
                f"Merged {len(merged)} unique findings from "
                f"{len(_PHASES)} review phases."
            ),
            items=merged,
            model_used=self._model,
        )

    def _parse_turn(
        self, content: str
    ) -> list[ReviewItem] | dict[str, str] | None:
        """Parse a conversation turn into items or a tool-call dict.

        Returns a list of ``ReviewItem`` when ``parse_items`` succeeds,
        a ``{"action": ..., "args": ...}`` dict for a tool call, or
        ``None`` when the content is not parseable.
        """
        items = self._parser.parse_items(content)
        if items:
            review_items: list[ReviewItem] = []
            for i, item_dict in enumerate(items, 1):
                review_item = ReviewItem(
                    number=i,
                    severity=str(item_dict.get("severity", "info")),
                    category=str(
                        item_dict.get("category", "maintainability")
                    ),
                    file_path=str(item_dict.get("file", "")),
                    description=str(item_dict.get("description", "")),
                    line=str(item_dict.get("line", "")),
                    current_code=str(item_dict.get("current_code", "")),
                    suggested_fix=str(item_dict.get("suggested_fix", "")),
                )
                review_items.append(review_item)
            return review_items

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.debug("Failed to parse turn content as JSON.")
            return None

        if isinstance(parsed, dict) and "action" in parsed:
            return {
                "action": str(parsed["action"]),
                "args": str(parsed.get("args", "")),
            }

        return None

    def _stream_chat(self, messages: list[dict[str, Any]]) -> str:
        """Send chat messages to Ollama and accumulate the streamed response."""
        url = f"{self._host}/api/chat"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "format": "json",
        }
        for attempt in range(self._max_retries):
            try:
                http_response = requests.post(
                    url,
                    json=payload,
                    timeout=self._timeout,
                    stream=True,
                )
                http_response.raise_for_status()
                content_parts: list[str] = []
                for line in http_response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        chunk: dict[str, Any] = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(
                            "Failed to parse streaming line as JSON "
                            "(attempt %d/%d): %.300s",
                            attempt + 1,
                            self._max_retries,
                            line,
                        )
                        raise
                    content_parts.append(
                        chunk.get("message", {}).get("content", "")
                    )
                    if chunk.get("done"):
                        break
                result = "".join(content_parts)
                logger.debug(
                    "Chat response: %d chars from %d lines, %d messages",
                    len(result),
                    len(content_parts),
                    len(messages),
                )
                return result
            except json.JSONDecodeError:
                if attempt == self._max_retries - 1:
                    raise LlmUnavailableError(
                        f"LLM chat API returned unparseable streaming "
                        f"response after {self._max_retries} attempts"
                    )
                time.sleep(2**attempt)
            except requests.RequestException as exc:
                if attempt == self._max_retries - 1:
                    raise LlmUnavailableError(
                        f"Chat request to {url} failed after "
                        f"{self._max_retries} attempts: {exc}"
                    ) from exc
                logger.warning(
                    "Chat attempt %d/%d failed, retrying...",
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(2**attempt)
        raise LlmUnavailableError("All chat requests exhausted")
