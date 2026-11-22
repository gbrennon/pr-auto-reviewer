# Live Textual Status Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make `pr-auto-reviewer status` launch a live Textual dashboard backed by structured application status data.

**Architecture:** The application will expose an immutable `DaemonStatusSnapshot`; the existing text formatter will consume that snapshot. The presentation layer will own all Textual imports and render the snapshot through a refreshable dashboard. The CLI will choose the dashboard for interactive terminals and retain plain text for redirected/non-TTY output.

**Tech Stack:** Python 3.14, Textual, argparse, dataclasses, pytest.

## Global Constraints

- Textual imports and types are restricted to `src/pr_auto_reviewer/presentation/`.
- Domain and application layers remain Textual-free.
- Refresh interval is one second.
- `q` and `Ctrl+C` exit the dashboard cleanly.
- Missing, stopped, and error states render explicitly without crashing.
- Existing plain-text status output remains available for non-interactive use.
- New behavior must have tests and the full suite must pass.
- Work proceeds in `feat/status-tui` and through the repository maintenance loop.

## File map

- Modify `pyproject.toml`: add the Textual runtime dependency.
- Create `src/pr_auto_reviewer/application/dtos/daemon_status_snapshot.py`: immutable application DTO.
- Modify `src/pr_auto_reviewer/application/services/show_status_service.py`: expose `snapshot()` and make `show_status()` format that snapshot.
- Create `tests/pr_auto_reviewer/application/services/test_daemon_status_snapshot.py`: snapshot behavior tests.
- Create `src/pr_auto_reviewer/presentation/status_dashboard.py`: Textual app and widgets.
- Modify `src/pr_auto_reviewer/presentation/composition_root/composition_root.py`: expose the structured status provider.
- Modify `src/pr_auto_reviewer/presentation/composition_root/_shared.py`: export the provider used by the CLI.
- Modify `src/pr_auto_reviewer/cli.py`: select dashboard versus plain output.
- Create `tests/pr_auto_reviewer/presentation/test_status_dashboard.py`: dashboard rendering and refresh tests.
- Modify `tests/pr_auto_reviewer/presentation/cli/test_cli_main.py`: CLI dispatch and fallback tests.

---

### Task 1: Add the structured application snapshot

**Files:**
- Modify: `pyproject.toml`
- Create: `src/pr_auto_reviewer/application/dtos/daemon_status_snapshot.py`
- Modify: `src/pr_auto_reviewer/application/services/show_status_service.py`
- Create: `tests/pr_auto_reviewer/application/services/test_daemon_status_snapshot.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class DaemonStatusSnapshot:
    runtime_status: DaemonRuntimeStatus | None
    daemon_alive: bool
    allowed_repositories: tuple[str, ...]
    capabilities: tuple[ApiAccessCapability, ...]
```

`ShowStatusService.snapshot() -> DaemonStatusSnapshot` reads the runtime store, checks the PID, resolves configured repositories, and reads capabilities. `ShowStatusService.show_status() -> str` remains unchanged externally and formats the snapshot.

- [ ] **Step 1: Add the failing snapshot tests.** Test running, missing status, stopped PID, and capability data using owned fakes for the runtime state and capability query.
- [ ] **Step 2: Run the focused tests and verify failure.**

```bash
uv run pytest tests/pr_auto_reviewer/application/services/test_daemon_status_snapshot.py -q
```

Expected: collection or assertion failures because the DTO and `snapshot()` method do not exist.

- [ ] **Step 3: Add Textual to `pyproject.toml` and implement the frozen DTO.** Keep the DTO free of Textual imports.
- [ ] **Step 4: Refactor `ShowStatusService` to build one snapshot and reuse it in the plain formatter.** Preserve all existing output strings and capability grouping behavior.
- [ ] **Step 5: Run focused tests and the existing formatter tests.**

```bash
uv run pytest tests/pr_auto_reviewer/application/services/test_daemon_status_snapshot.py tests/pr_auto_reviewer/application/services/test_show_status_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add pyproject.toml src/pr_auto_reviewer/application/dtos/daemon_status_snapshot.py src/pr_auto_reviewer/application/services/show_status_service.py tests/pr_auto_reviewer/application/services/test_daemon_status_snapshot.py
git commit -m "feat(status): expose structured daemon snapshot"
```

### Task 2: Expose a presentation status provider

**Files:**
- Modify: `src/pr_auto_reviewer/presentation/composition_root/composition_root.py`
- Modify: `src/pr_auto_reviewer/presentation/composition_root/_shared.py`
- Create or modify: `tests/pr_auto_reviewer/presentation/test_status_provider.py`

**Interfaces:**

```python
def status_snapshot(self) -> DaemonStatusSnapshot:
    """Return current structured daemon status."""
```

The composition root will construct the same `ShowStatusService` inputs currently used by `show_status()`, then expose `status_snapshot()` for presentation consumers. The provider must not expose infrastructure concrete classes outside the composition root.

- [ ] **Step 1: Add a test proving the shared composition entry point returns a snapshot with the current state.** Use a temporary state directory and owned fakes where the existing composition seams permit them.
- [ ] **Step 2: Run the focused test and verify failure.**

