# Phase 1: Domain Layer - Entities & Ports

**Prerequisites**: Phase 0 complete and all AC-0.x passing

**Goal**: Implement the core domain model with 100% test coverage using strict TDD.

**Duration Estimate**: 2-3 hours

---

## Overview

This phase builds the **heart of the application** - the domain layer that contains:
- Business entities (value objects)
- Port interfaces (contracts for infrastructure)
- Zero dependencies on frameworks or external libraries

**CRITICAL**: Write tests FIRST, then implementation. No exceptions.

---

## TDD Cycle for This Phase

```
For each entity/port:
  1. RED:   Write test that fails
  2. GREEN: Write minimal code to pass
  3. BLUE:  Run test → verify pass
  4. REFACTOR: Clean up
  5. BLUE:  Run test again → verify still pass
```

---

## Part 1: PromptFragment Entity

### TDD Iteration 1.1: Basic Construction

#### Step 1: Write Failing Test (RED)

Create `tests/unit/domain/test_entities.py`:

```python
import pytest
from src.domain.entities import PromptFragment


class TestPromptFragment:
    def test_creates_fragment_with_required_fields(self):
        """PromptFragment should be constructible with required fields."""
        fragment = PromptFragment(
            id="python-error-handling",
            content="# Error Handling\n\nCheck for exceptions.",
            language="python",
            priority=80,
            category="error-handling"
        )
        
        assert fragment.id == "python-error-handling"
        assert fragment.content == "# Error Handling\n\nCheck for exceptions."
        assert fragment.language == "python"
        assert fragment.priority == 80
        assert fragment.category == "error-handling"
```

**Run test (should FAIL):**
```bash
poetry run pytest tests/unit/domain/test_entities.py::TestPromptFragment::test_creates_fragment_with_required_fields -v
```

Expected: `ModuleNotFoundError: No module named 'src.domain.entities'`

---

#### Step 2: Write Minimal Code (GREEN)

Create `src/domain/entities.py`:

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class PromptFragment:
    """Immutable value object representing a prompt template fragment.
    
    A fragment is a reusable piece of a prompt that can be composed with
    other fragments to build a complete review prompt.
    """
    id: str
    content: str
    language: Optional[str]
    priority: int
    category: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            # Bypass frozen constraint using object.__setattr__
            object.__setattr__(self, 'metadata', {})
```

**Run test (should PASS):**
```bash
poetry run pytest tests/unit/domain/test_entities.py::TestPromptFragment::test_creates_fragment_with_required_fields -v
```

---

### TDD Iteration 1.2: Immutability

#### Step 1: Write Failing Test (RED)

Add to `test_entities.py`:

```python
def test_fragment_is_immutable(self):
    """PromptFragment should be immutable (frozen dataclass)."""
    fragment = PromptFragment(
        id="test-id",
        content="test content",
        language="python",
        priority=50,
        category="test"
    )
    
    with pytest.raises(AttributeError):
        fragment.id = "new-id"  # Should raise FrozenInstanceError
```

**Run test (should PASS immediately)** - because we used `frozen=True`

---

### TDD Iteration 1.3: Universal Fragment (No Language)

#### Step 1: Write Test (RED)

```python
def test_creates_universal_fragment_without_language(self):
    """PromptFragment with language=None represents universal fragment."""
    fragment = PromptFragment(
        id="solid-principles",
        content="# SOLID\n\nCheck for violations.",
        language=None,  # Universal
        priority=100,
        category="architecture"
    )
    
    assert fragment.language is None
    assert fragment.is_universal()
```

**Run test (should FAIL):** `AttributeError: 'PromptFragment' object has no attribute 'is_universal'`

---

#### Step 2: Write Code (GREEN)

Add method to `PromptFragment`:

```python
@dataclass(frozen=True)
class PromptFragment:
    # ... existing fields ...
    
    def is_universal(self) -> bool:
        """Returns True if this fragment applies to all languages."""
        return self.language is None
```

**Run test (should PASS)**

---

### TDD Iteration 1.4: Validation

#### Step 1: Write Test (RED)

```python
def test_rejects_empty_id(self):
    """PromptFragment should reject empty ID."""
    with pytest.raises(ValueError, match="id cannot be empty"):
        PromptFragment(
            id="",  # Empty
            content="content",
            language="python",
            priority=50,
            category="test"
        )

