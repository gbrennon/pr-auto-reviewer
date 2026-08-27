"""Shared helpers, fixtures, and imports for the split test modules."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
    ComposedPrompt,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_agent_adapter import (
    OllamaAgentAdapter,
)
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_chat_client import (
    OllamaChatClient,
)


def _adapter(orchestrator=None) -> OllamaAgentAdapter:
    chat_client = cast(OllamaChatClient, SimpleNamespace(_model="code-review:latest"))
    plan = ReviewPlan(phases=(), methodology="m")
    return OllamaAgentAdapter(chat_client, orchestrator or _FakeOrchestrator(), plan)


__all__ = ['CodeReview', 'ComposedPrompt', 'OllamaAgentAdapter', 'OllamaChatClient', 'Path', 'ReviewPlan', 'ReviewVerdict', 'RunMultiPhaseReviewCommand', 'SimpleNamespace', '_FakeOrchestrator', '_adapter', 'cast', 'pytest']


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.command: RunMultiPhaseReviewCommand | None = None

    def execute(self, command: RunMultiPhaseReviewCommand) -> CodeReview:
        self.command = command
        return CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="ran",
            summary="issues found",
            items=[],
            suggestions=[],
            praise=[],
            model_used="code-review:latest",
        )
