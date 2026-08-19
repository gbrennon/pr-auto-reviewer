# Architecture

Durable architecture reference for the pr-auto-reviewer application.
This document describes *rules* — layer responsibilities, dependency
direction, and invariants that hold regardless of feature details.
Companion documents: `review-flow-architecture.md` (runtime flow and
adapter wiring) and `verdict-event-mapping.md` (verdict-to-platform
event mapping).

---

## 1. Hexagonal Boundaries

The application is built as a hexagonal (ports & adapters) architecture
with four layers. Dependencies point **inward** — inner layers never
import from outer ones.

```
Domain ──── Application ──── Infrastructure ──── Presentation
  |              |                |                    |
entities      use cases       HTTP/LLM/FS            CLI/daemon
value objs    ports           adapters               DI wiring
```

| Dependency rule | Enforced by |
|---|---|
| Domain + Application import nothing from Infrastructure or Presentation | repository grep: `grep -r "infrastructure\|presentation" src/pr_auto_reviewer/domain src/pr_auto_reviewer/application` |
| All I/O goes through `Protocol`-based outbound ports in the application layer | the `application/ports/outbound/` directory |
| Infrastructure implements ports; it never defines new public interfaces Application depends on | code review |
| Dependency injection happens only in the presentation layer's composition root | `presentation/composition_root.py` |

---

## 2. Layer Responsibilities

### 2.1 Domain

Pure business logic. No I/O, no HTTP, no filesystem, no LLM calls.

- **Entities** — mutable-free state with behavior (`ReviewItem`, `PullRequest`).
- **Value objects** — `frozen=True` dataclasses (`CodeReview`,
  `ReviewVerdict`, `ItemSeverity`, `PullRequestDiff`, …). Mutation means
  `dataclasses.replace()`, never attribute assignment. Frozen objects
  must not gain mutable fields or side-effectful `__post_init__`.
- **Domain services** — stateless validators/factories
  (`ReviewItemFactory`, `IssueCommandParser`, …).
- **Messages** — commands (intent) and events (facts) that cross
  application boundaries.
- **Agent phase model** — `SubAgent` roles, `ReviewPlan`, `ReviewPhase`,
  `PhaseResult`, tool-call primitives. A `ReviewPlan` names the ordered
  phases and, via `suggestions_phase_id`, which phase's suggestions feed
  the final review.
- **Exceptions** — hierarchy rooted at `DomainError`.

### 2.2 Application

Orchestration only — it decides *what* to do, never *how* the outside
world does it.

- **Use cases / services** — inbound ports (use-case interfaces) and their
  implementations; they coordinate domain objects and dispatch commands.
- **Outbound ports** — `Protocol` classes declaring the I/O the
  application needs (changeset fetch, LLM review, review publish,
  persistence, conversation logging, …). Method signatures are contracts.
- **Serializers / handlers** — turn domain objects into payloads or
  react to events.

An application service never instantiates an infrastructure object; it
receives port implementations through its constructor.

### 2.3 Infrastructure

Adapters that implement the outbound ports, plus concrete
implementations of infrastructure concerns:

- Git host clients (Forgejo/Codeberg, GitHub) and their publishers/readers.
- LLM adapters (Ollama) and prompt fragments/renderers.
- Persistence (JSON file repository, rate-limit/token/state stores).
- Command bus, conversation logger, tool execution, notifiers.

An adapter owns platform-specific details (endpoints, headers, quirks)
behind its port. When a port signature changes, every adapter and every
test fake implementing it must change in the same commit.

### 2.4 Presentation

Entry points only:

- CLI runner and polling daemon.
- The DI container and composition root — the **only** place concrete
  implementations are wired to ports.

---

## 3. Review Pipeline (End to End)

1. CLI/daemon constructs a `ReviewPullRequestCommand` and invokes the
   review use case.
2. The use case loads the PR, fetches the diff, composes the review
   context/prompt, then runs a review plan: the multi-phase orchestrator
   walks `plan.phases`, and for each phase runs an agent conversation
   (multi-turn LLM loop with tool access: read_file, search_codebase,
   list_directory, run_git).
3. Each phase yields a `PhaseResult` (items, verdict, reason, summary,
   suggestions, praise).
4. The aggregator deduplicates items into a `CodeReview`.
5. Findings verification drops items that do not survive re-checking
   against source.
6. The publisher renders the body and posts a formal review or comment
   (platform-specific), and the use case persists the PR.

### Suggestion Policy

`CodeReview.suggestions` is **architecture-only**: the plan's
`suggestions_phase_id` names the phase whose `llm_suggestions` populate
the final suggestions (in the production plan, the architecture
phase). The other phases emit no suggestions, and rejected/dropped items
are never promoted into suggestions — a suggestion is an improvement
(design, coupling, patterns, layering), never a re-stated issue.

### Sub-Agent Phases

Each phase is a `ReviewPhase` whose `system_prompt` comes from a prompt
fragment (`infrastructure/fragments/content/universal/*.md`). Roles are
expressed through these prompts; the `SubAgent` role classes in the
domain model describe intent (role, responsibility, behavior) and stay
in sync with the fragments. To change what a sub-agent does, edit its
fragment; to change which phase produces what, edit the plan builder.

---

## 4. Core Invariants

1. **Domain value objects are frozen.** Unfreezing, mutable fields, or
   side-effectful `__post_init__` are breaking changes.
2. **Port signatures are contracts.** Renaming/adding/removing a method
   on an outbound port requires updating all adapters and test fakes.
3. **Verdict preservation.** When reconstructing a `CodeReview` from LLM
   output, always carry `verdict=review.verdict` — never hardcode
   `APPROVED`. See `verdict-event-mapping.md`.
4. **Blocking threshold.** `ItemSeverity.is_blocking` (CRITICAL/MAJOR,
   or SECURITY category) decides formal review vs comment-only output.
5. **No comments, classes only.** Python source uses docstrings, not
   comments; behavior lives in classes, not standalone functions. See
   the AI guardrails file at the repo root.
6. **External contracts are verified upstream.** Platform API behavior
   (endpoints, headers, review payloads, rate-limit headers) matches the
   official docs; quirks the hosts actually exhibit are preserved, not
   "fixed" — documented in `review-flow-architecture.md`.

---

## 5. Changing Things

| You want to… | Change |
|---|---|
| Tweak a review phase's instructions | The phase prompt fragment under `infrastructure/fragments/content/universal/` |
| Add/remove a review phase | The plan builder (prompt fragments + phase list); register the fragment |
| Change what suggestions contain | The suggestion phase prompt (fragment) + the orchestrator's suggestion source (`plan.suggestions_phase_id`) |
| Add an LLM capability | The agent conversation loop and its tool registry |
| Add a git-host | A new adapter set implementing the platform ports |
| Change persistence | The repository adapter — never the domain entity |
| Change wiring | The composition root / DI container |


Every change ships with tests and a full-suite run:

```bash
uv run pytest
```

That command will also show in terminal the test coverage report.
