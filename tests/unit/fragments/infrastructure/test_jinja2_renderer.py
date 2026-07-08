"""Unit tests for Jinja2Renderer — pure string transformation, no I/O."""

import pytest

from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext
from pr_auto_reviewer.infrastructure.fragments.renderers import Jinja2Renderer

class TestJinja2Renderer:
    """Tests for Jinja2Renderer template rendering."""

    @pytest.fixture
    def renderer(self) -> Jinja2Renderer:
        """Create a fresh renderer for each test."""
        return Jinja2Renderer()

    def test_renders_simple_variables(self, renderer: Jinja2Renderer) -> None:
        """Renderer should substitute simple {{ var }} placeholders."""
        template = "Language: {{ language }}\nCode:\n{{ code }}"
        variables = {"language": "python", "code": "+def foo(): pass"}

        result = renderer.render(template, variables)

        assert result == "Language: python\nCode:\n+def foo(): pass"

    def test_renders_with_review_context(
        self, renderer: Jinja2Renderer,
    ) -> None:
        """Renderer should work with variables extracted from ReviewContext."""
        template = "Reviewing {{ language }} code:\n{{ diff }}"

        context = ReviewContext(
            language="python",
            file_paths=["test.py"],
            diff="+new code",
        )

        variables = {
            "language": context.language,
            "diff": context.diff,
            "code": context.diff,
        }

        result = renderer.render(template, variables)

        assert "Reviewing python code:" in result
        assert "+new code" in result

    def test_renders_conditionals(self, renderer: Jinja2Renderer) -> None:
        """Renderer should support Jinja2 {% if %} conditionals."""
        template = (
            "{% if has_tests %}"
            "Check test coverage."
            "{% else %}"
            "No tests found - this is a problem!"
            "{% endif %}"
        )

        result_with = renderer.render(template, {"has_tests": True})
        assert "Check test coverage" in result_with
        assert "No tests found" not in result_with

        result_without = renderer.render(template, {"has_tests": False})
        assert "No tests found" in result_without
        assert "Check test coverage" not in result_without

    def test_renders_loops(self, renderer: Jinja2Renderer) -> None:
        """Renderer should support Jinja2 {% for %} loops."""
        template = (
            "Files to review:\n"
            "{% for file in files %}"
            "- {{ file }}\n"
            "{% endfor %}"
        )

        variables = {"files": ["main.py", "utils.py", "tests.py"]}

        result = renderer.render(template, variables)

        assert "- main.py" in result
        assert "- utils.py" in result
        assert "- tests.py" in result

    def test_renders_filters(self, renderer: Jinja2Renderer) -> None:
        """Renderer should support Jinja2 filters like {{ var|upper }}."""
        template = "Language: {{ language|upper }}"
        variables = {"language": "python"}

        result = renderer.render(template, variables)

        assert "PYTHON" in result

    def test_handles_missing_variables_gracefully(
        self, renderer: Jinja2Renderer,
    ) -> None:
        """Renderer should use default() filter for missing variables."""
        template = (
            "Language: {{ language }}\n"
            "Optional: {{ optional_var|default('N/A') }}"
        )
        variables = {"language": "python"}

        result = renderer.render(template, variables)

        assert "Language: python" in result
        assert "Optional: N/A" in result

    def test_raises_on_undefined_variable_without_default(
        self, renderer: Jinja2Renderer,
    ) -> None:
        """Renderer should raise ValueError on truly undefined variables."""
        template = "Value: {{ missing_var }}"
        variables: dict[str, str] = {}

        with pytest.raises(ValueError, match="Template rendering failed"):
            renderer.render(template, variables)

    def test_raises_on_malformed_syntax(
        self, renderer: Jinja2Renderer,
    ) -> None:
        """Renderer should raise ValueError on invalid Jinja2 syntax."""
        template = "{% if true %}unclosed"

        with pytest.raises(ValueError, match="Template rendering failed"):
            renderer.render(template, {})
