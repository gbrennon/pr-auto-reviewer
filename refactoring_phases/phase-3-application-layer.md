# Phase 3: Application Layer - Use Cases & Services

**Prerequisites**: Phase 2 complete and all AC-2.x passing

**Goal**: Implement business logic orchestration with unit tests using mocked ports.

**Duration Estimate**: 3-4 hours

---

## Overview

This phase builds the **application layer** that orchestrates domain entities and infrastructure ports:
- Fragment selection logic
- Prompt composition logic
- Use cases that tie everything together

**TESTING RULES FOR THIS PHASE:**
- ✅ **USE MOCKS** for port implementations
- ✅ **TEST LOGIC** not infrastructure
- ✅ **FAST TESTS** (milliseconds, no I/O)

---

## Part 1: Fragment Selection Service

### TDD Iteration 3.1: Basic Selection Strategy

#### Step 1: Write Failing Test (RED)

Create `tests/unit/application/test_services.py`:

```python
import pytest
from unittest.mock import Mock, MagicMock
from src.application.services import FragmentSelector
from src.domain.entities import PromptFragment, ReviewContext
from src.domain.ports import FragmentRepository


class TestFragmentSelector:
    @pytest.fixture
    def mock_repository(self) -> Mock:
        """Mock repository for testing."""
        return Mock(spec=FragmentRepository)
    
    @pytest.fixture
    def selector(self, mock_repository) -> FragmentSelector:
        """Create selector with mocked repository."""
        return FragmentSelector(repository=mock_repository)
    
    def test_selects_language_specific_fragments(self, selector, mock_repository):
        """Selector should load fragments for the detected language."""
        # Setup
        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def foo(): pass"
        )
        
        python_fragment = PromptFragment(
            id="python-errors",
            content="Check Python errors",
            language="python",
            priority=80,
            category="errors"
        )
        
        mock_repository.find_by_language.return_value = [python_fragment]
        mock_repository.find_universal.return_value = []
        
        # Execute
        fragments = selector.select_for(context)
        
        # Verify
        assert len(fragments) == 1
        assert fragments[0].id == "python-errors"
        mock_repository.find_by_language.assert_called_once_with("python")
```

**Run test (should FAIL):** `ModuleNotFoundError: No module named 'src.application.services'`

---

#### Step 2: Write Minimal Code (GREEN)

Create `src/application/services.py`:

```python
from src.domain.entities import PromptFragment, ReviewContext
from src.domain.ports import FragmentRepository


class FragmentSelector:
    """Service for selecting relevant fragments based on review context.
    
    Selection strategy:
    1. Load language-specific fragments
    2. Load universal fragments
    3. Combine and sort by priority
    """
    
    def __init__(self, repository: FragmentRepository):
        """Initialize selector.
        
        Args:
            repository: Fragment repository port
        """
        self._repository = repository
    
    def select_for(self, context: ReviewContext) -> list[PromptFragment]:
        """Select fragments relevant to the review context.
        
        Args:
            context: Review context with language and file info
            
        Returns:
            List of selected fragments, sorted by priority (descending)
        """
        language_fragments = self._repository.find_by_language(context.language)
        universal_fragments = self._repository.find_universal()
        
        # Combine and sort by priority
        all_fragments = language_fragments + universal_fragments
        return sorted(all_fragments, key=lambda f: f.priority, reverse=True)
```

**Run test (should PASS)**

---

### TDD Iteration 3.2: Universal Fragments Included

#### Step 1: Write Failing Test (RED)

```python
def test_includes_universal_fragments(self, selector, mock_repository):
    """Selector should include universal fragments with language-specific ones."""
    context = ReviewContext(
        language="python",
        file_paths=["src/main.py"],
        diff="+def foo(): pass"
    )
    
    python_fragment = PromptFragment(
        id="python-errors",
        content="Python errors",
        language="python",
        priority=80,
        category="errors"
    )
    
    universal_fragment = PromptFragment(
        id="solid-principles",
        content="SOLID",
        language=None,
        priority=100,
        category="architecture"
    )
    
    mock_repository.find_by_language.return_value = [python_fragment]
    mock_repository.find_universal.return_value = [universal_fragment]
    
    # Execute
    fragments = selector.select_for(context)
    
    # Verify
    assert len(fragments) == 2
    assert fragments[0].id == "solid-principles"  # Higher priority first
    assert fragments[1].id == "python-errors"
    mock_repository.find_universal.assert_called_once()
```

