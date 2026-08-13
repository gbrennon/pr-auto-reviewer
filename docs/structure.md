# Project Structure

This document explains the project structure and how the pieces fit together.

## Overview

The entry point is the Python CLI (`uv run python -m pr_auto_reviewer`).
All operations — bootstrap, PR watching, daemon management, command
processing — are handled by the Python application. Run `pr-auto-reviewer --help`
for available commands.

## Architecture

The project follows **Hexagonal Architecture (Ports and Adapters)** with four
layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                           │
│  cli.py (argparse)                                              │
│  └─ CliRunner (subcommand dispatch)                             │
│  └─ CompositionRoot (bootstrap, DI wiring)                      │
│  └─ PollingDaemon (watch-prs loop)                              │
└────────────────────────────┬────────────────────────────────────┘
                             │ calls ──── Driving Ports (Inbound)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Use Case Implementations                              │    │
│  │   ReviewPullRequestService                              │    │
│  │   ProcessIssueCommandsService                           │    │
│  │   MultiPhaseReviewOrchestrator                          │    │
│  │   AgentConversationService                              │    │
│  │   FindingVerifier                                       │    │
│  │   FindingAggregator                                     │    │
│  │   EventLoggingHandler                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Inbound Ports (Protocols)                             │    │
│  │   ReviewPullRequestUseCase                              │    │
│  │   ProcessIssueCommandsUseCase                           │    │
│  │   RunMultiPhaseReviewUseCase                            │    │
│  │   RunAgentConversationUseCase                           │    │
│  │   VerifyFindingsUseCase                                 │    │
│  │   AggregateReviewFindingsUseCase                        │    │
│  │   ParseReviewTurnUseCase                                │    │
│  │   RegisterIssuePort                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Domain Services                                       │    │
│  │   ReviewItemParser                                      │    │
│  │   IssueCommandParser                                    │    │
│  │   ReviewItemFactory                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             │ calls ──── Driven Ports (Outbound)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   OUTBOUND PORTS (Interfaces)                           │    │
│  │   ChangesetFetcherPort                                  │    │
│  │   ReviewContextFactoryPort                              │    │
│  │   LlmReviewPort                                         │    │
│  │   ReviewPublisherPort                                   │    │
│  │   PullRequestRepository                                 │    │
│  │   RepositoryContextPort                                 │    │
│  │   FragmentRepositoryPort                                │    │
│  │   PromptRendererPort                                    │    │
│  │   ComposeReviewPromptPort                               │    │
│  │   CommentReaderPort                                     │    │
│  │   CommentPublisherPort                                  │    │
│  │   IssueTrackerPort                                      │    │
│  │   CommandBusPort                                        │    │
│  │   ReviewReaderPort                                      │    │
│  │   TokenVerifierPort                                     │    │
│  │   CloneUrlResolverPort                                  │    │
│  │   LocalRepositoryPort                                   │    │
│  │   AgentChatPort                                         │    │
│  │   ToolExecutionPort                                     │    │
│  │   NotifierPort                                          │    │
│  │   ResponseParserPort                                    │    │
│  │   ConversationLoggerPort                                │    │
│  │   ReasonBuilderPort                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   ADAPTERS (Implementations)                            │    │
│  │   GitPlatformHttpClient (GitHub/Forgejo)                │    │
│  │   LocalChangesetFetcher (local git clone)               │    │
│  │   LocalRepositoryContext                                │    │
│  │   Github/Forgejo ReviewPublisher                        │    │
│  │   Github/Forgejo ReviewReader                           │    │
│  │   Github/Forgejo CommentReader/Publisher                │    │
│  │   Github/Forgejo IssueTracker                          │    │
│  │   Github/Forgejo PrLister/RepoLister                    │    │
│  │   Composite* adapters (multi-platform)                  │    │
│  │   TerminalReviewPublisherAdapter                        │    │
│  │   NullPullRequestRepository / JsonFilePullRequestRepo   │    │
│  │   OllamaLlmAdapter / OllamaExploratoryChatAdapter       │    │
│  │   OllamaAgentAdapter / OllamaChatClient                 │    │
│  │   FileSystemFragmentRepository                          │    │
│  │   Jinja2Renderer                                        │    │
│  │   ComposeReviewPromptAdapter                            │    │
│  │   InMemoryCommandBus                                    │    │
│  │   PreflightVerifier                                     │    │
│  │   RateLimitTracker / RateLimitStore / RateLimitWaiter   │    │
│  │   Https/SshCloneUrlResolver                             │    │
│  │   LinuxNotifier                                         │    │
│  │   TokenResolver / OrgTokenOverrides / RoleSuffixParser  │    │
│  │   RepoUpdateTracker / HttpRequestCounter                │    │
│  │   ConversationLogger                                    │    │
│  │   TempFileCleaner                                       │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             │ implements
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DOMAIN LAYER                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Entities (Aggregate Roots)                            │    │
│  │   PullRequest                                           │    │
│  │   Issue                                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Value Objects (frozen=True)                           │    │
│  │   CodeReview, ReviewVerdict, ReviewItem                 │    │
│  │   ReviewSuggestion, ReviewPraise                        │    │
│  │   ItemSeverity, IssueCategory                           │    │
│  │   PullRequestId, CommitSha, PullRequestDiff             │    │
│  │   RepositoryContext, CommentId, TokenSlug               │    │
│  │   IssueCommand, PrComment                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Domain Events & Commands (CQRS)                       │    │
│  │   ReviewPullRequestCommand                              │    │
│  │   ProcessIssueCommandsCommand                           │    │
│  │   RunMultiPhaseReviewCommand                            │    │
│  │   RunAgentConversationCommand                           │    │
│  │   VerifyFindingsCommand                                 │    │
│  │   AggregateReviewFindingsCommand                        │    │
│  │   ParseReviewTurnCommand                                │    │
│  │   RegisterIssueCommand                                  │    │
│  │   PhaseCompletedEvent, FindingsAggregatedEvent         │    │
│  │   ConversationCompletedEvent, ReviewTurnParsedEvent    │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Domain Errors                                         │    │
│  │   LlmUnavailableError, ReviewPublishError               │    │
│  │   PullRequestNotFoundError, EmptyDiffError              │    │
│  │   PreflightVerificationError, DomainError               │    │
│  │   Invalid*Error, IssueCreationError                     │    │
│  │   LLMResponseMalformedError, RepositoryCorruptedError   │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Agent System                                          │    │
│  │   AdvisorAgent, ArchitectAgent, EngineerAgent           │    │
│  │   ExplorerAgent, ManagerAgent, ReviewerAgent            │    │
│  │   Conversation, ConversationMessage, PhaseResult        │    │
│  │   TurnParseResult, ReviewPhase                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Fragment Domain                                       │    │
│  │   ComposedPrompt, PromptFragment, ReviewContext         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Data Files

