from pr_auto_reviewer.infrastructure.container._core_services import (
    wire_core_services,
)

pytest_plugins = (
    "tests.pr_auto_reviewer.infrastructure.container.core_services._helpers",
)


class TestSuggestionScopePrompt:
    """Production architecture prompts carry the suggestion scope contract."""

    def test_architecture_prompt_requires_related_changed_file_evidence(
        self, forgejo_config, repo_context,
    ) -> None:
        services = wire_core_services(forgejo_config, repo_context)
        architecture_phase = next(
            phase
            for phase in services.review_plan.phases
            if phase.phase_id == "architecture-review"
        )

        assert "directly or indirectly related" in architecture_phase.system_prompt
        assert "MUST name the changed file" in architecture_phase.system_prompt
        assert "empty `file`" in architecture_phase.system_prompt