def test_rejects_negative_priority(self):
    """PromptFragment should reject negative priority."""
    with pytest.raises(ValueError, match="priority must be non-negative"):
        PromptFragment(
            id="test",
            content="content",
            language="python",
            priority=-1,  # Negative
            category="test"
        )
```

**Run tests (should FAIL)**

---

#### Step 2: Write Code (GREEN)

Update `PromptFragment`:

```python
@dataclass(frozen=True)
class PromptFragment:
    id: str
    content: str
    language: Optional[str]
    priority: int
    category: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        # Validation
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
            
        # Initialize metadata
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {})
    
    def is_universal(self) -> bool:
        return self.language is None
```

**Run tests (should PASS)**

---

### TDD Iteration 1.5: Equality & Hashing

#### Step 1: Write Test (RED)

```python
def test_fragments_with_same_id_are_equal(self):
    """Fragments are equal if IDs match (value object equality)."""
    frag1 = PromptFragment(
        id="same-id",
        content="content A",
        language="python",
        priority=50,
        category="test"
    )
    frag2 = PromptFragment(
        id="same-id",
        content="content B",  # Different content
        language="go",         # Different language
        priority=80,           # Different priority
        category="other"       # Different category
    )
    
    assert frag1 == frag2  # Equal by ID
    assert hash(frag1) == hash(frag2)  # Hashable

def test_fragments_with_different_ids_are_not_equal(self):
    """Fragments with different IDs are not equal."""
    frag1 = PromptFragment(id="id-a", content="x", language=None, priority=1, category="x")
    frag2 = PromptFragment(id="id-b", content="x", language=None, priority=1, category="x")
    
    assert frag1 != frag2
