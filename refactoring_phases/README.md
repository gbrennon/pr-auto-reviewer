# PR Review Agent - Implementation Plan

**A complete TDD-driven implementation guide for building a fragment-based PR review system using hexagonal architecture.**

---

## 📋 Overview

This implementation plan guides you through building a production-ready PR review agent that uses **composable prompt fragments** to generate AI-powered code reviews. The system is built with:

- **Hexagonal Architecture** (ports & adapters)
- **SOLID Principles** enforced at every layer
- **Religious TDD** (Test-Driven Development)
- **Proper test layering** (unit, integration, E2E)
- **Decoupled design** for maximum testability

---

## 🎯 What You'll Build

```
User runs:
  $ pr-review review --repo user/repo --pr 123 --language python

System does:
  1. Fetches PR from GitHub/Forgejo
  2. Detects language and selects relevant fragments
  3. Composes prompt using Jinja2 templates
  4. Sends to Ollama LLM
  5. Returns AI-generated review

Fragments are:
  - Markdown templates with best practices
  - Language-specific (python/, go/) and universal (universal/)
  - Composable and reusable
  - Easily maintainable and versionable
```

---

## 📚 Implementation Phases

### **Phase 0: Architecture Design & Project Setup**
**File**: `phase-0-architecture-design.md`

- Define hexagonal architecture layers
- Setup directory structure
- Configure pytest and Poetry
- Understand testing strategy

**Duration**: 1-2 hours  
**Exit Criteria**: Project structure created, pytest runs, domain model designed

---

### **Phase 1: Domain Layer - Entities & Ports**
**File**: `phase-1-domain-layer.md`

- Implement `PromptFragment` (value object)
- Implement `ReviewContext` (value object)
- Implement `ComposedPrompt` (value object)
- Define port interfaces (FragmentRepository, PromptRenderer, etc.)
- 100% test coverage with pure unit tests

**Duration**: 2-3 hours  
**Exit Criteria**: All domain entities tested, zero dependencies, 100% coverage

---

### **Phase 2: Infrastructure Layer - Fragment Repository**
**File**: `phase-2-infrastructure-repository.md`

- Implement `FileSystemFragmentRepository`
- Parse YAML front matter from markdown files
- Load fragments by language and ID
- **Integration tests with REAL files** (NO MOCKS)

**Duration**: 2-3 hours  
**Exit Criteria**: Repository loads real fragments, integration tests pass

---

### **Phase 3: Application Layer - Use Cases & Services**
**File**: `phase-3-application-layer.md`

- Implement `FragmentSelector` service
- Implement `PromptComposer` service
- Implement `ComposeReviewPromptUseCase`
- Unit tests with **mocked ports**

**Duration**: 3-4 hours  
**Exit Criteria**: Business logic tested, 95%+ coverage, fast tests (<1s)

---

### **Phase 4: Advanced Features - Template Engine & Token Management**
**File**: `phase-4-advanced-features.md`

- Integrate Jinja2 for advanced templates
- Implement token budget management
- Fragment prioritization within budget
- Update test fixtures with Jinja2 features

**Duration**: 2-3 hours  
**Exit Criteria**: Templates work, budget prevents overflow, tests pass

---

### **Phase 5: Presentation Layer - CLI & E2E Tests**
**File**: `phase-5-presentation-layer.md`

- Implement CLI commands (`compose`, `fragments list`)
- Configuration file support (YAML)
- **E2E tests validating complete workflows** (NO MOCKS)
- User-facing error messages

**Duration**: 3-4 hours  
**Exit Criteria**: CLI usable, E2E tests pass, workflows validated

---

### **Phase 6: LLM Integration & Production Features**
**File**: `phase-6-llm-integration.md`

- Implement `OllamaAdapter` for LLM inference
- Implement `GitHubAdapter` and `ForgejoAdapter`
- Complete `ReviewPRUseCase` (fetch → compose → generate)
- Production features (logging, error handling)
- Complete E2E test

**Duration**: 3-4 hours  
**Exit Criteria**: Full workflow works, production-ready

---

## 🚦 How to Use This Plan

### **Golden Rules**

1. **NEVER skip a phase** - Each builds on previous work
2. **Complete ALL acceptance criteria** before advancing
3. **Write tests FIRST** - No implementation before failing test
4. **Follow TDD cycle**: RED → GREEN → REFACTOR
5. **Run verification commands** at phase exit

---

### **TDD Workflow (Religious)**

