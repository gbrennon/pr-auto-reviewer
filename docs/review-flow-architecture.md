# Review Command Flow: Architecture & Adapter Diagrams

**Command:** `uv run pr-auto-reviewer review -r gbrennon/pr-auto-reviewer -p 71 -v --force`

> **Note:** Line numbers in code references are approximate and reflect the codebase at time of writing. Refer to actual source for precise locations.

---

## 1. Execution Flow Overview

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
     │      → Load from ~/.config/pr-auto-reviewer/state.json
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

## 4. Detailed Flow: `review -r gbrennon/pr-auto-reviewer -p 71 -v --force`

### 4.1. CLI Parsing & Bootstrapping

```
  Shell: uv run pr-auto-reviewer review -r gbrennon/pr-auto-reviewer -p 71 -v --force
         │
         │  pyproject.toml entry point → pr_auto_reviewer.cli:main()
         ▼
  ┌───────────────────────────────────────────────────────────────┐
  │  cli.py:main()                                                │
  │                                                               │
  │  argparse parses:                                             │
  │    command  = "review"                                        │
  │    repo     = "gbrennon/pr-auto-reviewer"                     │
  │    pr       = 71                                              │
  │    force    = True                                            │
  │    verbose  = True                                            │
  │                                                               │
  │  → bootstrap()                                                │
  │      └─ CompositionRoot()                                     │
  │           ├─ load_config()                                    │
  │           │   ├─ Reads .env / user config                     │
  │           │   └─ Config(platform_token, llm_host, ...)        │
  │           ├─ Container(config)  → wires all adapters          │
  │           └─ _wire_components() → ApplicationComponents       │
  │                                                               │
  │  → Rebuilds argv:                                             │
  │    ["pr-auto-reviewer", "review",                             │
  │     "--repo", "gbrennon/pr-auto-reviewer",                    │
  │     "--pr", "71", "--force", "--verbose"]                     │
  │                                                               │
  │  → components.cli_runner.run(argv)                            │
  └───────────────────────────────────────────────────────────────┘
```

### 4.2. CLI Runner — PR Fetching

```
  ┌───────────────────────────────────────────────────────────────┐
  │  CliRunner._run_review(["--repo","...","--pr","71",           │
  │                         "--force","--verbose"])               │
  │                                                               │
  │  force_mode = True  (args.force is True)                      │
  │                                                               │
  │  Since --force:                                               │
  │    → pr_lister.get_pr("gbrennon/pr-auto-reviewer", 71)        │
  │       └─ ForgejoPrLister / GithubPrLister / CompositePrLister │
  │            GET /repos/gbrennon/pr-auto-reviewer/pulls/71      │
  │            → OpenPullRequest(pr_id, head_sha, title, desc)    │
  │       (state-agnostic — works for closed/merged PRs too)      │
  │                                                               │
  │  → ReviewPullRequestCommand(                                  │
  │       pr_id=PullRequestId("gbrennon/pr-auto-reviewer", 71),   │
  │       head_sha=CommitSha("abc123..."),                        │
  │       title="...",                                            │
  │       description="...",                                      │
  │       force=True,                                             │
  │    )                                                          │
  │                                                               │
  │  → review_service.execute(command)                            │
  └───────────────────────────────────────────────────────────────┘
```

### 4.3. Use Case: ReviewPullRequestService.execute()

