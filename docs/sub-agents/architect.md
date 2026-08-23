# Architect

The architect enforces architecture good practices and searches for
software architecture misses. It reads the source to identify
violations, coupling, and poor implementations, focusing on structure
rather than behavior.

## Interaction

Reviews its assigned phase with read_file / search_codebase /
list_directory / run_git, searching for what the change violates rather
than what it does: architecture-rule violations, coupling, bad
practices, anti-patterns, God classes, leaky abstractions, and
duplicated logic. Verifies that domain logic stays free of
infrastructure imports and that interfaces are narrow and segregated.

## Responsibility

Enforce architecture good practices and search for software
architecture misses.

## Behavior

Read source code to identify misses, violations, coupling, and poor
implementations.

## Typical checks

1. Domain logic free of infrastructure imports.
2. Interfaces (Protocols/ABCs) narrow and segregated.
3. New code follows existing patterns and conventions.
4. No God classes, deep coupling, or circular dependencies.
5. Composition over inheritance where appropriate.
6. Immutability conventions: frozen dataclasses, no side-effectful init.

The architect phase is also the sole producer of
`CodeReview.suggestions` — see the [suggestion policy](../architecture.md).

## Relation to other roles

The manager assigns the phase; the advisor keeps the architect on
structure; the engineer focuses on behavior so the two do not duplicate
findings.