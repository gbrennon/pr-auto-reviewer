# Deep Architecture Diagrams

Visual and structural reference for the pr-auto-reviewer codebase.

---

## 1. Hexagonal Layer Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION                             │
│  ┌──────────────┐  ┌──────────────────────┐  ┌───────────────┐  │
│  │   CLI Runner │  │  Polling Daemon      │  │ Composition   │  │
│  │   (cli.py)   │  │  (polling_daemon.py) │  │ Root          │  │
│  └──────┬───────┘  └──────────┬───────────┘  └───────┬───────┘  │
└─────────┼─────────────────────┼──────────────────────┼──────────┘
          │                     │                      │
          ▼                     ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                       APPLICATION                               │
│  ┌─────────────────┐ ┌──────────────────────────────────────┐  │
│  │  Inbound Ports  │ │          Use Cases / Services        │  │
│  │  (Interfaces)   │ │  • ReviewPullRequestService          │  │
│  │  • ReviewPRPort │ │  • MultiPhaseReviewOrchestrator      │  │
│  │  • CmdBusPort   │ │  • AgentConversationService          │  │
│  └────────┬────────┘ │  • FindingAggregatorService          │  │
│           │          │  • FindingVerifierService            │  │
│           ▼          │  • PhaseManagerService               │  │
│  ┌─────────────────┐ │  • PhaseAdvisorService               │  │
│  │ Outbound Ports  │ │  • TurnParserService                 │  │
│  │ (Protocols)     │ │  • IdentifierGroundingFilterService  │  │
│  │ • LlmReviewPort │ └──────────────────────────────────────┘  │
│  │ • ChgSetPort    │           │              │                │
│  │ • PRRepoPort    │           ▼              ▼                │
│  │ • ConvLogPort   │  ┌──────────────────────────────────────┐  │
│  │ • NotifierPort  │  │       Domain Events / Commands       │  │
│  │ • ChatPort      │  │  • ReviewPullRequestCommand          │  │
│  │ • PromptPort    │  │  • RunMultiPhaseReviewCommand        │  │
│  │ • FragRepoPort  │  │  • RunAgentConversationCommand       │  │
│  │ • CmdBusPort    │  │  • AggregateReviewFindingsCommand    │  │
│  │ • RepoCtxPort   │  │  • VerifyFindingsCommand             │  │
│  └─────────────────┘  │  • PhaseCompletedEvent               │  │
└───────────────────────┼─▶│  • FindingsAggregatedEvent         │  │
                        │  │  • ConversationCompletedEvent      │  │
                        │  │  • ReviewTurnParsedEvent           │  │
                        │  └──────────────────────────────────────┘  │
                        └────────────────────────────────────────────┘
                                       │              │
                                       ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      INFRASTRUCTURE                             │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────┐  │