```

**Run tests (should FAIL)** - default dataclass equality compares all fields

---

#### Step 2: Write Code (GREEN)

Update `PromptFragment`:

```python
@dataclass(frozen=True)
class PromptFragment:
    # ... fields ...
    
    def __eq__(self, other) -> bool:
        """Equality based on ID only (value object identity)."""
        if not isinstance(other, PromptFragment):
            return NotImplemented
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash based on ID only."""
        return hash(self.id)
    
    # ... other methods ...
```

**Run tests (should PASS)**

---

## Part 2: ReviewContext Entity

### TDD Iteration 2.1: Basic Construction

#### Step 1: Write Test (RED)

Add to `test_entities.py`:

```python
from src.domain.entities import ReviewContext


class TestReviewContext:
    def test_creates_context_with_required_fields(self):
        """ReviewContext should capture PR review metadata."""
        context = ReviewContext(
            language="python",
            file_paths=["src/main.py", "tests/test_main.py"],
            diff="+def foo():\n+    pass"
        )
        
        assert context.language == "python"
        assert context.file_paths == ["src/main.py", "tests/test_main.py"]
        assert context.diff == "+def foo():\n+    pass"
```

**Run test (should FAIL)**

---

#### Step 2: Write Code (GREEN)

Add to `entities.py`:

```python
@dataclass(frozen=True)
class ReviewContext:
    """Context information about the code being reviewed."""
    language: str
    file_paths: list[str]
    diff: str
    repository_context: Optional[str] = None
```

**Run test (should PASS)**

---

### TDD Iteration 2.2: Validation

#### Step 1: Write Test (RED)

```python
def test_rejects_empty_language(self):
    """ReviewContext should require non-empty language."""
    with pytest.raises(ValueError, match="language cannot be empty"):
        ReviewContext(
            language="",
            file_paths=["file.py"],
            diff="diff"
        )

def test_rejects_empty_file_paths(self):
    """ReviewContext should require at least one file path."""
    with pytest.raises(ValueError, match="file_paths cannot be empty"):
        ReviewContext(
            language="python",
            file_paths=[],
            diff="diff"
        )
```

**Run tests (should FAIL)**

---

#### Step 2: Write Code (GREEN)

```python
@dataclass(frozen=True)
class ReviewContext:
    language: str
    file_paths: list[str]
    diff: str
    repository_context: Optional[str] = None
    
    def __post_init__(self):
        if not self.language or not self.language.strip():
            raise ValueError("language cannot be empty")
        if not self.file_paths:
            raise ValueError("file_paths cannot be empty")
```

**Run tests (should PASS)**

---

## Part 3: ComposedPrompt Entity

### TDD Iteration 3.1: Basic Construction

#### Step 1: Write Test (RED)

```python
from src.domain.entities import ComposedPrompt


class TestComposedPrompt:
    def test_creates_composed_prompt(self):
        """ComposedPrompt should contain final rendered content."""
        prompt = ComposedPrompt(
            content="# Review\n\nCheck this code...",
            fragments_used=["python-errors", "solid-principles"],
            total_tokens=150
        )
        
        assert prompt.content == "# Review\n\nCheck this code..."
        assert prompt.fragments_used == ["python-errors", "solid-principles"]
        assert prompt.total_tokens == 150
```

**Run test (should FAIL)**

---

#### Step 2: Write Code (GREEN)

```python
@dataclass(frozen=True)
class ComposedPrompt:
    """Final assembled prompt ready for LLM consumption."""
    content: str
    fragments_used: list[str]
    total_tokens: int
    
    def __post_init__(self):
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be empty")
        if self.total_tokens < 0:
            raise ValueError("total_tokens must be non-negative")
```

**Run test (should PASS)**

---

## Part 4: Port Interfaces

### TDD Iteration 4.1: FragmentRepository Port

#### Step 1: Write Test (RED)

Create `tests/unit/domain/test_ports.py`:

```python
import pytest
from typing import Protocol
from src.domain.ports import FragmentRepository
from src.domain.entities import PromptFragment


class TestFragmentRepositoryProtocol:
    def test_is_protocol(self):
        """FragmentRepository should be a Protocol (interface)."""
        assert issubclass(FragmentRepository, Protocol)
    
    def test_has_find_by_language_method(self):
        """FragmentRepository must define find_by_language method."""
        # Verify signature
        import inspect
        sig = inspect.signature(FragmentRepository.find_by_language)
        params = list(sig.parameters.keys())
        
        assert 'language' in params
        assert sig.return_annotation == list[PromptFragment]
```

**Run test (should FAIL)**

---

#### Step 2: Write Code (GREEN)

Create `src/domain/ports.py`:

```python
from typing import Protocol, Optional
from src.domain.entities import PromptFragment


class FragmentRepository(Protocol):
    """Port for loading prompt fragments from storage.
    
    Implementations might load from filesystem, database, or remote API.
    """
    
    def find_by_language(self, language: str) -> list[PromptFragment]:
        """Load all fragments for a specific language.
        
        Args:
            language: Programming language (e.g., "python", "go")
            
        Returns:
            List of fragments. Returns empty list if none found.
        """
        ...
    
    def find_universal(self) -> list[PromptFragment]:
        """Load all language-agnostic (universal) fragments.
        
        Returns:
            List of universal fragments.
        """
        ...
    
    def find_by_id(self, fragment_id: str) -> Optional[PromptFragment]:
        """Load a specific fragment by ID.
        
        Args:
            fragment_id: Unique fragment identifier
            
        Returns:
            Fragment if found, None otherwise.
        """
        ...
```

**Run test (should PASS)**

---

### TDD Iteration 4.2: Additional Ports

```python
class PromptRenderer(Protocol):
    """Port for rendering fragment templates with variables."""
    
    def render(self, template: str, variables: dict[str, str]) -> str:
        """Render a template with variables.
        
        Args:
            template: Markdown template with placeholders
            variables: Variable substitutions
            
        Returns:
            Rendered content
        """
        ...


class LanguageDetector(Protocol):
    """Port for detecting programming language from file paths."""
    
    def detect(self, file_paths: list[str]) -> str:
        """Detect primary language from file paths.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Detected language (e.g., "python", "go")
            
        Raises:
            ValueError: If language cannot be detected
        """
        ...
```

---

## Part 5: Run Full Domain Test Suite

### Execute All Tests

```bash
# Run all domain tests
poetry run pytest tests/unit/domain/ -v

# Check coverage (MUST be 100%)
poetry run pytest tests/unit/domain/ --cov=src/domain --cov-report=term-missing --cov-fail-under=100
```

### Expected Output

```
tests/unit/domain/test_entities.py::TestPromptFragment::test_creates_fragment_with_required_fields PASSED
tests/unit/domain/test_entities.py::TestPromptFragment::test_fragment_is_immutable PASSED
tests/unit/domain/test_entities.py::TestPromptFragment::test_creates_universal_fragment_without_language PASSED
tests/unit/domain/test_entities.py::TestPromptFragment::test_rejects_empty_id PASSED
tests/unit/domain/test_entities.py::TestPromptFragment::test_rejects_negative_priority PASSED
tests/unit/domain/test_entities.py::TestPromptFragment::test_fragments_with_same_id_are_equal PASSED
tests/unit/domain/test_entities.py::TestPromptFragment::test_fragments_with_different_ids_are_not_equal PASSED
tests/unit/domain/test_entities.py::TestReviewContext::test_creates_context_with_required_fields PASSED
tests/unit/domain/test_entities.py::TestReviewContext::test_rejects_empty_language PASSED
tests/unit/domain/test_entities.py::TestReviewContext::test_rejects_empty_file_paths PASSED
tests/unit/domain/test_entities.py::TestComposedPrompt::test_creates_composed_prompt PASSED
tests/unit/domain/test_ports.py::TestFragmentRepositoryProtocol::test_is_protocol PASSED
tests/unit/domain/test_ports.py::TestFragmentRepositoryProtocol::test_has_find_by_language_method PASSED

---------- coverage: platform linux, python 3.11.x -----------
Name                      Stmts   Miss  Cover   Missing
-------------------------------------------------------
src/domain/__init__.py        0      0   100%
src/domain/entities.py       45      0   100%
src/domain/ports.py          12      0   100%
-------------------------------------------------------
TOTAL                        57      0   100%
```

---

## SOLID Analysis

Run analysis on domain layer:

```
┌─ SOLID ANALYSIS ──────────────────────────────────────────┐
│ S — Single Responsibility  [✓ OK]                         │
│ O — Open/Closed            [✓ OK]                         │
│ L — Liskov Substitution    [✓ OK]                         │
│ I — Interface Segregation  [✓ OK]                         │
│ D — Dependency Inversion   [✓ OK]                         │
└───────────────────────────────────────────────────────────┘

Analysis:
  ✓ PromptFragment: Pure value object, no responsibilities beyond data
  ✓ ReviewContext: Pure value object, encapsulates review metadata
  ✓ ComposedPrompt: Pure value object, represents final output
  ✓ Ports: All interfaces, no concrete dependencies
  ✓ Domain layer has ZERO dependencies on infrastructure
```

---

## Acceptance Criteria (Phase 1)

### ✅ AC-1.1: Domain Entities Implemented
- [ ] `PromptFragment` fully implemented with validation
- [ ] `ReviewContext` fully implemented with validation
- [ ] `ComposedPrompt` fully implemented with validation
- [ ] All entities are immutable (`frozen=True`)

### ✅ AC-1.2: Domain Ports Defined
- [ ] `FragmentRepository` protocol exists
- [ ] `PromptRenderer` protocol exists
- [ ] `LanguageDetector` protocol exists
- [ ] All ports use `Protocol` (runtime checkable)

### ✅ AC-1.3: Tests Pass
- [ ] All domain tests pass: `pytest tests/unit/domain/ -v`
- [ ] 100% coverage: `pytest tests/unit/domain/ --cov=src/domain --cov-fail-under=100`
- [ ] No SOLID violations

### ✅ AC-1.4: Documentation
- [ ] All classes have docstrings
- [ ] All public methods have docstrings
- [ ] Type hints on all signatures

---

## Phase 1 Exit Criteria

**YOU CAN ONLY PROCEED TO PHASE 2 IF:**

1. ✅ All AC-1.x criteria are met
2. ✅ Domain layer coverage is 100%
3. ✅ All tests pass in <1 second
4. ✅ `mypy src/domain/ --strict` passes (if using mypy)
5. ✅ Domain layer imports ONLY from:
   - Python stdlib
   - `typing`
   - Other domain modules

**Verification Command:**
```bash
pytest tests/unit/domain/ --cov=src/domain --cov-report=term-missing --cov-fail-under=100 -v
```

---

## Common TDD Mistakes to Avoid

❌ **Writing implementation before test**
✅ Always RED → GREEN → REFACTOR

❌ **Testing multiple behaviors in one test**
✅ One test = one behavior

❌ **Making tests pass by modifying the test**
✅ Test is the specification; change implementation

❌ **Skipping the refactor step**
✅ Always clean up after GREEN

❌ **Writing tests that depend on implementation details**
✅ Test behavior, not internal structure

---

## Next Phase Preview

**Phase 2** will implement:
- Infrastructure adapters (FileSystemFragmentRepository)
- Integration tests (real filesystem, no mocks)
- Markdown file loading

**DO NOT START PHASE 2 UNTIL ALL PHASE 1 CRITERIA ARE MET.**