```bash
uv run pytest tests/pr_auto_reviewer/presentation/test_status_provider.py -q
```

Expected: missing provider failure.

- [ ] **Step 3: Implement `CompositionRoot.status_snapshot()` and the shared export.** Refactor `show_status()` to call `snapshot()` and the existing formatter, avoiding duplicate wiring.
- [ ] **Step 4: Run provider and existing CLI/composition tests.**

```bash
uv run pytest tests/pr_auto_reviewer/presentation/test_status_provider.py tests/pr_auto_reviewer/presentation/cli/test_cli_main.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/pr_auto_reviewer/presentation/composition_root/composition_root.py src/pr_auto_reviewer/presentation/composition_root/_shared.py tests/pr_auto_reviewer/presentation/test_status_provider.py
git commit -m "feat(status): expose presentation snapshot provider"
```

### Task 3: Build the presentation-only Textual dashboard

**Files:**
- Create: `src/pr_auto_reviewer/presentation/status_dashboard.py`
- Create: `tests/pr_auto_reviewer/presentation/test_status_dashboard.py`

**Interfaces:**

```python
class StatusDashboard(App[None]):
    def __init__(self, status_provider: Callable[[], DaemonStatusSnapshot]) -> None: ...
    def compose(self) -> ComposeResult: ...
    def refresh_status(self) -> None: ...
```

The module may import Textual. It must consume only the application DTO and a callable provider. It will use `Header`, `Footer`, `Static`, and layout containers; `set_interval(1.0, self.refresh_status)` will update widgets. Widget IDs will be stable so tests can inspect them.

- [ ] **Step 1: Add dashboard tests for idle, reviewing, stopped, missing, capability, and error states.** Use Textual's test pilot and a deterministic fake provider; assert visible text and that `q` exits.
- [ ] **Step 2: Run the focused tests and verify failure.**

```bash
uv run pytest tests/pr_auto_reviewer/presentation/test_status_dashboard.py -q
```

Expected: import or assertion failures because the app does not exist.

- [ ] **Step 3: Implement `StatusDashboard`.** Render explicit state text, active review details, repositories, capabilities, last error, refresh time, and quit instructions. Catch provider failures and render an error state instead of raising from the timer callback.
- [ ] **Step 4: Run the dashboard tests.**

```bash
uv run pytest tests/pr_auto_reviewer/presentation/test_status_dashboard.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/pr_auto_reviewer/presentation/status_dashboard.py tests/pr_auto_reviewer/presentation/test_status_dashboard.py
git commit -m "feat(status): add live textual dashboard"
```

### Task 4: Wire CLI interactive and plain-text modes

**Files:**
- Modify: `src/pr_auto_reviewer/cli.py`
- Modify: `tests/pr_auto_reviewer/presentation/cli/test_cli_main.py`

**Interfaces:**

`status` will call `StatusDashboard(status_snapshot).run()` when stdout is a TTY. When stdout is not a TTY, it will print the existing plain status string and return. The dashboard module remains presentation-only; the CLI does not reconstruct status data itself.

- [ ] **Step 1: Add tests for TTY dashboard dispatch and non-TTY plain output.** Patch only owned presentation seams and assert observable output/dispatch, not private implementation calls.
- [ ] **Step 2: Run the CLI tests and verify failure.**

```bash
uv run pytest tests/pr_auto_reviewer/presentation/cli/test_cli_main.py -q
```

Expected: new dispatch assertions fail.

- [ ] **Step 3: Wire `status` to the dashboard and preserve the plain fallback.** Keep lifecycle commands and all other CLI commands unchanged.
- [ ] **Step 4: Run CLI and dashboard tests.**

```bash
uv run pytest tests/pr_auto_reviewer/presentation/cli/test_cli_main.py tests/pr_auto_reviewer/presentation/test_status_dashboard.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/pr_auto_reviewer/cli.py tests/pr_auto_reviewer/presentation/cli/test_cli_main.py
git commit -m "feat(status): launch dashboard from cli"
```

### Task 5: Verify, install, and enter the maintenance loop

**Files:**
- Modify: documentation only if verification exposes an actual user-facing mismatch.

- [ ] **Step 1: Run formatting/lint and the full test suite.**

```bash
uv run ruff check src tests
uv run pytest tests/ -x -q
```

Expected: all checks pass.

- [ ] **Step 2: Install from the feature worktree and restart the user service.**

```bash
uv tool install --force --reinstall .
pr-auto-reviewer restart
```

- [ ] **Step 3: Verify both modes.** Confirm `pr-auto-reviewer status` shows the live dashboard in the terminal, exits with `q`, and produces the existing plain output when redirected.
- [ ] **Step 4: Push the branch and create/update its PR.**
- [ ] **Step 5: Monitor CI and review comments.** Apply or dismiss findings through the next polling cycle, re-run verification after every change, and do not merge until the dashboard and fallback are confirmed working.
- [ ] **Step 6: After merge, pull `main`, remove the worktree, and update global agent state with completed work and remaining follow-ups.**
