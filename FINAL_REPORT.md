# Final Report — Fragment-Based Prompt Composition Refactoring

**Date**: 2026-05-14  
**Branch**: `refactoring`  
**Total Duration**: ~2.5 hours (target: 15–22h)

---

## 1. Executive Summary

This refactoring added a **fragment-based prompt composition system** to the `pr-auto-reviewer` codebase. The existing monolithic `PromptBuilder` (a single Jinja2 template per language) was supplemented with a composable, priority-based, token-budgeted fragment pipeline. The two systems coexist — the fragment system is opt-in via constructor parameters on `OllamaLlmAdapter`, while the legacy `PromptBuilder` remains the default.

### What was built

| Component | Count |
|-----------|-------|
| Domain entities | 5 (`PromptFragment`, `ComposedPrompt`, `ReviewContext`, 2 Protocols) |
| Application services | 3 (`FragmentSelector`, `PromptComposer`, `TokenBudgetManager`) |
| Application use cases | 1 (`ComposeReviewPromptUseCase`) |
| Infrastructure adapters | 2 (`FileSystemFragmentRepository`, `Jinja2Renderer`) |
| Integration point | 1 (`OllamaLlmAdapter` modified for coexistence) |
| Composition wiring | 1 (`CompositionRoot._wire_fragment_system`) |
| Production fragments | 12 (5 Python, 3 Go, 4 universal) |
| Tests | 83 (66 unit + 17 integration) |
| Report files | 8 |

---

## 2. Architecture

### 2.1 Fragment Pipeline Flow

```
PullRequestDiff ──► _detect_language() ──► ReviewContext
                                                │
                              FragmentRepository │ (load from disk)
                                                │
                          ┌─────────────────────▼──────────────────────┐
                          │  FragmentSelector.select_for()              │
                          │  1. Load language-specific fragments        │
                          │  2. Load universal fragments                │
                          │  3. Sort by priority descending             │
                          │  4. Apply greedy token budget filter        │
                          └─────────────────────┬──────────────────────┘
                                                │ list[PromptFragment]
                          ┌─────────────────────▼──────────────────────┐
                          │  PromptComposer.compose()                   │
                          │  1. Render each fragment via Jinja2Renderer │
                          │  2. Join with markdown separator            │
                          │  3. Estimate token count                    │
                          └─────────────────────┬──────────────────────┘
                                                │
                                          ComposedPrompt
                                          ┌───────┴───────┐
                                          │ content: str    │──► Ollama API
                                          │ fragments_used  │──► logs/telemetry
                                          │ total_tokens    │
                                          └─────────────────┘
```

### 2.2 File Tree (new/modified files only)

```
pr-auto-reviewer/
├── fragments/                              ← 12 production fragment files
│   ├── python/ (5 files)
│   ├── go/ (3 files)
│   └── universal/ (4 files)
│
├── src/pr_auto_reviewer/
│   ├── domain/fragments/
│   │   ├── entities/{prompt_fragment,composed_prompt,review_context}.py
│   │   └── ports/{fragment_repository,prompt_renderer}.py
│   ├── application/fragments/
│   │   ├── fragment_selector.py
│   │   ├── prompt_composer.py
│   │   ├── token_budget_manager.py
│   │   └── compose_review_prompt_use_case.py
│   ├── infrastructure/
│   │   ├── fragments/{repositories,renderers}.py
│   │   └── llm/ollama_llm_adapter.py  ← MODIFIED
│   └── presentation/composition_root.py ← MODIFIED
│
├── tests/
│   ├── unit/fragments/domain/            ← 6 test files
│   ├── unit/fragments/application/       ← 4 test files
│   ├── unit/fragments/infrastructure/    ← 1 test file
│   ├── integration/fragments/            ← 1 test file
│   └── fixtures/fragments/              ← 3 fixture files
│
├── REFACTORING_PLAN.md
├── PHASE_0_REPORT.md through PHASE_6_REPORT.md
└── FINAL_REPORT.md                       ← this file
```

### 2.3 Dependency Rules (Enforced)

```
✅ Domain NEVER imports from application, infrastructure, or presentation


## 3. Key Design Decisions

### 3.1 Fragment-Based vs Monolithic

**Before**: A single Jinja2 template per language, hardcoded in `infrastructure/llm/templates/review_prompt.j2`.

**After**: 12 composable Markdown fragments with YAML front matter. Each fragment is independently versionable, testable, and reusable. Adding a new language requires only creating a directory with `.md` files.

### 3.2 Coexistence Strategy

The legacy `PromptBuilder` is **NOT removed** — it is marked as deprecated and kept as a fallback. The `OllamaLlmAdapter` checks for fragment components:

```python
if self._fragment_selector and self._fragment_composer:
    prompt = self._build_fragment_prompt(diff)    # NEW
