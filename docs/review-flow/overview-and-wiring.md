# 1. Execution Flow Overview

```
 1  CLI entry
     │  pyproject.toml → pr_auto_reviewer.cli:main()
     │  Parses args: --repo=gbrennon/pr-auto-reviewer --pr=71 --force --verbose
     v
 2  bootstrap()
     │  CompositionRoot → Container (DI) → wires all adapters
     v
 3  cli.py:main() rebuilds argv
     │  ["pr-auto-reviewer", "review", "--repo", "...", "--pr", "71", "--force", "--verbose"]
     v
 4  CliRunner._run_review()
     │  force=True → pr_lister.get_pr(repo, 71)  [state-agnostic]
     │  Builds ReviewPullRequestCommand(pr_id, sha, title, desc, force=true)
     v
 5  ReviewPullRequestService.execute()
     ├─ 5a. PullRequestRepository.find(pr_id)
     │      → Load from ~/.local/state/pr-auto-reviewer/state.json
     ├─ 5b. force=true → skip needs_review check
     ├─ 5c. TokenVerifierPort.verify(pr_id)  [preflight]
     ├─ 5d. ChangesetFetcherPort.fetch(pr_id, sha)
     │      → Local git clone: git fetch, compute diff, read file contents
     ├─ 5e. ReviewContextFactoryPort.build(pr_id, diff, pr_title=title, pr_description=desc, target_branch=target_branch)
     │      → Fetches repo structure via local git
     │      → Detects language/architecture
     │      → Fetches prompt fragments, renders via Jinja2, composes prompt
     ├─ 5f. LlmReviewPort.review_prompt(prompt)
     │      → POST Ollama /api/generate, parse JSON response
     │      → Retry orchestrator handles retries on failure
     ├─ 5g. _add_deterministic_findings(review, diff)  [preserves verdict]
     ├─ 5h. Blocker tracking (resolve old, track new, override verdict if needed)
     ├─ 5i. ReviewPublisherPort.publish(pr_id, review, diff)
     │      → POST Git API: submit formal review or comment
     │      → Platform-specific: Forgejo splits non-blocking items
     ├─ 5j. pr.add_review(review, sha)  [new immutable PullRequest]
     └─ 5k. PullRequestRepository.save(pr)
            → Write to state.json
```

---

## 2. Hexagonal Architecture — Port & Adapter Map

