# PR Auto Reviewer — Fragment-Based Prompt Composition Refactoring Plan

**Status**: Planning  
**Branch**: `refactoring`  
**Date**: 2026-05-14  
**Total Estimated Duration**: 15–22 hours across 7 phases  

---

## Executive Summary

This plan describes adding a **fragment-based prompt composition system** to the existing `pr-auto-reviewer` codebase, replacing the current monolithic `PromptBuilder` (located at `infrastructure/llm/prompt_builder.py`). The existing codebase already implements hexagonal architecture with DDD; this refactoring extends it with a new sub-system rather than rewriting from scratch.

### Current State

- Production hexagonal architecture: `domain/`, `application/`, `infrastructure/`, `presentation/`
- `CompositionRoot` with full dependency injection
- Ports as ABCs with one adapter per port
- Ollama LLM adapter, Git platform adapters, JSON persistence
- Polling daemon + CLI runner
- **Monolithic PromptBuilder**: single Jinja2 template per language, no composability
- ~50 test files across all layers

### Target State

- **Composable fragments**: Markdown files with YAML front matter, loaded from disk
- **Fragment selection by language**: load `python/`, `go/`, `universal/` fragments
- **Priority-based ordering**: fragments sorted by `priority` field
- **Token budget management**: prevents exceeding LLM context window
- **Jinja2 rendering**: advanced templates with conditionals, loops, filters
- **CLI support**: `fragments list`, `fragments validate`, `compose` commands
- **Telemetry**: track which fragments were used per review

---

## Architecture Integration

### Where the new code lives

```
src/pr_auto_reviewer/
│
├── domain/                              # EXISTING — no changes needed
│   └── ...
│
├── domain/fragments/                    # NEW — fragment domain entities
│   ├── __init__.py
│   ├── entities.py                      # PromptFragment, ComposedPrompt
│   └── ports.py                         # FragmentRepository, PromptRenderer
│
├── application/                         # EXISTING — modified (new services)
│   ├── ...
│   └── fragments/                       # NEW — fragment services + use cases
│       ├── __init__.py
│       ├── services.py                  # FragmentSelector, PromptComposer, TokenBudgetManager
│       └── use_cases.py                 # ComposeReviewPromptUseCase
│
├── infrastructure/                      # EXISTING — modified (new adapters)
│   ├── ...
│   └── fragments/                       # NEW — fragment adapters
│       ├── __init__.py
│       ├── repositories.py              # FileSystemFragmentRepository
│       └── renderers.py                 # Jinja2Renderer
│
├── presentation/                        # EXISTING — modified (new CLI commands)
│   ├── ...
│   └── cli/                             # modified: add fragment subcommands
│
└── composition_root.py                  # MODIFIED — wire new services

fragments/                               # NEW — fragment markdown files
├── python/
│   ├── error-handling.md
│   ├── idioms.md
│   └── performance.md
├── go/
│   └── concurrency.md
└── universal/
    └── solid-principles.md

tests/
├── unit/
│   └── fragments/domain/                # NEW — unit tests (pure, fast)
│       ├── test_entities.py
│       └── test_ports.py
├── unit/
│   └── fragments/application/           # NEW — unit tests with mocked ports
│       ├── test_services.py
│       └── test_use_cases.py
├── integration/
│   └── fragments/infrastructure/        # NEW — integration tests (REAL files)
│       ├── test_filesystem_repository.py
│       └── test_jinja2_renderer.py
└── e2e/
    └── test_fragment_compose_workflow.py  # NEW — end-to-end CLI tests
```

### Dependency Rules (Hexagonal Architecture)

```
PRESENTATION ──► APPLICATION ──► DOMAIN ◄── INFRASTRUCTURE
     │               │              ▲              │
     │               │              │              │
     └───────────────┴──────────────┘              │
                                                    │
            (infrastructure DEPENDS ON domain ports) 
```

**Hard rules**:
- Domain NEVER imports from application, infrastructure, or presentation
- Application NEVER imports from infrastructure
- Infrastructure implements domain ports
- Only the CompositionRoot knows about all layers

---

## Phase 0 — Domain Entities & Ports

**Duration**: 1–2 hours  
**Prerequisites**: None  
**Focus**: Pure domain model, zero dependencies, 100% test coverage

### New Domain Entities (Value Objects)

#### `PromptFragment` (frozen dataclass)

