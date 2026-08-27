from ._helpers import *


class TestAdvisorGranularityWiring:
    """ADVISOR_GRANULARITY controls per-turn advisor observation."""

    def _config(self, granularity: AdvisorGranularity):
        return Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            advisor_granularity=granularity,
        )

    def test_phase_granularity_disables_turn_observer(
        self, repo_context
    ) -> None:
        result = wire_core_services(
            self._config(AdvisorGranularity.PHASE), repo_context, _config_dir=None
        )

        assert result.conversation_service._turn_observer is None

    def test_turn_granularity_enables_advisor_as_turn_observer(
        self, repo_context
    ) -> None:
        result = wire_core_services(
            self._config(AdvisorGranularity.TURN), repo_context, _config_dir=None
        )

        from pr_auto_reviewer.application.services.phase_advisor_service import (
            PhaseAdvisorService,
        )

        assert isinstance(result.conversation_service._turn_observer, PhaseAdvisorService)

