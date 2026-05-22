# Phase 0: Architecture Design & Project Setup

**Goal**: Establish the hexagonal architecture foundation for fragment-based prompt composition.

**Duration Estimate**: 1-2 hours

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│  (CLI / API / Integration Tests - User Flow Validation)     │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    APPLICATION LAYER                         │
│   Use Cases:                                                 │
│   - ComposeReviewPromptUseCase                              │
│   - SelectFragmentsUseCase                                  │
│                                                              │
│   Services:                                                  │
│   - FragmentSelector                                        │
│   - PromptComposer                                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      DOMAIN LAYER                            │
│   Entities & Value Objects:                                 │
│   - PromptFragment (immutable)                              │
│   - ReviewContext                                           │
│   - ComposedPrompt                                          │
│                                                              │
│   Ports (Interfaces):                                       │
│   - FragmentRepository                                      │
│   - PromptRenderer                                          │
│   - LanguageDetector                                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   INFRASTRUCTURE LAYER                       │
│   Adapters (Integration Tests - No Mocks):                  │
│   - FileSystemFragmentRepository                            │
│   - MarkdownRenderer                                        │
│   - GitHubPRAdapter                                         │
│   - OllamaLLMAdapter                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
pr-review-agent/
├── src/
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── entities.py           # PromptFragment, ReviewContext
│   │   └── ports.py              # Repository interfaces
│   │
│   ├── application/
│   │   ├── __init__.py
│   │   ├── use_cases.py          # ComposeReviewPromptUseCase
│   │   └── services.py           # FragmentSelector, PromptComposer
│   │
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── repositories.py       # FileSystemFragmentRepository
│   │   └── renderers.py          # MarkdownRenderer
│   │
│   └── presentation/
│       ├── __init__.py
│       └── cli.py                # CLI interface
│
├── tests/
│   ├── unit/                     # Domain & Application (mocks allowed)
│   │   ├── domain/
│   │   │   └── test_entities.py
│   │   └── application/
│   │       ├── test_use_cases.py
│   │       └── test_services.py
│   │
│   ├── integration/              # Infrastructure (NO MOCKS)
│   │   └── infrastructure/
│   │       ├── test_filesystem_repository.py
│   │       └── test_markdown_renderer.py
│   │
│   └── e2e/                      # Presentation (User flows)
│       └── test_compose_workflow.py
│
├── fragments/                    # Fragment storage
│   ├── python/
│   │   └── error-handling.md
│   ├── go/
│   │   └── concurrency.md
│   └── universal/
│       └── solid-principles.md
│
├── pyproject.toml               # Poetry dependencies
└── README.md
```

---

## Core Domain Concepts

### 1. PromptFragment (Value Object)
**Immutable** representation of a reusable prompt piece.

```python
@dataclass(frozen=True)
class PromptFragment:
    id: str                      # e.g., "python-error-handling"
    content: str                 # Markdown template
    language: Optional[str]      # None = universal
    priority: int                # For selection ordering
    category: str                # "idioms", "security", "performance"
    metadata: Dict[str, Any]     # Extensible metadata
```

### 2. ReviewContext (Value Object)
Context about the PR being reviewed.

```python
@dataclass(frozen=True)
class ReviewContext:
    language: str                # Detected language
    file_paths: List[str]
    diff: str
    repository_context: Optional[str]
```

### 3. ComposedPrompt (Value Object)
Final assembled prompt ready for LLM.

```python
@dataclass(frozen=True)
class ComposedPrompt:
    content: str                 # Final rendered markdown
    fragments_used: List[str]    # Fragment IDs for telemetry
    total_tokens: int            # Estimated token count
