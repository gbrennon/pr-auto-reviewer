# 7. Advanced Review Flows

### 7.1. Multi-Phase Review

```
RunMultiPhaseReviewCommand
       │
       ▼
MultiPhaseReviewOrchestrator.execute()
       │
       ├─▶ Full retry loop (max_retries times)
       │    │
       │    ├─▶ Manager briefs EVERY phase (incl. the first)
       │    └─▶ _run_phases(plan, repo_path, changed_files, model)
       │         │
       │         ├─▶ Phase 1: Bug Hunt — Diff (engineer)
       │         │    RunAgentConversationCommand → AgentConversationService
       │         │    │
       │         │    ├─▶ Tool exploration: read_file, search_codebase,
       │         │    │    list_directory, run_git
       │         │    └─▶ Advisor observes every turn (S/A/B/C/D/F)
       │         │
       │         ├─▶ Phase 2: Bug Hunt — Branch (engineer)
       │         │    (injects prior findings via __FINDINGS__)
       │         │
       │         ├─▶ Phase 3: Architecture Review (architect)
       │         │
       │         ├─▶ After each phase: advisor grades the finished output.
       │         │    On F → manager re-plans the task → restart once,
       │         │    never replaying the failed prompt.
       │         │
       │         └─▶ Aggregate: AggregateReviewFindingsCommand
       │              ├─▶ FindingAggregator → deduplicate, merge
       │              └─▶ VerifyFindingsCommand
       │                   └─▶ FindingVerifier → validate against source
       │
       └─▶ If zero findings: _run_feedback_loop() (max_feedback_rounds)
            Re-runs with feedback context from prior attempt
```

### 7.2. Agent System

The agent system provides specialized agents for different review aspects. The `MultiPhaseReviewOrchestrator` creates a `ReviewPlan` with phases, each phase specifying an agent type:

| Agent | Purpose |
|-------|---------|
| `ManagerAgent` | Plans every phase, briefs each peer with a focused task |
| `AdvisorAgent` | Grades every peer turn (S/A/B/C/D/F); hands blockers to the manager |
| `EngineerAgent` | Bugs, security, edge cases, biased tests — incl. indirect callers |
| `ArchitectAgent` | Structure, coupling, anti-patterns |
| Teacher | The coaching approach behind the above; see `docs/sub-agents/teacher.md` |

The domain agents are `AdvisorAgent`, `ArchitectAgent`, `EngineerAgent`,
and `ManagerAgent`; they are metadata attached to phases via
`ReviewPhase.role`.

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

### No silent defaults

`COMMENTED` is not a valid produced verdict: constructing a `CodeReview` with it (or with empty `reason`/`summary`/`model_used`) raises `ReviewVerdictError`. Persistence maps any legacy `commented` records to `APPROVED`/`CHANGES_REQUESTED` on load, so the comment-only publish path is unreachable with valid reviews.

### Transcripts

Every LLM exchange — peer conversations, advisor gradings, manager briefs, verifier runs — is persisted under `~/.local/state/pr-auto-reviewer/conversations/<repo>_<pr>/`.

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
