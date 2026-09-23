"""Compose configuration parser dependencies."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.config.config_builder import ConfigBuilder
from pr_auto_reviewer.infrastructure.config.llm_config_parser import LlmConfigParser
from pr_auto_reviewer.infrastructure.config.llm_defaults import LlmDefaults
from pr_auto_reviewer.infrastructure.config.platform_config_parser import PlatformConfigParser
from pr_auto_reviewer.infrastructure.config.repository_config_parser import RepositoryConfigParser
from pr_auto_reviewer.infrastructure.config.review_config_parser import ReviewConfigParser
from pr_auto_reviewer.infrastructure.config.token_overrides_parser import TokenOverridesParser


class ConfigBuilderComposition:
    """Compose the focused parsers required by ``ConfigBuilder``."""

    def compose(self) -> ConfigBuilder:
        """Return a fully composed configuration builder."""
        return ConfigBuilder(
            platform_parser=PlatformConfigParser(),
            llm_parser=LlmConfigParser(LlmDefaults()),
            review_parser=ReviewConfigParser(),
            repository_parser=RepositoryConfigParser(),
            token_parser=TokenOverridesParser(),
        )