```
┌─────────────────────────────────────────────────────────────────┐
│ ReviewPullRequestService.execute(command)                       │
│                                                                 │
│ 4.3.1 LOAD OR CREATE PR                                         │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ pr_repository.find(pr_id)                                │   │
│ │ JsonFilePullRequestRepository.find()                     │   │
│ │   Read ~/.config/pr-auto-reviewer/state.json             │   │
│ │   → PullRequest or None                                  │   │
│ │ If None → PullRequest(id, title, head_sha)               │   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.2 CHECK IF REVIEW NEEDED                                   │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ command.force == True → ALWAYS REVIEW (skip check)      │   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.3 PREFLIGHT TOKEN VERIFICATION                             │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ token_verifier.verify(pr_id)                             │   │
│ │   PreflightVerifier:                                     │   │
│ │     1. GET /user (auth check)                            │   │
│ │     2. POST /pulls/{n}/requested_reviewers (write check) │   │
│ │   Cached in ~/.config/pr-auto-reviewer/verified-tokens.json│   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.4 FETCH DIFF VIA LOCAL GIT CLONE                           │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ changeset_fetcher.fetch(pr_id, head_sha)                 │   │
│ │                                                          │   │
│ │ LocalChangesetFetcher                                    │   │
│ │  ┌──────────────────────────────────────────────────┐   │   │
│ │  │ ① Resolve clone URL (HTTPS or SSH)               │   │   │
│ │  │ ② Clone/fetch repo to ~/.cache/pr-auto-reviewer/ │   │   │
│ │  │     repos/{owner}_{repo}_{pr}/                    │   │   │
│ │  │ ③ git fetch origin pull/{pr}/head:pr-{pr}        │   │   │
│ │  │ ④ Resolve base SHA (merge-base)                  │   │   │
│ │  │ ⑤ git diff base_sha..pr-{pr} → raw unified diff  │   │   │
│ │  │ ⑥ Extract changed file paths from diff headers   │   │   │
│ │  │    regex: ^diff --git a/(.+) b/(.+)              │   │   │
│ │  │    → ["src/main.py", "src/utils.py", ...]         │   │   │
│ │  │ ⑦ For each changed file:                         │   │   │
│ │  │    git show pr-{pr}:{file_path} → file contents  │   │   │
│ │  │    → file_contents: {"src/main.py": "...", ...}  │   │   │
│ │  │ ⑧ git log base_sha..pr-{pr} --format=%s          │   │   │
│ │  │    → ["feat: add ...", "fix: ...", ...]           │   │   │
│ │  └──────────────────────────────────────────────────┘   │   │
│ │                                                          │   │
│ │ → PullRequestDiff(                                       │   │
│ │     pr_id, head_sha,                                     │   │
│ │     diff_content="...",                                  │   │
│ │     file_contents={"src/main.py": "...", ...},           │   │
│ │     commit_messages=["feat: ...", "fix: ..."],           │   │
│ │   )                                                      │   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.5 BUILD REVIEW CONTEXT + COMPOSE PROMPT                    │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ review_context_factory.build(pr_id, diff,                │   │
│ │     pr_title=title, pr_description=desc,                 │   │
│ │     target_branch=target_branch)                         │   │
│ │                                                          │   │
│ │ ┌─ ReviewContextFactory (Composite Port) ─────────────┐  │   │
│ │ │                                                     │  │   │
│ │ │ 4.5.a RepositoryContextPort.fetch(pr_id)            │  │   │
│ │ │   └─ LocalRepositoryContext                          │  │   │
│ │ │      ① git ls-tree -r --name-only HEAD               │  │   │
│ │ │         → tree_paths: ["src/...", "tests/..."]       │  │   │
│ │ │      ② ArchitectureDetector.detect(paths)            │  │   │
│ │ │         → "hexagonal" / "mvc" / "unknown"            │  │   │
│ │ │      ③ Fetch CONVENTIONS.md / ARCHITECTURE.md        │  │   │
│ │ │      ④ PythonVersionDetector.detect(paths)→"3.12"   │  │   │
│ │ │      → RepositoryContext(arch, conventions, struc)   │  │   │
│ │ │                                                     │  │   │
│ │ │   Augment: attach pr_title, pr_description           │  │   │
│ │ │                                                     │  │   │
│ │ │ 4.5.b RepositoryContextPort.build_fragment_context() │  │   │
│ │ │   └─ LocalRepositoryContext                          │  │   │
│ │ │      ① LanguageDetector.detect(file_paths)           │  │   │
│ │ │         → "python" (from .py extension)              │  │   │
│ │ │      ② ContextSerializer.serialize(repo_ctx,        │  │   │
│ │ │           commit_msgs, python_version)               │  │   │
│ │ │         → Markdown string                            │  │   │
│ │ │      → ("python", serialized_context | None)         │  │   │
│ │ │                                                     │  │   │
│ │ │   ReviewContext(                                     │  │   │
│ │ │     language="python",                              │  │   │
│ │ │     file_paths=["src/main.py", ...],                 │  │   │
│ │ │     diff=pull_request_diff.diff_content,             │  │   │
│ │ │     repository_context=serialized,                   │  │   │
│ │ │   )                                                  │  │   │
│ │ │                                                     │  │   │
│ │ │ 4.5.c ComposeReviewPromptPort.execute(ctx)           │  │   │
│ │ │   └─ ComposeReviewPromptAdapter                      │  │   │
│ │ │                                                     │  │   │
│ │ │   ── SELECT FRAGMENTS ──                            │  │   │
│ │ │   fragment_repository.find_by_language("python")    │  │   │
│ │ │     → type-hints.md, resource-management.md, ...    │  │   │
│ │ │   fragment_repository.find_universal()              │  │   │
│ │ │     → reviewer-system-prompt.md (priority 1000),    │  │   │
│ │ │       solid-principles.md, naming-conventions.md    │  │   │
│ │ │   Merge + sort by priority (descending)             │  │   │
│ │ │                                                     │  │   │
│ │ │   ── APPLY TOKEN BUDGET (if configured) ──          │  │   │
│ │ │   Greedy select highest-priority fragments          │  │   │
│ │ │   that fit within fragment_max_tokens               │  │   │
│ │ │                                                     │  │   │
│ │ │   ── STRICT SELECTION (if USE_STRICT_FRAGMENT_SELECTION) ──│
│ │ │   Filter fragments by keyword/path match against   │  │   │
│ │ │   diff and file paths                              │  │   │
│ │ │                                                     │  │   │
│ │ │   ── RENDER FRAGMENTS ──                            │  │   │
│ │ │   For each fragment:                                │  │   │
│ │ │     Jinja2Renderer.render(template, variables)     │  │   │
│ │ │     variables: language, file_paths,               │  │   │
│ │ │               repository_context                    │  │   │
│ │ │     (diff placeholder: "[Full diff below...]")     │  │   │
│ │ │                                                     │  │   │
│ │ │   ── COMPOSE FINAL PROMPT ──                        │  │   │
│ │ │   Join rendered sections with "\n\n---\n\n"        │  │   │
│ │ │   Append repository_context                         │  │   │
│ │ │   Append JSON output reminder                       │  │   │
│ │ │   Append "## Diff\n```diff\n{diff}\n```"            │  │   │
│ │ │   (Truncate diff if > max_total_chars)             │  │   │
│ │ │                                                     │  │   │
│ │ │   → ComposedPrompt(                                 │  │   │
│ │ │       content="Full prompt text...",               │  │   │
│ │ │       fragments_used=["type-hints", "solid", ...], │  │   │
│ │ │       total_tokens=len//4,                         │  │   │
│ │ │     )                                              │  │   │
│ │ └─────────────────────────────────────────────────────┘  │   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.6 RUN LLM REVIEW                                           │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ llm_review.review_prompt(composed_prompt)                │   │
│ │                                                          │   │
│ │ OllamaLlmAdapter                                         │   │
│ │  ┌──────────────────────────────────────────────────┐   │   │
│ │  │ Split prompt at "\n\n---\n\n":                    │   │   │
│ │  │   system_text = first fragment (reviewer-system-  │   │   │
│ │  │                 prompt.md — priority 1000)        │   │   │
│ │  │   user_text  = rest of prompt                     │   │   │
│ │  │                                                   │   │   │
│ │  │ POST {llm_host}/api/generate                      │   │   │
│ │  │ {                                                  │   │   │
│ │  │   "model": "code-review:latest",                   │   │   │
│ │  │   "prompt": user_text,                             │   │   │
│ │  │   "system": system_text,                           │   │   │
│ │  │   "stream": false                                  │   │   │
│ │  │ }                                                  │   │   │
│ │  │                                                   │   │   │
│ │  │ → Raw JSON response text                           │   │   │
│ │  │                                                   │   │   │
│ │  │ ── PARSE RESPONSE ──                              │   │   │
│ │  │ ReviewResponseParser.parse(raw_text, model)        │   │   │
│ │  │  ① Attempt pure JSON.parse                        │   │   │
│ │  │  ② Extract outermost JSON object                   │   │   │
│ │  │     (brace-matching, last valid wins)              │   │   │
│ │  │  ③ Fallback: Markdown regex parser                 │   │   │
│ │  │                                                   │   │   │
│ │  │ → CodeReview(                                      │   │   │
│ │  │     verdict=APPROVED|CHANGES_REQUESTED|COMMENTED,  │   │   │
│ │  │     reason="...",                                  │   │   │
│ │  │     summary="...",                                 │   │   │
│ │  │     items=[ReviewItem(number, severity,            │   │   │
│ │  │            category, file_path, line,              │   │   │
│ │  │            description, current_code,              │   │   │
│ │  │            suggested_fix)],                        │   │   │
│ │  │     suggestions=[ReviewSuggestion(file, line,      │   │   │
│ │  │            description, current_code,              │   │   │
│ │  │            suggested_code)],                       │   │   │
│ │  │     praise=[ReviewPraise(description, file)],       │   │   │
│ │  │     model_used="code-review:latest",               │   │   │
│ │  │   )                                                │   │   │
│ │  └──────────────────────────────────────────────────┘   │   │
│ │                                                          │   │
│ │  ── RETRY ORCHESTRATION (on failure) ──                │   │   │
│ │  RetryOrchestrator:                                    │   │   │
│ │    - Max retries: LLM_MAX_RETRIES (default 5)          │   │   │
│ │    - On unparseable: builds correction prompt          │   │   │
│ │    - On token exhaustion: restarts                     │   │   │
│ │    - Dumps prompts to /tmp/ollama-prompt-try*.txt      │   │   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.7 ADD DETERMINISTIC FINDINGS                               │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ _add_deterministic_findings(review, diff)                │   │
│ │   Scans diff for noisy logger.info() calls with          │   │   │
│ │   specific markers (GET, POST, keys=, tokens, etc.)      │   │   │
│ │   Adds MINOR/MAINTAINABILITY items suggesting            │   │   │
│ │   logger.debug() instead                                 │   │   │
│ │   Preserves original review.verdict (not hardcoded!)     │   │   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.8 TRACK BLOCKING ITEMS                                     │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ blocking_ids = [item.id for item in review.items         │   │
│ │                if item.is_blocking and item.id]          │   │
│ │                                                          │   │
│ │ // Resolve old blockers no longer in this review         │   │
│ │ if pr.unresolved_blocking_ids:                           │   │
│ │     resolved = [id for id in pr.unresolved_blocking_ids  │   │
│ │                  if id not in blocking_ids]              │   │
│ │     if resolved: pr = pr.with_resolved_blocking(*resolved)│
│ │                                                          │   │
│ │ // Track new/persistent blockers                          │   │
│ │ if blocking_ids:                                         │   │
│ │     pr = pr.with_unresolved_blocking(*blocking_ids)      │   │
│ │                                                          │   │
│ │ // Guard: override verdict if blockers remain            │   │
│ │ if pr.unresolved_blocking_ids and                        │   │
│ │    review.verdict != ReviewVerdict.CHANGES_REQUESTED:    │   │
│ │     review = CodeReview(                                 │   │
│ │         verdict=ReviewVerdict.CHANGES_REQUESTED,         │   │
│ │         reason=build_unresolved_reason(...),             │   │
│ │         summary=review.summary,                          │   │
│ │         items=review.items,                              │   │
│ │         ...                                              │   │
│ │     )                                                    │   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.9 PUBLISH REVIEW                                           │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ review_publisher.publish(pr_id, review, diff)            │   │
│ │                                                          │   │
│ │ GitReviewPublisherAdapter (since output_mode="codeberg") │   │
│ │  ┌──────────────────────────────────────────────────┐   │   │
│ │  │ ProcessedReview = ReviewPublisherProcessor.process() │   │   │
│ │  │   verdict_event = _VERDICT_TO_EVENT[review.verdict]  │   │   │
│ │  │   APPROVED          → "APPROVE" (GitHub)            │   │   │
│ │  │   CHANGES_REQUESTED → "REQUEST_CHANGES"            │   │   │
│ │  │   COMMENTED         → "COMMENT"                    │   │   │
│ │  │                                                     │   │   │
│ │  │   If COMMENTED → comment-only path                 │   │   │
│ │  │     All non-blocking items → single PR comment     │   │   │
│ │  │                                                     │   │   │
│ │  │   If formal review → formal path                   │   │   │
│ │  │     Build body with all items (GitHub)             │   │   │
│ │  │     OR split: blocking in review, non-blocking     │   │   │
│ │  │         as separate comment (Forgejo)              │   │   │
│ │  │     count_existing_items() for number offset       │   │   │
│ │  │                                                     │   │   │
│ │  │   Forgejo override:                                │   │   │
│ │  │     if verdict_event == "APPROVE":                 │   │   │
│ │  │         verdict_event = "APPROVED"                 │   │   │
│ │  │                                                     │   │   │
│ │  │   POST /pulls/{n}/reviews with:                    │   │   │
│ │  │     {event, body, commit_id, comments[], official} │   │   │
│ │  │   Forgejo: official=true, GitHub: no official      │   │   │
│ │  │   Inline comments:                                 │   │   │
│ │  │     GitHub: "position" from diff                   │   │   │
│ │  │     Forgejo: "old_position"/"new_position"         │   │   │
│ │  │   Request reviewer: POST /pulls/{n}/requested_reviewers│
│ │  └──────────────────────────────────────────────────┘   │   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.10 RECORD & PERSIST                                        │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ pr.add_review(review, head_sha)                          │   │
│ │   → new PullRequest with review appended, sha updated    │   │
│ │   (immutable — returns new instance)                     │   │
│ │                                                          │   │
│ │ pr_repository.save(pr)                                   │   │
│ │ JsonFilePullRequestRepository.save()                     │   │
│ │   Atomic write to ~/.config/pr-auto-reviewer/state.json  │   │
│ └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

> **Platform difference (blocking/non-blocking split):** The review processor
> (`_review_processor.py`) now splits items by severity before publishing.
> For **Forgejo/Codeberg**, blocking items (CRITICAL/MAJOR) go in the formal
> review while non-blocking items (MINOR/INFO) are published as a separate
> comment. For **GitHub**, all items remain in the formal review body
> (matching GitHub's review model where every inline comment is part of the
> review). The terminal publisher is unaffected.

---

## 5. Adapter Communication Diagrams

### 5.1. Git Adapter / External API Communication

```
┌────────────────────────────────────────────────────────────────────────────┐
│                      GitPlatformHttpClient                                 │
│                                                                             │
│  GET(path, **params)    → requests.get(api_url + path, params, headers)    │
│  GET_RAW(path)          → requests.get(api_url + path, headers) → .text    │
│  POST(path, body)       → requests.post(api_url + path, json=body, hdrs)  │
│  Rate limit headers parsed: x-ratelimit-limit, -remaining, -reset          │
└────────────────────────────────────────────────────────────────────────────┘
          ▲                      ▲                      ▲
          │                      │                      │
          │ injected into        │ injected into        │ injected into
     ┌────┴────────────┐   ┌────┴────────────┐   ┌────┴────────────┐
     │ ChangesetFetcher│   │ RepositoryCtx   │   │ ReviewPublisher │
     │   (Local git)   │   │   (Local git)   │   │   Adapter       │
     └─────────────────┘   └─────────────────┘   └─────────────────┘
          │                      │                      │
          │ Git commands:        │ Git commands:        │ API calls:
          │                      │                      │
     ══════════════════════════════════════════════════════════════════════════
          ▼                      ▼                      ▼
     ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────┐
     │  Local Git Repo  │ │  Local Git Repo  │ │  Forgejo / Codeberg /    │
     │  (cloned cache)  │ │  (cloned cache)  │ │  GitHub                  │
     └──────────────────┘ └──────────────────┘ └──────────────────────────┘