```python
@dataclass(frozen=True)
class PromptFragment:
    id: str                       # e.g., "python-error-handling"
    content: str                  # Markdown template with Jinja2 placeholders
    language: Optional[str]       # None = universal (applies to all languages)
    priority: int                 # Higher = more important (sort descending)
    category: str                 # "error-handling", "security", "performance"
    metadata: Dict[str, Any]      # Extensible metadata from YAML front matter
```

- Equality by `id` only (custom `__eq__` / `__hash__`)
- `is_universal()` → `self.language is None`
- Validation: non-empty `id`, non-negative `priority`

#### `ComposedPrompt` (frozen dataclass)

```python
@dataclass(frozen=True)
class ComposedPrompt:
    content: str                  # Final rendered prompt, ready for LLM
    fragments_used: list[str]     # Fragment IDs for telemetry
    total_tokens: int             # Estimated token count
```

### New Domain Ports (Protocols)

#### `FragmentRepository`

```python
class FragmentRepository(Protocol):
    def find_by_language(self, language: str) -> list[PromptFragment]: ...
    def find_universal(self) -> list[PromptFragment]: ...
    def find_by_id(self, fragment_id: str) -> Optional[PromptFragment]: ...
```

#### `PromptRenderer`

```python
class PromptRenderer(Protocol):
    def render(self, template: str, variables: dict[str, str]) -> str: ...
```

### Acceptance Criteria

- [ ] `PromptFragment` implemented with validation + immutability
- [ ] `ComposedPrompt` implemented
- [ ] `FragmentRepository`, `PromptRenderer` protocols defined
- [ ] 100% test coverage on domain layer
- [ ] All tests pass in < 1 second
- [ ] Zero SOLID violations

### Verification

```bash
pytest tests/unit/fragments/domain/ --cov=pr_auto_reviewer.domain.fragments --cov-fail-under=100 -v
```

---

## Phase 1 — FileSystemFragmentRepository

**Duration**: 2–3 hours  
**Prerequisites**: Phase 0 complete  
**Focus**: Load real Markdown files with YAML front matter — NO MOCKS in tests

### Fragment File Format

```markdown
---
id: python-error-handling
language: python
priority: 80
category: error-handling
---

# Python Error Handling Review

Reviewing the following code:

```python
{{ diff }}
```

## Checks

{% if 'except:' in diff %}
⚠️ **Bare except clause detected** — specify exception types
{% endif %}

- Resource leaks (files/connections not in `with` statements)
- Swallowed exceptions (empty except blocks)
```

### Implementation: `FileSystemFragmentRepository`

- Constructor receives `base_path: Path`
- Validates the path exists at construction time
- Scans `<base_path>/<language>/*.md` for language-specific fragments
- Scans `<base_path>/universal/*.md` for universal fragments
- Parses YAML front matter via `yaml.safe_load()`
- Skips malformed files gracefully (no crashes)
- Returns fragments sorted by priority descending

### Test Fixtures (REAL files)

```
tests/fixtures/fragments/
├── python/
│   └── error-handling.md       # With valid YAML front matter
├── go/
│   └── concurrency.md
└── universal/
    └── solid-principles.md
```

### Acceptance Criteria

- [ ] `FileSystemFragmentRepository` implements `FragmentRepository` protocol
- [ ] Loads language-specific fragments correctly
- [ ] Loads universal fragments correctly
- [ ] `find_by_id()` works across all directories
- [ ] Handles malformed YAML (skips, no crash)
- [ ] Handles missing directories (returns empty list)
- [ ] Integration tests use REAL files — zero mocks
- [ ] Test artifacts cleaned up after tests

### Verification

```bash
pytest tests/integration/fragments/ -v
grep -r "mock\|Mock\|@patch" tests/integration/fragments/  # Must return nothing
```

---

## Phase 2 — Application Services & Use Cases

**Duration**: 3–4 hours  
**Prerequisites**: Phase 1 complete  
**Focus**: Business orchestration logic — MOCKED ports in tests

### `FragmentSelector`

```python
class FragmentSelector:
    def __init__(self, repository: FragmentRepository, max_tokens: Optional[int] = None):
        ...
    
    def select_for(self, context: ReviewContext) -> list[PromptFragment]:
        """Select and sort fragments based on review context."""
```

**Selection strategy**:
1. Load language-specific fragments via `repository.find_by_language()`
2. Load universal fragments via `repository.find_universal()`
3. Combine, sort by priority descending
4. If `max_tokens` is set, apply greedy budget constraint

### `PromptComposer`

