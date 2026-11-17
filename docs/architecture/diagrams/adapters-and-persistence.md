# 5. Adapter Communication Sequences

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

### 5.2 OpenAI-Compatible LLM Adapter

```
AgentConversationService
    │
    ▼
LlmAgentAdapter
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
OpenAiCompatibleChatClient (handles tool loop)
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