│  │ Git Platform │ │    LLM       │ │ Persistence│ │ Fragments│  │
│  │  Adapters    │ │  Adapters    │ │ Adapters   │ │ Adapters │  │
│  ├──────────────┤ ├──────────────┤ ├────────────┤ ├──────────┤  │
│  │ • ForgejoPR  │ │ • Ollama     │ │ • JSONFile │ │ • FS     │  │
│  │   Lister     │ │   Adapter    │ │   PR Repo  │ │   Repo   │  │
│  │ • GitHubPR   │ │ • LlamaCpp   │ │ • NullPR   │ │ • Jinja2 │  │
│  │   Lister     │ │   Adapter    │ │   Repo     │ │   Render │  │
│  │ • Forgejo    │ │ • BaseLLM    │ └────────────┘ └──────────┘  │
│  │   ReviewPub  │ │   Adapter    │  ┌──────────────┐            │
│  │ • GitHub     │ │              │  │ Conversation │            │
│  │   ReviewPub  │ │              │  │ Logger       │            │
│  │ • Forgejo    │ │              │  │ (Markdown)   │            │
│  │   CommentPub │ │              │  └──────────────┘            │
│  │ • GitHub     │ │              │  ┌──────────────┐            │
│  │   CommentPub │ │              │  │ Exploration  │            │
│  │ • HTTP Client│ │              │  │ Tool Service │            │
│  │ • Token Mgr  │ │              │  └──────────────┘            │
│  └──────────────┘ └──────────────┘  ┌──────────────┐            │
│  ┌──────────────┐                    │ Prompt Builder│           │
│  │ Local Repo   │                    │ Token Budget │            │
│  │  Adapters    │                    └──────────────┘            │
│  │ • Changeset  │                                        
│  │   Fetcher    │                                        
│  │ • GitRepo    │                                        
│  │ • RepoCtx    │                                        
│  └──────────────┘                                        
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Domain Model Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                      DOMAIN LAYER                               │
│                                                                 │
│  ┌─────────────────┐       ┌─────────────────┐                 │
│  │  PullRequest    │◀──────│  ReviewItem     │                 │
│  │  (Aggregate)    │       │  (Entity)       │                 │
│  ├─────────────────┤       ├─────────────────┤                 │
│  │ id: PullRequestId     │ id: str          │                 │
│  │ number: int           │ severity: ItemSeverity│            │
│  │ repository: str       │ category: IssueCategory│           │
│  │ title: str            │ file_path: str   │                 │
│  │ description: str      │ line_number: int │                 │
│  │ head_sha: CommitSHA   │ description: str │                 │
│  │ target_branch: str    │ suggested_fix: str│                │
│  │ is_draft: bool        │ current_code: str│                 │
│  │ review_requested:bool │ is_blocking: bool│                 │
│  │ unresolved_blocking:  │ grade: SubAgentGrade│              │
│  │   set[ReviewItemId]   └────────┬──────────┘                 │
│  └─────────────────────────────────┼───────────────────────────┘
│                                    │
│  ┌─────────────────┐       ┌─────────────────┐                 │
│  │  ReviewVerdict  │       │  CodeReview     │                 │
│  │  (StrEnum)      │       │  (Frozen Entity)│                 │
│  ├─────────────────┤       ├─────────────────┤                 │
│  │ APPROVED        │       │ verdict: ReviewVerdict           │
│  │ CHANGES_REQUESTED  │   │ reason: str                     │
│  │ COMMENTED       │       │ summary: str                    │
│  └────────┬────────┘       │ items: list[ReviewItem]         │
│           │                │ suggestions: list[ReviewSuggestion]│
│           ▼                │ praise: list[ReviewPraise]      │
│  ┌─────────────────┐       │ model_used: str                 │
│  │  SubReview      │       └──────────────────────────────────┘
│  │  Guardrails     │
│  ├─────────────────┤
│  │ is_coherent(v,i)│
│  │ reconcile(v,i)  │
│  └─────────────────┘
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Multi-Phase Review Orchestration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  MultiPhaseReviewOrchestratorService.run()                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
            ┌─────────────────────────────────┐
            │ Build ReviewPlan                │
            │ • Bug Hunt — Diff (Engineer)    │
            │ • Bug Hunt — Branch (Engineer)  │
            │ • Architecture Review (Architect)│
            │ • suggestions_phase_id = arch   │
            │ • manager_brief = "..."         │
            └──────────────┬──────────────────┘
                           │
                           ▼
            ┌─────────────────────────────────┐
            │ For each phase in plan.phases:  │
            └──────────────┬──────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ Manager    │  │  Advisor   │  │  Peer      │
    │ Agent      │  │  Agent     │  │  Agent     │
    │ (plans)    │  │ (grades)   │  │ (executes) │
    └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
          │               │               │
          │ 1. Briefs     │ 2. Grades     │ 3. Runs
          │    phase      │    each turn  │    conversation
          │               │               │
          ▼               ▼               ▼
    ┌─────────────────────────────────────────────┐
    │ PhaseTurnObserver → Advisor grades S/A/B/C/D/F │
    │ On F: block output → Manager re-plans       │
    │ On D: interrupt with feedback                │
    └─────────────────────────────────────────────┘
                           │
                           ▼
            ┌─────────────────────────────────┐
            │ FindingVerifierService.verify() │
            │ • Ground findings in source     │
            │ • Drop ungrounded findings      │
            │ • Return PhaseRunOutcome        │
            └──────────────┬──────────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
            ┌───────────┐ ┌───────────────┐
            │ All refuted? │ Has blocking? │
            │    (dropped) │ (CRITICAL/MAJOR)│
            └─────┬─────┘ └───────┬────────┘
                  │               │
           ┌──────┘               └──────┐
           ▼                              ▼
    ┌───────────────┐              ┌──────────────────┐
    │ Retry up to   │              │ Build CodeReview │
    │ REVIEW_MAX_   │              │ verdict =         │
    │ TRIES (2)     │              │ CHANGES_REQUESTED│
    │ Then raise    │              │ (if blocking)    │
    │ ReviewVerdictError           │ APPROVED         │
    └───────────────┘              │ (if no blocking)│
                                   └────────┬─────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │ Publisher        │
                                   │ (GitHub/Forgejo) │
                                   └──────────────────┘