```

**Local Git Operations (ChangesetFetcher / RepositoryContext):**
```
  git clone/fetch → ~/.cache/pr-auto-reviewer/repos/{owner}_{repo}_{pr}/
  git fetch origin pull/{pr}/head:pr-{pr}
  git merge-base origin/main pr-{pr}  → base_sha
  git diff base_sha..pr-{pr}          → raw diff
  git show pr-{pr}:{file_path}        → file contents
  git log base_sha..pr-{pr} --format=%s → commit messages
  git ls-tree -r --name-only HEAD     → repo structure
  git show HEAD:CONVENTIONS.md        → convention files
```

**API Calls (ReviewPublisher / ReviewReader / etc.):**
```
  GET  /repos/{repo}/pulls/{num}              (PR metadata)
  GET  /repos/{repo}/pulls/{num}/reviews      (existing reviews)
  POST /repos/{repo}/pulls/{num}/reviews      (submit formal review)
  POST /repos/{repo}/pulls/{num}/requested_reviewers (request reviewer)
  POST /repos/{repo}/issues/{num}/comments    (post comment)
  GET  /repos/{repo}/issues/{num}/comments    (read comments)
  POST /repos/{repo}/issues                   (create tracker issue)
  GET  /user/repos                            (list repos)
  GET  /repos/{repo}/pulls                    (list open PRs)
  GET  /user                                  (auth check)
