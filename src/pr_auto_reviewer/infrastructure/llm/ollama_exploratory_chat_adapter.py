"""Staged multi-phase code review via Ollama chat API with exploration tools."""

from __future__ import annotations

import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any, ClassVar

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

_METHODOLOGY = (
    "\n## ANTI-HALLUCINATION RULES\n\n"
    "Before identifying any issue in a file, you MUST read that file first.\n"
    "Never reference a file path or symbol you have not confirmed exists\n"
    "via read_file, search_codebase, or list_directory.\n"
    "Every finding MUST be grounded in code you actually observed.\n"
    "If a tool returns an error (e.g. file not found, permission denied),\n"
    "do NOT report that error as a finding. Either retry with a corrected\n"
    "path or skip the file entirely. Tool errors are not code issues.\n"
    "If the repository appears to be in a language you do not understand,\n"
    "say so — never fabricate findings in a different language.\n"
    "After reading each file, describe what you observed before forming judgments.\n"
    "Only include findings whose evidence comes from code you successfully read.\n"
)


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

    _FABRICATED_ERROR_PATTERNS: ClassVar[tuple[str, ...]] = (
        "file not found",
        "unable to verify",
        "cannot access",
        "could not read",
        "does not exist",
        "not accessible",
        "not found in",
        "could not be found",
        "unable to locate",
    )

    _DUPLICATE_SUFFIX = ". This was previously identified but may have additional instances."

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
        changed_files = self._extract_file_listing(composed.content)
        return self._run_phases(repo_path.strip(), changed_files)

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
    @staticmethod
    def _extract_file_listing(composed_content: str) -> list[str]:
        """Extract changed file paths from the rendered prompt's diff section."""
        paths: set[str] = set()
        seen_section = False
        for line in composed_content.split("\n"):
            if line.startswith("## Diff"):
                seen_section = True
                continue
            if not seen_section:
                continue
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                raw = line.split(" ", 1)[1] if " " in line else ""
                if not raw:
                    continue
                if raw == "/dev/null":
                    continue
                if raw.startswith(("a/", "b/")):
                    raw = raw[2:]
                paths.add(raw)
        return sorted(paths)

    def _run_phases(self, repo_path: str, changed_files: list[str]) -> CodeReview:
        """Orchestrate all review phases, merging results."""
        all_items: list[ReviewItem] = []
        previous_findings: str = ""

        for phase_id, phase_name in _PHASES:
            logger.info("Starting phase: %s", phase_name)
            phase_prompt = _METHODOLOGY + "\n\n" + self._load_phase_prompt(phase_id)

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
                changed_files=changed_files,
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
        changed_files: list[str],
    ) -> list[ReviewItem]:
        """Run a single-phase multi-turn conversation with tool access."""
        file_listing = "\n  - ".join(changed_files) if changed_files else "(none)"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Changed files for this review:\n"
                    f"  - {file_listing}\n\n"
                    f"Repository path: {repo_path}\n\n"
                    "Use run_git log or run_git diff to discover what "
                    "changed, then use read_file to inspect files.\n"
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

            parsed = self._parse_turn(content, repo_path)
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

            action = parsed["action"]
            args = parsed.get("args", "")
            logger.debug(
                "Tool call — action=%s args=%s",
                action,
                str(args)[:200],
            )
            result = tool_service.execute(action, args)
            result_truncated = json.dumps(result)[:300]
            logger.debug(
                "Tool result (%d chars): %s",
                len(json.dumps(result)),
                result_truncated,
            )
            messages.append({
                "role": "user",
                "content": json.dumps(result),
            })

        fd, dump_path = tempfile.mkstemp(
            prefix="pr-review-exhausted-",
            suffix=".json",
        )
        with open(fd, "w") as f:
            json.dump(messages, f, indent=2, default=str)
        raise LlmUnavailableError(
            f"Phase exceeded max turns ({self._MAX_TURNS}) without a verdict. "
            f"Full conversation dumped to {dump_path}"
        )

    def _merge_items(self, items: list[ReviewItem]) -> CodeReview:
        """Deduplicate and merge items across phases into a CodeReview."""
        seen: set[tuple[str, str, str, str]] = set()
        merged: list[ReviewItem] = []

        for item in items:
            desc = item.description
            if desc.endswith(self._DUPLICATE_SUFFIX):
                desc = desc[: -len(self._DUPLICATE_SUFFIX)]
            key = (
                item.file_path or "",
                str(item.severity),
                str(item.category),
                desc,
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
        self, content: str, repo_path: str
    ) -> list[ReviewItem] | dict[str, str] | None:
        """Parse a conversation turn into items or a tool-call dict.

        Returns a list of ``ReviewItem`` when ``parse_items`` succeeds,
        a ``{"action": ..., "args": ...}`` dict for a tool call, or
        ``None`` when the content is not parseable.
        """
        items = self._parser.parse_items(content)
        if items:
            return self._build_review_items(items, repo_path)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            extracted = self._parser._extract_outermost_json(content)
            if extracted is not None:
                try:
                    parsed = json.loads(extracted)
                except json.JSONDecodeError:
                    logger.debug("Failed to parse turn content as JSON.")
                    return None
            else:
                logger.debug("Failed to parse turn content as JSON.")
                return None
        if isinstance(parsed, dict) and "action" in parsed:
            raw_args = parsed.get("args", "")
            if isinstance(raw_args, list):
                args = " ".join(str(a) for a in raw_args)
            elif isinstance(raw_args, dict):
                args = self._extract_dict_args(
                    str(parsed["action"]), raw_args
                )
            else:
                args = str(raw_args)
            return {"action": str(parsed["action"]), "args": args}

        if isinstance(parsed, dict) and "verdict" in parsed:
            items_data = (
                parsed.get("items")
                or parsed.get("issues")
                or parsed.get("findings")
                or []
            )
            if not items_data:
                logger.warning(
                    "Verdict present but no items found in parsed response"
                )
            return self._build_review_items(items_data, repo_path)

        return None

    _DICT_ARG_KEYS: ClassVar[dict[str, list[str]]] = {
        "read_file": ["file", "file_path"],
        "list_directory": ["path", "directory_path"],
        "search_codebase": ["pattern"],
        "run_git": ["command"],
    }

    def _extract_dict_args(
        self, action: str, raw_args: dict[str, Any]
    ) -> str:
        """Extract args from dict-format tool calls the LLM sometimes sends."""
        for key in self._DICT_ARG_KEYS.get(action, []):
            if key in raw_args:
                return str(raw_args[key])
        for fallback in (
            "command", "path", "pattern", "file", "file_path",
            "directory_path", "query",
        ):
            if fallback in raw_args:
                return str(raw_args[fallback])
        return str(raw_args)
    def _build_review_items(
        self,
        item_dicts: list[dict[str, Any]],
        repo_path: str,
    ) -> list[ReviewItem]:
        """Construct ReviewItem domain objects from parsed item dicts.

        Validates that each ``file_path`` exists in the repository;
        hallucinated paths are skipped with a warning.
        """
        repo_root = Path(repo_path) if repo_path else None
        review_items: list[ReviewItem] = []
        for item_dict in item_dicts:
            file_path = str(item_dict.get("file", ""))
            if file_path.startswith(("a/", "b/")):
                file_path = file_path[2:]
            if repo_root is not None and file_path:
                full_path = repo_root / file_path
                if not full_path.exists():
                    logger.warning(
                        "Skipping finding for non-existent file: %s",
                        file_path,
                    )
                    continue
                try:
                    file_path = str(
                        full_path.resolve().relative_to(
                            repo_root.resolve()
                        )
                    )
                except ValueError:
                    pass
            current_code = str(item_dict.get("current_code", ""))
            suggested_fix = str(item_dict.get("suggested_fix", ""))
            if file_path and not current_code and not suggested_fix:
                logger.warning(
                    "Skipping finding with no code evidence for file: %s",
                    file_path,
                )
                continue
            description = str(item_dict.get("description", ""))
            if file_path and not current_code and description:
                description_lower = description.lower()
                if any(
                    pattern in description_lower
                    for pattern in self._FABRICATED_ERROR_PATTERNS
                ):
                    logger.warning(
                        "Skipping finding with fabricated error narrative "
                        "for file: %s — %s",
                        file_path,
                        description[:80],
                    )
                    continue

            review_item = ReviewItem(
                number=len(review_items) + 1,
                severity=str(item_dict.get("severity", "info")),
                category=str(
                    item_dict.get("category", "maintainability")
                ),
                file_path=file_path,
                description=str(item_dict.get("description", "")),
                line=str(item_dict.get("line", "")),
                current_code=current_code,
                suggested_fix=suggested_fix,
            )
            review_items.append(review_item)
        return review_items

    def _stream_chat(self, messages: list[dict[str, Any]]) -> str:
        """Send chat messages to Ollama and accumulate the streamed response."""
        url = f"{self._host}/api/chat"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
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
                thinking_parts: list[str] = []
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
                    message = chunk.get("message", {})
                    content_parts.append(message.get("content", ""))
                    thinking_parts.append(message.get("thinking", ""))
                    if chunk.get("done"):
                        break
                result = "".join(content_parts)
                if not result:
                    result = "".join(thinking_parts)
                    logger.debug(
                        "No content in response; fell back to %d chars of thinking",
                        len(result),
                    )
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