else:
    prompt = self._prompt_builder.build(diff, ctx)  # LEGACY
```

When fragments are enabled but no matching fragments exist, the adapter falls back to legacy with a warning log.

### 3.3 Protocols vs ABCs

Ports use `typing.Protocol` instead of `abc.ABC`. This enables structural subtyping — any object with the right methods satisfies the interface without explicit inheritance.

### 3.4 Token Budget — Greedy Priority

When `max_tokens` is configured, `FragmentSelector` uses a greedy algorithm:
1. Sort fragments by priority descending
2. Include each fragment if it fits within remaining budget
3. Skip fragments that would exceed the limit

### 3.5 YAML Front Matter Convention

Each fragment is a single `.md` file with YAML front matter (Jekyll/Hugo convention):

```markdown
---
id: python-error-handling
language: python
priority: 80
category: error-handling
---

# Fragment Content Here
```

✅ Application NEVER imports from infrastructure


## 4. Test Results

```
╔══════════════════════════════════════════════╗
║ Layer            Type         Tests   Time   ║
╠══════════════════════════════════════════════╣
║ Domain           Unit          35    0.04s   ║
║ Application      Unit          23    0.03s   ║
║ Infrastructure   Unit           8    0.02s   ║
║ Infrastructure   Integration   17    0.05s   ║
║ Existing         Varied       720    9.54s   ║
╠══════════════════════════════════════════════╣
║ TOTAL                         803    9.68s   ║
╚══════════════════════════════════════════════╝
```

1 pre-existing failure (unrelated): `test_build_ends_with_diff_fence`

### Testing Rules Enforced

- Domain tests: **zero mocks**, pure functions, run in <0.05s
- Application tests: ports mocked with `Mock(spec=Protocol)` — fast, no I/O
- Integration tests: **zero mocks**, real filesystem, real YAML, real Jinja2
- E2E: deferred for future work (requires running Ollama instance)

✅ Infrastructure implements domain Protocols
✅ Only CompositionRoot knows about all layers
```


## 5. Pros and Cons

### Pros

| Area | Benefit |
|------|---------|
| **Maintainability** | Each fragment is a standalone file — edit one without touching others |
| **Extensibility** | Add a language by creating a directory with `.md` files |
| **Testability** | Every fragment can be tested independently |
| **Token budget** | Prevents LLM context overflow with greedy priority-based filtering |
| **Telemetry** | `ComposedPrompt.fragments_used` tracks which fragments were included |
| **Version control** | Git diffs on individual fragments are readable and meaningful |
| **No breaking changes** | Coexistence strategy — production cutover is a config change |
| **SOLID compliance** | Hexagonal architecture maintained at every layer |
| **Fast tests** | 83 fragment tests run in <0.2s total |
| **Lazy auto-wiring** | `CompositionRoot._wire_fragment_system()` auto-detects `fragments/` dir |

### Cons

| Concern | Mitigation |
|---------|------------|
| More files (12 fragments vs 1 template) | Accepted trade-off — fragments scale linearly |
| Language detection is simple (file extensions) | Can upgrade to `LanguageDetector` port |
| Token estimation is approximate (4 chars ≈ 1 token) | Can upgrade to `tiktoken` without interface change |
| No E2E tests with real Ollama | Deferred; integration tests cover the composition pipeline |
| Coexistence adds complexity to `OllamaLlmAdapter` | Temporary — `PromptBuilder` will be removed after validation |
| `CompositionRoot` uses lazy imports | Accepted — it's the only module allowed to import across layers |

---

## 6. Migration Path

### Current (coexistence)
```
Default:  PromptBuilder (legacy, deprecated)
Opt-in:   FragmentSelector + PromptComposer (when fragments/ dir exists)
```

### Step 1 — Validate (ready now)
Run with `fragments/` directory present. `CompositionRoot` auto-detects and wires.

### Step 2 — Cut over (future)
```python
llm = OllamaLlmAdapter(host=..., model=...,
    fragment_selector=selector, fragment_composer=composer)
```

### Step 3 — Remove legacy (future)
Delete `infrastructure/llm/prompt_builder.py` and its templates. Remove fallback.

---

## 7. Files Summary

| Category | Files | Lines |
|----------|-------|-------|
| Domain entities | 3 | 75 |
| Domain ports | 2 | 20 |
| Application services | 3 | 205 |
| Application use case | 1 | 34 |
| Infrastructure adapters | 2 | 140 |
| Modified files | 2 | +120 |
| Fragment .md files | 12 | ~400 |
| Test files | 12 | ~900 |
| Report files | 8 | ~1200 |
| **TOTAL** | **45** | **~3100** |