```

### 5.2. LLM Adapter / Ollama Communication

```
┌─────────────────────────────────────────────────────────┐
│                    OllamaLlmAdapter                      │
│                                                          │
│  review_prompt(composed_prompt)                          │
│    │                                                     │
│    ├─ Split prompt at "\n\n---\n\n"                      │
│    │   system = parts[0]  (reviewer-system-prompt)       │
│    │   user   = parts[1]  (fragments + diff + reminder)  │
│    │                                                     │
│    └─ POST {host}/api/generate                           │
│        {                                                 │
│          "model": "code-review:latest",                   │
│          "prompt": user_text,                             │
│          "system": system_text,                           │
│          "stream": false                                  │
│        }                                                 │
│        ↓                                                 │
│        {                                                 │
│          "model": "code-review:latest",                   │
│          "response": "{...JSON...}",                      │
│          "eval_count": 1234,                              │
│          "eval_duration": 5678900000                      │
│        }                                                 │
│                                                          │
│    └─ ReviewResponseParser.parse(response, model)        │
│        │                                                 │
│        ├─ Try json.loads(raw)                            │
│        ├─ Extract outermost JSON via brace-matching      │
│        └─ Fallback: Markdown regex parser                │
│                                                          │
│        → CodeReview(verdict, items, summary, ...)        │
│                                                          │
│  RetryOrchestrator (on failure):                         │
│    - Max retries: LLM_MAX_RETRIES                        │
│    - On parse error: RetryPromptBuilder builds           │
│      correction prompt with error details                │
│    - Dumps each attempt to /tmp/ollama-prompt-try*.txt   │
└─────────────────────────────────────────────────────────┘
```

### 5.3. Fragment Prompt Composition

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ComposeReviewPromptAdapter                        │
│                                                                          │
│  execute(ReviewContext) → ComposedPrompt                                 │
│    │                                                                     │
│    ├─ 1. SELECT FRAGMENTS                                               │
│    │    fragment_repository.find_by_language("python")                   │
│    │    └─ FileSystemFragmentRepository                                 │
│    │         Read content/python/type-hints.md                         │
│    │         Read content/python/resource-management.md                │
│    │         Read content/python/error-handling.md                     │
│    │         ...                                                         │
│    │                                                                     │
│    │    fragment_repository.find_universal()                             │
│    │    └─ FileSystemFragmentRepository                                 │
│    │         Read content/universal/reviewer-system-prompt.md          │
│    │         Read content/universal/solid-principles.md                │
│    │         Read content/universal/naming-conventions.md              │
│    │         ...                                                         │
│    │                                                                     │
│    │    Merge → sort by priority descending                              │
│    │    TokenBudgetManager: greedy filter to fit max_tokens             │
│    │    Strict selection (if enabled): keyword/path heuristic filter   │
│    │                                                                     │
│    ├─ 2. RENDER FRAGMENTS                                               │
│    │    For each fragment:                                               │
│    │      Jinja2Renderer.render(fragment.content, variables)            │
│    │      variables = {                                                  │
│    │        language: "python",                                          │
│    │        file_paths: "src/main.py\nsrc/utils.py",                     │
│    │        repository_context: serialized,                              │
│    │        code: "[Full diff below...]",        ← placeholder          │
│    │        diff: "[Full diff below...]",        ← placeholder          │
│    │        issue_category_values: "bug/security/..."                   │
│    │        issue_severity_values: "high/medium/info"                   │
│    │      }                                                             │
│    │                                                                     │
│    ├─ 3. COMPOSE                                                        │
│    │    body = "\n\n---\n\n".join(rendered_sections)                     │
│    │    body += separator + repository_context (if exists)              │
│    │    overhead = len(body) + len(reminder) + len(separator)           │
│    │    available = max(0, max_total_chars - overhead)                   │
│    │    diff_text = truncate(diff, available)  (whole-line boundaries)  │
│    │    final = body + separator + "## Diff\n```diff\n" + diff_text     │
│    │            + "\n```" + reminder                                    │
│    │                                                                     │
│    │    → ComposedPrompt(content, fragments_used, total_tokens)         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Flow Diagram

