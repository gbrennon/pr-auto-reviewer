from __future__ import annotations

class ArchitectureDetector:
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
        source_paths = [
            p for p in tree_paths
            if not p.startswith(("tests/", "test/", "scripts/", "script/"))
        ]
        combined = "\n".join(source_paths)

        for name, required_markers, optional_markers in self._ARCHITECTURES:
            has_required = any(m in combined for m in required_markers)
            if not has_required:
                continue

            optional_matches = sum(1 for m in optional_markers if m in combined)
            if optional_matches >= 1:
                return name

        return "unknown"