```
~/.config/pr-auto-reviewer/
├── state.json              # State file - tracks reviewed PRs by SHA
├── config                  # Configuration file (env-file format)
├── verified-tokens.json    # Token verification cache
└── temp/                   # Temporary files for LLM prompts
```

The state file prevents duplicate reviews. A PR is only re-reviewed if the SHA changes.

## Source Tree (266 Python Files)

```
src/pr_auto_reviewer/
├── __init__.py
├── __main__.py
├── cli.py                          # CLI entry point (argparse, systemd)
├── presentation/
│   ├── __init__.py
│   ├── composition_root.py         # DI wiring, bootstrap()
│   ├── cli/
│   │   ├── __init__.py
│   │   └── runner.py               # CliRunner with subcommands
│   ├── polling_daemon/
│   │   ├── __init__.py
│   │   ├── polling_daemon.py       # Polling daemon
│   │   └── polling_daemon_config.py
│   └── ports/
│       ├── __init__.py
│       ├── open_pull_request.py
│       ├── repo_info.py
│       ├── pr_lister_port.py
│       └── repo_lister_port.py
├── application/
│   ├── __init__.py
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── inbound/
│   │   │   ├── __init__.py
│   │   │   ├── review_pull_request_use_case.py
│   │   │   ├── process_issue_commands_use_case.py
│   │   │   ├── run_multi_phase_review_use_case.py
│   │   │   ├── run_agent_conversation_use_case.py
│   │   │   ├── verify_findings_use_case.py
│   │   │   ├── aggregate_review_findings_use_case.py
│   │   │   ├── parse_review_turn_use_case.py
│   │   │   └── register_issue_port.py
│   │   └── outbound/
│   │       ├── __init__.py
│   │       ├── changeset_fetcher_port.py
│   │       ├── review_context_factory_port.py
│   │       ├── llm_review_port.py
│   │       ├── review_publisher_port.py
│   │       ├── pull_request_repository.py
│   │       ├── repository_context_port.py
│   │       ├── fragment_repository_port.py
│   │       ├── prompt_renderer_port.py
│   │       ├── compose_review_prompt_port.py
│   │       ├── comment_reader_port.py
│   │       ├── comment_publisher_port.py
│   │       ├── issue_tracker_port.py
│   │       ├── command_bus_port.py
│   │       ├── review_reader_port.py
│   │       ├── token_verifier_port.py
│   │       ├── clone_url_resolver_port.py
│   │       ├── local_repository_port.py
│   │       ├── agent_chat_port.py
│   │       ├── tool_execution_port.py
│   │       ├── notifier_port.py
│   │       ├── response_parser_port.py
│   │       ├── conversation_logger_port.py
│   │       └── reason_builder_port.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── review_pull_request_service.py
│   │   ├── process_issue_commands_service.py
│   │   ├── multi_phase_review_orchestrator.py
│   │   ├── agent_conversation_service.py
│   │   ├── finding_verifier.py
│   │   ├── finding_aggregator.py
│   │   ├── event_logging_handler.py
│   │   ├── register_issue_service.py
│   │   └── turn_parser.py
│   └── serializers/
│       ├── __init__.py
│       └── issue_body_builder.py
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── pull_request.py
│   │   ├── review_item.py
│   │   ├── review_suggestion.py
│   │   ├── review_praise.py
│   │   └── issue.py
│   ├── value_objects/
│   │   ├── __init__.py
│   │   ├── code_review.py
│   │   ├── review_verdict.py
│   │   ├── review_item.py
│   │   ├── item_severity.py
│   │   ├── issue_category.py
│   │   ├── pull_request_id.py
│   │   ├── commit_sha.py
│   │   ├── pull_request_diff.py
│   │   ├── repository_context.py
│   │   ├── comment_id.py
│   │   ├── issue_command.py
│   │   ├── pr_comment.py
│   │   └── token_slug.py
│   ├── messages/
│   │   ├── __init__.py
│   │   ├── commands/
│   │   │   ├── __init__.py
│   │   │   ├── review_pull_request_command.py
│   │   │   ├── process_issue_commands_command.py
│   │   │   ├── run_multi_phase_review_command.py
│   │   │   ├── run_agent_conversation_command.py
│   │   │   ├── verify_findings_command.py
│   │   │   ├── aggregate_review_findings_command.py
│   │   │   ├── parse_review_turn_command.py
│   │   │   └── register_issue_command.py
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   ├── phase_completed_event.py
│   │   │   ├── findings_aggregated_event.py
│   │   │   ├── conversation_completed_event.py
│   │   │   └── review_turn_parsed_event.py
│   │   └── messages.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── review_item_parser.py
│   │   ├── review_item_factory.py
│   │   └── issue_command_parser.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── advisor_agent.py
│   │   ├── architect_agent.py
│   │   ├── conversation.py
│   │   ├── conversation_message.py
│   │   ├── engineer_agent.py
│   │   ├── explorer_agent.py
│   │   ├── manager_agent.py
│   │   ├── phase_result.py
│   │   ├── reviewer_agent.py
│   │   ├── turn_parse_result.py
│   │   └── review_phase.py
│   ├── fragments/
│   │   ├── __init__.py
│   │   └── entities/
│   │       ├── __init__.py
│   │       ├── composed_prompt.py
│   │       ├── prompt_fragment.py
│   │       └── review_context.py
│   └── exceptions/
│       ├── __init__.py
│       ├── domain_error.py
│       ├── empty_diff_error.py
│       ├── invalid_comment_id_error.py
│       ├── invalid_commit_sha_error.py
│       ├── invalid_issue_body_error.py
│       ├── invalid_pull_request_id_error.py
│       ├── issue_creation_error.py
│       ├── llm_response_malformed_error.py
│       ├── llm_unavailable_error.py
│       ├── preflight_verification_error.py
│       ├── pull_request_not_found_error.py
│       ├── repository_corrupted_error.py
│       ├── review_item_not_found_error.py
│       └── review_publish_error.py
├── infrastructure/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── config_builder.py
│   │   ├── config_dataclass.py
│   │   ├── environment_detector.py
│   │   ├── org_token_overrides.py
│   │   ├── org_token_entry.py
│   │   ├── forgejo_api_url_normalizer.py
│   │   ├── repo_root.py
│   │   └── role_suffix_parser.py
│   ├── container/
│   │   ├── __init__.py
│   │   ├── _container.py
│   │   ├── _platform_clients.py
│   │   ├── _platform_adapters.py
│   │   └── _core_services.py
│   ├── client/
│   │   ├── __init__.py
│   │   ├── git_platform_http_client.py
│   │   ├── http_request_counter.py
│   │   ├── preflight_verifier.py
│   │   ├── repo_update_tracker.py
│   │   ├── token_verifier.py
│   │   ├── preflight/
│   │   │   ├── __init__.py
│   │   │   ├── preflight_verifier.py
│   │   │   ├── requests_http_client.py
│   │   │   ├── github_auth_headers.py
│   │   │   └── forgejo_auth_headers.py
│   │   ├── rate_limit_tracker/
│   │   │   ├── __init__.py
│   │   │   ├── rate_limit_tracker.py
│   │   │   ├── rate_limit_store.py
│   │   │   └── rate_limit_waiter.py
│   │   ├── token_resolver/
│   │   │   ├── __init__.py
│   │   │   ├── token_resolver.py
│   │   │   ├── role_suffix_parser.py
│   │   │   ├── org_extractor.py
│   │   │   ├── env_token_scanner.py
│   │   │   └── token_role_defaults.py
│   │   └── token_defaults.py
│   ├── local_repository/
│   │   ├── __init__.py
│   │   ├── local_changeset_fetcher.py
│   │   ├── local_git_repository.py
│   │   └── local_repository_context.py
│   ├── clone_url_resolvers/
│   │   ├── __init__.py
│   │   ├── https_clone_url_resolver.py
│   │   └── ssh_clone_url_resolver.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── ollama_llm_adapter.py
│   │   ├── ollama_chat_client.py
│   │   ├── ollama_exploratory_chat_adapter.py
│   │   ├── ollama_agent_adapter.py
│   │   ├── prompt_builder.py
│   │   ├── prompt_budget.py
│   │   ├── response_normalizer.py
│   │   ├── review_response_parser.py
│   │   ├── retry_orchestrator.py
│   │   ├── schemas.py
│   │   ├── diff_analyzer.py
│   │   └── exploration_tool_service.py
│   ├── fragments/
│   │   ├── __init__.py
│   │   ├── compose_review_prompt_adapter.py
│   │   ├── file_system_fragment_repository.py
│   │   ├── jinja2_renderer.py
│   │   └── token_budget_manager.py
│   ├── review_publishers/
│   │   ├── __init__.py
│   │   ├── review_publishing_service.py
│   │   ├── terminal_publisher.py
│   │   ├── body_formatter.py
│   │   ├── _shared.py
│   │   └── _review_processor.py
│   ├── forgejo/
│   │   ├── __init__.py
│   │   ├── forgejo_review_publisher.py
│   │   ├── pr_lister.py
│   │   ├── repo_lister.py
│   │   ├── issue_tracker.py
│   │   ├── comment_reader.py
│   │   ├── comment_publisher.py
│   │   └── review_reader.py
│   ├── github/
│   │   ├── __init__.py
│   │   ├── github_review_publisher.py
│   │   ├── pr_lister.py
│   │   ├── repo_lister.py
│   │   ├── issue_tracker.py
│   │   ├── comment_reader.py
│   │   ├── comment_publisher.py
│   │   └── review_reader.py
│   ├── git_platform/
│   │   ├── __init__.py
│   │   ├── git_provider.py
│   │   ├── multi_platform/
│   │   │   ├── __init__.py
│   │   │   ├── composite_changeset_fetcher.py
│   │   │   ├── composite_repository_context.py
│   │   │   ├── composite_review_publisher.py
│   │   │   ├── composite_review_reader.py
│   │   │   ├── composite_comment_reader.py
│   │   │   ├── composite_comment_publisher.py
│   │   │   ├── composite_issue_tracker.py
│   │   │   ├── composite_repo_lister.py
│   │   │   ├── composite_pr_lister.py
│   │   │   └── _parse_platform_prefix.py
│   │   └── practices/
│   │       └── python/
│   │           └── pep_store/
│   │               ├── __init__.py
│   │               ├── fetcher.py
│   │               ├── filter.py
│   │               ├── formatter.py
│   │               ├── matcher.py
│   │               ├── ranker.py
│   │               ├── store.py
│   │               └── types.py
│   ├── context/
│   │   ├── __init__.py
│   │   ├── review_context_factory.py
│   │   ├── architecture_detector.py
│   │   ├── conventions_generator.py
│   │   ├── context_serializer.py
│   │   ├── language_detector.py
│   │   └── python_version_detector.py
│   ├── command_bus/
│   │   ├── __init__.py
│   │   └── in_memory_command_bus.py
│   ├── notifier/
│   │   ├── __init__.py
│   │   └── linux_notifier.py
│   ├── conversation_logger.py
│   └── temp_file_cleaner.py
└── fragments/                      # Prompt fragment content (not Python)
    └── content/
        ├── universal/
        │   ├── reviewer-system-prompt.md
        │   ├── solid-principles.md
        │   ├── naming-conventions.md
        │   └── ...
        └── python/
            ├── type-hints.md
            ├── error-handling.md
            └── ...
```

