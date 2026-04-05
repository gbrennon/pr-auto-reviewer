# PR Auto Reviewer

Automatically review pull requests on Codeberg using local Ollama AI models.

## Features

- **Automatic PR Detection** - Watches your Codeberg repos for open PRs
- **AI Code Review** - Uses Ollama to analyze diffs and provide feedback
- **Verdict System** - Automatically determines if changes should be approved or require changes
- **Hot Reload** - Change configuration without restarting (edit `.env`)
- **Multiple Repos** - Can watch all your Codeberg repos or specific ones

## Requirements

- Codeberg account with API token
- Ollama running locally or remotely
- At least one Ollama model (recommended: `code-review`)

## Quick Start

```bash
# Clone and setup
git clone https://github.com/gbrennon/pr-ai-auto-reviewer.git
cd pr-ai-auto-reviewer

# Copy and edit configuration
cp .env.example .env
# Edit .env with your tokens

# Start the watcher
bash scripts/watch-prs.sh
```

## Configuration

Edit `.env` with your settings:

```bash
# Required: Codeberg API token (generate at https://codeberg.org/settings/applications)
CODEBERG_TOKEN=your_codeberg_token_here

# Optional: GitHub token (for GitHub repos)
GITHUB_PAT=your_github_token_here

# Optional: Ollama settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=code-review

# Optional: Poll interval in seconds
POLL_INTERVAL=60
```

## Usage

```bash
# Run as daemon (default 60s interval)
bash scripts/watch-prs.sh

# Run with custom interval
bash scripts/watch-prs.sh -i 30

# Watch specific repo only
bash scripts/watch-prs.sh -r owner/repo

# Single cycle (for testing)
bash scripts/watch-prs.sh --once

# Use autostart system
bash scripts/autostart/autostart.sh
bash scripts/autostart/autostart.sh --stop  # stop all
bash scripts/autostart/autostart.sh --status  # check status
```

## Hot Reload

Edit `.env` and changes are detected automatically within 10 seconds:

```bash
# Change model
sed -i 's/OLLAMA_MODEL=.*/OLLAMA_MODEL=phi4:latest/' .env

# Or manually trigger reload
bash scripts/reload.sh
```

## Model Setup

The default model is `code-review`. To create it:

```bash
# In your gb-ollama-container:
cd /path/to/gb-ollama-container
./scripts/build-modelfiles.sh
```

Or use any Ollama model you have available:

```bash
OLLAMA_MODEL=qwen2.5-coder:14b bash scripts/watch-prs.sh
```

## Output

The review will be posted as a comment on the PR with:

- **Verdict**: Approved ✅ or Changes Requested ❌
- **Issues**: Critical/High severity problems
- **Suggestions**: Improvement ideas
- **Praise**: What was done well
- **Summary**: Overall assessment

Example:

```markdown
## AI Code Review ✅

**Verdict:** Approved

### Suggestions
- src/main.rs:21: Consider adding a comment

### Praise
- Clean code structure

**Summary:** Good work, ready to merge.

---
*Review by code-review via PR AI Auto-Reviewer*
```

## Files

| File | Description |
|------|-------------|
| `scripts/watch-prs.sh` | Main daemon script |
| `scripts/autostart/autostart.sh` | Autostart manager |
| `scripts/reload.sh` | Manual reload trigger |
| `scripts/lib/` | Shared libraries |
| `.env.example` | Configuration template |
