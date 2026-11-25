# Tests

```
tests/
├── conftest.py
├── pr_auto_reviewer/
│   ├── test_e2e_review_flow.py
│   ├── test_multilang_review_verdict.py
│   ├── test_e2e_review_verdict.py
│   ├── presentation/
│   │   ├── test_composition_root.py
│   │   ├── ports/
│   │   └── cli/
│   ├── application/
│   │   ├── ports/
│   │   └── services/
│   ├── domain/
│   │   ├── value_objects/
│   │   ├── entities/
│   │   └── services/
│   ├── infrastructure/
│   │   ├── config/
│   │   ├── client/
│   │   ├── local_repository/
│   │   ├── llm/
│   │   ├── fragments/
│   │   ├── review_publishers/
│   │   ├── git_platform/
│   │   │   ├── multi_platform/
│   │   │   └── ...
│   │   ├── command_bus/
│   │   └── notifier/
```

## Key Principles

- **Domain Layer**: Pure business logic, no external dependencies, all value objects are `frozen=True`
- **Application Layer**: Use cases orchestrate domain logic and call outbound ports
- **Infrastructure Layer**: Implements outbound ports (HTTP clients, LLM, file I/O, git)
- **Presentation Layer**: CLI, daemon, DI wiring (CompositionRoot)
- **Dependency Rule**: Inner layers never import from outer layers
- **Ports as Protocols**: All outbound ports are `Protocol` classes (interfaces)
- **CQRS**: Commands (writes) and queries (reads) are separate
- **Events**: Domain events published via in-memory command bus
- **Frozen Value Objects**: All domain value objects are immutable (`frozen=True`)
- **DI Container**: Centralized wiring in `CompositionRoot` / `Container`