```python
class PromptComposer:
    def __init__(self, renderer: Optional[PromptRenderer] = None, separator: str = "\n\n---\n\n"):
        ...
    
    def compose(self, fragments: list[PromptFragment], context: ReviewContext) -> ComposedPrompt:
        """Render all fragments and join into final prompt."""
```

- Renders each fragment with variables from context (`{{ diff }}`, `{{ language }}`)
- Falls back to simple string substitution if no renderer provided
- Joins fragments with markdown separator
- Estimates tokens (4 chars ≈ 1 token)
- Returns `ComposedPrompt`

### `ComposeReviewPromptUseCase`

```python
class ComposeReviewPromptUseCase:
    def __init__(self, selector: FragmentSelector, composer: PromptComposer): ...
    
    def execute(self, context: ReviewContext) -> ComposedPrompt:
        """Orchestrate: select → compose → return."""
```

### Acceptance Criteria

- [ ] `FragmentSelector` selects language + universal, sorts by priority
- [ ] `PromptComposer` renders templates and returns `ComposedPrompt`
- [ ] `ComposeReviewPromptUseCase` orchestrates selection + composition
- [ ] Variable substitution works (`{{ diff }}`, `{{ language }}`, `{{ file_paths }}`)
- [ ] Errors raised for empty fragment lists
- [ ] All application tests use mocked ports (fast, no I/O)
- [ ] Coverage ≥ 95%

### Verification

```bash
pytest tests/unit/fragments/application/ --cov=pr_auto_reviewer.application.fragments --cov-fail-under=95 -v
```

---

## Phase 3 — Jinja2 Renderer + Token Budget

**Duration**: 2–3 hours  
**Prerequisites**: Phase 2 complete  
**Focus**: Advanced template rendering and context window management

### `Jinja2Renderer`

```python
class Jinja2Renderer:
    def render(self, template: str, variables: dict[str, Any]) -> str:
        """Render with full Jinja2 support."""
```

- Uses `jinja2.Environment` with `BaseLoader` (template strings, not files)
- Supports: variables `{{ var }}`, conditionals `{% if %}`, loops `{% for %}`, filters `{{ var|upper }}`
- Handles missing variables with `default('N/A')` filter
- Wraps `jinja2.TemplateError` in `ValueError`

### `TokenBudgetManager`

```python
class TokenBudgetManager:
    def __init__(self, max_tokens: int): ...
    def estimate_tokens(self, text: str) -> int: ...
    def fits_budget(self, text: str) -> bool: ...
    def consume(self, text: str) -> int: ...
    def remaining(self) -> int: ...
    def reset(self) -> None: ...
```

- Rough heuristic: 1 token ≈ 4 characters (can upgrade to tiktoken later)
- Tracks cumulative token consumption
- Greedy allocation: highest priority fragments first

### Integration with `FragmentSelector`

When `max_tokens` is provided:
```python
def _apply_budget_constraints(self, fragments: list[PromptFragment]) -> list[PromptFragment]:
    selected = []
    self._budget_manager.reset()
    for fragment in fragments:
        if self._budget_manager.fits_budget(fragment.content):
            self._budget_manager.consume(fragment.content)
            selected.append(fragment)
    return selected
```

### Acceptance Criteria

- [ ] `Jinja2Renderer` implements `PromptRenderer` protocol
- [ ] Supports conditionals, loops, and filters
- [ ] `TokenBudgetManager` prevents exceeding budget
- [ ] High-priority fragments selected first when budget is limited
- [ ] Backward compatible — `PromptComposer` works with and without renderer

---

## Phase 4 — Integrate into Existing System

**Duration**: 3–4 hours  
**Prerequisites**: Phases 0–3 complete  
**Focus**: Wire fragment system into existing review pipeline

### Key Integration Points

#### 1. Modify `OllamaLlmAdapter` (infrastructure/llm/ollama_llm_adapter.py)

**Current flow**:
```python
def review(self, diff: PullRequestDiff, context: ReviewContext) -> CodeReview:
    prompt = PromptBuilder().build(diff, context)  # Monolithic
    raw = self._call_ollama(prompt)
    return ReviewResponseParser.parse(raw)
```

**New flow** (coexistence strategy):
```python
def review(self, diff: PullRequestDiff, context: ReviewContext) -> CodeReview:
    if self._fragment_composer:
        # NEW: fragment-based composition
        prompt = self._compose_from_fragments(diff, context)
    else:
        # EXISTING: monolithic fallback
        prompt = self._prompt_builder.build(diff, context)
    raw = self._call_ollama(prompt)
    return ReviewResponseParser.parse(raw)
```

