"""ArchitectureDetector — infrastructure utility, not a port.

Inspects repository file tree entries for known layout patterns
to produce an architecture hint string for RepositoryContext.
"""

from __future__ import annotations


class ArchitectureDetector:
    """Inspects file paths for known layout patterns."""

    _ARCHITECTURES: list[tuple[str, list[str], list[str]]] = [
        (
            "cqrs",
            ["src/commands/", "commands/", "src/queries/", "queries/"],
            ["src/commands/", "commands/", "src/queries/", "queries/"],
        ),
        (
            "mvc",
            ["src/views/", "views/", "src/templates/", "templates/"],
            ["src/controllers/", "controllers/", "src/handlers/", "handlers/", "src/routes/", "routes/", "src/models/", "models/"],
        ),
        (
            "onion",
            ["src/core/", "core/"],
            ["src/application/", "application/", "src/infrastructure/", "infrastructure/"],
        ),
        (
            "layered",
            ["src/presentation/", "presentation/"],
            ["src/domain/", "domain/", "src/application/", "application/", "src/infrastructure/", "infrastructure/"],
        ),
        (
            "clean",
            ["src/use_cases/", "use_cases/", "src/usecases/", "usecases/"],
            ["src/domain/", "domain/", "src/infrastructure/", "infrastructure/"],
        ),
        (
            "hexagonal",
            ["src/domain/", "domain/"],
            ["src/application/", "application/", "src/adapters/", "adapters/", "src/ports/", "ports/"],
        ),
    ]

    def detect(self, tree_paths: list[str]) -> str:
        """Return an architecture hint based on file tree traversal.

        Args:
            tree_paths: List of path strings from the git tree API
                (e.g. 'src/domain/__init__.py', 'src/main.rs').

        Returns:
            Architecture hint string, e.g. 'hexagonal', or 'unknown'.
        """
        combined = "\n".join(tree_paths)

        for name, required_markers, optional_markers in self._ARCHITECTURES:
            has_required = any(m in combined for m in required_markers)
            if not has_required:
                continue

            optional_matches = sum(1 for m in optional_markers if m in combined)
            if optional_matches >= 1:
                return name

        return "unknown"
