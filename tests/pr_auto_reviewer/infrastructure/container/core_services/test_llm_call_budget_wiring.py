from ._helpers import *


class TestLlmCallBudgetWiring:
    """LLM_CALL_BUDGET is enforced by the shared chat client."""

    def test_chat_client_receives_configured_call_budget(
        self, forgejo_config: Config, repo_context, tmp_path
    ) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            llm_call_budget=7,
        )
        result = wire_core_services(config, repo_context, _config_dir=tmp_path)

        client = result.llm_review._chat_client

        assert client._max_llm_calls == 7

