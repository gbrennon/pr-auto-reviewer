# Overview

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
│  │   AdvisorAgent, ArchitectAgent, EngineerAgent,         │    │
│  │   ManagerAgent                                          │    │
│  │   Conversation, ConversationMessage, PhaseResult        │    │
│  │   TurnParseResult, ReviewPhase                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Fragment Domain                                       │    │
│  │   ComposedPrompt, PromptFragment, ReviewContext         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```
