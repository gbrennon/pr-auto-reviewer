"""LlmAgentAdapter — generic wiring adapter implementing LlmReviewPort."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from pr_auto_reviewer.application.ports.inbound.run_multi_phase_review_port import (
    RunMultiPhaseReviewPort,
)
from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.application.ports.outbound.llm_review_port import (
    LlmReviewPort,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
    ComposedPrompt,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import (
    RepositoryContext,
)
from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan
from pr_auto_reviewer.infrastructure.llm.diff_analyzer import DiffAnalyzer

logger = logging.getLogger(__name__)


class LlmAgentAdapter(LlmReviewPort):
    """Generic adapter wiring multi-phase agentic reviews to LlmReviewPort.

    Extracts repository context from ComposedPrompt and delegates execution
    to RunMultiPhaseReviewPort using any configured AgentChatPort backend.
    """

    def __init__(
        self,
        chat_client: AgentChatPort,
        orchestrator: RunMultiPhaseReviewPort,
        plan: ReviewPlan,
        model: str | None = None,
        diff_analyzer: DiffAnalyzer | None = None,
    ) -> None:
        """Initialize the adapter with chat client, orchestrator, and plan."""
        self._chat_client = chat_client
        self._orchestrator = orchestrator
        self._plan = plan
        self._model = model
        self._diff_analyzer = diff_analyzer or DiffAnalyzer()

    def review(
        self, diff: PullRequestDiff, context: RepositoryContext
    ) -> CodeReview:
        """Reject unprompted reviews; multi-phase review requires a ComposedPrompt."""
        del diff, context
        raise NotImplementedError(
            "Use review_prompt(ComposedPrompt) for staged multi-phase review"
        )

    def review_prompt(self, prompt: ComposedPrompt) -> CodeReview:
        """Run all review phases against the composed prompt repository."""
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
                model=self._resolve_model(),
                review_session=datetime.now(UTC).strftime("%Y%m%d_%H%M%S"),
            )
        )

    def _model_from_attribute(self, attr_name: str) -> str:
        """Extract non-empty string model attribute from chat client."""
        val = getattr(self._chat_client, attr_name, None)
        if isinstance(val, str) and val:
            return val
        return ""

    def _resolve_model(self) -> str:
        """Resolve the model name from explicit config or chat client attributes."""
        if self._model:
            return self._model
        return (
            self._model_from_attribute("_model")
            or self._model_from_attribute("model")
            or "default"
        )

    def _extract_file_listing(self, composed_content: str) -> list[str]:
        """Extract changed file paths from the rendered prompt diff section."""
        return self._diff_analyzer.extract_file_listing(composed_content)