```
For EVERY feature:

┌─────────────────────────────────────────┐
│ 1. RED Phase                            │
│    - Write a failing test               │
│    - Test should fail for right reason  │
│    - Run: pytest -v (verify RED)        │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│ 2. GREEN Phase                          │
│    - Write MINIMAL code to pass         │
│    - No premature optimization          │
│    - Run: pytest -v (verify GREEN)      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│ 3. REFACTOR Phase                       │
│    - Clean up code                      │
│    - Remove duplication                 │
│    - Run: pytest -v (still GREEN)       │
└──────────────┬──────────────────────────┘
               │
               └──► Repeat for next behavior
```

---

### **Testing Strategy by Layer**

#### **Domain Layer** (Pure Unit Tests)
```bash
# Location: tests/unit/domain/
# Rules:
#   ✅ NO external dependencies
#   ✅ Test all business logic
#   ✅ Run in milliseconds
#   ❌ NO mocks needed (pure functions)

pytest tests/unit/domain/ --cov=src/domain --cov-fail-under=100
```

#### **Application Layer** (Unit Tests with Mocks)
```bash
# Location: tests/unit/application/
# Rules:
#   ✅ Mock all port implementations
#   ✅ Test orchestration logic
#   ✅ Run in milliseconds
#   ❌ NO real I/O

pytest tests/unit/application/ --cov=src/application --cov-fail-under=95
```

#### **Infrastructure Layer** (Integration Tests - NO MOCKS)
```bash
# Location: tests/integration/infrastructure/
# Rules:
#   ✅ Use REAL filesystem, files, APIs
#   ✅ Test actual I/O operations
#   ❌ NO mocking filesystem or HTTP
#   ✅ Clean up test artifacts

pytest tests/integration/ -v
```

#### **Presentation Layer** (E2E Tests)
```bash
# Location: tests/e2e/
# Rules:
#   ✅ Test complete user workflows
#   ✅ Use REAL CLI invocation (subprocess)
#   ✅ Validate input → output
#   ❌ NO mocking anything

pytest tests/e2e/ -v
```

---

## 📂 Final Project Structure

```
pr-review-agent/
├── src/
│   ├── domain/                 # Pure business logic (no deps)
│   │   ├── entities.py         # PromptFragment, ReviewContext, etc.
│   │   └── ports.py            # Interfaces (Protocols)
│   │
│   ├── application/            # Use cases & services
│   │   ├── use_cases.py        # ComposeReviewPromptUseCase, ReviewPRUseCase
│   │   └── services.py         # FragmentSelector, PromptComposer
│   │
│   ├── infrastructure/         # Adapters (I/O)
│   │   ├── repositories.py     # FileSystemFragmentRepository
│   │   ├── renderers.py        # Jinja2Renderer
│   │   ├── llm.py             # OllamaAdapter
│   │   └── git_providers.py   # GitHubAdapter, ForgejoAdapter
│   │
│   └── presentation/           # User interface
│       ├── cli.py             # CLI commands
│       └── __main__.py        # Entry point
│
├── tests/
│   ├── unit/                   # Fast tests (ms)
│   │   ├── domain/
│   │   └── application/
│   │
│   ├── integration/            # Real I/O tests
│   │   └── infrastructure/
│   │
│   └── e2e/                    # Complete workflows
│       └── fixtures/
│
├── fragments/                  # Prompt templates
│   ├── python/
│   │   └── error-handling.md
│   ├── go/
│   │   └── concurrency.md
│   └── universal/
│       └── solid-principles.md
│
├── pyproject.toml             # Poetry config
└── README.md                  # This file
```

---

## 🎓 Key Architectural Decisions

### **1. Why Hexagonal Architecture?**

```
┌─────────────────────────────────────────────────────┐
│              PRESENTATION LAYER                      │
│  (CLI, API - User-facing, integration tests)        │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│           APPLICATION LAYER                          │
│  (Use Cases, Services - Business orchestration)     │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│              DOMAIN LAYER                            │
│  (Entities, Ports - Pure business logic)            │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│         INFRASTRUCTURE LAYER                         │
│  (Adapters - I/O implementations)                    │
└─────────────────────────────────────────────────────┘
```

**Benefits**:
- Business logic independent of frameworks
- Easy to swap adapters (Ollama → OpenAI, GitHub → GitLab)
- Testable at every layer
- Clear dependency direction (inward)

---

### **2. Why Fragment-Based Prompts?**

**Traditional approach** (monolithic prompt):
```python
# Hard to maintain, version, or test
prompt = """
Review this Python code for:
- Error handling
- Performance
- Security
- SOLID violations
...
(5000 lines of prompt)
"""
```

