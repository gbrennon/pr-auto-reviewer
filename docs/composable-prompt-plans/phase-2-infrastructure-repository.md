# Phase 2: Infrastructure Layer - Fragment Repository

**Prerequisites**: Phase 1 complete and all AC-1.x passing

**Goal**: Implement FileSystemFragmentRepository with REAL filesystem integration tests (NO MOCKS).

**Duration Estimate**: 2-3 hours

---

## Overview

This phase implements the **first infrastructure adapter** - loading fragments from the filesystem.

**CRITICAL RULES FOR THIS PHASE:**
- ❌ **NO MOCKING** filesystem operations
- ✅ **USE REAL FILES** in test fixtures
- ✅ **CLEAN UP** test artifacts after tests
- ✅ **TEST ACTUAL I/O** operations

---

## Part 1: Create Test Fragment Files

### Setup Test Fixtures Directory

Before writing any tests, create real fragment files for testing.

```bash
mkdir -p tests/fixtures/fragments/{python,go,universal}
```

---

### Fixture 1: Python Error Handling

Create `tests/fixtures/fragments/python/error-handling.md`:

```markdown
# Python Error Handling Best Practices

Review the following code for proper error handling:

{{code}}

## Checks

- Bare `except:` clauses (should specify exception types)
- Missing exception context (`raise` without `from`)
- Resource leaks (files/connections not in `with` statements)
- Swallowed exceptions (empty except blocks)

## Good Example

```python
try:
    with open(file_path) as f:
        data = json.load(f)
except FileNotFoundError as e:
    raise ConfigError(f"Config not found: {file_path}") from e
except json.JSONDecodeError as e:
    raise ConfigError(f"Invalid JSON in {file_path}") from e
```

## Bad Example

```python
try:
    f = open(file_path)
    data = json.load(f)
except:
    pass
```
```

---

### Fixture 2: Go Concurrency

Create `tests/fixtures/fragments/go/concurrency.md`:

```markdown
# Go Concurrency Patterns

Review goroutines and channel usage:

{{code}}

## Checks

- Goroutines that might leak (no way to stop them)
- Unbuffered channels that might deadlock
- Missing `context.Context` for cancellation
- Race conditions on shared state

## Good Example

```go
func worker(ctx context.Context, jobs <-chan int) {
    for {
        select {
        case job := <-jobs:
            process(job)
        case <-ctx.Done():
            return
        }
    }
}
```
```

---

### Fixture 3: Universal SOLID Principles

Create `tests/fixtures/fragments/universal/solid-principles.md`:

```markdown
# SOLID Principles Review

Check for violations of SOLID principles:

{{code}}

## Single Responsibility Principle
- Each class/module should have one reason to change
- Look for "god classes" with multiple unrelated responsibilities

## Open/Closed Principle
- Open for extension, closed for modification
- Avoid long if/switch chains for type checking

## Liskov Substitution Principle
- Subtypes must be substitutable for base types
- Check for method signature violations in overrides

## Interface Segregation Principle
- Clients shouldn't depend on interfaces they don't use
- Look for fat interfaces

## Dependency Inversion Principle
- Depend on abstractions, not concretions
- Check for `new ConcreteClass()` instantiations
```

---

## Part 2: Fragment Metadata Convention

Before implementing the repository, define how metadata is extracted from markdown files.

### Convention: YAML Front Matter

Fragments use YAML front matter for metadata:

```markdown
---
id: python-error-handling
language: python
priority: 80
category: error-handling
---

# Python Error Handling Best Practices
...
```

For universal fragments (no language):
```markdown
---
id: solid-principles
language: null
priority: 100
category: architecture
---

# SOLID Principles Review
...
```

---

## Part 3: TDD Implementation

### TDD Iteration 2.1: Repository Construction

#### Step 1: Write Failing Test (RED)

Create `tests/integration/infrastructure/test_filesystem_repository.py`:

```python
import pytest
from pathlib import Path
from src.infrastructure.repositories import FileSystemFragmentRepository
from src.domain.entities import PromptFragment


class TestFileSystemFragmentRepository:
    @pytest.fixture
    def fixtures_dir(self) -> Path:
        """Path to test fixtures directory."""
        return Path(__file__).parent.parent.parent / "fixtures" / "fragments"
    
    @pytest.fixture
    def repository(self, fixtures_dir: Path) -> FileSystemFragmentRepository:
        """Create repository pointing to test fixtures."""
        return FileSystemFragmentRepository(base_path=fixtures_dir)
    
    def test_creates_repository_with_valid_path(self, fixtures_dir):
        """Repository should initialize with valid base path."""
        repo = FileSystemFragmentRepository(base_path=fixtures_dir)
        
        assert repo.base_path == fixtures_dir
    
    def test_rejects_nonexistent_path(self):
        """Repository should reject non-existent base path."""
        with pytest.raises(ValueError, match="base_path does not exist"):
            FileSystemFragmentRepository(base_path=Path("/nonexistent/path"))
```

