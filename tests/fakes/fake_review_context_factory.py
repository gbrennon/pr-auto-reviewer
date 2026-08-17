"""Fake review context factory for tests."""

from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class FakeReviewContextFactory:
    def __init__(self, prompt: ComposedPrompt | None = None) -> None:
        self._prompt = prompt
        self.build_calls: list = []

    def build(
        self,
        pr_id: PullRequestId,
        diff: PullRequestDiff,
        pr_title: str | None = None,
        pr_description: str | None = None,
        target_branch: str = "",
    ) -> ComposedPrompt:
        self.build_calls.append((pr_id, diff, pr_title, pr_description))
        if self._prompt is not None:
            return self._prompt
        parts = [
            "You are a Senior Principal Software Engineer and Code Reviewer.",
            "",
            "Review the following diff and report issues as JSON:",
            "",
            "```diff",
            diff.diff_content,
            "```",
        ]
        if pr_title:
            parts.insert(2, f"PR Title: {pr_title}")
        if pr_description:
            parts.insert(3, f"PR Description: {pr_description}")
        content = "\n".join(parts)
        return ComposedPrompt(
            content=content,
            fragments_used=["solid", "python-errors"],
            total_tokens=len(content) // 4,
        )