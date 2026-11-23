# Status TUI

`pr-auto-reviewer status` opens the live Textual terminal user interface when stdout is an interactive terminal. The dashboard reads the daemon status snapshot once per second and updates only changed table cells, preserving the table cursor during refreshes.

## Dashboard

| Key | Action |
|---|---|
| `q` | Quit the dashboard |
| `s` | Cycle sorting by platform, repository, or status |
| `r` | Refresh immediately |
| `p` | Pause or resume automatic refresh |
| `e` | Open the settings screen |

The dashboard displays daemon state, allowed repositories, API capabilities, active review progress, errors, and the last refresh time. Redirected or non-interactive output uses the plain-text status report instead of Textual.

## Settings screen

Press `e` to open the full-screen settings editor. Press `q` or `Escape` to return to the dashboard.

Settings values are displayed without exposing secret values. Tokens and other secret settings are write-only: they can be entered or replaced, but never read back into the interface.

The settings screen supports:

- Saving or unsetting a named setting.
- Adding a repository with separate manager and reviewer token fields.
- Removing a repository from the allow list.
- Selecting the keyboard navigation mode.

Repository token fields are masked and are never included in rendered settings output.

## Navigation modes

The default mode is `arrows`. Set the mode from the settings screen or with:

```bash
pr-auto-reviewer config set TUI_NAVIGATION_MODE arrows
```

Supported modes:

### Arrows

The standard Textual input behavior. Arrow keys move the cursor, and Tab/Shift-Tab move focus between controls.

### Vim

- Normal mode: `h`/`l` move the text cursor; `j`/`k` move focus between controls.
- Press `i` to enter insert mode.
- Press `Escape` to leave insert mode.
- Arrow keys do not move the cursor in Vim mode.
- `j`/`k` can reach buttons such as Save and Unset.

### Emacs

- `ArrowLeft`/`ArrowRight` and `Ctrl-b`/`Ctrl-f` move by character.
- `ArrowUp`/`ArrowDown` and `Ctrl-p`/`Ctrl-n` move between controls.
- Text objects and word motions are not implemented.
- `Ctrl-p` is reserved for previous-control movement; the command palette is available with `Ctrl-Shift-p`.

## Live review progress

While the daemon reviews a pull request, the dashboard reports the repository, pull request number, phase, turn, and latest action. Progress events are written to the shared runtime status file so a separately launched TUI observes the active review without restarting the daemon.