```
  ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────┐
  │  CLI     │────▶│  Bootstrap   │────▶│  CliRunner   │────▶│  PR     │
  │  Args    │     │  (Composi-   │     │  .run_review │     │  Lister │
  │  -r, -p  │     │  tionRoot)   │     │              │     │  (Git)  │
  │  -v,     │     │              │     │  Parses args,│     └────┬────┘
  │  --force │     │  Wires all   │     │  fetches PR  │          │
  └──────────┘     │  adapters    │     │  metadata    │          │ GET /pulls/71
                    └──────────────┘     └──────┬───────┘          │
                                                │                  ▼
                                                │           ┌────────────┐
                                                │           │  Git API   │
                                                │           │ (Forgejo/  │
                                                │           │  GitHub)   │
                                                │           └────────────┘
                                                │
                                                ▼
                                     ┌─────────────────────┐
                                     │ ReviewPullRequest   │
                                     │ Service.execute()   │
                                     └──┬───┬───┬───┬───┬──┘
                                        │   │   │   │   │
               ┌────────────────────────┘   │   │   │   └──────────────┐
               ▼                            │   │   │                  ▼
      ┌────────────────┐                    │   │   │        ┌────────────────┐
      │ PullRequestRepo│                    │   │   │        │  state.json    │
      │ .find()        │                    │   │   │        │  (persist)     │
      └────────────────┘                    │   │   │        └────────────────┘
               │                            │   │   │
               ▼                            │   │   │
      ┌────────────────┐                    │   │   │
      │ Changeset      │                    │   │   │
      │ Fetcher.fetch()│────────────────────┼───┼───┼──────▶ Local Git
      │ (Local git)    │   clone, diff,     │   │   │
      └────────────────┘   file contents    │   │   │
               │                            │   │   │
               ▼                            │   │   │
      ┌────────────────┐                    │   │   │
      │ ReviewContext  │                    │   │   │
      │ Factory.build()│────────────────────┼───┼───┼──────▶ Local Git
      │ (local git)    │   repo structure,  │   │   │
      └────────────────┘   conventions       │   │   │
               │                            │   │   │
               ▼                            │   │   │
      ┌────────────────┐                    │   │   │
      │ ComposePrompt  │                    │   │   │
      │ Adapter.execute│                    │   │   │
      └────────────────┘                    │   │   │
               │                            │   │   │
               ▼                            │   │   │
      ┌────────────────┐                    │   │   │
      │ LlmReviewPort  │                    │   │   │
      │ .review_prompt │────────────────────┼───┼───┼──────▶ Ollama
      └────────────────┘                    │   │   │
               │                            │   │   │
               ▼                            │   │   │
      ┌────────────────┐                    │   │   │
      │ Deterministic  │                    │   │   │
      │ Findings       │                    │   │   │
      └────────────────┘                    │   │   │
               │                            │   │   │
               ▼                            │   │   │
      ┌────────────────┐                    │   │   │
      │ Blocker        │                    │   │   │
      │ Tracking       │                    │   │   │
      └────────────────┘                    │   │   │
               │                            │   │   │
               ▼                            │   │   │
      ┌────────────────┐                    │   │   │
      │ Review         │                    │   │   │
      │ Publisher      │────────────────────┼───┼───┼──────▶ Git API
      │ .publish()     │                    │   │   │
      └────────────────┘                    │   │   │
               │                            │   │   │
               ▼                            │   │   │
      ┌────────────────┐                    │   │   │
      │ PullRequest    │                    │   │   │
      │ .add_review()  │                    │   │   │
      └────────────────┘                    │   │   │
               │                            │   │   │
               ▼                            │   │   │
      ┌────────────────┐                    │   │   │
      │ PullRequest    │                    │   │   │
      │ Repo.save()    │────────────────────┼───┼───┼──────▶ state.json
      └────────────────┘                    │   │   │
```

