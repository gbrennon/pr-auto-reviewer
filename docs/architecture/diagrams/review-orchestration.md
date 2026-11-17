# 3. Multi-Phase Review Orchestration Flow

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
    │ (OpenAI-compatible)   │  │            │  │ list_dir   │
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
