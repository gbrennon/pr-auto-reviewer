"""OllamaAgentAdapter — thin wiring adapter implementing LlmReviewPort."""

from __future__ import annotations

import logging
from pathlib import Path

from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.application.ports.inbound.run_multi_phase_review_use_case import (
    RunMultiPhaseReviewUseCase,
)
from pr_auto_reviewer.application.ports.outbound.llm_review_port import (
    LlmReviewPort,
)
from pr_auto_reviewer.domain.agent.review_plan import ReviewPlan
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
    ComposedPrompt,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_chat_client import (
    OllamaChatClient,
)

logger = logging.getLogger(__name__)


class OllamaAgentAdapter(LlmReviewPort):
    """Thin adapter wiring the agentic review pipeline to ``LlmReviewPort``.

    Extracts repository context from the ``ComposedPrompt`` and delegates
    entirely to ``RunMultiPhaseReviewUseCase``.
    """

    def __init__(
        self,
        chat_client: OllamaChatClient,
        orchestrator: RunMultiPhaseReviewUseCase,
        plan: ReviewPlan,
    ) -> None:
        self._chat_client = chat_client
        self._orchestrator = orchestrator
        self._plan = plan

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
            if line.startswith(("--- a/", "+++ b/")):
                raw = line.split(" ", 1)[1] if " " in line else ""
                if not raw:
                    continue
                if raw == "/dev/null":
                    continue
                if raw.startswith(("a/", "b/")):
                    raw = raw[2:]
                paths.add(raw)
        return sorted(paths)

    def review(self, diff: object, context: object) -> CodeReview:
        """Not used in production; raises NotImplementedError."""
        raise NotImplementedError(
            "Use review_prompt(ComposedPrompt) for staged multi-phase review"
        )

    def review_prompt(self, prompt: ComposedPrompt) -> CodeReview:
        """Run all review phases against the composed prompt's repository."""
        repo_path = prompt.repo_path
        if not repo_path or not repo_path.strip():
            raise ValueError(
                "repo_path is required for staged multi-phase review"
            )
        changed_files = self._extract_file_listing(prompt.content)
        return self._orchestrator.execute(
            RunMultiPhaseReviewCommand(
                plan=self._plan,
                repo_path=Path(repo_path.strip()),
                changed_files=changed_files,
                model=self._chat_client._model,
            )
        )
