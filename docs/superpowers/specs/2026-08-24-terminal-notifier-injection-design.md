# FakeNotifier Injection Seam — Design

Date: 2026-08-24

## Problem

The container hard-wires `LinuxNotifier` (notify-send), and `bootstrap()`
offered no way to override it. E2E tests therefore spawned real desktop
notifications during `uv run pytest`.

## Goals

- An explicit injection seam so tests can override the notifier.
- Test suite uses a recording `FakeNotifier` instead of the desktop notifier.

## Non-Goals

- New production notifier backends (terminal/logging adapter).
- Config-selectable notifier backends.
- Changing `NotifierPort` signatures.

## Design

### 1. Test fake

New file: `tests/fakes/fake_notifier.py` with `FakeNotifier(NotifierPort)` —
a real class implementing the port that records each call (`successes`,
`errors`) so tests assert observable side effects. No mocks.

### 2. Injection seam

- `CompositionRoot.__init__(config_path=None, *, notifier=None)` stores the
  optional override.
- `_wire_components()` uses the override when provided, otherwise
  `c.notifier`. Both `ApplicationComponents.notifier` and the `CliRunner`
  constructor receive the effective notifier; `PollingDaemon` picks it up via
  `run_daemon()` unchanged.
- `bootstrap(*, notifier=None)` forwards the parameter to `CompositionRoot`.

### 3. E2E usage

`tests/e2e/test_review_vcr.py` calls `bootstrap(notifier=FakeNotifier())`
and asserts after a successful review run that no error notifications were
recorded and exactly one success notification (`"Review complete"`) was.
No `notify-send` subprocess is spawned anywhere in the suite.

## Testing

- Unit: `FakeNotifier` records success and error notifications in order.
- Unit (seam): a notifier passed to `CompositionRoot` surfaces as
  `components.notifier`; absent override falls back to the container's.
- E2E: review flow asserts the recorded notifications on the injected fake.
- Full suite stays green.
