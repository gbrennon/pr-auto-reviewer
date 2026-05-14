# Phase 4: Advanced Features - Template Engine & Token Management

**Prerequisites**: Phase 3 complete and all AC-3.x passing

**Goal**: Replace simple string substitution with Jinja2 templates and implement token budget management.

**Duration Estimate**: 2-3 hours

---

## Overview

This phase enhances the composition layer with:
- Professional template rendering (Jinja2)
- Token counting and budget management
- Fragment prioritization with budget constraints
- Advanced variable handling

---

## Part 1: Jinja2 Template Renderer

### TDD Iteration 4.1: Basic Jinja2 Rendering

#### Step 1: Add Dependency

```bash
poetry add jinja2
```

---

#### Step 2: Write Failing Test (RED)

Create `tests/unit/infrastructure/test_renderers.py`:

```python
import pytest
from src.infrastructure.renderers import Jinja2Renderer
from src.domain.entities import ReviewContext


class TestJinja2Renderer:
    @pytest.fixture
    def renderer(self) -> Jinja2Renderer:
        return Jinja2Renderer()
    
    def test_renders_simple_variables(self, renderer):
        """Renderer should substitute simple variables."""
        template = "Language: {{ language }}\nCode:\n{{ code }}"
        variables = {
            "language": "python",
            "code": "+def foo(): pass"
        }
        
        result = renderer.render(template, variables)
        
        assert result == "Language: python\nCode:\n+def foo(): pass"
    
    def test_renders_with_review_context(self, renderer):
        """Renderer should work with ReviewContext objects."""
        template = "Reviewing {{ language }} code:\n{{ diff }}"
        
        context = ReviewContext(
            language="python",
            file_paths=["test.py"],
            diff="+new code"
        )
        
        variables = {
            "language": context.language,
            "diff": context.diff,
            "code": context.diff  # Alias for backward compatibility
        }
        
        result = renderer.render(template, variables)
        
        assert "Reviewing python code:" in result
        assert "+new code" in result
```

**Run test (should FAIL)**

---

#### Step 3: Write Code (GREEN)

Create `src/infrastructure/renderers.py`:

```python
from jinja2 import Environment, BaseLoader, TemplateError


class Jinja2Renderer:
    """Renders prompt templates using Jinja2 template engine.
    
    Supports:
    - Variable substitution: {{ variable }}
    - Conditionals: {% if condition %}...{% endif %}
    - Loops: {% for item in items %}...{% endfor %}
    - Filters: {{ variable|upper }}
    """
    
    def __init__(self):
        """Initialize renderer with basic Jinja2 environment."""
        self._env = Environment(
            loader=BaseLoader(),
            autoescape=False,  # We're generating prompts, not HTML
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def render(self, template: str, variables: dict[str, str]) -> str:
        """Render a template with variables.
        
        Args:
            template: Jinja2 template string
            variables: Dictionary of variables to substitute
            
        Returns:
            Rendered template content
            
        Raises:
            ValueError: If template rendering fails
        """
        try:
            jinja_template = self._env.from_string(template)
            return jinja_template.render(**variables)
        except TemplateError as e:
            raise ValueError(f"Template rendering failed: {e}") from e
```

**Run test (should PASS)**

---

### TDD Iteration 4.2: Advanced Jinja2 Features

#### Step 1: Write Failing Test (RED)

```python
def test_renders_conditionals(self, renderer):
    """Renderer should support Jinja2 conditionals."""
    template = """
{% if has_tests %}
Check test coverage.
{% else %}
No tests found - this is a problem!
{% endif %}
""".strip()
    
    # With tests
    result_with_tests = renderer.render(template, {"has_tests": True})
    assert "Check test coverage" in result_with_tests
    assert "No tests found" not in result_with_tests
    
    # Without tests
    result_no_tests = renderer.render(template, {"has_tests": False})
    assert "No tests found" in result_no_tests
    assert "Check test coverage" not in result_no_tests

def test_renders_loops(self, renderer):
    """Renderer should support Jinja2 loops."""
    template = """
Files to review:
{% for file in files %}
- {{ file }}
{% endfor %}
""".strip()
    
    variables = {
        "files": ["main.py", "utils.py", "tests.py"]
    }
    
    result = renderer.render(template, variables)
    
    assert "- main.py" in result
    assert "- utils.py" in result
    assert "- tests.py" in result

def test_renders_filters(self, renderer):
    """Renderer should support Jinja2 filters."""
    template = "Language: {{ language|upper }}"
    variables = {"language": "python"}
    
    result = renderer.render(template, variables)
    
    assert result == "Language: PYTHON"

def test_handles_missing_variables_gracefully(self, renderer):
    """Renderer should handle missing variables without crashing."""
    template = "Language: {{ language }}\nOptional: {{ optional_var|default('N/A') }}"
    variables = {"language": "python"}
    
    result = renderer.render(template, variables)
    
    assert "Language: python" in result
    assert "Optional: N/A" in result
```

