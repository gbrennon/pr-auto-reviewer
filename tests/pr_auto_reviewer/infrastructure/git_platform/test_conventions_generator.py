from __future__ import annotations

from pr_auto_reviewer.infrastructure.context.conventions_generator import (
    ConventionsGenerator,
)


class TestConventionsGenerator:

    def test_generate_returns_none_for_empty_paths(self):
        g = ConventionsGenerator()
        result = g.generate(architecture_hint="unknown", tree_paths=[])
        assert result is None

    def test_generate_includes_hexagonal_architecture_conventions(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="hexagonal",
            tree_paths=["src/main.py", "tests/test_main.py"],
        )
        assert result is not None
        assert "hexagonal" in result.lower()
        assert "ports" in result.lower()

    def test_generate_includes_layered_architecture_conventions(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="layered",
            tree_paths=["src/presentation/views.py"],
        )
        assert result is not None
        assert "layered" in result.lower()

    def test_generate_includes_mvc_architecture_conventions(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="mvc",
            tree_paths=["src/views/index.py"],
        )
        assert result is not None
        assert "MVC" in result

    def test_generate_unknown_architecture_still_produces_structure_hints(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="unknown",
            tree_paths=["tests/test_app.py", "docs/readme.md", "pyproject.toml", ".pre-commit-config.yaml"],
        )
        assert result is not None
        assert "Project Structure" in result
        assert "tests/" in result
        assert "docs/" in result
        assert "Tooling" in result
        assert "pre-commit" in result.lower()

    def test_generate_detects_test_directories(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="unknown",
            tree_paths=["tests/unit/test_core.py"],
        )
        assert result is not None
        assert "tests/" in result

    def test_generate_detects_colocated_test_directory(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="unknown",
            tree_paths=["test/foo_test.py"],
        )
        assert result is not None
        assert "test/" in result

    def test_generate_detects_tooling_files(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="unknown",
            tree_paths=["Dockerfile", "docker-compose.yml", "Makefile"],
        )
        assert result is not None
        assert "Tooling" in result
        assert "Docker" in result
        assert "Makefile" in result
        assert "Docker Compose" in result

    def test_generate_detects_language_config_files(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="unknown",
            tree_paths=["pyproject.toml", "src/main.py"],
        )
        assert result is not None
        assert "pyproject.toml" in result

    def test_generate_includes_language_conventions_when_provided(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="unknown",
            tree_paths=["src/main.py"],
            language="python",
        )
        assert result is not None
        assert "Python" in result
        assert "PEP 8" in result
        assert "type hints" in result.lower()

    def test_generate_includes_rust_conventions(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="unknown",
            tree_paths=["src/main.rs"],
            language="rust",
        )
        assert result is not None
        assert "Rust" in result
        assert "clippy" in result

    def test_generate_combines_all_hint_types(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="clean",
            tree_paths=[
                "src/domain/models.py",
                "src/use_cases/create_user.py",
                "src/infrastructure/db.py",
                "tests/test_models.py",
                "pyproject.toml",
                ".pre-commit-config.yaml",
                "Makefile",
            ],
            language="python",
        )
        assert result is not None
        assert "clean architecture" in result.lower()
        assert "Project Structure" in result
        assert "Tooling" in result
        assert "Python" in result

    def test_generate_handles_cqrs_architecture(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="cqrs",
            tree_paths=["src/commands/create.py", "src/queries/list.py"],
        )
        assert result is not None
        assert "CQRS" in result

    def test_generate_handles_onion_architecture(self):
        g = ConventionsGenerator()
        result = g.generate(
            architecture_hint="onion",
            tree_paths=["src/core/models.py", "src/application/services.py"],
        )
        assert result is not None
        assert "onion" in result.lower()