---

## 7. Advanced Review Flows

### 7.1. Multi-Phase Review

```
RunMultiPhaseReviewCommand
       │
       ▼
MultiPhaseReviewOrchestrator.execute()
       │
       ├─▶ Full retry loop (max_retries times)
       │    │
       │    ├─▶ _run_phases(plan, repo_path, changed_files, model)
       │    │    │
       │    │    ├─▶ Phase 1: Security Review
       │    │    │    RunAgentConversationCommand → AgentConversationService
       │    │    │    └─▶ Tool calls: read_file, search_codebase, etc.
       │    │    │
       │    │    ├─▶ Phase 2: Architecture Review
       │    │    │    (injects Phase 1 findings via __PREVIOUS_FINDINGS__)
       │    │    │
       │    │    ├─▶ Phase 3: Style Review
       │    │    │
       │    │    └─▶ Aggregate: AggregateReviewFindingsCommand
       │    │         └─▶ FindingAggregator → deduplicate, merge
       │    │         └─▶ VerifyFindingsCommand
       │    │              └─▶ FindingVerifier → validate against source
       │    │
       │    └─▶ If zero items: _run_feedback_loop() (max_feedback_rounds)
       │         Re-runs with feedback context from prior attempt
       │
       └─▶ Returns final CodeReview
```

