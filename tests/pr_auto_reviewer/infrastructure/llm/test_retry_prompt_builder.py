"""Tests for RetryPromptBuilder using captured fixtures."""

from pr_auto_reviewer.infrastructure.llm.response_normalizer import RetryPromptBuilder
from tests.fixtures.response_normalizer_fixtures import ResponseNormalizerFixtures as F


class TestRetryPromptBuilder:
    def test_build_correction_prompt_single_failure(self):
        builder = RetryPromptBuilder()
        result = builder.build_correction_prompt(
            "original prompt", F.retry_failures_single
        )
        assert "original prompt" in result
        assert len(result) > len("original prompt")

    def test_build_correction_prompt_multiple_failures(self):
        builder = RetryPromptBuilder()
        result = builder.build_correction_prompt("prompt", F.retry_failures_multiple)
        assert "prompt" in result

    def test_build_correction_prompt_unknown_failure(self):
        builder = RetryPromptBuilder()
        result = builder.build_correction_prompt("prompt", F.retry_failures_unknown)
        assert isinstance(result, str)