```

---

## 4. Agent Conversation Turn Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  AgentConversationService.run_conversation()                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
            ┌─────────────────────────────────┐
            │ Build initial messages          │
            │ • System prompt (phase + role)  │
            │ • Manager brief (if first)      │
            │ • Anti-hallucination rules      │
            │ • Diff context                  │
            └──────────────┬──────────────────┘
                           │
           ┌───────────────┴───────────────┐
           │ Loop: max_turns (10)          │
           └───────────────┬───────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ LLM        │  │ Parse      │  │ Tools:     │
    │ Chat       │─▶│ Response   │─▶│ read_file  │
    │ Adapter    │  │ (TurnParser)   search_codebase│
    │ (Ollama)   │  │            │  │ list_dir   │
    └────────────┘  └────────────┘  │ run_git    │
           │                        │ get_files  │
           │                        └────────────┘
           │                          │
           ▼                          ▼
    ┌─────────────────────────────────────────────┐
    │ Advisor observes EVERY peer turn            │
    │ • Grades S/A/B/C/D/F                        │
    │ • On D/F: interrupts, restates task         │
    │ • On repeated F: reports to Manager         │
    └─────────────────────────────────────────────┘
                           │
                           ▼
            ┌─────────────────────────────────┐
            │ TurnParserService.parse()       │
            │ • Extract verdict (coerce)      │
            │ • Parse items (ReviewItem)      │
            │ • Parse suggestions/praise      │
            │ • Handle malformed JSON → prose │
            └──────────────┬──────────────────┘
                           │
                           ▼
            ┌─────────────────────────────────┐
            │ Verifier validates findings     │
            │ • Read cited files              │
            │ • Confirm snippets exist        │
            │ • Check superclasses/mixins     │
            │ • Drop ungrounded items         │
            └──────────────┬──────────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
            ┌───────────┐ ┌─────────────────┐
            │ Continue  │ │ Phase complete  │
            │ next turn │ │ → Findings      │
            │           │ │   Aggregated    │
            └───────────┘ └─────────────────┘
```

---

## 5. Adapter Communication Sequences

### 5.1 Git Platform API (Forgejo/Codeberg)

