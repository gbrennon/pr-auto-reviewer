# PR Auto Reviewer

An AI-powered code review assistant that automatically reviews pull requests on Forgejo or Codeberg using local Ollama AI models. Think of it as having an extra team member who never sleeps and always provides constructive feedback on your PRs.

## How It Works

This project sits between your Forgejo/Codeberg repositories and a local Ollama instance. Here's the flow:

1. **Watches for PRs** - Continuously polls your repositories for open pull requests
2. **Fetches the diff** - When a new or updated PR is found, it downloads the changes
3. **Sends to AI** - The diff is sent to your Ollama model for analysis
4. **Posts review** - A formatted review comment is posted directly on the PR

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

# Create your configuration file
cp .env.example .env

# Edit .env with your tokens
# Generate tokens at: https://codeberg.org/settings/applications

# Bootstrap starts everything
bash scripts/bootstrap.sh
```

## Understanding the Tokens

You need **two** different API tokens:

| Token | Purpose | Required Scopes |
|-------|---------|-----------------|
| `FORGEJO_TOKEN` | Your account - fetches repos, requests reviewers | `repo`, `read:user` |
| `FORGEJO_REVIEWER_TOKEN` | Different user - posts the formal review | `repo` |

The reviewer must be a **different account** than the PR author because you cannot review your own PRs.

Generate tokens at https://codeberg.org/settings/applications

## Understanding FORGEJO_MODE

The mode tells the system where your repositories live:

```
FORGEJO_MODE=codeberg   # Your repos are on codeberg.org (default)
FORGEJO_MODE=local      # Your repos are on a self-hosted Forgejo instance
```

**For codeberg (default):**
```bash
FORGEJO_MODE=codeberg
FORGEJO_HOST=https://codeberg.org  # This is the default, can omit
```

**For local Forgejo:**
```bash
FORGEJO_MODE=local
FORGEJO_HOST=http://forgejo.local  # Your Forgejo instance URL
```

## Usage

### Starting the Watcher

```bash
# Using bootstrap (recommended) - handles dependency checks and env loading
bash scripts/bootstrap.sh

# Or directly
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

# Stop all running services
bash scripts/autostart/autostart.sh --stop

# Check what's running
bash scripts/autostart/autostart.sh --status
```

## Configuration

Edit your `.env` file:

```bash
# === FORGEJO CONFIGURATION ===
# Your account token - fetches repos and requests reviewers
FORGEJO_TOKEN=your_token_here

# "codeberg" or "local" (default: codeberg)
FORGEJO_MODE=codeberg

# Your Forgejo instance URL
FORGEJO_HOST=https://codeberg.org

# === REVIEWER CONFIGURATION ===
# A DIFFERENT user's token - posts the formal review
FORGEJO_REVIEWER_TOKEN=reviewer_token_here
FORGEJO_REVIEWER_USERNAME=reviewer_username

# === OLLAMA CONFIGURATION ===
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=code-review
POLL_INTERVAL=60
```

## The Review Output

When the AI reviews a PR, it posts a comment that looks like this:

```markdown
## AI Code Review

**Verdict:** Approved

### Issues Found
- src/auth.rs:45: Consider using constant-time comparison for passwords

### Suggestions  
- Consider adding a unit test for the new validate_email function

### Praise
- Clean separation of concerns in the router
- Good use of Rust's type system

**Summary:** Solid implementation. Ready to merge once the security concern is addressed.

---
*Review by code-review via PR AI Auto-Reviewer*
```

The "verdict" is either:
- **Approved** - The changes look good
- **Changes Requested** - There are issues that should be addressed

## Hot Reload

You can change settings without restarting:

```bash
# Change the AI model
sed -i 's/OLLAMA_MODEL=.*/OLLAMA_MODEL=llama3.2/' .env

# Or manually trigger a reload
bash scripts/reload.sh
```

The watcher will pick up the changes within 10 seconds.

## Setting Up the AI Model

The default model is `code-review`. If you don't have it:

```bash
# Pull the model
ollama pull code-review

# List available models
ollama list

# Use a different model temporarily
OLLAMA_MODEL=qwen2.5-coder:14b bash scripts/watch-prs.sh
```

## Project Structure

```
pr-auto-reviewer/
├── scripts/
│   ├── bootstrap.sh          # Entry point - starts everything
│   ├── watch-prs.sh          # Main daemon that watches and reviews
│   ├── reload.sh             # Trigger config reload
│   ├── autostart/            # Service manager
│   └── lib/                  # Shared helper scripts
├── docs/
│   ├── structure.md          # File structure explanation
│   ├── features.md           # Implemented and planned features
│   └── permissions.md        # Token scope documentation
├── .env.example              # Configuration template
└── runner-data/              # State storage (PR reviews, PIDs)
```

## Troubleshooting

### "token does not have at least one of required scope(s)"
Your `FORGEJO_TOKEN` is missing the `read:user` scope. Regenerate at https://codeberg.org/settings/applications with both `repo` and `read:user` scopes.

### "Self-review detected"
The reviewer token belongs to the same account as the PR author. Use a different account's token for `FORGEJO_REVIEWER_TOKEN`.

### "Target couldn't be found"
- For `FORGEJO_MODE=local`: Check that `FORGEJO_HOST` points to your local Forgejo
- For `FORGEJO_MODE=codeberg`: Verify the repo exists on codeberg.org

### "Ollama not available"
Make sure Ollama is running:
```bash
ollama serve
# Or check it's running
curl http://localhost:11434/api/tags
```

## License

MIT