from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


class TestParserEnrichedFields:
    """The public item parser captures remediation-context labels."""

    def test_structured_item_captures_remediation_context(self) -> None:
        content = (
            "### [critical] [security] src/a.py:10 — SQL injection\n\n"
            "```python\nquery = 'SELECT ' + user\n```\n\n"
            "**Fix:**\n```python\nquery = param(user)\n```\n\n"
            "Root cause: user input concatenated into SQL\n"
            "Reproduction: call build_query(\"' OR 1=1\")\n"
            "Acceptance criteria: injection input returns no rows\n"
            "Detection method: trace tainted input to the SQL sink\n"
        )

        items = ReviewResponseParser().parse_items(content)

        target = next(i for i in items if "a.py" in i["file"])
        assert target["root_cause"] == "user input concatenated into SQL"
        assert "OR 1=1" in target["reproduction"]
        assert target["acceptance_criteria"] == "injection input returns no rows"
        assert target["detection_method"] == "trace tainted input to the SQL sink"

    def test_structured_item_without_labels_leaves_fields_empty(self) -> None:
        content = (
            "### [minor] [style] src/b.py:3 — long line\n\n"
            "```python\nx = 1\n```\n\n"
            "**Fix:**\n```python\ny = 2\n```\n"
        )

        items = ReviewResponseParser().parse_items(content)

        target = items[0]
        assert target["root_cause"] == ""
        assert target["reproduction"] == ""
        assert target["acceptance_criteria"] == ""
        assert target["detection_method"] == ""
