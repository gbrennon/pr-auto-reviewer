"""OllamaLlmAdapter — implements LlmReviewPort using a local Ollama instance."""

import json
import logging
import re
from typing import Any

import requests

from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.review_context import ReviewContext
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict

logger = logging.getLogger(__name__)


class OllamaLlmAdapter(LlmReviewPort):
    """Call a local Ollama instance to review a pull-request diff."""

    def __init__(self, host: str, model: str) -> None:
        self._host = host.rstrip("/")
        self._model = model

    def review(self, diff: PullRequestDiff, context: ReviewContext) -> CodeReview:
        prompt = _PromptBuilder.build(diff, context)

        try:
            response = requests.post(
                f"{self._host}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LlmUnavailableError(
                f"Ollama @ {self._host} unreachable or error: {exc}"
            ) from exc

        try:
            body: dict[str, Any] = response.json()
        except json.JSONDecodeError as exc:
            raise LlmUnavailableError(
                f"Ollama returned invalid JSON: {exc}"
            ) from exc

        raw_text: str = body.get("response", "")
        if not raw_text:
            raise LlmUnavailableError(
                "Ollama returned an empty response — model may have failed silently."
            )

        return _ReviewResponseParser.parse(raw_text, self._model)


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


class _PromptBuilder:
    """Build the prompt sent to the LLM from a diff + review context."""

    @staticmethod
    def build(diff: PullRequestDiff, context: ReviewContext) -> str:
        parts: list[str] = [
            "You are an expert code reviewer. "
            "Analyse the pull-request diff below.",
            "",
            "## Instructions",
            "Produce a structured review with the following sections, "
            "each starting with exactly the given markdown heading "
            "on its own line:",
            "",
            "## Verdict",
            "One of: approved | changes_requested | commented",
            "",
            "## Summary",
            "A concise, one-paragraph summary of the changes and "
            "your overall judgment.",
            "",
            "## Items",
            "Zero or more bullet-point findings. Each bullet must "
            "use this format:",
            "- [severity] <category> (<file_path>) <description>",
            "  severity: critical | major | minor | info",
            "",
            "If there are no findings, write `None` under the "
            "## Items heading.",
            "",
            "---",
        ]

        if context.architecture_hint:
            parts.append(
                f"## Architecture / context\n"
                f"{context.architecture_hint}\n"
            )

        conventions = context.conventions or diff.conventions
        if conventions:
            parts.append(f"## Project conventions\n{conventions}\n")

        repo_structure = (
            context.repository_structure or diff.repository_structure
        )
        if repo_structure:
            parts.append(
                f"## Repository structure\n{repo_structure}\n"
            )

        parts.append("## Diff\n```diff")
        parts.append(diff.diff_content)
        parts.append("```")

        return "\n".join(parts)


class _ReviewResponseParser:
    """Parse the raw LLM text into a CodeReview domain object."""

    _ITEM_RE = re.compile(
        r"^\s*[-*]\s*\[(?P<severity>critical|major|minor|info)\]\s*"
        r"(?P<category>[^(]+?)\s*"
        r"\((?P<file_path>[^)]*)\)\s*"
        r"(?P<description>.+)$",
        re.IGNORECASE | re.MULTILINE,
    )

    @staticmethod
    def parse(raw_text: str, model_used: str) -> CodeReview:
        verdict = _ReviewResponseParser._extract_verdict(raw_text)
        summary = _ReviewResponseParser._extract_summary(raw_text)
        items = _ReviewResponseParser._extract_items(raw_text)
        return CodeReview(
            verdict=verdict,
            summary=summary,
            items=items,
            model_used=model_used,
        )

    @staticmethod
    def _extract_verdict(raw_text: str) -> ReviewVerdict:
        match = re.search(
            r"##\s*Verdict\s*\n\s*(.+)", raw_text, re.IGNORECASE
        )
        if not match:
            return ReviewVerdict.COMMENTED

        value = match.group(1).strip().lower()
        if "changes_requested" in value or "request changes" in value:
            return ReviewVerdict.CHANGES_REQUESTED
        if "approved" in value:
            return ReviewVerdict.APPROVED
        return ReviewVerdict.COMMENTED

    @staticmethod
    def _extract_summary(raw_text: str) -> str:
        pattern = r"##\s*Summary\s*\n(.*?)(?=##\s*Items|\Z)"
        match = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

    @staticmethod
    def _extract_items(raw_text: str) -> list[ReviewItem]:
        items_section = _ReviewResponseParser._isolate_items_section(
            raw_text
        )
        if not items_section:
            return []

        items: list[ReviewItem] = []
        for idx, match in enumerate(
            _ReviewResponseParser._ITEM_RE.finditer(items_section),
            start=1,
        ):
            severity_str = match.group("severity").lower()
            try:
                severity = ItemSeverity(severity_str)
            except ValueError:
                severity = ItemSeverity.INFO

            file_path = match.group("file_path").strip() or None

            items.append(
                ReviewItem(
                    number=idx,
                    severity=severity,
                    category=match.group("category").strip(),
                    file_path=file_path,
                    description=match.group("description").strip(),
                )
            )

        return items

    @staticmethod
    def _isolate_items_section(raw_text: str) -> str | None:
        """Return the portion between ## Items and the next ## heading."""
        match = re.search(
            r"##\s*Items\s*\n(.*?)(?=\n##\s|\Z)",
            raw_text,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None

        body = match.group(1).strip()
        if not body or body.lower() in ("none", "n/a", "no items"):
            return None
        return body