**Run test (should PASS)** - already implemented

---

### TDD Iteration 3.3: Empty Results Handling

#### Step 1: Write Failing Test (RED)

```python
def test_returns_empty_list_when_no_fragments_found(self, selector, mock_repository):
    """Selector should return empty list when no fragments exist."""
    context = ReviewContext(
        language="rust",
        file_paths=["src/main.rs"],
        diff="+fn main() {}"
    )
    
    mock_repository.find_by_language.return_value = []
    mock_repository.find_universal.return_value = []
    
    # Execute
    fragments = selector.select_for(context)
    
    # Verify
    assert fragments == []
```

**Run test (should PASS)** - already handled

---

## Part 2: Prompt Composition Service

### TDD Iteration 3.4: Basic Composition

#### Step 1: Write Failing Test (RED)

Add to `test_services.py`:

```python
from src.application.services import PromptComposer
from src.domain.entities import ComposedPrompt


class TestPromptComposer:
    @pytest.fixture
    def composer(self) -> PromptComposer:
        """Create composer."""
        return PromptComposer()
    
    def test_composes_single_fragment(self, composer):
        """Composer should assemble single fragment into prompt."""
        fragment = PromptFragment(
            id="test-fragment",
            content="# Test\n\nCheck this code:\n\n{{code}}",
            language="python",
            priority=50,
            category="test"
        )
        
        context = ReviewContext(
            language="python",
            file_paths=["test.py"],
            diff="+def foo(): pass"
        )
        
        # Execute
        prompt = composer.compose([fragment], context)
        
        # Verify
        assert isinstance(prompt, ComposedPrompt)
        assert "# Test" in prompt.content
        assert "Check this code" in prompt.content
        assert prompt.fragments_used == ["test-fragment"]
```

**Run test (should FAIL):** `AttributeError: module has no attribute 'PromptComposer'`

---

#### Step 2: Write Minimal Code (GREEN)

Add to `services.py`:

```python
class PromptComposer:
    """Service for composing fragments into a complete prompt.
    
    Composition strategy:
    1. Render each fragment with context variables
    2. Join fragments with separators
    3. Calculate token count estimate
    """
    
    def __init__(self, separator: str = "\n\n---\n\n"):
        """Initialize composer.
        
        Args:
            separator: String to join fragments (default: markdown separator)
        """
        self._separator = separator
    
    def compose(
        self,
        fragments: list[PromptFragment],
        context: ReviewContext
    ) -> ComposedPrompt:
        """Compose fragments into a complete prompt.
        
        Args:
            fragments: Selected fragments to compose
            context: Review context for variable substitution
            
        Returns:
            Composed prompt ready for LLM
        """
        if not fragments:
            raise ValueError("Cannot compose prompt from empty fragment list")
        
        # Render each fragment
        rendered_sections = []
        fragment_ids = []
        
        for fragment in fragments:
            rendered = self._render_fragment(fragment, context)
            rendered_sections.append(rendered)
            fragment_ids.append(fragment.id)
        
        # Join sections
        final_content = self._separator.join(rendered_sections)
        
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        estimated_tokens = len(final_content) // 4
        
        return ComposedPrompt(
            content=final_content,
            fragments_used=fragment_ids,
            total_tokens=estimated_tokens
        )
    
    def _render_fragment(
        self,
        fragment: PromptFragment,
        context: ReviewContext
    ) -> str:
        """Render a single fragment with variable substitution.
        
        Args:
            fragment: Fragment to render
            context: Context for variables
            
        Returns:
            Rendered fragment content
        """
        content = fragment.content
        
        # Simple variable substitution
        # TODO: Phase 4 will use proper template engine (Jinja2)
        content = content.replace("{{code}}", context.diff)
        content = content.replace("{{language}}", context.language)
        
        return content
```

