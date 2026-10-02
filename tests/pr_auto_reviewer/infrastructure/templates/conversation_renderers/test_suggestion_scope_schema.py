from pr_auto_reviewer.infrastructure.templates.conversation_renderers.review_phase.suggestions_praise_message_renderer import (
    SuggestionsPraiseMessageRenderer,
)


class TestSuggestionScopeSchema:
    """The dedicated suggestions turn carries the same scope contract."""

    def test_schema_requires_relation_evidence_without_new_fields(self) -> None:
        message = SuggestionsPraiseMessageRenderer().render()

        assert "directly or indirectly related" in message.content
        assert "MUST name the changed file" in message.content
        assert '"file"' in message.content
        assert '"description"' in message.content
        assert '"related_file"' not in message.content
        assert '"relation"' not in message.content
        assert '"evidence"' not in message.content
