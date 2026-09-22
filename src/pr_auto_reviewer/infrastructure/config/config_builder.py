"""Compose application configuration from focused configuration parsers."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.config.advisor_granularity import AdvisorGranularity
from pr_auto_reviewer.infrastructure.config.config_dataclass import Config
from pr_auto_reviewer.infrastructure.config.llm_config_parser import LlmConfigParser
from pr_auto_reviewer.infrastructure.config.platform_config_parser import PlatformConfigParser
from pr_auto_reviewer.infrastructure.config.repository_config_parser import RepositoryConfigParser
from pr_auto_reviewer.infrastructure.config.review_config_parser import ReviewConfigParser
from pr_auto_reviewer.infrastructure.config.token_overrides_parser import TokenOverridesParser


class ConfigBuilder:
    """Compose focused parsers into the application configuration."""

    def __init__(
        self,
        platform_parser: PlatformConfigParser,
        llm_parser: LlmConfigParser,
        review_parser: ReviewConfigParser,
        repository_parser: RepositoryConfigParser,
        token_parser: TokenOverridesParser,
    ) -> None:
        self._platform_parser = platform_parser
        self._llm_parser = llm_parser
        self._review_parser = review_parser
        self._repository_parser = repository_parser
        self._token_parser = token_parser

    def build(
        self,
        source: dict[str, str],
        env_name: str,
        llm_max_retries: int = 5,
        llm_max_turns: int = 10,
        advisor_max_blocks: int = 2,
        review_max_conversations: int = 48,
        review_max_tries: int = 2,
        llm_call_budget: int = 300,
        advisor_granularity: AdvisorGranularity = AdvisorGranularity.PHASE,
    ) -> Config:
        """Build immutable configuration data from environment values."""
        platform = self._platform_parser.parse(source)
        llm = self._llm_parser.parse(
            source, llm_max_retries, llm_max_turns, llm_call_budget
        )
        review = self._review_parser.parse(
            source,
            advisor_max_blocks,
            review_max_conversations,
            review_max_tries,
            AdvisorGranularity.parse(advisor_granularity),
        )
        repository = self._repository_parser.parse(source)
        tokens = self._token_parser.parse(source)
        return Config(
            env=env_name,
            platform_mode=platform.mode,
            github_api_url=platform.github_api_url,
            forgejo_api_url=platform.forgejo_api_url,
            github_owner_token=platform.github_owner_token,
            github_reviewer_token=platform.github_reviewer_token,
            github_reviewer_username=platform.github_reviewer_username,
            github_review_mode=platform.github_review_mode,
            forgejo_owner_token=platform.forgejo_owner_token,
            forgejo_reviewer_token=platform.forgejo_reviewer_token,
            forgejo_reviewer_username=platform.forgejo_reviewer_username,
            org_token_overrides=tokens,
            llm_host=llm.host,
            llm_model=llm.model,
            llm_timeout=llm.timeout,
            llm_max_retries=llm.max_retries,
            llm_max_turns=llm.max_turns,
            advisor_max_blocks=review.advisor_max_blocks,
            review_max_conversations=review.review_max_conversations,
            review_max_tries=review.review_max_tries,
            llm_call_budget=llm.call_budget,
            advisor_granularity=review.advisor_granularity,
            poll_interval=review.poll_interval,
            run_once=review.run_once,
            repos_filter=repository.repos_filter,
            repos_allow_list=repository.repos_allow_list,
            force_pr=repository.force_pr,
            debug=review.debug,
            output_mode=review.output_mode,
            output_path=review.output_path,
            max_prompt_tokens=review.max_prompt_tokens,
            max_file_chars=review.max_file_chars,
            max_files=review.max_files,
            max_structure_lines=review.max_structure_lines,
            use_compact_template=review.use_compact_template,
            use_strict_fragment_selection=review.use_strict_fragment_selection,
            local_clone_base_dir=repository.local_clone_base_dir,
            clone_protocol=repository.clone_protocol,
        )