**Run test (should PASS)**

---

### TDD Iteration 3.5: Multiple Fragments

#### Step 1: Write Failing Test (RED)

```python
def test_composes_multiple_fragments_with_separator(self, composer):
    """Composer should join multiple fragments with separator."""
    fragment1 = PromptFragment(
        id="fragment-1",
        content="# First Fragment",
        language=None,
        priority=100,
        category="test"
    )
    
    fragment2 = PromptFragment(
        id="fragment-2",
        content="# Second Fragment",
        language=None,
        priority=80,
        category="test"
    )
    
    context = ReviewContext(
        language="python",
        file_paths=["test.py"],
        diff="+code"
    )
    
    # Execute
    prompt = composer.compose([fragment1, fragment2], context)
    
    # Verify
    assert "# First Fragment" in prompt.content
    assert "# Second Fragment" in prompt.content
    assert "\n---\n" in prompt.content  # Separator present
    assert prompt.fragments_used == ["fragment-1", "fragment-2"]
```

**Run test (should PASS)** - already handled

---

### TDD Iteration 3.6: Variable Substitution

#### Step 1: Write Failing Test (RED)

```python
def test_substitutes_variables_in_templates(self, composer):
    """Composer should replace template variables with context values."""
    fragment = PromptFragment(
        id="template-fragment",
        content="Language: {{language}}\n\nCode:\n{{code}}",
        language=None,
        priority=50,
        category="test"
    )
    
    context = ReviewContext(
        language="python",
        file_paths=["test.py"],
        diff="+def hello():\n+    print('world')"
    )
    
    # Execute
    prompt = composer.compose([fragment], context)
    
    # Verify
    assert "Language: python" in prompt.content
    assert "+def hello():" in prompt.content
    assert "+    print('world')" in prompt.content
    assert "{{language}}" not in prompt.content  # No unreplaced variables
    assert "{{code}}" not in prompt.content
```

**Run test (should PASS)** - already handled

---

### TDD Iteration 3.7: Error Handling

#### Step 1: Write Failing Test (RED)

```python
def test_raises_error_for_empty_fragment_list(self, composer):
    """Composer should reject empty fragment list."""
    context = ReviewContext(
        language="python",
        file_paths=["test.py"],
        diff="+code"
    )
    
    with pytest.raises(ValueError, match="Cannot compose prompt from empty fragment list"):
        composer.compose([], context)
```

**Run test (should PASS)** - already implemented

---

## Part 3: Use Case - Compose Review Prompt

### TDD Iteration 3.8: End-to-End Use Case

#### Step 1: Write Failing Test (RED)

Create `tests/unit/application/test_use_cases.py`:

```python
import pytest
from unittest.mock import Mock
from src.application.use_cases import ComposeReviewPromptUseCase
from src.application.services import FragmentSelector, PromptComposer
from src.domain.entities import PromptFragment, ReviewContext, ComposedPrompt
from src.domain.ports import FragmentRepository


class TestComposeReviewPromptUseCase:
    @pytest.fixture
    def mock_repository(self) -> Mock:
        return Mock(spec=FragmentRepository)
    
    @pytest.fixture
    def selector(self, mock_repository) -> FragmentSelector:
        return FragmentSelector(repository=mock_repository)
    
    @pytest.fixture
    def composer(self) -> PromptComposer:
        return PromptComposer()
    
    @pytest.fixture
    def use_case(self, selector, composer) -> ComposeReviewPromptUseCase:
        return ComposeReviewPromptUseCase(
            selector=selector,
            composer=composer
        )
    
    def test_executes_full_composition_workflow(
        self,
        use_case,
        mock_repository
    ):
        """Use case should orchestrate selection and composition."""
        # Setup context
        context = ReviewContext(
            language="python",
            file_paths=["src/main.py"],
            diff="+def new_function():\n+    pass"
        )
        
        # Setup mock fragments
        python_fragment = PromptFragment(
            id="python-errors",
            content="# Python Review\n\n{{code}}",
            language="python",
            priority=80,
            category="errors"
        )
        
        universal_fragment = PromptFragment(
            id="solid",
            content="# SOLID Principles",
            language=None,
            priority=100,
            category="architecture"
        )
        
        mock_repository.find_by_language.return_value = [python_fragment]
        mock_repository.find_universal.return_value = [universal_fragment]
        
        # Execute
        result = use_case.execute(context)
        
        # Verify
        assert isinstance(result, ComposedPrompt)
        assert "# SOLID Principles" in result.content
        assert "# Python Review" in result.content
        assert "+def new_function():" in result.content
        assert result.fragments_used == ["solid", "python-errors"]
        assert result.total_tokens > 0
```