**Fragment approach** (composable):
```python
fragments = [
    load("python/error-handling.md"),   # 50 lines
    load("python/performance.md"),       # 40 lines
    load("universal/solid.md")           # 60 lines
]
prompt = compose(fragments, context)     # Composed dynamically
```

**Benefits**:
- Each fragment is independently testable
- Easy to add new languages (create go/ directory)
- Version control tracks changes per-fragment
- Fragments can be shared across projects
- Token budget management (prioritize important fragments)

---

## 🔍 Verification Checklist

Before considering the project complete, verify:

### Architecture
- [ ] Zero imports from infrastructure → domain
- [ ] Zero imports from application → infrastructure
- [ ] All dependencies point inward
- [ ] No SOLID violations

### Testing
- [ ] Unit tests run in < 1 second
- [ ] Integration tests use real I/O
- [ ] E2E tests validate user stories
- [ ] Coverage ≥ 90% overall
- [ ] Domain layer coverage = 100%

### Functionality
- [ ] Can compose prompts from fragments
- [ ] Can fetch PRs from GitHub/Forgejo
- [ ] Can generate reviews with Ollama
- [ ] CLI commands work end-to-end
- [ ] Error messages are helpful

---

## 🚀 Quick Start

```bash
# 1. Read Phase 0
cat phase-0-architecture-design.md

# 2. Setup project
mkdir pr-review-agent && cd pr-review-agent
poetry init
poetry add --group=dev pytest pytest-cov pytest-mock

# 3. Follow each phase sequentially
# Start with Phase 0, complete ALL acceptance criteria
# Only proceed when exit criteria are met

# 4. Run tests frequently
poetry run pytest -v --cov=src

# 5. Verify at each phase
poetry run pytest tests/unit/domain/ --cov=src/domain --cov-fail-under=100
```

---

## 📖 Learning Resources

### Hexagonal Architecture
- "Hexagonal Architecture" by Alistair Cockburn
- "Clean Architecture" by Robert C. Martin

### TDD
- "Test Driven Development: By Example" by Kent Beck
- "Growing Object-Oriented Software, Guided by Tests" by Freeman & Pryce

### SOLID Principles
- "Agile Software Development, Principles, Patterns, and Practices" by Robert C. Martin

---

## 🤝 Contributing to This Plan

This implementation plan is designed for a **specific architectural style**:
- Hexagonal architecture
- Religious TDD
- SOLID principles
- Proper test layering

If you find issues or improvements, ensure they align with these principles.

---

## ⚠️ Common Pitfalls to Avoid

1. **Skipping tests** → Always write test first
2. **Mocking in integration tests** → Use real I/O
3. **Wrong dependency direction** → Always point inward
4. **Bloated services** → One responsibility per service
5. **Premature optimization** → Make it work, then optimize
6. **Rushing through phases** → Complete ALL acceptance criteria

---

## 🎯 Success Metrics

You'll know you've succeeded when:

1. ✅ All 6 phases complete with passing tests
2. ✅ You can swap Ollama for OpenAI in < 10 minutes
3. ✅ You can add a new language fragment in < 5 minutes
4. ✅ Unit tests run in milliseconds
5. ✅ Another developer can understand the architecture
6. ✅ No god objects or tight coupling
7. ✅ The system works end-to-end

---

## 📝 Phase Navigation

| Phase | File | Focus | Duration |
|-------|------|-------|----------|
| 0 | `phase-0-architecture-design.md` | Setup & Architecture | 1-2h |
| 1 | `phase-1-domain-layer.md` | Domain Entities & Ports | 2-3h |
| 2 | `phase-2-infrastructure-repository.md` | Fragment Loading | 2-3h |
| 3 | `phase-3-application-layer.md` | Business Logic | 3-4h |
| 4 | `phase-4-advanced-features.md` | Templates & Budgets | 2-3h |
| 5 | `phase-5-presentation-layer.md` | CLI & E2E Tests | 3-4h |
| 6 | `phase-6-llm-integration.md` | LLM & Production | 3-4h |

**Total Estimated Time**: 15-22 hours (spread across multiple days)

---

## 🏁 Final Thoughts

This is not just an implementation plan — it's a **training program** for building production-quality software using industry best practices.

By the end, you'll have:
- A working PR review agent
- Deep understanding of hexagonal architecture
- Mastery of TDD workflow
- Experience with proper test layering
- A codebase you're proud to show

**Start with Phase 0. Read carefully. Test religiously. Build incrementally.**

Good luck! 🚀
