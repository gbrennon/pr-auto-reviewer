# 7. Verdict → Platform Event Mapping

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
| OpenAICompatibleAdapter | `src/pr_auto_reviewer/infrastructure/llm/openai_compatible_chat_client.py` |
| LocalChangesetFetcher | `src/pr_auto_reviewer/infrastructure/local_repository/local_changeset_fetcher.py` |
| ConfigLoader | `src/pr_auto_reviewer/infrastructure/config/config.py` |
