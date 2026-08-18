"""Fake ComposeReviewPromptAdapter for tests."""

from __future__ import annotations


class FakeComposeReviewPromptAdapter:
    """Fake ComposeReviewPromptAdapter that returns pre-configured prompts."""

    def __init__(self, compose_result: str | None = None) -> None:
        if compose_result is None:
            compose_result = """---model: code-review:latest
messages:
  - role: user
    content: |-
      You are a senior code reviewer. Analyse the following pull request diff and produce a structured JSON review.
      
---
{diff_content}
---
JSON schema for the review:
{schema_block}
---
Produce *only* a valid JSON object matching the schema above. The engine will guarantee validity; do not add any text before or after the JSON."""
        self.compose_result = compose_result

    def compose(self, diff_content: str, json_schema: dict[str, Any]) -> str:
        """Return fake composed prompt without actual LLM calls."""
        schema_block = str(json_schema)
        result = self.compose_result.replace("{diff_content}", diff_content).replace("{schema_block}", schema_block)
        self.compose_calls: list[tuple[str, dict[str, Any]]] = [(diff_content, json_schema)]
        return result