**Run test (should FAIL):**
```bash
poetry run pytest tests/integration/infrastructure/test_filesystem_repository.py::TestFileSystemFragmentRepository::test_creates_repository_with_valid_path -v
```

---

#### Step 2: Write Minimal Code (GREEN)

Create `src/infrastructure/repositories.py`:

```python
from pathlib import Path
from typing import Optional
from src.domain.entities import PromptFragment


class FileSystemFragmentRepository:
    """Loads prompt fragments from markdown files on disk.
    
    Directory structure:
        base_path/
            python/
                error-handling.md
                idioms.md
            go/
                concurrency.md
            universal/
                solid-principles.md
    """
    
    def __init__(self, base_path: Path):
        """Initialize repository.
        
        Args:
            base_path: Root directory containing fragment subdirectories
            
        Raises:
            ValueError: If base_path does not exist
        """
        if not base_path.exists():
            raise ValueError(f"base_path does not exist: {base_path}")
        
        self.base_path = base_path
```

**Run test (should PASS)**

---

### TDD Iteration 2.2: Loading Fragments by Language

#### Step 1: Add Metadata to Test Fixtures

Update `tests/fixtures/fragments/python/error-handling.md`:

```markdown
---
id: python-error-handling
language: python
priority: 80
category: error-handling
---

# Python Error Handling Best Practices
...
```

Update `tests/fixtures/fragments/go/concurrency.md`:

```markdown
---
id: go-concurrency
language: go
priority: 85
category: concurrency
---

# Go Concurrency Patterns
...
```

Update `tests/fixtures/fragments/universal/solid-principles.md`:

```markdown
---
id: solid-principles
language: null
priority: 100
category: architecture
---

# SOLID Principles Review
...
```

---

#### Step 2: Write Failing Test (RED)

```python
def test_finds_fragments_by_language(self, repository):
    """Repository should load all fragments for a language."""
    fragments = repository.find_by_language("python")
    
    assert len(fragments) == 1
    assert fragments[0].id == "python-error-handling"
    assert fragments[0].language == "python"
    assert fragments[0].priority == 80
    assert fragments[0].category == "error-handling"
    assert "Python Error Handling" in fragments[0].content

def test_finds_multiple_fragments_for_language(self, repository, fixtures_dir):
    """Repository should load all fragments when multiple exist."""
    # Create second Python fragment
    second_fragment = fixtures_dir / "python" / "idioms.md"
    second_fragment.write_text("""---
id: python-idioms
language: python
priority: 70
category: idioms
---

# Python Idioms

Use list comprehensions over map/filter.
""")
    
    try:
        fragments = repository.find_by_language("python")
        
        assert len(fragments) == 2
        ids = {f.id for f in fragments}
        assert ids == {"python-error-handling", "python-idioms"}
    finally:
        # Clean up
        second_fragment.unlink()

def test_returns_empty_list_for_unknown_language(self, repository):
    """Repository should return empty list for non-existent language."""
    fragments = repository.find_by_language("rust")
    
    assert fragments == []
```

**Run tests (should FAIL)**

---

#### Step 3: Write Code (GREEN)

First, add YAML parsing dependency:
```bash
poetry add pyyaml
poetry add --group=dev types-pyyaml  # Type stubs
```

Update `repositories.py`:

