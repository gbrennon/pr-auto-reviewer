# 5. Adapter Communication Diagrams

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