**Run test (should FAIL):** `ModuleNotFoundError: No module named 'src.application.use_cases'`

---

#### Step 2: Write Minimal Code (GREEN)

Create `src/application/use_cases.py`:

```python
from src.application.services import FragmentSelector, PromptComposer
from src.domain.entities import ReviewContext, ComposedPrompt


class ComposeReviewPromptUseCase:
    """Use case for composing a complete review prompt from fragments.
    
    Orchestrates:
    1. Fragment selection based on context
    2. Prompt composition with variable substitution
    3. Returns ready-to-send prompt
    """
    
    def __init__(
        self,
        selector: FragmentSelector,
        composer: PromptComposer
    ):
        """Initialize use case.
        
        Args:
            selector: Fragment selection service
            composer: Prompt composition service
        """
        self._selector = selector
        self._composer = composer
    
    def execute(self, context: ReviewContext) -> ComposedPrompt:
        """Execute the use case.
        
        Args:
            context: Review context with language and code info
            
        Returns:
            Composed prompt ready for LLM
            
        Raises:
            ValueError: If no fragments can be selected
        """
        # Step 1: Select relevant fragments
        fragments = self._selector.select_for(context)
        
        if not fragments:
            raise ValueError(
                f"No fragments found for language: {context.language}"
            )
        
        # Step 2: Compose prompt
        prompt = self._composer.compose(fragments, context)
        
        return prompt
```

**Run test (should PASS)**

---

### TDD Iteration 3.9: Error Handling in Use Case

#### Step 1: Write Failing Test (RED)

```python
def test_raises_error_when_no_fragments_selected(
    self,
    use_case,
    mock_repository
):
    """Use case should raise error when no fragments are available."""
    context = ReviewContext(
        language="unknown-language",
        file_paths=["test.xyz"],
        diff="+code"
    )
    
    mock_repository.find_by_language.return_value = []
    mock_repository.find_universal.return_value = []
    
    with pytest.raises(ValueError, match="No fragments found for language: unknown-language"):
        use_case.execute(context)
```

**Run test (should PASS)** - already implemented

---

## Part 4: Run Full Application Test Suite

```bash
# Run all application layer tests
poetry run pytest tests/unit/application/ -v

# Check coverage (should be high)
poetry run pytest tests/unit/application/ --cov=src/application --cov-report=term-missing

# Run all unit tests (domain + application)
poetry run pytest tests/unit/ -v --cov=src --cov-report=term-missing
```