```python
import yaml
from pathlib import Path
from typing import Optional
from src.domain.entities import PromptFragment


class FileSystemFragmentRepository:
    def __init__(self, base_path: Path):
        if not base_path.exists():
            raise ValueError(f"base_path does not exist: {base_path}")
        self.base_path = base_path
    
    def find_by_language(self, language: str) -> list[PromptFragment]:
        """Load all fragments for a specific language.
        
        Args:
            language: Programming language (e.g., "python", "go")
            
        Returns:
            List of fragments, sorted by priority (descending)
        """
        language_dir = self.base_path / language
        
        if not language_dir.exists():
            return []
        
        fragments = []
        for md_file in language_dir.glob("*.md"):
            fragment = self._load_fragment(md_file)
            if fragment:
                fragments.append(fragment)
        
        # Sort by priority descending
        return sorted(fragments, key=lambda f: f.priority, reverse=True)
    
    def _load_fragment(self, file_path: Path) -> Optional[PromptFragment]:
        """Load a single fragment from a markdown file.
        
        Args:
            file_path: Path to .md file
            
        Returns:
            PromptFragment if valid, None if parsing fails
        """
        try:
            content = file_path.read_text()
            
            # Parse YAML front matter
            if not content.startswith("---"):
                return None
            
            # Split front matter and content
            parts = content.split("---", 2)
            if len(parts) < 3:
                return None
            
            front_matter = yaml.safe_load(parts[1])
            markdown_content = parts[2].strip()
            
            return PromptFragment(
                id=front_matter["id"],
                content=markdown_content,
                language=front_matter.get("language"),
                priority=front_matter.get("priority", 50),
                category=front_matter.get("category", "general"),
                metadata=front_matter
            )
        except Exception:
            # Skip malformed files
            return None
```

**Run tests (should PASS)**

---

### TDD Iteration 2.3: Loading Universal Fragments

#### Step 1: Write Failing Test (RED)

```python
def test_finds_universal_fragments(self, repository):
    """Repository should load fragments with language=null."""
    fragments = repository.find_universal()
    
    assert len(fragments) == 1
    assert fragments[0].id == "solid-principles"
    assert fragments[0].language is None
    assert fragments[0].is_universal()
    assert "SOLID Principles" in fragments[0].content
```

**Run test (should FAIL):** `AttributeError: 'FileSystemFragmentRepository' object has no attribute 'find_universal'`

---

#### Step 2: Write Code (GREEN)

```python
def find_universal(self) -> list[PromptFragment]:
    """Load all language-agnostic (universal) fragments.
    
    Returns:
        List of universal fragments, sorted by priority (descending)
    """
    universal_dir = self.base_path / "universal"
    
    if not universal_dir.exists():
        return []
    
    fragments = []
    for md_file in universal_dir.glob("*.md"):
        fragment = self._load_fragment(md_file)
        if fragment and fragment.is_universal():
            fragments.append(fragment)
    
    return sorted(fragments, key=lambda f: f.priority, reverse=True)
```

**Run test (should PASS)**

---

### TDD Iteration 2.4: Loading by ID

#### Step 1: Write Failing Test (RED)

```python
def test_finds_fragment_by_id(self, repository):
    """Repository should find specific fragment by ID."""
    fragment = repository.find_by_id("python-error-handling")
    
    assert fragment is not None
    assert fragment.id == "python-error-handling"
    assert fragment.language == "python"

def test_returns_none_for_nonexistent_id(self, repository):
    """Repository should return None for non-existent ID."""
    fragment = repository.find_by_id("nonexistent-id")
    
    assert fragment is None

def test_finds_universal_fragment_by_id(self, repository):
    """Repository should find universal fragments by ID."""
    fragment = repository.find_by_id("solid-principles")
    
    assert fragment is not None
    assert fragment.id == "solid-principles"
    assert fragment.is_universal()
```

**Run tests (should FAIL)**

---

#### Step 2: Write Code (GREEN)

```python
def find_by_id(self, fragment_id: str) -> Optional[PromptFragment]:
    """Load a specific fragment by ID.
    
    Searches across all language directories and universal.
    
    Args:
        fragment_id: Unique fragment identifier
        
    Returns:
        Fragment if found, None otherwise
    """
    # Search all subdirectories
    for subdir in self.base_path.iterdir():
        if not subdir.is_dir():
            continue
        
        for md_file in subdir.glob("*.md"):
            fragment = self._load_fragment(md_file)
            if fragment and fragment.id == fragment_id:
                return fragment
    
    return None
```

**Run tests (should PASS)**

---

### TDD Iteration 2.5: Error Handling

#### Step 1: Write Failing Test (RED)

```python
def test_handles_malformed_yaml_gracefully(self, repository, fixtures_dir, tmp_path):
    """Repository should skip files with malformed YAML."""
    # Create malformed fragment
    malformed_file = fixtures_dir / "python" / "malformed.md"
    malformed_file.write_text("""---
id: malformed
this is not valid yaml: [
---

Content here
""")
    
    try:
        # Should not raise, just skip the malformed file
        fragments = repository.find_by_language("python")
        
        # Should only get the valid fragment
        assert all(f.id != "malformed" for f in fragments)
    finally:
        malformed_file.unlink()

def test_handles_missing_required_fields(self, repository, fixtures_dir):
    """Repository should skip fragments missing required fields."""
    incomplete_file = fixtures_dir / "python" / "incomplete.md"
    incomplete_file.write_text("""---
language: python
---

Content without ID
""")
    
    try:
        fragments = repository.find_by_language("python")
        
        # Should skip the incomplete fragment
        assert all(f.id != "" for f in fragments)
    finally:
        incomplete_file.unlink()
```