```

---

## Testing Strategy

### Layer-by-Layer Testing Rules

#### ✅ **Domain Layer** (Pure Unit Tests)
- **MUST**: Test all business logic in isolation
- **MUST**: Use NO external dependencies
- **MUST**: Run in milliseconds
- Test value object immutability, validation, equality

#### ✅ **Application Layer** (Unit Tests with Mocks)
- **MUST**: Mock all port (interface) implementations
- **MUST**: Test use case orchestration logic
- **MUST**: Verify correct port method calls
- Test fragment selection logic, composition logic

#### ✅ **Infrastructure Layer** (Integration Tests - NO MOCKS)
- **MUST**: Test against REAL filesystem
- **MUST**: Test against REAL file formats (markdown, YAML)
- **MUST NOT**: Mock filesystem operations
- **MUST**: Clean up test artifacts in fixtures
- Validate actual file I/O, parsing, rendering

#### ✅ **Presentation Layer** (E2E Tests)
- **MUST**: Test complete user workflows
- **MUST**: Validate CLI arguments → output
- **MUST**: Test error messages and exit codes
- Test: "User runs command → sees expected output"

---

## Technology Stack

### Core
- **Python 3.14+**: Strict built-in type hints(dict, list and None intead of Dict, List and Optional), dataclasses, Protocol
- **UV**: Dependency management

### Testing
- **pytest**: Test runner
- **pytest-cov**: Coverage reports
- **pytest-mock**: For application layer mocks ONLY

### Infrastructure
- **PyYAML**: YAML parsing (Phase 2+)
- **Jinja2**: Template rendering (Phase 2+)

---

## TDD Workflow

**RELIGIOUS TDD MEANS:**

```
┌──────────────────────────────────────┐
│  1. Write failing test (RED)         │
│     - Test ONE behavior               │
│     - Test should fail for right reason│
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  2. Write minimal code (GREEN)       │
│     - ONLY enough to pass test       │
│     - No premature optimization      │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  3. Refactor (REFACTOR)              │
│     - Clean up duplication           │
│     - Tests MUST still pass          │
└──────────────┬───────────────────────┘
               │
               └──────► Repeat for next behavior
```

**NEVER WRITE IMPLEMENTATION BEFORE TEST!**

---

## Acceptance Criteria (Phase 0)

### ✅ AC-0.1: Project Structure Created
- [ ] All directories exist as shown above
- [ ] `pyproject.toml` configured with dependencies
- [ ] `pytest` runs (even with 0 tests)
- [ ] Git repository initialized with `.gitignore`

### ✅ AC-0.2: Can Run Tests by Layer
```bash
# These commands work:
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/
pytest --cov=src tests/
```

### ✅ AC-0.3: Domain Model Designed
- [ ] `domain/entities.py` has type-hinted dataclasses
- [ ] `domain/ports.py` has Protocol definitions
- [ ] Domain layer has ZERO imports from other layers

### ✅ AC-0.4: First Test Written and Passing
- [ ] `tests/unit/domain/test_entities.py` exists
- [ ] Contains at least 1 test for `PromptFragment` creation
- [ ] Test passes: `pytest tests/unit/domain/test_entities.py -v`

---

## Phase 0 Exit Criteria

**YOU CAN ONLY PROCEED TO PHASE 1 IF:**

1. ✅ All AC-0.x criteria are met
2. ✅ `pytest` runs successfully across all test directories
3. ✅ Domain entities are implemented and tested
4. ✅ Zero SOLID violations in domain layer
5. ✅ Test coverage for domain layer is 100%

Run this command to verify:
```bash
pytest tests/unit/domain/ --cov=src/domain --cov-report=term-missing --cov-fail-under=100
```

---

## Setup Instructions

### 1. Initialize Project
```bash
mkdir -p pr-review-agent/{src,tests,fragments}
cd pr-review-agent

# Initialize Poetry
poetry init --name=pr-review-agent --python="^3.11"
poetry add --group=dev pytest pytest-cov pytest-mock

# Create __init__.py files
touch src/{__init__,domain/__init__,application/__init__,infrastructure/__init__,presentation/__init__}.py
touch tests/{__init__,unit/__init__,integration/__init__,e2e/__init__}.py

# Initialize git
git init
echo "__pycache__/
*.pyc
.pytest_cache/
.coverage
htmlcov/
dist/
*.egg-info/" > .gitignore
```

### 2. Configure pytest
Create `pyproject.toml` section:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --strict-markers --cov=src --cov-report=term-missing"

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

### 3. Verify Setup
```bash
poetry install
poetry run pytest --collect-only  # Should show 0 tests collected
```

---

## Next Phase Preview

**Phase 1** will implement:
- Fragment repository (infrastructure)
- Basic file loading
- Integration tests for filesystem access

**DO NOT START PHASE 1 UNTIL ALL PHASE 0 CRITERIA ARE MET.**
