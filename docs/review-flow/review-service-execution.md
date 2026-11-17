# 4.3. Use Case: ReviewPullRequestService.execute()

### 4.3. Use Case: ReviewPullRequestService.execute()

```
┌─────────────────────────────────────────────────────────────────┐
│ ReviewPullRequestService.execute(command)                       │
│                                                                 │
│ 4.3.1 LOAD OR CREATE PR                                         │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ pr_repository.find(pr_id)                                │   │
│ │ JsonFilePullRequestRepository.find()                     │   │
│ │   Read ~/.local/state/pr-auto-reviewer/state.json        │   │
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
│ │   Cached in ~/.cache/pr-auto-reviewer/verified-tokens.json │   │
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
│ │  │     verdict=APPROVED|CHANGES_REQUESTED,  # COMMENTED now raises  │   │   │
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
│ │   Atomic save ~/.local/state/pr-auto-reviewer/state.json │   │
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
