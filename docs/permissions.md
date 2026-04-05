# Permissions

This document describes the required permissions for the PR AI Auto-Reviewer.

## Codeberg API Token

Generate at: https://codeberg.org/settings/applications

| Field (Scope) | Permission | Description |
|---------------|------------|-------------|
| `user` | read | Get user repository subscriptions and settings |
| `user` | write | Update user repository subscriptions and settings |
| `repository` | read | Get repository files, releases, and collaborators |
| `repository` | write | Get/update repository files, create pull requests |
| `issue` | read | Get issue comments, attachments, and milestones |
| `issue` | write | Post or edit issue comments, update milestones |
| `activitypub` | read | ActivityPub read operations |
| `activitypub` | write | ActivityPub write/delete operations |
| `misc` | read | Get label and gitignore templates |
| `misc` | write | Markup utility operations |
| `notification` | read | Read user notifications |
| `notification` | write | Mark notifications as read |
| `organization` | read | List organizations and teams |
| `organization` | write | Create/update teams and org settings |
| `package` | read | Read and download packages |
| `package` | write | Same as read currently |

### Required Scopes

For this project, you need at minimum:

| Field (Scope) | Permission |
|---------------|------------|
| `user` | read |
| `repository` | read |
| `repository` | write |
| `issue` | write |

### Why these scopes?

- `user` (read) - Needed to identify the authenticated user
- `repository` (read) - Needed to read repository files and pull requests
- `repository` (write) - Needed to create pull request reviews
- `issue` (write) - Required to post comments on PRs (uses issues endpoint)

### GitHub (Not Implemented)

GitHub support is planned but not yet implemented. The table below documents what will be required when it is.

| Field (Scope) | Permission | Description |
|---------------|------------|-------------|
| `repo` | full | Required to read PRs and post reviews |

## Ollama

No authentication required. Ensure Ollama is running at the configured host.
