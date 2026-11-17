# 1. Hexagonal Layer Dependencies

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
│  │ • ForgejoPR  │ │ • OpenAI-Compat│ │ • JSONFile │ │ • FS     │  │
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