```
                    ┌──────────────────────────────────────────┐
                    │           PRESENTATION LAYER             │
                    │                                          │
                    │  cli.py (argparse)                       │
                    │  └─ CliRunner (subcommand dispatch)      │
                    │  └─ CompositionRoot (bootstrap)          │
                    │  └─ PollingDaemon (watch-prs loop)       │
                    └──────────────┬───────────────────────────┘
                                   │ calls ───── Driving Ports (Inbound)
                                   │
                    ┌──────────────▼───────────────────────────┐
                    │            APPLICATION LAYER              │
                    │                                          │
                    │  ┌──────────────────────────────────┐     │
                    │  │   Use Case Implementations       │     │
                    │  │                                  │     │
                    │  │  ReviewPullRequestService        │─────│───┐
                    │  │  ProcessIssueCommandsService     │     │   │
                    │  │  MultiPhaseReviewOrchestrator    │     │   │
                    │  │  AgentConversationService        │     │   │
                    │  │  FindingVerifier                 │     │   │
                    │  │  FindingAggregator               │     │   │
                    │  │  EventLoggingHandler             │     │   │
                    │  └──────────────────────────────────┘     │   │
                    │                                          │   │
                    │  ┌──────────────────────────────────┐     │   │
                    │  │   Inbound Ports (Protocols)      │     │   │
                    │  │   ─────────────────────────      │     │   │
                    │  │  ReviewPullRequestUseCase        │     │   │
                    │  │  ProcessIssueCommandsUseCase     │     │   │
                    │  │  RunMultiPhaseReviewUseCase      │     │   │
                    │  │  RunAgentConversationUseCase     │     │   │
                    │  │  VerifyFindingsUseCase           │     │   │
                    │  │  AggregateReviewFindingsUseCase  │     │   │
                    │  │  ParseReviewTurnUseCase          │     │   │
                    │  │  RegisterIssuePort               │     │   │
                    │  └──────────────────────────────────┘     │   │
                    │                                          │   │
                    │  ┌──────────────────────────────────┐     │   │
                    │  │   Commands (CQRS)                │     │   │
                    │  │   ──────────────────────         │     │   │
                    │  │  ReviewPullRequestCommand        │     │   │
                    │  │  ProcessIssueCommandsCommand     │     │   │
                    │  │  RunMultiPhaseReviewCommand      │     │   │
                    │  │  RunAgentConversationCommand     │     │   │
                    │  │  VerifyFindingsCommand           │     │   │
                    │  │  AggregateReviewFindingsCommand  │     │   │
                    │  │  ParseReviewTurnCommand          │     │   │
                    │  │  RegisterIssueCommand            │     │   │
                    │  └──────────────────────────────────┘     │   │
                    │                                          │   │
                    │  ┌──────────────────────────────────┐     │   │
                    │  │   Domain Services                │     │   │
                    │  │   ReviewItemParser               │     │   │
                    │  │  IssueCommandParser              │     │   │
                    │  │  ReviewItemFactory               │     │   │
                    │  └──────────────────────────────────┘     │   │
                    └──────────────┬───────────────────────────┘   │
                                   │ calls ───── Driven Ports     │
                                   │            (Outbound)        │
                    ┌──────────────▼───────────────────────────┐   │
                    │         INFRASTRUCTURE LAYER             │   │
                    │                                          │   │
                    │  ┌────────────────────────────────────┐   │
                    │  │   OUTBOUND PORTS (Interfaces)      │   │
                    │  │                                    │   │
                    │  │  ChangesetFetcherPort  ◄───── Use  │   │
                    │  │  ReviewContextFactoryPort ◄── Case │   │
                    │  │  LlmReviewPort          ◄───── Im- │   │
                    │  │  ReviewPublisherPort    ◄───── ple │   │
                    │  │  PullRequestRepository  ◄───── men │   │
                    │  │  RepositoryContextPort  ◄───── tat │   │
                    │  │  FragmentRepositoryPort ◄───── ion │   │
                    │  │  PromptRendererPort     ◄────────  │   │
                    │  │  ComposeReviewPromptPort ◄────────  │   │
                    │  │  CommentReaderPort                 │   │
                    │  │  CommentPublisherPort               │   │
                    │  │  IssueTrackerPort                   │   │
                    │  │  CommandBusPort                     │   │
                    │  │  ReviewReaderPort                   │   │
                    │  │  TokenVerifierPort                  │   │
                    │  │  ConversationLoggerPort             │   │
                    │  │  ReasonBuilderPort                  │   │
                    │  └────────────────────────────────────┘   │
                    │                                            │
                    │  ┌────────────────────────────────────┐   │
                    │  │   ADAPTERS (Implementations)       │   │
                    │  │                                    │   │
                    │  │  LocalChangesetFetcher  ──────────▶│───│─── Local git
                    │  │  LocalRepositoryContext ──────────▶│───│─── Local git
                    │  │  Github/Forgejo ReviewPublisher ──▶│───│─── Git API
                    │  │  Github/Forgejo ReviewReader  ────▶│───│─── Git API
                    │  │  Github/Forgejo CommentReader ──▶│───│─── Git API
                    │  │  Github/Forgejo CommentPublisher─▶│───│─── Git API
                    │  │  Github/Forgejo IssueTracker  ────▶│───│─── Git API
                    │  │  Github/Forgejo PrLister  ────────▶│───│─── Git API
                    │  │  Github/Forgejo RepoLister  ──────▶│───│─── Git API
                    │  │  Composite* adapters  ────────────▶│───│─── Multi-platform
                    │  │                                    │   │
                    │  │  OllamaLlmAdapter ────────────────▶│───│─── Ollama
                    │  │  OllamaExploratoryChatAdapter ────▶│───│─── Ollama
                    │  │  OllamaAgentAdapter ──────────────▶│───│─── Ollama
                    │  │                                    │   │
                    │  │  TerminalReviewPublisherAdapter ──▶│─── stdout
                    │  │  NullPullRequestRepository ────────▶│─── no-op
                    │  │  JsonFilePullRequestRepo ─────────▶│─── state.json
                    │  │                                    │   │
                    │  │  FileSystemFragmentRepository ────▶│─── content/*.md
                    │  │  Jinja2Renderer ──────────────────▶│─── Jinja2
                    │  │  ComposeReviewPromptAdapter ──────▶│─── prompt assembly
                    │  │  InMemoryCommandBus ──────────────▶│─── in-process
                    │  │  PreflightVerifier ───────────────▶│─── Git API
                    │  │  RateLimitTracker ────────────────▶│─── disk
                    │  │  Https/SshCloneUrlResolver ───────▶│─── URL construction
                    │  │  LinuxNotifier ───────────────────▶│─── libnotify
                    │  └────────────────────────────────────┘   │
                    └────────────────────────────────────────────┘
```