**Run tests (should PASS)** - Jinja2 already supports these features

---

### TDD Iteration 4.3: Integration with PromptComposer

#### Step 1: Write Failing Test (RED)

Update `tests/unit/application/test_services.py`:

```python
from src.infrastructure.renderers import Jinja2Renderer


class TestPromptComposerWithJinja2:
    @pytest.fixture
    def composer_with_jinja(self) -> PromptComposer:
        """Create composer with Jinja2 renderer."""
        renderer = Jinja2Renderer()
        return PromptComposer(renderer=renderer)
    
    def test_uses_jinja2_for_advanced_templates(self, composer_with_jinja):
        """Composer should use Jinja2 for advanced template features."""
        fragment = PromptFragment(
            id="advanced-template",
            content="""
# Review for {{ language|upper }}

Files:
{% for file in file_paths %}
- {{ file }}
{% endfor %}

Code changes:
```
{{ diff }}
```
""".strip(),
            language=None,
            priority=50,
            category="test"
        )
        
        context = ReviewContext(
            language="python",
            file_paths=["main.py", "utils.py"],
            diff="+def foo(): pass"
        )
        
        # Execute
        prompt = composer_with_jinja.compose([fragment], context)
        
        # Verify
        assert "# Review for PYTHON" in prompt.content
        assert "- main.py" in prompt.content
        assert "- utils.py" in prompt.content
        assert "+def foo(): pass" in prompt.content
```

**Run test (should FAIL)** - `PromptComposer` doesn't accept renderer yet

---

#### Step 2: Write Code (GREEN)

Update `src/application/services.py`:

```python
from typing import Optional
from src.domain.ports import PromptRenderer


class PromptComposer:
    """Service for composing fragments into a complete prompt."""
    
    def __init__(
        self,
        renderer: Optional[PromptRenderer] = None,
        separator: str = "\n\n---\n\n"
    ):
        """Initialize composer.
        
        Args:
            renderer: Template renderer (if None, uses simple substitution)
            separator: String to join fragments
        """
        self._renderer = renderer
        self._separator = separator
    
    def compose(
        self,
        fragments: list[PromptFragment],
        context: ReviewContext
    ) -> ComposedPrompt:
        """Compose fragments into a complete prompt."""
        if not fragments:
            raise ValueError("Cannot compose prompt from empty fragment list")
        
        rendered_sections = []
        fragment_ids = []
        
        for fragment in fragments:
            rendered = self._render_fragment(fragment, context)
            rendered_sections.append(rendered)
            fragment_ids.append(fragment.id)
        
        final_content = self._separator.join(rendered_sections)
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
        """Render a single fragment with variable substitution."""
        variables = {
            "code": context.diff,
            "diff": context.diff,
            "language": context.language,
            "file_paths": context.file_paths,
        }
        
        if self._renderer:
            # Use advanced renderer (e.g., Jinja2)
            return self._renderer.render(fragment.content, variables)
        else:
            # Fall back to simple string substitution
            content = fragment.content
            content = content.replace("{{code}}", context.diff)
            content = content.replace("{{language}}", context.language)
            return content
```

**Run test (should PASS)**

---

## Part 2: Token Budget Management

### TDD Iteration 4.4: Token Counter

#### Step 1: Write Failing Test (RED)

Add to `tests/unit/application/test_services.py`:

```python
class TestTokenBudgetManager:
    def test_estimates_tokens_from_text(self):
        """Should estimate token count from text."""
        from src.application.services import TokenBudgetManager
        
        manager = TokenBudgetManager(max_tokens=1000)
        
        # Rough estimate: 1 token ≈ 4 characters
        text = "a" * 400  # Should be ~100 tokens
        
        tokens = manager.estimate_tokens(text)
        
        assert 90 <= tokens <= 110  # Allow some variance
    
    def test_checks_if_content_fits_budget(self):
        """Should check if content fits within token budget."""
        from src.application.services import TokenBudgetManager
        
        manager = TokenBudgetManager(max_tokens=100)
        
        small_text = "a" * 200  # ~50 tokens
        large_text = "a" * 600  # ~150 tokens
        
        assert manager.fits_budget(small_text) is True
        assert manager.fits_budget(large_text) is False
    
    def test_calculates_remaining_budget(self):
        """Should track remaining budget after consumption."""
        from src.application.services import TokenBudgetManager
        
        manager = TokenBudgetManager(max_tokens=1000)
        
        text = "a" * 400  # ~100 tokens
        manager.consume(text)
        
        remaining = manager.remaining()
        
        assert 890 <= remaining <= 910  # ~900 remaining
```

**Run test (should FAIL)**

---

#### Step 2: Write Code (GREEN)

Add to `services.py`:

```python
class TokenBudgetManager:
    """Manages token budget for prompt composition.
    
    Prevents exceeding LLM context window by tracking token consumption.
    """
    
    def __init__(self, max_tokens: int):
        """Initialize budget manager.
        
        Args:
            max_tokens: Maximum tokens allowed in prompt
        """
        self._max_tokens = max_tokens
        self._consumed = 0
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text.
        
        Uses rough heuristic: 1 token ≈ 4 characters.
        For production, use tiktoken library for accurate counting.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def fits_budget(self, text: str) -> bool:
        """Check if text fits within remaining budget.
        
        Args:
            text: Text to check
            
        Returns:
            True if text fits, False otherwise
        """
        tokens = self.estimate_tokens(text)
        return self._consumed + tokens <= self._max_tokens
    
    def consume(self, text: str) -> int:
        """Consume budget for text.
        
        Args:
            text: Text being added to prompt
            
        Returns:
            Tokens consumed
            
        Raises:
            ValueError: If text exceeds remaining budget
        """
        tokens = self.estimate_tokens(text)
        
        if self._consumed + tokens > self._max_tokens:
            raise ValueError(
                f"Text would exceed budget: {tokens} tokens needed, "
                f"{self.remaining()} remaining"
            )
        
        self._consumed += tokens
        return tokens
    
    def remaining(self) -> int:
        """Get remaining token budget.
        
        Returns:
            Tokens remaining
        """
        return self._max_tokens - self._consumed
    
    def reset(self):
        """Reset consumed tokens to zero."""
        self._consumed = 0
```

**Run test (should PASS)**

---

### TDD Iteration 4.5: Fragment Prioritization with Budget

#### Step 1: Write Failing Test (RED)

```python
class TestFragmentSelectorWithBudget:
    @pytest.fixture
    def mock_repository(self) -> Mock:
        return Mock(spec=FragmentRepository)
    
    @pytest.fixture
    def selector_with_budget(self, mock_repository) -> FragmentSelector:
        return FragmentSelector(
            repository=mock_repository,
            max_tokens=1000
        )
    
    def test_selects_fragments_within_budget(self, selector_with_budget, mock_repository):
        """Selector should only include fragments that fit budget."""
        context = ReviewContext(
            language="python",
            file_paths=["test.py"],
            diff="+code"
        )
        
        # Create fragments of varying sizes
        small_fragment = PromptFragment(
            id="small",
            content="a" * 400,  # ~100 tokens
            language="python",
            priority=100,
            category="test"
        )
        
        medium_fragment = PromptFragment(
            id="medium",
            content="b" * 800,  # ~200 tokens
            language="python",
            priority=80,
            category="test"
        )
        
        huge_fragment = PromptFragment(
            id="huge",
            content="c" * 4000,  # ~1000 tokens (exceeds budget alone)
            language="python",
            priority=60,
            category="test"
        )
        
        mock_repository.find_by_language.return_value = [
            small_fragment,
            medium_fragment,
            huge_fragment
        ]
        mock_repository.find_universal.return_value = []
        
        # Execute
        fragments = selector_with_budget.select_for(context)
        
        # Verify: should exclude huge fragment
        assert len(fragments) == 2
        assert fragments[0].id == "small"
        assert fragments[1].id == "medium"
        assert "huge" not in [f.id for f in fragments]
```

**Run test (should FAIL)**

---

#### Step 2: Write Code (GREEN)

Update `FragmentSelector`:

```python
class FragmentSelector:
    """Service for selecting relevant fragments based on review context."""
    
    def __init__(
        self,
        repository: FragmentRepository,
        max_tokens: Optional[int] = None
    ):
        """Initialize selector.
        
        Args:
            repository: Fragment repository port
            max_tokens: Optional token budget limit
        """
        self._repository = repository
        self._budget_manager = TokenBudgetManager(max_tokens) if max_tokens else None
    
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
        sorted_fragments = sorted(all_fragments, key=lambda f: f.priority, reverse=True)
        
        # Apply budget constraints if configured
        if self._budget_manager:
            return self._apply_budget_constraints(sorted_fragments)
        
        return sorted_fragments
    
    def _apply_budget_constraints(
        self,
        fragments: list[PromptFragment]
    ) -> list[PromptFragment]:
        """Filter fragments to fit within token budget.
        
        Greedily selects highest priority fragments that fit.
        
        Args:
            fragments: Sorted fragments (highest priority first)
            
        Returns:
            Filtered list of fragments within budget
        """
        selected = []
        self._budget_manager.reset()
        
        for fragment in fragments:
            if self._budget_manager.fits_budget(fragment.content):
                self._budget_manager.consume(fragment.content)
                selected.append(fragment)
        
        return selected
```

**Run test (should PASS)**

---

## Part 3: Update Test Fixtures with Advanced Templates

### Update Python Fragment

Update `tests/fixtures/fragments/python/error-handling.md`:

```markdown
---
id: python-error-handling
language: python
priority: 80
category: error-handling
---

# Python Error Handling Review

Reviewing {{ file_paths|length }} Python file(s):
{% for file in file_paths %}
- `{{ file }}`
{% endfor %}

## Code Changes

```python
{{ diff }}
```

## Checks

Look for the following issues:

{% if 'except:' in diff %}
⚠️ **Bare except clause detected** - specify exception types
{% endif %}

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
```

---

## Part 4: Run Full Test Suite

```bash
# Run all tests
poetry run pytest -v

# Check coverage
poetry run pytest --cov=src --cov-report=term-missing --cov-report=html

# Performance check (unit tests should still be fast)
poetry run pytest tests/unit/ --durations=10
```

---

## Acceptance Criteria (Phase 4)

### ✅ AC-4.1: Jinja2 Renderer Implemented
- [ ] `Jinja2Renderer` implements `PromptRenderer` port
- [ ] Supports variables, conditionals, loops, filters
- [ ] Handles missing variables gracefully
- [ ] Integration tests pass

### ✅ AC-4.2: Token Budget Management
- [ ] `TokenBudgetManager` tracks token consumption
- [ ] `FragmentSelector` respects token budget
- [ ] High-priority fragments selected first when budget limited
- [ ] Budget exceeded errors are clear

### ✅ AC-4.3: PromptComposer Enhanced
- [ ] Accepts optional `PromptRenderer` in constructor
- [ ] Falls back to simple substitution if no renderer
- [ ] Works with Jinja2 for advanced templates
- [ ] Backward compatible with Phase 3 tests

### ✅ AC-4.4: Advanced Templates Work
- [ ] Test fixtures use Jinja2 features
- [ ] Conditionals render correctly
- [ ] Loops render correctly
- [ ] Variables are properly escaped

---

## Phase 4 Exit Criteria

**YOU CAN ONLY PROCEED TO PHASE 5 IF:**

1. ✅ All AC-4.x criteria are met
2. ✅ All tests pass (unit + integration)
3. ✅ Coverage remains ≥ 90%
4. ✅ Token budget prevents context overflow
5. ✅ Advanced templates render correctly

**Verification Commands:**
```bash
# Full test suite
poetry run pytest -v --cov=src --cov-fail-under=90

# Verify Jinja2 works
poetry run python -c "
from src.infrastructure.renderers import Jinja2Renderer
r = Jinja2Renderer()
result = r.render('Hello {{ name|upper }}', {'name': 'world'})
assert result == 'Hello WORLD'
print('✓ Jinja2 working')
"

# Verify token budget works
poetry run python -c "
from src.application.services import TokenBudgetManager
m = TokenBudgetManager(max_tokens=100)
m.consume('a' * 200)  # ~50 tokens
assert m.remaining() > 40
print('✓ Token budget working')
"
```

---

## Next Phase Preview

**Phase 5** will implement:
- Presentation layer (CLI interface)
- End-to-end tests (complete user workflows)
- Real PR integration (GitHub/Forgejo)
- LLM integration (Ollama)

**DO NOT START PHASE 5 UNTIL ALL PHASE 4 CRITERIA ARE MET.**