#### 2. Update `ReviewPullRequestService` (application/services/review_pull_request_service.py)

No structural changes needed — the service already calls `LlmReviewPort.review()`. 
The fragment system is encapsulated behind the port.

#### 3. Update `CompositionRoot` (presentation/composition_root.py)

```python
def _wire_components(self) -> ApplicationComponents:
    c = self._container
    
    # NEW: Fragment sub-system
    fragment_repo = FileSystemFragmentRepository(
        base_path=Path(c.config.fragments_dir or "fragments")
    )
    fragment_renderer = Jinja2Renderer()
    fragment_selector = FragmentSelector(repository=fragment_repo, max_tokens=4000)
    fragment_composer = PromptComposer(renderer=fragment_renderer)
    
    # Modified: inject fragment composer into LLM adapter
    llm_adapter = OllamaLlmAdapter(
        host=c.config.ollama_host,
        model=c.config.ollama_model,
        fragment_composer=fragment_composer,  # NEW
    )
    
    # Existing wiring continues unchanged...
    review_service = ReviewPullRequestService(
        pr_repository=c.pr_repository,
        changeset_fetcher=c.changeset_fetcher,
        repository_context=c.repository_context,
        llm_review=llm_adapter,
        review_publisher=c.review_publisher,
    )
```

#### 4. Add fragment CLI commands

```bash
# List fragments
pr-auto-reviewer fragments list --language python

# Validate all fragment files
pr-auto-reviewer fragments validate

# Compose a prompt without sending to LLM (debugging)
pr-auto-reviewer compose --language python --diff-file changes.diff
```

### Acceptance Criteria

- [ ] Fragment system coexists with existing `PromptBuilder`
- [ ] Feature flag controls which system is used (env var or config)
- [ ] All existing tests continue to pass
- [ ] E2E test validates fragment-based review workflow
- [ ] CompositionRoot correctly wires fragment dependencies

---

## Phase 5 — Create Fragment Library

**Duration**: 2–3 hours  
**Prerequisites**: Phase 4 complete  
**Focus**: Populate the `fragments/` directory with real review fragments

### Fragment Categories

| Language | Fragment | Priority | Category |
|----------|----------|----------|----------|
| python | error-handling | 80 | best-practices |
| python | type-hints | 70 | best-practices |
| python | async-await | 60 | concurrency |
| python | resource-management | 75 | security |
| python | input-validation | 90 | security |
| go | concurrency | 85 | concurrency |
| go | error-wrapping | 80 | best-practices |
| go | context-usage | 75 | best-practices |
| universal | solid-principles | 100 | architecture |
| universal | naming-conventions | 50 | style |
| universal | test-coverage | 70 | quality |
| universal | documentation | 40 | quality |

### Fragment Template Example

```markdown
---
id: python-error-handling
language: python
priority: 80
category: error-handling
---

# Error Handling Review (Python)

Review the following diff for proper error handling patterns:

```python
{{ diff }}
```

## Checks

{% if 'except:' in diff %}
⚠️ **CRITICAL**: Bare `except:` clause detected. Specify exception types.
{% endif %}

{% for file in file_paths %}
- File: `{{ file }}`
{% endfor %}

### Common Issues

1. **Bare except clauses**: Always specify exception types
2. **Missing exception chaining**: Use `raise ... from exc`
3. **Swallowed exceptions**: Empty except blocks hide bugs
4. **Resource leaks**: Files/connections must use context managers (`with`)

### Good Pattern

```python
try:
    with open(path) as f:
        data = json.load(f)
except FileNotFoundError as e:
    raise ConfigError(f"Missing: {path}") from e
```

### Bad Pattern

```python
try:
    f = open(path)
    data = json.load(f)
except:
    pass
```
```

---

## Phase 6 — Cleanup & Remove Monolithic PromptBuilder

**Duration**: 1–2 hours  
**Prerequisites**: Phase 5 complete, fragment system validated in production  
**Focus**: Remove old code, run full test suite

### Steps

1. Mark `PromptBuilder` as deprecated with `warnings.warn()`
2. Migrate all existing Jinja2 templates into fragment format
3. Remove fallback code from `OllamaLlmAdapter`
4. Remove feature flag — fragment system is always on
5. Delete `infrastructure/llm/prompt_builder.py` and its tests
6. Run full test suite:
   ```bash
   pytest -v --cov=pr_auto_reviewer --cov-report=term-missing
   ```
7. Update `pyproject.toml` — ensure `pyyaml` is in dependencies (it already is)

### Acceptance Criteria

