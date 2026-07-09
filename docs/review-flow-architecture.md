# Review Command Flow: Architecture & Adapter Diagrams

**Command:** `uv run pr-auto-reviewer review -r gbrennon/pr-auto-reviewer -p 71 -v --force`

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
 3  CliRunner._run_review()
    │  force=True → pr_lister.get_pr(repo, 71)  [state-agnostic]
    │  Builds ReviewPullRequestCommand(pr_id, sha, title, desc, force=true)
    v
 4  ReviewPullRequestService.execute()
    ├─ 4a. PullRequestRepository.find(pr_id)
    │      → Load from ~/.config/pr-auto-reviewer/state.json
    ├─ 4b. force=true → skip needs_review check
    ├─ 4c. ChangesetFetcherPort.fetch(pr_id, sha)
    │      → Git API: GET diff, GET file contents, GET commits
    ├─ 4d. ReviewContextFactoryPort.build(pr_id, diff, title, desc)
    │      → Fetches repo structure, detects language/architecture
    │      → Fetches prompt fragments, renders via Jinja2, composes prompt
    ├─ 4e. LlmReviewPort.review_prompt(prompt)
    │      → POST Ollama /api/generate, parse JSON response
    ├─ 4f. ReviewPublisherPort.publish(pr_id, review)
    │      → POST Git API: submit formal review
    ├─ 4g. pr.add_review(review, sha)  [new immutable PullRequest]
    └─ 4h. PullRequestRepository.save(pr)
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
                    │  └──────────────────────────────────┘     │   │
                    │                                          │   │
                    │  ┌──────────────────────────────────┐     │   │
                    │  │   Inbound Ports (Protocols)      │     │   │
                    │  │   ─────────────────────────      │     │   │
                    │  │   ReviewPullRequestUseCase       │     │   │
                    │  │   ProcessIssueCommandsUseCase    │     │   │
                    │  │   RegisterIssuePort              │     │   │
                    │  └──────────────────────────────────┘     │   │
                    │                                          │   │
                    │  ┌──────────────────────────────────┐     │   │
                    │  │   Commands (CQRS)                │     │   │
                    │  │   ──────────────────────         │     │   │
                    │  │   ReviewPullRequestCommand       │     │   │
                    │  │   ProcessIssueCommandsCommand    │     │   │
                    │  │   RegisterIssueCommand           │     │   │
                    │  └──────────────────────────────────┘     │   │
                    │                                          │   │
                    │  ┌──────────────────────────────────┐     │   │
                    │  │   Domain Services                │     │   │
                    │  │   ReviewItemParser               │     │   │
                    │  │   IssueCommandParser             │     │   │
                    │  └──────────────────────────────────┘     │   │
                    └──────────────┬───────────────────────────┘   │
                                   │ calls ───── Driven Ports     │
                                   │            (Outbound)        │
                    ┌──────────────▼───────────────────────────┐   │
                    │         INFRASTRUCTURE LAYER            ◄───┘
                    │                                          │
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
                    │  └────────────────────────────────────┘   │
                    │                                            │
                    │  ┌────────────────────────────────────┐   │
                    │  │   ADAPTERS (Implementations)       │   │
                    │  │                                    │   │
                    │  │  GitChangesetFetcherAdapter  ─────▶│───│─── Git API
                    │  │  GitRepositoryContextAdapter ─────▶│───│─── Git API
                    │  │  GitReviewPublisherAdapter  ─────▶│───│─── Git API
                    │  │  GitReviewReaderAdapter     ─────▶│───│─── Git API
                    │  │  GitCommentReaderAdapter    ─────▶│───│─── Git API
                    │  │  GitCommentPublisherAdapter ─────▶│───│─── Git API
                    │  │  GitIssueTrackerAdapter     ─────▶│───│─── Git API
                    │  │  GitPrListerAdapter         ─────▶│───│─── Git API
                    │  │  GitRepoListerAdapter       ─────▶│───│─── Git API
                    │  │                                    │   │
                    │  │  OllamaLlmAdapter ────────────────▶│───│─── Ollama
                    │  │                                    │   │
                    │  │  TerminalReviewPublisherAdapter ──▶│─── stdout
                    │  │  NullPullRequestRepository  ──────▶│─── no-op
                    │  │  JsonFilePullRequestRepo ─────────▶│─── state.json
                    │  │                                    │   │
                    │  │  FileSystemFragmentRepository ────▶│─── content/*.md
                    │  │  Jinja2Renderer              ─────▶│─── Jinja2
                    │  │  ComposeReviewPromptAdapter  ─────▶│─── prompt assembly
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
│                                                                 │
│  Adapters created:                                              │
│    pr_repository ──── JsonFilePullRequestRepository(state.json) │
│    changeset_fetcher ─ GitChangesetFetcherAdapter(http_client)  │
│    repository_context ─ GitRepositoryContextAdapter(http_client)│
│    llm_review ──────── OllamaLlmAdapter(host, model, ...)       │
│    review_publisher ── GitReviewPublisherAdapter(reviewer_cli)  │
│    review_reader ───── GitReviewReaderAdapter(http_client)      │
│    comment_reader ──── GitCommentReaderAdapter(http_client)     │
│    comment_publisher ─ GitCommentPublisherAdapter(reviewer_cli) │
│    issue_tracker ───── GitIssueTrackerAdapter(http_client)      │
│    repo_lister ─────── GitRepoListerAdapter(http_client)        │
│    pr_lister ───────── GitPrListerAdapter(http_client)          │
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
└─────────────────────────────────────────────────────────────────┘

  CompositionRoot._wire_components()
  │
  ├── ReviewPullRequestService(
  │       pr_repository,
  │       changeset_fetcher,
  │       review_context_factory,    ← Composite: wraps 2 ports
  │       llm_review,
  │       review_publisher,
  │   )
  │
  ├── ProcessIssueCommandsService(
  │       pr_repository, review_reader, comment_reader,
  │       comment_publisher, issue_tracker, review_item_parser,
  │       issue_command_parser, issue_body_builder,
  │   )
  │
  └── CliRunner(
          review_service,
          process_commands_service,
          review_reader,
          pr_lister,
          review_item_parser,
          pr_repository,
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
  │       └─ GitPrListerAdapter                                   │
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
│ 4.3.3 FETCH DIFF (step-by-step inside)                         │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ changeset_fetcher.fetch(pr_id, head_sha)                 │   │
│ │                                                          │   │
│ │ GitChangesetFetcherAdapter                               │   │
│ │  ┌──────────────────────────────────────────────────┐   │   │
│ │  │ ① GET /repos/gbrennon/pr-auto-reviewer/          │   │   │
│ │  │       pulls/71.diff                              │   │   │
│ │  │   → raw unified diff (string)                    │   │   │
│ │  │   Validate: len > 50 chars                       │   │   │
│ │  │                                                  │   │   │
│ │  │ ② Extract changed file paths from diff headers   │   │   │
│ │  │   regex: ^diff --git a/(.+) b/(.+)               │   │   │
│ │  │   → ["src/main.py", "src/utils.py", ...]         │   │   │
│ │  │                                                  │   │   │
│ │  │ ③ For each changed file:                         │   │   │
│ │  │   GET /repos/gbrennon/pr-auto-reviewer/          │   │   │
│ │  │       raw/{sha}/{file_path}                      │   │   │
│ │  │   → file_contents: {"src/main.py": "...", ...}   │   │   │
│ │  │                                                  │   │   │
│ │  │ ④ GET /repos/gbrennon/pr-auto-reviewer/          │   │   │
│ │  │       pulls/71/commits?limit=30                  │   │   │
│ │  │   → ["feat: add ...", "fix: ...", ...]           │   │   │
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
│ 4.3.4 BUILD REVIEW CONTEXT + COMPOSE PROMPT                    │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ review_context_factory.build(pr_id, diff, title, desc)   │   │
│ │                                                          │   │
│ │ ┌─ ReviewContextFactory (Composite Port) ─────────────┐  │   │
│ │ │                                                     │  │   │
│ │ │ 4.4.a RepositoryContextPort.fetch(pr_id)            │  │   │
│ │ │   └─ GitRepositoryContextAdapter                    │  │   │
│ │ │      ① GET .../git/trees/main?recursive=1           │  │   │
│ │ │        → tree_paths: ["src/...", "tests/..."]       │  │   │
│ │ │      ② ArchitectureDetector.detect(paths)           │  │   │
│ │ │        → "hexagonal" / "mvc" / "unknown"            │  │   │
│ │ │      ③ Fetch CONVENTIONS.md / ARCHITECTURE.md       │  │   │
│ │ │      ④ PythonVersionDetector.detect(paths)→"3.12"  │  │   │
│ │ │      → RepositoryContext(arch, conventions, struc)  │  │   │
│ │ │                                                     │  │   │
│ │ │   Augment: attach pr_title, pr_description          │  │   │
│ │ │                                                     │  │   │
│ │ │ 4.4.b RepositoryContextPort.build_fragment_context() │  │   │
│ │ │   └─ GitRepositoryContextAdapter                    │  │   │
│ │ │      ① LanguageDetector.detect(file_paths)          │  │   │
│ │ │        → "python" (from .py extension)              │  │   │
│ │ │      ② ContextSerializer.serialize(repo_ctx,       │  │   │
│ │ │           commit_msgs, python_version)              │  │   │
│ │ │        → Markdown string                            │  │   │
│ │ │      → ("python", serialized_context | None)        │  │   │
│ │ │                                                     │  │   │
│ │ │   ReviewContext(                                     │  │   │
│ │ │     language="python",                              │  │   │
│ │ │     file_paths=["src/main.py", ...],                 │  │   │
│ │ │     diff=pull_request_diff.diff_content,             │  │   │
│ │ │     repository_context=serialized,                   │  │   │
│ │ │   )                                                  │  │   │
│ │ │                                                     │  │   │
│ │ │ 4.4.c ComposeReviewPromptPort.execute(ctx)          │  │   │
│ │ │   └─ ComposeReviewPromptAdapter                     │  │   │
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
│ │ │   ── RENDER FRAGMENTS ──                            │  │   │
│ │ │   For each fragment:                                │  │   │
│ │ │     Jinja2Renderer.render(template, variables)      │  │   │
│ │ │     variables: language, file_paths,                │  │   │
│ │ │               repository_context                    │  │   │
│ │ │     (diff placeholder: "[Full diff below...]")      │  │   │
│ │ │                                                     │  │   │
│ │ │   ── COMPOSE FINAL PROMPT ──                        │  │   │
│ │ │   Join rendered sections with "\n\n---\n\n"         │  │   │
│ │ │   Append repository_context                         │  │   │
│ │ │   Append JSON output reminder                       │  │   │
│ │ │   Append "## Diff\n```diff\n{diff}\n```"            │  │   │
│ │ │   (Truncate diff if > max_total_chars)              │  │   │
│ │ │                                                     │  │   │
│ │ │   → ComposedPrompt(                                 │  │   │
│ │ │       content="Full prompt text...",                │  │   │
│ │ │       fragments_used=["type-hints", "solid", ...],  │  │   │
│ │ │       total_tokens=len//4,                          │  │   │
│ │ │     )                                               │  │   │
│ │ └─────────────────────────────────────────────────────┘  │   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.5 RUN LLM REVIEW                                           │
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
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.6 PUBLISH REVIEW                                           │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ review_publisher.publish(pr_id, review)                  │   │
│ │                                                          │   │
│ │ GitReviewPublisherAdapter (since output_mode="codeberg") │   │
│ │  ┌──────────────────────────────────────────────────┐   │   │
│ │  │ Map verdict → event:                              │   │   │
│ │  │   APPROVED          → "APPROVED"                  │   │   │
│ │  │   CHANGES_REQUESTED → "REQUEST_CHANGES"           │   │   │
│ │  │   COMMENTED         → "COMMENT"                   │   │   │
│ │  │                                                   │   │   │
│ │  │ COMMENTED → POST /issues/{num}/comments            │   │   │
│ │  │   (non-blocking items only; blocking → formal only) │   │   │
│ │  │ APPROVED/REQUEST_CHANGES → first counts existing    │   │   │
│ │  │   reviews to offset item numbers (no duplicates).   │   │   │
│ │  │   Then: request reviewer → POST /pulls/{num}/reviews│   │   │
│ │  │   with full body + inline diff comments.            │   │   │
│ │  │                                                   │   │   │
│ │  │ format_review_body(review, start_number=N)          │   │   │
│ │  │   Jinja2 template: review_output.j2               │   │   │
│ │  │   → Markdown body with verdict, summary,          │   │   │
│ │  │     issue table, suggestions, praise              │   │   │
│ │  │                                                   │   │   │
│ │  │ POST .../pulls/71/requested_reviewers              │   │   │
│ │  │   { reviewers: [reviewer_username] }              │   │   │
│ │  │   (non-fatal if fails)                             │   │   │
│ │  │                                                   │   │   │
│ │  │ POST .../pulls/71/reviews                          │   │   │
│ │  │   { event: verdict_event, body: formatted_body }  │   │   │
│ │ └──────────────────────────────────────────────────┘   │   │
│ └──────────────────────────────────────────────────────────┘   │
│                    │                                            │
│ 4.3.7 RECORD & PERSIST                                         │
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
└────────────────────────────────────────────────────────────────────────────┘
         ▲                      ▲                      ▲
         │                      │                      │
         │ injected into        │ injected into        │ injected into
    ┌────┴────────────┐   ┌────┴────────────┐   ┌────┴────────────┐
    │ ChangesetFetcher│   │ RepositoryCtx   │   │ ReviewPublisher │
    │   Adapter       │   │   Adapter       │   │   Adapter       │
    └─────────────────┘   └─────────────────┘   └─────────────────┘
         │                      │                      │
         │ API calls:           │ API calls:           │ API calls:
         │                      │                      │
    ═════╪══════════════════════╪══════════════════════╪═══════════════
         ▼                      ▼                      ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                 Forgejo / Codeberg / GitHub                   │
    │                                                              │
    │  GET  /repos/{repo}/pulls/{num}.diff                         │
    │  GET  /repos/{repo}/raw/{sha}/{file}                         │
    │  GET  /repos/{repo}/pulls/{num}/commits                      │
    │  GET  /repos/{repo}/git/trees/{branch}?recursive=1           │
    │  GET  /repos/{repo}/raw/main/{CONVENTIONS.md,...}            │
    │  GET  /repos/{repo}/pulls/{num}                              │
    │  GET  /user                                                  │
    │  GET  /user/repos                                            │
    │  POST /repos/{repo}/pulls/{num}/reviews                      │
    │  POST /repos/{repo}/pulls/{num}/requested_reviewers          │
    │  POST /repos/{repo}/issues                                   │
    │  POST /repos/{repo}/issues/{num}/comments                    │
    └──────────────────────────────────────────────────────────────┘
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
     │ Fetcher.fetch()│────────────────────┼───┼───┼──────▶ Git API
     └────────────────┘                    │   │   │        (diff, files,
              │                            │   │   │         commits)
              ▼                            │   │   │
     ┌────────────────┐                    │   │   │
     │ ReviewContext  │                    │   │   │
     │ Factory.build()│────────────────────┼───┼───┼──────▶ Git API
     └────────────────┘                    │   │   │        (tree, conv)
              │                            │   │   │
              ├────────────────────────────┼───┼───┼──────▶ content/*.md
              │                            │   │   │
              ▼                            │   │   │
     ┌────────────────┐                    │   │   │
     │ ComposeReview  │                    │   │   │
     │ PromptAdapter  │────────────────────┼───┼───┼──────▶ Jinja2 render
     │ .execute()     │                    │   │   │
     └────────────────┘                    │   │   │
              │                            │   │   │
              ▼                            │   │   │
     ┌────────────────┐                    │   │   │
     │ OllamaLlm      │                    │   │   │
     │ Adapter        │────────────────────┼───┼───┼──────▶ Ollama HTTP
     │ .review_prompt │                    │   │   │        /api/generate
     └────────────────┘                    │   │   │
              │                            │   │   │
              ▼                            │   │   │
     ┌────────────────┐                    │   │   │
     │ ReviewPublisher│                    │   │   │
     │ .publish()     │────────────────────┼───┼───┼──────▶ Git API
     └────────────────┘                    │   │   │        POST /reviews
                                           │   │   │
                                           ▼   ▼   ▼
                                    ┌─────────────────────┐
                                    │  Review posted to   │
                                    │  PR #71             │
                                    └─────────────────────┘
```

---

## 7. Layered Domain Model

```
┌─────────────────────────────────────────────────────────────────────┐
│  VALUE OBJECTS (immutable, no identity)                              │
│                                                                     │
│  PullRequestId(repository, number)  ─── identity of the review      │
│  CommitSha(value)                   ─── git commit hash              │
│  PullRequestDiff                    ─── diff + file contents + msgs │
│  CodeReview                         ─── LLM output (verdict+items)  │
│  ReviewVerdict                      ─── APPROVED/CHANGES_REQUESTED/ │
│  ItemSeverity                       ─── CRITICAL/MAJOR/MINOR/INFO   │
│  RepositoryContext                  ─── repo metadata for prompt    │
│  CommentId / PrComment / IssueCommand                               │
│  ComposedPrompt / ReviewContext / PromptFragment                    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  ENTITIES (mutable identity tracked over time)                      │
│                                                                     │
│  PullRequest (aggregate root)                                       │
│    └─ id: PullRequestId                                             │
│    └─ head_sha: CommitSha                                           │
│    └─ reviews: tuple[CodeReview]                                    │
│    └─ processed_comment_ids: frozenset[CommentId]                   │
│    └─ needs_review(sha) → bool                                      │
│    └─ add_review(review, sha) → PullRequest (immutable replace)     │
│                                                                     │
│  ReviewItem                                                         │
│    └─ number, severity, category, file_path,                        │
│       line, description, current_code, suggested_fix                │
│                                                                     │
│  ReviewSuggestion                                                   │
│    └─ file, line, description,                                      │
│       current_code, suggested_code                                  │
│                                                                     │
│  ReviewPraise                                                       │
│    └─ description, file                                             │
│       (never enumerated — purely qualitative)                       │
│                                                                     │
│  Issue                                                              │
│    └─ id, title, body, closed                                       │
│    └─ close() → Issue (immutable replace)                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Hexagonal Architecture** | Domain + Application layers have zero dependencies on infrastructure. Every external system (Git API, Ollama, filesystem) is behind a port/adapter. |
| **Composite `ReviewContextFactory`** | Wraps `RepositoryContextPort` + `ComposeReviewPromptPort` into a single port, eliminating data-clump in `ReviewPullRequestService`. |
| **Immutable aggregate** | `PullRequest` is a frozen dataclass. "Mutation" methods return a new instance via `dataclasses.replace()`. Prevents accidental state corruption. |
| **Fragment-based prompts** | Language-specific + universal prompt fragments are selected by priority, rendered via Jinja2, and composed into a single prompt. Token-budget-aware greedy selection. |
| **Force mode bypass** | `--force` skips the `needs_review()` check and the open-PR filter, enabling re-review of closed/merged PRs. |
| **Two-level CLI parsing** | `cli.py` (outer) parses top-level args and bootstraps; `CliRunner` (inner) re-parses for subcommand dispatch. Enables reuse from `CliRunner.main()`. |

## 9. File Index

| Layer | Key Files |
|---|---|
| **Entry** | `src/pr_auto_reviewer/cli.py` (argparse + dispatch) |
| **Composition** | `src/pr_auto_reviewer/presentation/composition_root.py` (bootstrap, wiring) |
| **CLI** | `src/pr_auto_reviewer/presentation/cli/runner.py` (subcommand dispatch) |
| **Use Case** | `src/pr_auto_reviewer/application/services/review_pull_request_service.py` |
| **Domain** | `src/pr_auto_reviewer/domain/entities/pull_request.py` |
| **Value Objects** | `src/pr_auto_reviewer/domain/value_objects/` (13 files) |
| **Ports** | `src/pr_auto_reviewer/application/ports/` (3 inbound, 14 outbound) |
| **Adapter: Git** | `src/pr_auto_reviewer/infrastructure/git_platform/` (11 adapters) |
| **Adapter: LLM** | `src/pr_auto_reviewer/infrastructure/llm/` (Ollama, parser) |
| **Adapter: Fragments** | `src/pr_auto_reviewer/infrastructure/fragments/` (compose, repos, renderers) |
| **Persistence** | `src/pr_auto_reviewer/infrastructure/persistence/` (JSON file, null) |
| **Fragments Content** | `src/pr_auto_reviewer/infrastructure/fragments/content/` (universal/, python/, shell/, ...) |
| **Templates** | `src/pr_auto_reviewer/infrastructure/llm/templates/` (review_output.j2) |
| **DI Container** | `src/pr_auto_reviewer/infrastructure/container.py` |
| **Config** | `src/pr_auto_reviewer/infrastructure/config/config.py` |
