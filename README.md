# PR Auto Reviewer

An AI-powered code review assistant that automatically reviews pull requests on Codeberg using local Ollama AI models. Think of it as having an extra team member who never sleeps and always provides constructive feedback on your PRs.

## How It Works

This project sits between your Codeberg repositories and a local Ollama instance. Here's the flow:

1. **Watches for PRs** - Continuously polls your Codeberg repos for open pull requests
2. **Fetches the diff** - When a new or updated PR is found, it downloads the changes
3. **Sends to AI** - The diff is sent to your Ollama model for analysis
4. **Posts review** - A formatted review comment is posted directly on the PR

## Why Use It

- **Consistent feedback** - Every PR gets reviewed, not just when you have time
- **Privacy-first** - Your code never leaves your machine; it runs entirely locally
- **Learning tool** - The AI suggestions can help developers grow their skills
- **Catches basics** - Frees up human reviewers to focus on architecture and logic, not style nits

## What It Does NOT Do

- It does not approve or merge PRs automatically (verdict is informational only)
- It does not replace human code review
- It does not store your code anywhere

## Requirements

- **Ollama** - A local AI inference server. Ollama runs entirely on your machine.
- **Codeberg account** - Where your repositories live
- **API token** - Required to read PRs and post review comments

## Quick Start

```bash
# Clone the project
git clone https://codeberg.org/gbrennon/pr-auto-reviewer.git
cd pr-auto-reviewer

# Create your configuration file
cp .env.example .env

# Edit .env with your Codeberg API token
# Generate one at: https://codeberg.org/settings/applications
# See docs/permissions.md for required scopes

# Bootstrap starts everything
bash scripts/bootstrap.sh
```

## Understanding the Scopes

When generating your Codeberg token, you'll need specific scopes:

| Scope | Why It's Needed |
|-------|-----------------|
| `user` (read) | To identify your account and list your repositories |
| `repository` (read) | To fetch PR details and diffs |
| `repository` (write) | To submit formal reviews |
| `issue` (write) | To post review comments on PRs |

See `docs/permissions.md` for the full breakdown.

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
# Required: Your Codeberg API token
CODEBERG_TOKEN=your_token_here

# Optional: GitHub support (for GitHub repos)
GITHUB_PAT=your_github_token

# Optional: Ollama settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=code-review

# Optional: How often to check for new PRs (in seconds)
POLL_INTERVAL=60
```

## The Review Output

When the AI reviews a PR, it posts a comment that looks like this:

```markdown
## AI Code Review ✅

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
│   ├── autostart/            # Systemd-like service manager
│   └── lib/                  # Shared helper scripts
├── docs/
│   └── permissions.md        # Token scope documentation
├── .env.example              # Configuration template
└── runner-data/              # State storage (PR reviews, PIDs)
```

## Troubleshooting

### "No repos found"
Your token might be missing the `read:user` scope. Check your token at https://codeberg.org/settings/applications

### "Failed to post to Codeberg"
Your token might be missing the `issue` (write) scope.

### "Ollama not available"
Make sure Ollama is running:
```bash
ollama serve
# Or check it's running
curl http://localhost:11434/api/tags
```

## License

MIT