### 7.2. Agent System

The agent system provides specialized agents for different review aspects. The `MultiPhaseReviewOrchestrator` creates a `ReviewPlan` with phases, each phase specifying an agent type:

| Agent | Purpose |
|-------|---------|
| `AdvisorAgent` | Provides advisory feedback |
| `ArchitectAgent` | Reviews architecture and design |
| `EngineerAgent` | Reviews implementation details |
| `ExplorerAgent` | Explores codebase for context |
| `ManagerAgent` | Orchestrates the review process |
| `ReviewerAgent` | Performs the actual code review |

Each agent is instantiated with a role-specific system prompt. The `AgentConversationService` runs the multi-turn conversation with tool access (read_file, search_codebase, list_directory, run_git, get_changed_files).

### 7.3. Agent Conversation (Single Phase)

```
RunAgentConversationCommand
       │
       ▼
AgentConversationService._run()
       │
       ├─▶ Initialize messages: [system_prompt, user_prompt_with_tools]
       │
       ├─▶ Loop (max 10 turns):
       │    │
       │    ├─▶ chat_port.send(messages) → OllamaExploratoryChatAdapter
       │    │
       │    ├─▶ ParseReviewTurnCommand → TurnParseResult
       │    │    ├─▶ verdict: build PhaseResult, validate, return
       │    │    ├─▶ tool_call: execute_tool → append result → continue
       │    │    ├─▶ unparseable: reprompt (max 3 consecutive)
       │    │    └─▶ empty: reprompt (max 3 consecutive)
       │    │
       │    └─▶ Demand tool exploration if verdict with no tool calls
       │
       └─▶ Max turns exceeded → LlmUnavailableError with dump
```

