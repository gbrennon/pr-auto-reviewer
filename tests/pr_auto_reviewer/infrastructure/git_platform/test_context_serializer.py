from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.git_platform.context_serializer import (
    ContextSerializer,
)


def _ctx(**kwargs):
    return RepositoryContext(architecture_hint=kwargs.pop("architecture_hint", ""), **kwargs)


class TestContextSerializer:

    def test_serialize_when_empty_context_then_returns_none(self):
        assert ContextSerializer().serialize(_ctx()) is None

    def test_serialize_when_architecture_hint_then_includes_it(self):
        result = ContextSerializer().serialize(_ctx(architecture_hint="clean"))
        assert "## Architecture: clean" in result

    def test_serialize_when_conventions_then_includes_them(self):
        result = ContextSerializer().serialize(_ctx(conventions="Use 4 spaces"))
        assert "## Conventions" in result
        assert "Use 4 spaces" in result

    def test_serialize_when_repository_structure_then_includes_it(self):
        result = ContextSerializer().serialize(_ctx(repository_structure="src/\ntests/"))
        assert "## Repository Structure" in result
        assert "src/" in result

    def test_serialize_when_pr_title_then_includes_it(self):
        result = ContextSerializer().serialize(_ctx(pr_title="Add login"))
        assert "## PR Title" in result
        assert "Add login" in result

    def test_serialize_when_pr_description_then_includes_it(self):
        result = ContextSerializer().serialize(_ctx(pr_description="OAuth2"))
        assert "## PR Description" in result
        assert "OAuth2" in result

    def test_serialize_when_python_version_guidance_then_includes_it(self):
        version_guidance = "## Python Version\nTargets 3.9+"
        result = ContextSerializer().serialize(_ctx(), python_version=version_guidance)
        assert version_guidance in result

    def test_serialize_when_commit_messages_then_includes_them(self):
        result = ContextSerializer().serialize(
            _ctx(), commit_messages=["feat: add login", "fix: null pointer"]
        )
        assert "## Commit Messages" in result
        assert "- feat: add login" in result
        assert "- fix: null pointer" in result

    def test_serialize_when_all_fields_then_joined_correctly(self):
        result = ContextSerializer().serialize(
            _ctx(architecture_hint="hexagonal", pr_title="Refactor core"),
            commit_messages=["feat: initial"],
        )
        assert result is not None
        assert result.startswith("## Architecture: hexagonal")
        assert result.endswith("- feat: initial")