```
CLI/Daemon
    │
    ▼
GitPlatformHttpClient (base_url: /api/v1)
    │
    ├── GET /user                    → token verification
    ├── GET /repos/{owner}/{repo}/pulls/{pr}
    ├── GET /repos/{owner}/{repo}/pulls/{pr}.diff
    ├── GET /repos/{owner}/{repo}/pulls/{pr}/files
    ├── GET /repos/{owner}/{repo}/contents/{path}?ref={sha}
    ├── GET /repos/{owner}/{repo}/pulls/{pr}/reviews
    ├── POST /repos/{owner}/{repo}/pulls/{pr}/reviews
    │     { event: "APPROVED"|"REQUEST_CHANGES", body, commit_id, official: true }
    ├── POST /repos/{owner}/{repo}/issues/{pr}/comments
    ├── POST /repos/{owner}/{repo}/issues
    │     { title: "[CRITICAL] BUG: ...", body: "..." }
    └── GET /repos/{owner}/{repo}/issues/{pr}/comments
```

### 5.2 LLM Adapter (Ollama)

```
AgentConversationService
    │
    ▼
OllamaExploratoryChatAdapter / LlmAgentAdapter
    │
    ├── POST /api/chat
    │     { model, messages: [{role, content}], stream: true, tools }
    │
    ▼ (streaming SSE)
┌─────────────────────────────────────┐
│ Chunk 1: { message: { content } }   │
│ Chunk 2: { message: { tool_calls } }│
│ Chunk N: { done: true }             │
└─────────────────────────────────────┘
    │
    ▼
OllamaStreamingChatImpl (handles tool loop)
    │
    ├── Tool calls → ExplorationToolService
    │     • read_file(path)
    │     • search_codebase(query)
    │     • list_directory(path)
    │     • run_git(cmd)
    │     • get_changed_files()
    │
    ▼
Tool results injected back → continue conversation
```

---

## 6. Data Persistence & State

```
┌─────────────────────────────────────────────────────────────────┐
│  XDG State Directories                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ~/.config/pr-auto-reviewer/                                    │
│  └── config                  ← User config (env-file format)    │
│                                                                 │
│  ~/.local/state/pr-auto-reviewer/                               │
│  ├── state.json             ← Reviewed PRs by SHA (dedup)       │
│  └── conversations/         ← LLM transcripts per review        │
│       └── {owner}_{repo}_{pr}/{timestamp}/                      │
│           ├── 00-planning.md                                     │
│           ├── 01-bug-hunt-diff.md                                │
│           ├── 02-bug-hunt-branch.md                              │
│           ├── 03-architecture-review.md                          │
│           └── 05-verifier.md                                     │
│                                                                 │
│  ~/.cache/pr-auto-reviewer/                                     │
│  ├── verified-tokens.json   ← Token verification cache          │
│  └── repos/                 ← Local git clones for diffs        │
│       └── {owner}_{repo}_{pr}/                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Verdict → Platform Event Mapping

```
┌─────────────────────────────────────────────────────────────────┐
│  CodeReview.verdict (frozen, never COMMENTED)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                             ▼
    ┌───────────────┐              ┌───────────────┐
    │  GitHub       │              │  Forgejo/     │
    │  Publisher    │              │  Codeberg     │
    │               │              │  Publisher    │
    ├───────────────┤              ├───────────────┤
    │ APPROVED      │              │ APPROVED      │
    │   → "APPROVE" │              │   → "APPROVED"│
    │ CHANGES_REQ   │              │ CHANGES_REQ   │
    │   → "REQUEST_ │              │   → "REQUEST_ │
    │     CHANGES"  │              │     CHANGES"  │
    │               │              │               │
    │ COMMENTED     │              │ COMMENTED     │
    │   → "COMMENT" │              │   → "COMMENT" │
    │   (unreachable)             │   (unreachable)│
    └───────────────┘              └───────────────┘
            │                             │
            ▼                             ▼
    ┌─────────────────────────────────────────────────────────┐
    │  Blocking/Non-Blocking Split (ReviewPublisherProcessor) │
    ├─────────────────────────────────────────────────────────┤
    │  GitHub:     ALL items in formal review body            │
    │  Forgejo:    BLOCKING (CRITICAL/MAJOR) in formal review │
    │              NON-BLOCKING (MINOR/INFO) as separate PR   │
    │              comment                                    │
    └─────────────────────────────────────────────────────────┘