---

## 8. Key Implementation Details

### Local Git Clone for Diffs

The `LocalChangesetFetcher` uses local git clones instead of API calls:
- Clones to `~/.cache/pr-auto-reviewer/repos/{owner}_{repo}_{pr}/`
- Uses `git fetch origin pull/{pr}/head:pr-{pr}` to get PR ref
- Computes diff via `git diff base_sha..pr-{pr}`
- Reads file contents via `git show pr-{pr}:{file_path}`
- Avoids API rate limits, provides full file context

### Token Budget & Fragment Selection

- Fragments have `priority` (1000=system, 100-999=language, 1-99=supplementary)
- `TokenBudgetManager` greedily selects highest-priority fragments
- `USE_STRICT_FRAGMENT_SELECTION=true` adds heuristic relevance filter
- Diff included once at end, truncated to fit `max_total_chars` (default 60k)

### Verdict Preservation

`CodeReview` is `frozen=True`. Every construction site must preserve verdict:
- `_add_deterministic_findings`: uses `verdict=review.verdict` (was bug: hardcoded APPROVED)
- Blocker guard: only overrides to CHANGES_REQUESTED when unresolved blockers exist
- Publishers: copy input verdict, apply platform-specific event mapping

### Rate Limit Tracking

- `RateLimitTracker` parses `x-ratelimit-limit`, `-remaining`, `-reset`
- State persisted to `~/.config/pr-auto-reviewer/rate-limits.json`
- Waits before requests when remaining < threshold
- Survives restarts to avoid immediate re-exhaustion

### Preflight Verification

- Runs before each review: `GET /user` + `POST /requested_reviewers`
- Caches verified `(org, role)` pairs in `verified-tokens.json`
- Side-effect-free (empty reviewers list)

---

## 9. Files Referenced

| Component | File |
|-----------|------|
| CLI entry | `src/pr_auto_reviewer/cli.py` |
| Bootstrap | `src/pr_auto_reviewer/presentation/composition_root.py` |
| DI Container | `src/pr_auto_reviewer/infrastructure/container/_container.py` |
| Review Service | `src/pr_auto_reviewer/application/services/review_pull_request_service.py` |
| Changeset Fetcher | `src/pr_auto_reviewer/infrastructure/local_repository/local_changeset_fetcher.py` |
| Local Git Repo | `src/pr_auto_reviewer/infrastructure/local_repository/local_git_repository.py` |
| Review Context Factory | `src/pr_auto_reviewer/infrastructure/context/review_context_factory.py` |
| Compose Prompt | `src/pr_auto_reviewer/infrastructure/fragments/compose_review_prompt_adapter.py` |
| Fragment Repo | `src/pr_auto_reviewer/infrastructure/fragments/file_system_fragment_repository.py` |
| LLM Adapter | `src/pr_auto_reviewer/infrastructure/llm/ollama_llm_adapter.py` |
| Response Parser | `src/pr_auto_reviewer/infrastructure/llm/review_response_parser.py` |
| Retry Orchestrator | `src/pr_auto_reviewer/infrastructure/llm/retry_orchestrator.py` |
| Review Publisher | `src/pr_auto_reviewer/infrastructure/review_publishers/review_publishing_service.py` |
| Forgejo Publisher | `src/pr_auto_reviewer/infrastructure/forgejo/forgejo_review_publisher.py` |
| GitHub Publisher | `src/pr_auto_reviewer/infrastructure/github/github_review_publisher.py` |
| Review Processor | `src/pr_auto_reviewer/infrastructure/review_publishers/_review_processor.py` |
| Verdict Mapping | `src/pr_auto_reviewer/infrastructure/review_publishers/_shared.py` |
| Multi-Phase Orchestrator | `src/pr_auto_reviewer/application/services/multi_phase_review_orchestrator.py` |
| Agent Conversation | `src/pr_auto_reviewer/application/services/agent_conversation_service.py` |
| Finding Verifier | `src/pr_auto_reviewer/application/services/finding_verifier.py` |
| Finding Aggregator | `src/pr_auto_reviewer/application/services/finding_aggregator.py` |
| Polling Daemon | `src/pr_auto_reviewer/presentation/polling_daemon/polling_daemon.py` |
| Config Loader | `src/pr_auto_reviewer/infrastructure/config/config.py` |
| Rate Limit Tracker | `src/pr_auto_reviewer/infrastructure/client/rate_limit_tracker/rate_limit_tracker.py` |
| Preflight Verifier | `src/pr_auto_reviewer/infrastructure/client/preflight_verifier.py` |