Expected output:
```
tests/unit/application/test_services.py::TestFragmentSelector::test_selects_language_specific_fragments PASSED
tests/unit/application/test_services.py::TestFragmentSelector::test_includes_universal_fragments PASSED
tests/unit/application/test_services.py::TestFragmentSelector::test_returns_empty_list_when_no_fragments_found PASSED
tests/unit/application/test_services.py::TestPromptComposer::test_composes_single_fragment PASSED
tests/unit/application/test_services.py::TestPromptComposer::test_composes_multiple_fragments_with_separator PASSED
tests/unit/application/test_services.py::TestPromptComposer::test_substitutes_variables_in_templates PASSED
tests/unit/application/test_services.py::TestPromptComposer::test_raises_error_for_empty_fragment_list PASSED
tests/unit/application/test_use_cases.py::TestComposeReviewPromptUseCase::test_executes_full_composition_workflow PASSED
tests/unit/application/test_use_cases.py::TestComposeReviewPromptUseCase::test_raises_error_when_no_fragments_selected PASSED

---------- coverage: platform linux, python 3.11.x -----------
Name                          Stmts   Miss  Cover   Missing
-----------------------------------------------------------
src/application/__init__.py       0      0   100%
src/application/services.py      45      0   100%
src/application/use_cases.py     12      0   100%
-----------------------------------------------------------
TOTAL                            57      0   100%
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
  ✓ FragmentSelector: Single responsibility (fragment selection)
  ✓ PromptComposer: Single responsibility (composition logic)
  ✓ ComposeReviewPromptUseCase: Orchestrates, doesn't implement
  ✓ All depend on abstractions (ports), not concretions
  ✓ Services are testable with mocked ports
  ✓ Open for extension (new selection strategies, renderers)
```

---

## Acceptance Criteria (Phase 3)

### ✅ AC-3.1: Services Implemented
- [ ] `FragmentSelector` selects fragments based on context
- [ ] `PromptComposer` composes fragments into prompt
- [ ] Both services use dependency injection (ports)
- [ ] Variable substitution works ({{code}}, {{language}})

### ✅ AC-3.2: Use Case Orchestrates Workflow
- [ ] `ComposeReviewPromptUseCase` exists
- [ ] Use case calls selector → composer in sequence
- [ ] Use case handles errors gracefully
- [ ] Returns `ComposedPrompt` domain entity

### ✅ AC-3.3: Unit Tests Pass
- [ ] All application tests pass: `pytest tests/unit/application/ -v`
- [ ] Tests use MOCKS for repositories (not real I/O)
- [ ] Coverage > 95%: `pytest tests/unit/application/ --cov=src/application --cov-fail-under=95`

### ✅ AC-3.4: Fast Test Execution
- [ ] All unit tests run in < 1 second
- [ ] No file I/O in application tests
- [ ] No network calls in application tests

---

## Phase 3 Exit Criteria

**YOU CAN ONLY PROCEED TO PHASE 4 IF:**

1. ✅ All AC-3.x criteria are met
2. ✅ Application layer coverage ≥ 95%
3. ✅ All unit tests (domain + application) pass in < 1 second
4. ✅ No SOLID violations in application layer
5. ✅ Services depend only on ports (DIP)

**Verification Commands:**
```bash
# Run all unit tests with timing
poetry run pytest tests/unit/ -v --durations=0

# Verify coverage
poetry run pytest tests/unit/ --cov=src --cov-report=term-missing --cov-fail-under=90

# Check dependency direction (application should import domain, not infra)
grep -r "from src.infrastructure" src/application/ && echo "FAIL: Wrong dependency" || echo "PASS"

# Verify mocks used correctly
grep -r "Mock\|MagicMock" tests/unit/application/ | wc -l
# Should be > 0 (mocks are used)

grep -r "Mock\|MagicMock" tests/unit/domain/ | wc -l
# Should be 0 (domain is pure)
```

---

## Common Application Layer Mistakes to Avoid

❌ **Services doing infrastructure work**
✅ Services orchestrate, ports do I/O

❌ **Use cases containing business logic**
✅ Use cases orchestrate services, services contain logic

❌ **Not using dependency injection**
✅ All dependencies passed via constructor

❌ **Testing with real infrastructure**
✅ Mock all ports in unit tests

❌ **Bloated services with multiple responsibilities**
✅ Keep services focused on one concern

---

## Next Phase Preview

**Phase 4** will implement:
- Advanced template rendering (Jinja2)
- Token budget management
- Fragment prioritization strategies
- More sophisticated variable substitution

**DO NOT START PHASE 4 UNTIL ALL PHASE 3 CRITERIA ARE MET.**