```

---

## 8. Configuration → Runtime Wiring

```
┌─────────────────────────────────────────────────────────────────┐
│  Config Loading (ConfigLoader)                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Precedence:  Shell env > User config (.env) > Defaults        │
│                                                                 │
│  ┌─────────────────┐       ┌─────────────────┐                 │
│  │  Config Dataclass│      │  ConfigBuilder  │                 │
│  │  (config_dc.py)  │◀──────│  (config_bldr)  │                 │
│  ├─────────────────┤       ├─────────────────┤                 │
│  │ platform_mode   │       │ • parse GitProvider│              │
│  │ clone_protocol  │       │ • normalize URL  │                │
│  │ github_* tokens │       │ • parse org      │                │
│  │ forgejo_* tokens│       │   token overrides│                │
│  │ llm_* settings  │       │ • build Config   │                │
│  │ poll_interval   │       └────────┬────────┘                 │
│  │ review_max_tries│                │                          │
│  │ use_* flags     │                ▼                          │
│  └─────────────────┘       ┌─────────────────┐                 │
│                            │  CompositionRoot│                 │
│                            │  (DI Container) │                 │
│                            ├─────────────────┤                 │
│                            │ • wires all     │                 │
│                            │   adapters to   │                 │
│                            │   ports         │                 │
│                            │ • provides      │                 │
│                            │   typed         │                 │
│                            │   Application   │                 │
│                            └─────────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Key Source Files Referenced

| Diagram Element | Source File |
|---|---|
| CLI Entry | `src/pr_auto_reviewer/cli.py` |
| CompositionRoot | `src/pr_auto_reviewer/presentation/composition_root/composition_root.py` |
| PollingDaemon | `src/pr_auto_reviewer/presentation/polling_daemon/polling_daemon.py` |
| ReviewPullRequestService | `src/pr_auto_reviewer/application/services/review_pull_request_service.py` |
| MultiPhaseReviewOrchestrator | `src/pr_auto_reviewer/application/services/multi_phase_review_orchestrator_service/` |
| AgentConversationService | `src/pr_auto_reviewer/application/services/agent_conversation_service.py` |
| PhaseAdvisorService | `src/pr_auto_reviewer/application/services/phase_advisor_service.py` |
| PhaseManagerService | `src/pr_auto_reviewer/application/services/phase_manager_service.py` |
| FindingVerifierService | `src/pr_auto_reviewer/application/services/finding_verifier_service.py` |
| TurnParserService | `src/pr_auto_reviewer/application/services/turn_parser_service.py` |
| ReviewVerdict | `src/pr_auto_reviewer/domain/value_objects/review_verdict.py` |
| CodeReview | `src/pr_auto_reviewer/domain/entities/code_review.py` |
| ReviewItem | `src/pr_auto_reviewer/domain/entities/review_item.py` |
| SubReviewGuardrails | `src/pr_auto_reviewer/domain/value_objects/sub_review_guardrails.py` |
| ForgejoReviewPublisher | `src/pr_auto_reviewer/infrastructure/forgejo/forgejo_review_publisher.py` |
| GithubReviewPublisher | `src/pr_auto_reviewer/infrastructure/github/github_review_publisher.py` |
| ReviewPublisherProcessor | `src/pr_auto_reviewer/infrastructure/review_publishers/review_publishing_service.py` |
| OllamaAdapter | `src/pr_auto_reviewer/infrastructure/llm/ollama/ollama_llm_adapter.py` |
| LocalChangesetFetcher | `src/pr_auto_reviewer/infrastructure/local_repository/local_changeset_fetcher.py` |
| ConfigLoader | `src/pr_auto_reviewer/infrastructure/config/config.py` |