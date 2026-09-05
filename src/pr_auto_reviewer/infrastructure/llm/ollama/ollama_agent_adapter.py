"""OllamaAgentAdapter — thin wiring adapter implementing LlmReviewPort."""

from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.inbound.run_multi_phase_review_port import (
    RunMultiPhaseReviewPort,
)
from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan
from pr_auto_reviewer.infrastructure.llm.llm_agent_adapter import (
    LlmAgentAdapter,
)
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_chat_client import (
    OllamaChatClient,
)

logger = logging.getLogger(__name__)


class OllamaAgentAdapter(LlmAgentAdapter):
    """Thin adapter wiring the agentic review pipeline to LlmReviewPort.

    Extracts repository context from the ComposedPrompt and delegates
    entirely to RunMultiPhaseReviewPort using Ollama.
    """

    def __init__(
        self,
        chat_client: OllamaChatClient,
        orchestrator: RunMultiPhaseReviewPort,
        plan: ReviewPlan,
    ) -> None:
        """Initialize the adapter with Ollama chat client and review orchestrator."""
        super().__init__(
            chat_client=chat_client,
            orchestrator=orchestrator,
            plan=plan,
            model=chat_client._model,
        )
