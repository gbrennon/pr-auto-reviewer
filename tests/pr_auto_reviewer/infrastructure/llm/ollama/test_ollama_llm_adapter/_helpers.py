"""Shared helpers, fixtures, and imports for the split test modules."""

import json
import logging
from pathlib import Path

import pytest
import requests as _requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
    PullRequestDiff,
)
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_llm_adapter import (
    OllamaLlmAdapter,
)
from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


@pytest.fixture
def adapter() -> OllamaLlmAdapter:
    """Create OllamaLlmAdapter with test host."""
    return OllamaLlmAdapter("http://localhost:11434", "code-review")


@pytest.fixture
def prompt_builder() -> PromptBuilder:
    """Create PromptBuilder instance."""
    return PromptBuilder()


@pytest.fixture
def sample_diff() -> PullRequestDiff:
    """Create a sample diff from real PR fixture."""
    fixture_path = Path(__file__).parents[5] / "fixtures" / "diffs" / "sample-ollama.diff"
    return PullRequestDiff(
        pr_id=None,
        head_sha=None,
        diff_content=fixture_path.read_text(),
    )


@pytest.fixture
def sample_context() -> RepositoryContext:
    """Create a sample review context."""
    return RepositoryContext(
        architecture_hint="Layered architecture",
        conventions="Use type hints",
        repository_structure="src/\n  main.py\n  utils/",
    )


__all__ = ['CodeReview', 'ItemSeverity', 'LlmUnavailableError', 'OllamaLlmAdapter', 'Path', 'PromptBuilder', 'PullRequestDiff', 'RepositoryContext', 'ReviewResponseParser', 'ReviewVerdict', '_requests', 'adapter', 'json', 'logging', 'prompt_builder', 'pytest', 'sample_context', 'sample_diff']