---

## 3. Dependency Injection Wiring (Container)

```
┌─────────────────────────────────────────────────────────────────┐
│  Container(config)                                              │
│                                                                 │
│  HTTP Clients:                                                  │
│    GitPlatformHttpClient(api_url, token)           ── main      │
│    GitPlatformHttpClient(api_url, reviewer_token)  ── reviewer  │
│    Forgejo/GitHub-specific clients for multi-platform mode      │
│                                                                 │
│  Adapters created:                                              │
│    pr_repository ──── JsonFilePullRequestRepository(state.json) │
│    changeset_fetcher ─ LocalChangesetFetcher(local_repo, resolver)│
│    repository_context ─ LocalRepositoryContext(local_repo)      │
│    llm_review ──────── OllamaLlmAdapter(host, model, ...)       │
│    review_publisher ── Github/Forgejo/Composite/Terminal        │
│    review_reader ───── Github/Forgejo/Composite                  │
│    comment_reader ──── Github/Forgejo/Composite                  │
│    comment_publisher ─ Github/Forgejo/Composite                  │
│    issue_tracker ───── Github/Forgejo/Composite                  │
│    repo_lister ─────── Github/Forgejo/Composite                  │
│    pr_lister ───────── Github/Forgejo/Composite                  │
│                                                                 │
│  Fragment System:                                               │
│    fragment_repository ── FileSystemFragmentRepository(fragments)│
│    fragment_renderer ──── Jinja2Renderer()                      │
│    compose_prompt ─────── ComposeReviewPromptAdapter(           │
│                             repository, renderer, max_tokens)   │
│                                                                 │
│  Composite Port:                                                │
│    review_context_factory ── ReviewContextFactory(              │
│                               repository_context,              │
│                               compose_review_prompt)            │
│                                                                 │
│  Advanced Services:                                             │
│    command_bus ──────── InMemoryCommandBus()                    │
│    token_verifier ────── PreflightVerifier()                    │
│    notifier ──────────── LinuxNotifier()                        │
└─────────────────────────────────────────────────────────────────┘

  CompositionRoot._wire_components()
  │
  ├── ReviewPullRequestService(
  │       pr_repository,
  │       changeset_fetcher,
  │       review_context_factory,    ← Composite: wraps 2 ports
  │       llm_review,
  │       review_publisher,
  │       token_verifier,
  │   )
  │
  ├── ProcessIssueCommandsService(
  │       pr_repository, review_reader, comment_reader,
  │       comment_publisher, issue_tracker, review_item_parser,
  │       issue_command_parser, issue_body_builder,
  │   )
  │
  ├── MultiPhaseReviewOrchestrator(
  │       command_bus, tool_factory, max_retries, max_feedback_rounds
  │   )
  │
  ├── AgentConversationService(
  │       chat_port, command_bus, conversation_logger, ...
  │   )
  │
  └── CliRunner(
          review_service,
          process_commands_service,
          review_reader,
          pr_lister,
          review_item_parser,
          pr_repository,
          notifier,
          token_verifier,
          output_mode,
      )
```

---
