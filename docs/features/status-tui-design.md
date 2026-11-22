# Live Textual Status Dashboard

## Goal

Make `pr-auto-reviewer status` an interactive, real-time terminal dashboard while preserving the existing status data and application boundaries.

## Architecture

Textual is presentation-only:

- Domain and application layers remain unaware of Textual.
- The application exposes a structured immutable status snapshot containing daemon state, active review progress, allowed repositories, API capabilities, and errors.
- Existing outbound ports remain the source of runtime data.
- Presentation owns the Textual application, widgets, layout, refresh scheduling, keyboard handling, and conversion from the snapshot to widgets.
- The CLI dispatches `status` to the dashboard and retains a plain-text path for non-interactive or scripted use.

## User experience

`pr-auto-reviewer status` launches a live dashboard and refreshes once per second. The screen contains:

- Header with daemon state, PID, mode, and cycle.
- Main state panel showing idle, reviewing, error, or stopped state.
- Active review panel showing repository, pull request, phase, agent, turn, and latest action.
- Allowed-repository panel grouped by platform.
- API-capability panel showing roles, scopes, and active suspension countdowns.
- Footer showing refresh timing and `q`/`Ctrl+C` quit instructions.

Missing status data, stopped daemons, and read errors render as explicit states rather than crashing the UI.

## Data flow

1. The Textual app starts from the CLI status command.
2. A presentation adapter requests the structured snapshot from the application service.
3. Widgets are updated from the snapshot on a one-second timer.
4. The app exits cleanly on `q` or `Ctrl+C`.
5. Plain text remains available through a non-interactive fallback for redirected output or environments without a usable terminal.

## Dependency and compatibility

Textual is added as a runtime dependency. Imports are restricted to presentation modules. Existing service commands and daemon behavior are unchanged. The status command remains usable in CI and shell scripts through the plain-text fallback.

## Testing

- Application tests verify snapshot contents for running, reviewing, stopped, missing-status, capability, suspension, and error states.
- Presentation tests verify widget content and state transitions using owned fakes, without coupling application tests to Textual.
- CLI tests verify interactive dispatch and non-interactive fallback selection.
- Existing full-suite tests must continue to pass.

## Delivery

Implement in a dedicated `feat/status-tui` worktree and pull request. Run the full test suite, install from the feature worktree, restart the user service, verify the live dashboard and fallback, address review findings through the repository maintenance loop, merge the PR, remove the worktree, and update global agent state.
