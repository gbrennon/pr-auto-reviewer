"""Tests for LlmAgentAdapter."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pr_auto_reviewer.application.ports.inbound.run_multi_phase_review_port import (
    RunMultiPhaseReviewPort,
)
from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
    ComposedPrompt,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
    PullRequestDiff,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import (
    RepositoryContext,
)
from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.llm_agent_adapter import (
    LlmAgentAdapter,
)


class _FakeChatPort(AgentChatPort):
    def __init__(self, model: str = "test-model") -> None:
        self._model = model

    def send(self, messages: list[ConversationMessage]) -> str:
        del messages
        return "response"


class _FakeOrchestrator(RunMultiPhaseReviewPort):
    def __init__(self) -> None:
        self.last_command: RunMultiPhaseReviewCommand | None = None

    def execute(self, command: RunMultiPhaseReviewCommand) -> CodeReview:
        self.last_command = command
        return CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="All clear",
            model_used=command.model,
            items=[],
            reason="clean",
        )


class TestLlmAgentAdapter:
    def test_review_raises_not_implemented_error(self) -> None:
        chat = _FakeChatPort()
        orchestrator = _FakeOrchestrator()
        plan = ReviewPlan(phases=(), methodology="standard")
        adapter = LlmAgentAdapter(chat, orchestrator, plan)

        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="org/repo", number=1),
            head_sha=CommitSha("a" * 40),
            diff_content="",
        )
        context = RepositoryContext(architecture_hint="test")
        with pytest.raises(NotImplementedError):
            adapter.review(diff, context)

    def test_review_prompt_requires_repo_path(self) -> None:
        chat = _FakeChatPort()
        orchestrator = _FakeOrchestrator()
        plan = ReviewPlan(phases=(), methodology="standard")
        adapter = LlmAgentAdapter(chat, orchestrator, plan)

        prompt = ComposedPrompt(
            content="## Diff\n--- a/file.py\n+++ b/file.py\n",
            total_tokens=10,
            fragments_used=[],
            repo_path="",
        )
        with pytest.raises(ValueError):
            adapter.review_prompt(prompt)

    def test_review_prompt_executes_orchestrator_with_extracted_files(
        self,
    ) -> None:
        chat = _FakeChatPort(model="model-alpha")
        orchestrator = _FakeOrchestrator()
        plan = ReviewPlan(phases=(), methodology="standard")
        adapter = LlmAgentAdapter(chat, orchestrator, plan)

        prompt = ComposedPrompt(
            content=(
                "## Diff\n"
                "--- a/src/app.py\n"
                "+++ b/src/app.py\n"
                "--- /dev/null\n"
                "+++ b/src/new.py\n"
            ),
            total_tokens=20,
            fragments_used=[],
            repo_path="/tmp/test-repo",
        )
        review = adapter.review_prompt(prompt)

        assert review.verdict == ReviewVerdict.APPROVED
        assert orchestrator.last_command is not None
        assert orchestrator.last_command.repo_path == Path("/tmp/test-repo")
        assert orchestrator.last_command.changed_files == [
            "src/app.py",
            "src/new.py",
        ]
        assert orchestrator.last_command.model == "model-alpha"

    def test_resolve_model_precedence(self) -> None:
        orchestrator = _FakeOrchestrator()
        plan = ReviewPlan(phases=(), methodology="standard")

        adapter_explicit = LlmAgentAdapter(
            _FakeChatPort("ignored"),
            orchestrator,
            plan,
            model="explicit-model",
        )
        assert adapter_explicit._resolve_model() == "explicit-model"

        chat_with_model_attr: Any = SimpleNamespace(model="named-model")
        adapter_attr = LlmAgentAdapter(chat_with_model_attr, orchestrator, plan)
        assert adapter_attr._resolve_model() == "named-model"

        chat_bare: Any = SimpleNamespace()
        adapter_default = LlmAgentAdapter(chat_bare, orchestrator, plan)
        assert adapter_default._resolve_model() == "default"