**Run tests (should PASS)** - already handled by `try/except` in `_load_fragment`

---

## Part 4: Run Full Integration Test Suite

```bash
# Run all integration tests
poetry run pytest tests/integration/ -v

# Check that integration tests use REAL files
poetry run pytest tests/integration/ -v -k "filesystem"

# Verify no mocks are used (manual check)
grep -r "mock" tests/integration/
# Should return nothing or only fixture-related mocks
```

---

## Part 5: SOLID Analysis

```
┌─ SOLID ANALYSIS ──────────────────────────────────────────┐
│ S — Single Responsibility  [✓ OK]                         │
│ O — Open/Closed            [✓ OK]                         │
│ L — Liskov Substitution    [✓ OK]                         │
│ I — Interface Segregation  [✓ OK]                         │
│ D — Dependency Inversion   [✓ OK]                         │
└───────────────────────────────────────────────────────────┘

Analysis:
  ✓ FileSystemFragmentRepository: Single responsibility (file loading)
  ✓ Implements FragmentRepository port (DIP)
  ✓ No concrete dependencies (only stdlib and domain)
  ✓ Testable through real filesystem (integration tests)
  ✓ Error handling doesn't leak exceptions
```

---

## Acceptance Criteria (Phase 2)

### ✅ AC-2.1: Repository Implements Port
- [ ] `FileSystemFragmentRepository` implements `FragmentRepository` protocol
- [ ] All port methods implemented: `find_by_language`, `find_universal`, `find_by_id`
- [ ] Constructor validates base_path exists

### ✅ AC-2.2: Integration Tests Pass
- [ ] Tests use REAL files in `tests/fixtures/`
- [ ] NO mocks used for filesystem operations
- [ ] Tests clean up artifacts (temp files deleted)
- [ ] All integration tests pass: `pytest tests/integration/ -v`

### ✅ AC-2.3: Fragment Loading Works
- [ ] Loads Python fragments correctly
- [ ] Loads Go fragments correctly
- [ ] Loads universal fragments correctly
- [ ] Parses YAML front matter correctly
- [ ] Handles malformed files gracefully (no crashes)

### ✅ AC-2.4: Test Fixtures Exist
- [ ] `tests/fixtures/fragments/python/error-handling.md`
- [ ] `tests/fixtures/fragments/go/concurrency.md`
- [ ] `tests/fixtures/fragments/universal/solid-principles.md`
- [ ] All fixtures have valid YAML front matter

---

## Phase 2 Exit Criteria

**YOU CAN ONLY PROCEED TO PHASE 3 IF:**

1. ✅ All AC-2.x criteria are met
2. ✅ Integration tests pass: `pytest tests/integration/ -v`
3. ✅ No mocks in integration tests: `grep -r "mock" tests/integration/` returns nothing
4. ✅ Repository correctly implements port protocol
5. ✅ Error handling is robust (malformed files don't crash)

**Verification Commands:**
```bash
# Run integration tests
poetry run pytest tests/integration/ -v

# Verify implementation matches port
poetry run python -c "
from src.infrastructure.repositories import FileSystemFragmentRepository
from src.domain.ports import FragmentRepository
import typing

# Runtime check that class implements protocol
repo = FileSystemFragmentRepository(path='.')
assert isinstance(repo, typing.Protocol)  # Should work with Protocol
"

# Check for mocks in integration tests
grep -r "mock\|Mock\|@patch" tests/integration/ && echo "FAIL: Mocks found" || echo "PASS: No mocks"
```

---

## Common Integration Testing Mistakes to Avoid

❌ **Using mocks for filesystem**
✅ Use real files and clean up

❌ **Testing only happy paths**
✅ Test error cases (malformed files, missing directories)

❌ **Leaving test artifacts on disk**
✅ Use fixtures with cleanup (try/finally or pytest fixtures)

❌ **Hardcoding absolute paths**
✅ Use `Path(__file__).parent` for relative paths

❌ **Not testing edge cases**
✅ Test empty directories, malformed YAML, missing fields

---

## Next Phase Preview

**Phase 3** will implement:
- Application layer (use cases and services)
- Fragment selection logic
- Prompt composition logic
- Unit tests with mocked repositories

**DO NOT START PHASE 3 UNTIL ALL PHASE 2 CRITERIA ARE MET.**
