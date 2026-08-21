# AI Guardrails — Architecture Rules

This file defines the **durable boundaries** of this codebase for AI
agents: the architecture pattern, layer responsibilities, and coding
conventions that stay true regardless of feature details. Details that
change with the code (endpoints, adapters, flow diagrams, mapping
tables) live in `docs/` — if a rule here seems wrong, re-read the
referenced documents and the actual code before changing the rule.

- `docs/architecture.md` — architecture rules, layer responsibilities,
  invariants, and how to change each layer
- `docs/review-flow-architecture.md` — runtime flow and adapter wiring
- `docs/verdict-event-mapping.md` — verdict-to-platform-event mapping
  and `CodeReview` construction danger zones

---

## 1. Architecture Invariants

### 1.1 Hexagonal Boundaries

Four layers; dependencies point **inward**:

```
Domain ──── Application ──── Infrastructure ──── Presentation
```

| Rule | Where to check |
|---|---|
| Domain + Application have **zero** imports from Infrastructure or Presentation | `grep -r "infrastructure\|presentation" src/pr_auto_reviewer/domain src/pr_auto_reviewer/application` |
| All I/O goes through `Protocol`-based outbound ports in `application/ports/outbound/` | the port directory |
| Infrastructure *implements* ports; it never defines new public interfaces Application depends on | `infrastructure/` |
| DI wiring happens **only** in `presentation/composition_root.py` (through the DI container) | the composition root |

### 1.2 Layer Responsibilities

- **Domain** — entities, value objects (all `frozen=True`), domain
  services, messages (commands/events), the agent phase model, and
  exceptions. Pure business logic; no I/O of any kind.
- **Application** — use cases, inbound/outbound ports, serializers,
  event handlers. Orchestration only; it never instantiates or imports
  concrete infrastructure.
- **Infrastructure** — adapters implementing the outbound ports (git
  hosts, LLM, persistence, command bus, conversation logging, tool
  execution, prompt fragments/renderers). Platform-specific behavior
  lives here, behind its port.
- **Presentation** — CLI runner, polling daemon, and the DI
  container/composition root. The only layer that wires implementations
  to ports.

Read `docs/architecture.md` before adding or moving code between layers.

### 1.3 Frozen Domain Objects

Domain value objects are `frozen=True` dataclasses. "Mutation" means
`dataclasses.replace()`, never attribute assignment. **DO NOT** unfreeze
them, add mutable fields, or add side-effectful `__post_init__`.

### 1.4 Port Signatures Are Contracts

Outbound ports are `Protocol` classes; their method signatures are the
contract between Application and Infrastructure. Changing a method name,
parameter count, or return type requires updating **every** adapter and
**every** test fake that implements the port — in the same change.

---

## 2. Coding Conventions

- **No comments — docstrings only.** Comments, linter/type-checker
  suppressions (`# noqa`, `# type: ignore`, `# pyright: ignore`),
  pragmas, and waivers are prohibited in Python source. When a linter or
  type checker flags a line, fix the code (narrowing, protocol classes,
  generics, restructure) — never suppress. Pre-existing suppressions are
  technical debt; remove them when touching the file.
- **Classes only — no standalone functions.** Module-level `def` becomes
  a class method (static, class, or instance); nested functions become
  private methods. Inline `lambda` arguments to higher-order functions
  are allowed. Pre-existing standalone functions are technical debt;
  convert them when touching the file.
- **Suggestions are architecture-only.** `CodeReview.suggestions` come
  exclusively from the phase named by `ReviewPlan.suggestions_phase_id`
  (the architecture phase in the production plan). Never promote
  rejected or dropped items into suggestions, and never emit
  code-snippet `current_code`/`suggested_fix` dumps in suggestions —
  they are design/architecture improvements, not re-stated issues.
- **Comprehensions over loops.** Prefer list, dict, and set
  comprehensions over manual accumulation loops when they read clearly.
  Keep them simple and side-effect free — one level of nesting, no
  statements inside. If a comprehension becomes hard to read, extract a
  small helper method instead of forcing it.
- **Code style.** Expressive, intention-revealing names; short lines and
  small methods; no magic values — use named constants or enums. When
  the configured linter flags style, fix the code, never suppress.
- **Program to interfaces, not implementations.** Design, read, and
  change code against the ports (the `Protocol` contracts), value-object
  fields, and public signatures — what the caller needs — not against
  adapter internals. Prefer touching a port and its contract over a
  concrete implementation.
- **Read interfaces, not implementations.** Prefer reading port
  signatures, value-object definitions, and docstrings over
  implementation bodies. Open an implementation only when the task
  actually requires it: fixing a bug, writing tests for it, or
  explaining/verifying how it works. Reading bodies you don't need
  burns tokens.
- **Consult official docs, never guess.** When implementing or
  refactoring code that interacts with an external dependency (a
  platform API, a third-party library or service) and that dependency is
  not available locally, read its official documentation on the web
  instead of guessing at its behavior. If the user provides a local path
  (a vendored copy, a checkout, docs on disk), read the path you were
  given rather than searching the web.

---

## 3. Testing

- **Always write tests.** New behavior and bug fixes ship with tests
  that exercise the behavior. Untested changes do not land.
- **Test behavior, not internals.** Assert observable outcomes — return
  values, published payloads, persisted state, side effects the caller
  sees. Do not assert call counts, private attribute access, or
  internal implementation steps.
- **Integrate with the real source, fake the seams.** Infrastructure
  tests run against the actual external surface (real Forgejo/GitHub
  API shapes, real Ollama, real files and clones) wired through
  **fakes/stubs you own** — never mocks of external services.
- **Don't mock what you don't own.** Mocks are allowed only for pure,
  in-repo implementations you own with deterministic behavior. External
  systems (HTTP, LLM, filesystem, git) are never mocked wholesale —
  implement the port with a fake instead.
- **Fakes over mocks for ports.** When a test needs a collaborator that
  implements a port, write a small fake (a real class implementing the
  port) — not a `MagicMock`.

---

## 4. Git Hooks

- **Never skip git hooks.** Pre-commit, pre-push, and other hooks always
  run. A failing hook means the change is not ready — fix the underlying
  issue, never bypass with `--no-verify`.

---

## 5. Contracts That Must Not Change Casually

- **Verdict preservation.** Reconstructing a `CodeReview` from LLM
  output must carry `verdict=review.verdict`, never a hardcoded verdict.
  The verdict-to-event mapping is a single source of truth; adding a
  verdict is a breaking change across both platforms (see
  `docs/verdict-event-mapping.md`).
- **Blocking threshold.** `ItemSeverity.is_blocking` (CRITICAL/MAJOR, or
  SECURITY category) decides formal review vs comment-only publishing.
  Changing it changes the published review flow on every platform.
- **Platform API payloads.** Endpoints, headers, and review payload
  schemas are verified against official upstream documentation; quirks
  the hosts actually exhibit are preserved, not "fixed" (see
  `docs/review-flow-architecture.md` and `docs/verdict-event-mapping.md`).

---

## 6. When You CAN Change Things

- **Infrastructure adapters** — when an upstream API deprecates an
  endpoint (verified against official docs) or you add a new adapter.
- **Domain entities** — when a business requirement demands it and the
  change preserves compatibility with existing ports.
- **Application services** — when adding deterministic steps that do
  not change verdict or item semantics.

**Always** run the full test suite after any change:

```bash
python -m pytest tests/ -x -q
```
