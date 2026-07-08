from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_ARCHITECTURE_CONVENTIONS: dict[str, str] = {
    "hexagonal": (
        "This project follows a **hexagonal (ports & adapters)** architecture.\n"
        "- Keep domain logic completely isolated — no infrastructure imports.\n"
        "- Define interfaces (ports) in the domain/application layer; "
        "implement them in infrastructure/adapters.\n"
        "- Dependency inversion: higher-level layers must not depend on "
        "lower-level details.\n"
    ),
    "layered": (
        "This project follows a **layered architecture**.\n"
        "- Dependencies flow top-down: presentation → application → domain → infrastructure.\n"
        "- Each layer should only depend on the layer directly below it.\n"
        "- Shared kernel/value objects may be used across layers."
    ),
    "clean": (
        "This project follows a **clean architecture**.\n"
        "- Entities encapsulate enterprise-wide business rules.\n"
        "- Use cases orchestrate the flow of data to and from entities.\n"
        "- Interface adapters convert data between use cases and external agents.\n"
        "- The dependency rule: source code dependencies point inwards only."
    ),
    "onion": (
        "This project follows an **onion architecture**.\n"
        "- The domain model is at the centre, with no outward dependencies.\n"
        "- Application services surround the domain, orchestrating use cases.\n"
        "- Infrastructure lives at the outermost ring.\n"
        "- All dependencies point toward the centre."
    ),
    "mvc": (
        "This project follows an **MVC architecture**.\n"
        "- Models contain data and business logic.\n"
        "- Views handle presentation only; keep them thin.\n"
        "- Controllers handle input, coordinate models and views.\n"
        "- Avoid putting business logic in controllers or views."
    ),
    "cqrs": (
        "This project follows a **CQRS pattern**.\n"
        "- Commands mutate state; queries read state.\n"
        "- Command handlers should be separate from query handlers.\n"
        "- The read and write models may differ in structure."
    ),
}

_DIRECTORY_HINTS: dict[str, str] = {
    "tests/": "- Unit and integration tests live under ``tests/``.",
    "test/": "- Tests are colocated under ``test/``.",
    "spec/": "- Specifications/tests live under ``spec/``.",
    "docs/": "- Documentation lives under ``docs/``.",
    "scripts/": "- Build/CI helper scripts are in ``scripts/``.",
}

_TOOLING_HINTS: dict[str, str] = {
    ".pre-commit-config.yaml": (
        "- Pre-commit hooks are configured — ensure all code passes linting "
        "before committing."
    ),
    "Makefile": (
        "- A Makefile is present — use ``make`` targets for common tasks "
        "(build, test, lint)."
    ),
    "Dockerfile": (
        "- The project uses Docker — ensure any changes are compatible with "
        "the containerised environment."
    ),
    "docker-compose.yml": (
        "- Docker Compose is used — service definitions should remain "
        "consistent."
    ),
    ".github/": "- GitHub Actions CI is configured — ensure changes pass CI.",
    "pyproject.toml": (
        "- Python project metadata and tool config lives in ``pyproject.toml``."
    ),
    "Cargo.toml": "- Rust project — follow Cargo conventions.",
    "go.mod": "- Go module — follow Go conventions and module structure.",
    "package.json": "- Node.js project — follow npm/package conventions.",
}

_LANGUAGE_CONVENTIONS: dict[str, str] = {
    "python": (
        "- Follow PEP 8 style guide.\n"
        "- Use type hints consistently.\n"
        "- Prefer ``pathlib`` over ``os.path``.\n"
        "- Use ``dataclasses`` for plain data containers."
    ),
    "rust": (
        "- Follow Rust API guidelines.\n"
        "- Prefer ``Result`` over panicking.\n"
        "- Use ``clippy`` for linting and ``rustfmt`` for formatting."
    ),
    "go": (
        "- Follow Effective Go conventions.\n"
        "- Handle errors explicitly — don't ignore them.\n"
        "- Use ``gofmt`` for formatting."
    ),
}

class ConventionsGenerator:

    def generate(
        self,
        architecture_hint: str,
        tree_paths: list[str],
        language: str | None = None,
    ) -> str | None:
        """Generate conventions from directory structure and architecture.

        Args:
            architecture_hint: Architecture name from
                ``ArchitectureDetector.detect`` (e.g. ``"hexagonal"``).
            tree_paths: Repository file paths from the git tree API.
            language: Optional detected primary language.

        Returns:
            A Markdown conventions string, or ``None`` if nothing
            meaningful can be derived.
        """
        parts: list[str] = []

        if architecture_hint in _ARCHITECTURE_CONVENTIONS:
            parts.append(_ARCHITECTURE_CONVENTIONS[architecture_hint])

        dir_hints: list[str] = []
        for marker, hint in _DIRECTORY_HINTS.items():
            if any(p.startswith(marker) or f"/{marker}" in p for p in tree_paths):
                dir_hints.append(hint)
        if dir_hints:
            parts.append(
                "## Project Structure\n" + "\n".join(dir_hints)
            )

        tool_hints: list[str] = []
        for marker, hint in _TOOLING_HINTS.items():
            if marker in tree_paths or any(
                p.startswith(marker + "/") or p == marker for p in tree_paths
            ):
                tool_hints.append(hint)
        if tool_hints:
            parts.append(
                "## Tooling & CI\n" + "\n".join(tool_hints)
            )

        if language and language in _LANGUAGE_CONVENTIONS:
            parts.append(
                f"## {language.title()} Conventions\n"
                f"{_LANGUAGE_CONVENTIONS[language]}"
            )

        if not parts:
            return None

        logger.info(
            "ConventionsGenerator: produced %d sections for arch=%s",
            len(parts), architecture_hint,
        )
        return "\n\n".join(parts)
