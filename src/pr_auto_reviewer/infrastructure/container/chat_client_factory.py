"""Build the configured OpenAI-compatible chat client."""

from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.infrastructure.config.config_dataclass import Config
from pr_auto_reviewer.infrastructure.llm.chat_client_settings import (
    ChatClientSettings,
)
from pr_auto_reviewer.infrastructure.llm.openai_compatible_chat_client import (
    OpenAiCompatibleChatClient,
)


class ChatClientFactory:
    """Create chat clients from resolved application configuration."""

    @staticmethod
    def create(config: Config) -> AgentChatPort:
        """Create the configured OpenAI-compatible chat client."""
        settings = ChatClientSettings(
            model=config.llm_model or "",
            host=config.llm_host,
            timeout=config.llm_timeout,
            max_retries=config.llm_max_retries,
            max_llm_calls=config.llm_call_budget,
            max_context_tokens=config.llm_context_tokens,
        )
        return OpenAiCompatibleChatClient(settings)
