# PR Auto Reviewer

An AI-powered code review assistant that automatically reviews pull requests on Forgejo or Codeberg using local Ollama AI models. Think of it as having an extra team member who never sleeps and always provides constructive feedback on your PRs.

## How It Works

This project sits between your Forgejo/Codeberg repositories and a local Ollama instance. Here's the flow:

1. **Watches for PRs** - Continuously polls your repositories for open pull requests
2. **Fetches the diff** - When a new or updated PR is found, it downloads the changes
3. **Sends to AI** - The diff is sent to your Ollama model for analysis
4. **Posts review** - A formal review (approve/request changes) is posted on the PR

## Why Use It

- **Consistent feedback** - Every PR gets reviewed, not just when you have time
- **Privacy-first** - Your code never leaves your machine; it runs entirely locally
- **Learning tool** - The AI suggestions can help developers grow their skills
- **Catches basics** - Frees up human reviewers to focus on architecture and logic, not style nits

## What It Does NOT Do

- It does not merge PRs automatically (verdict is informational only)
- It does not replace human code review
- It does not store your code anywhere
- It does not self-review (reviewer must be a different account than PR author)

## Requirements

- **Ollama** - A local AI inference server. [Install from ollama.ai](https://ollama.ai)
- **Forgejo or Codeberg account** - Where your repositories live
- **Two API tokens** - One from your account, one from a reviewer account

## Supported Platforms

Currently supports:
- Forgejo (local and self-hosted)
- Codeberg

Planned support (not yet available):
- GitHub
- GitLab
- Other Git-based platforms

## Quick Start

```bash
# Clone the project
git clone https://codeberg.org/gbrennon/pr-auto-reviewer.git
cd pr-auto-reviewer

# Run the install script - creates config and sets up systemd service
bash scripts/install-service.sh
```

The install script will:
1. Create `~/.config/pr-auto-reviewer/config` with the configuration template
2. Set up the systemd user service
3. Start the service immediately

## Configuration

Edit your config file at `~/.config/pr-auto-reviewer/config`:

```bash
# === FORGEJO/CODEBERG ===
FORGEJO_TOKEN=           # Required - Your account token (scopes: repo, read:user)
FORGEJO_HOST=https://codeberg.org

# === REVIEWER ===
FORGEJO_REVIEWER_TOKEN=  # Required - Different user's token (scopes: repo)
FORGEJO_REVIEWER_USERNAME=  # Required - Username of reviewer account

# === OLLAMA ===
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=             # Required - Your model (e.g., code-review, llama3.2, qwen2.5-coder:14b)
POLL_INTERVAL=60
```

### Generating Tokens

1. **Owner token** (FORGEJO_TOKEN): Generate at https://codeberg.org/settings/applications
   - Scopes: `repo`, `read:user`

2. **Reviewer token** (FORGEJO_REVIEWER_TOKEN): Generate from a different account
   - Scopes: `repo`
   - Get the username from the reviewer's account

## Usage

### Starting the Watcher

```bash
# Install and start the service (creates config, sets up systemd)
bash scripts/install-service.sh

# Or run manually without installing
bash scripts/watch-prs.sh
```

### Common Options

```bash
# Watch specific repo instead of all repos
bash scripts/watch-prs.sh -r owner/repo

# Custom poll interval (default is 60 seconds)
bash scripts/watch-prs.sh -i 30

# Single run (good for testing)
bash scripts/watch-prs.sh --once

# Check service status
systemctl --user status pr-ai-auto-reviewer.service

# Stop the service
systemctl --user stop pr-ai-auto-reviewer.service

# View logs
journalctl --user -u pr-ai-auto-reviewer.service --no-pager -f
```

## Starting on Boot

By default, the service starts when you log in. To start automatically at boot (even without an active login session):

```bash
loginctl enable-linger $USER
```

## The Review Output

When the AI reviews a PR, it posts a formal review with verdict:

- **Approved** - The changes look good
- **Changes Requested** - There are issues that should be addressed

The review includes:
- Issues found (with severity: HIGH, MEDIUM, LOW)
- Suggestions for improvement
- Praise for good practices
- Summary

Example:
```markdown
## AI Code Review

**Verdict:** Approved

### Issues
- [MEDIUM] [architecture] src/auth.rs:45: Consider using constant-time comparison

### Suggestions
- Consider adding a unit test for the validate_email function

### Praise
- Clean separation of concerns in the router

**Summary:** Solid implementation. Ready to merge once the security concern is addressed.

---
*Review by code-review via PR AI Auto-Reviewer*
```

## Hot Reload

You can change settings without restarting the service. Edit `~/.config/pr-auto-reviewer/config` and the service will reload within 10 seconds. You can also trigger a reload:

```bash
# Trigger config reload
pkill -HUP -f "watch-prs.sh"
```

## Setting Up the AI Model

Check what models you have available:

```bash
# List available models
ollama list

# Pull a model if needed (example)
ollama pull code-review
```

## Manual/Dev Mode

For development or testing without installing the service, you can use `.env` in the repo:

```bash
# Create .env in repo root
cp .env.example .env
# Edit .env with your tokens

# Run manually
bash scripts/watch-prs.sh --once
```

The watcher will use `.env` from the repo when no user config exists at `~/.config/pr-auto-reviewer/config`.

## Project Structure

```
pr-auto-reviewer/
├── scripts/
│   ├── bootstrap.sh          # Entry point - starts everything
│   ├── install-service.sh    # Install as systemd service
│   ├── watch-prs.sh          # Main daemon that watches and reviews
│   ├── reload.sh             # Trigger config reload
│   ├── autostart/            # Service manager
│   └── lib/                  # Shared helper scripts
├── .env.example              # Configuration template (for manual mode)
└── runner-data/              # State storage (reviewed PRs)
```

## Troubleshooting

### "No repos found"
Your token might be missing the `read:user` scope.

Regenerate your token at https://codeberg.org/settings/applications with both `repo` and `read:user` scopes.

### "Self-review detected"
The reviewer token belongs to the same account as the PR author.

Use a different account's token for `FORGEJO_REVIEWER_TOKEN`.

### "Failed to post review"
- Check that `FORGEJO_REVIEWER_TOKEN` is valid and has `repo` scope
- Verify `FORGEJO_REVIEWER_USERNAME` is correct

### "Ollama not available"
Make sure Ollama is running:
```bash
ollama serve
# Or check it's running
curl http://localhost:11434/api/tags
```

### Service won't start
Check systemd logs:
```bash
journalctl --user -u pr-ai-auto-reviewer.service --no-pager -f
```

## License

MIT