## Tests

```
tests/
├── conftest.py
├── pr_auto_reviewer/
│   ├── test_e2e_review_flow.py
│   ├── test_multilang_review_verdict.py
│   ├── test_e2e_review_verdict.py
│   ├── presentation/
│   │   ├── test_composition_root.py
│   │   ├── ports/
│   │   └── cli/
│   ├── application/
│   │   ├── ports/
│   │   └── services/
│   ├── domain/
│   │   ├── value_objects/
│   │   ├── entities/
│   │   └── services/
│   ├── infrastructure/
│   │   ├── config/
│   │   ├── client/
│   │   ├── local_repository/
│   │   ├── llm/
│   │   ├── fragments/
│   │   ├── review_publishers/
│   │   ├── git_platform/
│   │   │   ├── multi_platform/
│   │   │   └── ...
│   │   ├── command_bus/
│   │   └── notifier/
```

## Key Principles

- **Domain Layer**: Pure business logic, no external dependencies, all value objects are `frozen=True`
- **Application Layer**: Use cases orchestrate domain logic and call outbound ports
- **Infrastructure Layer**: Implements outbound ports (HTTP clients, LLM, file I/O, git)
- **Presentation Layer**: CLI, daemon, DI wiring (CompositionRoot)
- **Dependency Rule**: Inner layers never import from outer layers
- **Ports as Protocols**: All outbound ports are `Protocol` classes (interfaces)
- **CQRS**: Commands (writes) and queries (reads) are separate
- **Events**: Domain events published via in-memory command bus
- **Frozen Value Objects**: All domain value objects are immutable (`frozen=True`)
- **DI Container**: Centralized wiring in `CompositionRoot` / `Container`