- [ ] Zero references to `PromptBuilder` in codebase
- [ ] All templates migrated to fragment format
- [ ] Full test suite passes
- [ ] Coverage ≥ 90% overall
- [ ] E2E tests pass with real fragments

---

## Testing Strategy Summary

| Layer | Test Type | Mocks? | I/O? | Speed | Coverage Target |
|-------|-----------|--------|------|-------|----------------|
| Domain | Unit | None | None | <1s | 100% |
| Application | Unit | Ports mocked | None | <1s | ≥95% |
| Infrastructure | Integration | **None** | Real files | <5s | ≥90% |
| Presentation | E2E | **None** | Real CLI + files | <30s | Workflow coverage |

### Key Testing Rules

1. **Domain tests**: Pure functions, zero dependencies, run in milliseconds
2. **Application tests**: Mock all ports via `Mock(spec=Protocol)`, no I/O
3. **Integration tests**: Real filesystem, real YAML, real Jinja2 — NEVER mock I/O
4. **E2E tests**: Real CLI invocation via `subprocess`, validate input → output

---

## Risk Analysis

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fragment system generates worse reviews | High | Coexistence strategy — validate before cutting over |
| Token budget miscalculation | Medium | Rough heuristic is tunable; can add tiktoken later |
| YAML parsing errors on edge cases | Low | Graceful skip of malformed files; extensive test cases |
| Python 3.14 compatibility | Low | All features (Protocol, frozen dataclass) work on 3.11+ |
| Breaking existing tests | Medium | New code in separate dirs; existing tests run before merge |
| File system path issues in CI | Low | Use `Path(__file__).parent` for relative paths |

---

## Key Design Decisions

1. **Why `Protocol` instead of `ABC`?** — Protocols enable structural subtyping. Any object with the right methods satisfies the interface without explicit inheritance. This reduces coupling.

2. **Why fragments and not a single template?** — Fragments are independently maintainable, versionable, and testable. Adding a new language means adding a directory. Fragment priority allows smart selection when token budget is limited.

3. **Why YAML front matter in Markdown files?** — Single file per fragment stores both metadata and content. Human-readable. Easy to edit. Standard format (Jekyll, Hugo, etc use the same convention).

4. **Why integrate into existing codebase instead of a separate project?** — The fragment system is a better prompt builder, not a different product. Integrating into the existing hexagonal architecture means we reuse the LLM adapter, PR fetching, and composition root.

5. **Why coexistence before replacement?** — Avoids a flag-day deployment. The fragment system can be tested side-by-side with the monolithic approach before cutting over.

---

## Quick Reference: Key Commands

```bash
# Run all tests
pytest -v

# Domain layer only (must be 100%)
pytest tests/unit/fragments/domain/ --cov=pr_auto_reviewer.domain.fragments --cov-fail-under=100

# Application layer only (must be ≥95%)
pytest tests/unit/fragments/application/ --cov=pr_auto_reviewer.application.fragments --cov-fail-under=95

# Integration tests (real files, no mocks)
pytest tests/integration/fragments/ -v

# Verify NO mocks in integration tests
grep -r "mock\|Mock\|@patch" tests/integration/fragments/ && echo "FAIL" || echo "PASS"

# Verify dependency direction (application never imports infrastructure)
grep -r "from pr_auto_reviewer.infrastructure" src/pr_auto_reviewer/application/fragments/ && echo "FAIL" || echo "PASS"

# E2E tests (real CLI)
pytest tests/e2e/ -v -s

# Full coverage report
pytest --cov=pr_auto_reviewer --cov-report=html --cov-report=term-missing
```

---

## Phase Dependency Graph

```
Phase 0 (Domain)
    │
    ▼
Phase 1 (Repository)
    │
    ▼
Phase 2 (Services + Use Cases)
    │
    ▼
Phase 3 (Jinja2 + Budget)
    │
    ▼
Phase 4 (Integration)
    │
    ▼
Phase 5 (Fragment Library)
    │
    ▼
Phase 6 (Cleanup)
```

**No phase can start until the previous phase passes ALL acceptance criteria.**

---

## References

- Detailed TDD instructions per phase: `refactoring_phases/phase-*.md`
- Existing architecture docs: `domain-model.md`, `application-layer.md`, `infrastructure-layer.md`, `presentation-layer.md`
- Original refactoring plan: `refactoring-core.md` (the core/ → domain/ split that is already done)
- Existing codebase: `src/pr_auto_reviewer/`
- Existing tests: `tests/pr_auto_reviewer/`

