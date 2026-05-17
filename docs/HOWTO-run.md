# How to Run — PR Auto Reviewer

## Prerequisites

- Python 3.14+
- [Ollama](https://ollama.com) running locally (or accessible URL)
- A Forgejo/Codeberg API token
- Git platform API URL (e.g. `https://codeberg.org`)

## Installation

```bash
cd pr-auto-reviewer

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

## Configuration

Create a `.env` file in the project root:

```bash
FORGEJO_TOKEN=your_owner_token_here
FORGEJO_HOST=https://codeberg.org
FORGEJO_REVIEWER_TOKEN=your_reviewer_token_here
FORGEJO_REVIEWER_USERNAME=code-reviewer
OLLAMA_MODEL=code-review
OLLAMA_HOST=http://localhost:11434
POLL_INTERVAL=60
```

See [configuration.md](configuration.md) for details.

---

## Commands

### 1. Review a specific PR (publish to platform)

```bash
# Basic
pr-auto-reviewer review --repo owner/repo --pr 42

# With verbose output (shows progress)
pr-auto-reviewer review --repo owner/repo --pr 42 --verbose

# Force re-review (even if already reviewed at same commit)
pr-auto-reviewer review --repo owner/repo --pr 42 --force --verbose
```

What happens:
1. Fetches PR #42 from `owner/repo`
2. Gets the diff + full file contents
3. **Autonomously detects the language** from file extensions in the diff
4. Loads language-specific + universal review fragments
5. Composes a prompt and sends it to Ollama
6. Publishes the review back to the platform

### 2. Review a PR — output to terminal only (no publishing)

```bash
REVIEW_OUTPUT=terminal pr-auto-reviewer review --repo owner/repo --pr 42 --force --verbose
```

This prints the review to stdout instead of publishing to the platform.

### 3. Daemon mode — continuous polling

```bash
# Watch all repos, poll every 60s
pr-auto-reviewer watch-prs

# Single repo, every 30 seconds
pr-auto-reviewer watch-prs --repo owner/repo --interval 30

# Run once and exit (cron-friendly)
pr-auto-reviewer watch-prs --once

# Force re-review a specific PR during daemon run
pr-auto-reviewer watch-prs --repo owner/repo --pr 42

# With debug logging
pr-auto-reviewer watch-prs --verbose
```

### 4. Compose prompt / review locally (standalone script)

```bash
# Auto-detect language from file extension (--full-file provides the source)
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --diff-file path/to/diff.diff \
    --full-file path/to/source.sh \
    --prompt-only

# Explicit language (no source file needed)
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --diff-file path/to/diff.diff \
    --language shell \
    --prompt-only

# From a live PR (auto-detects language from PR file list)
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --repo owner/repo --pr 42 \
    --prompt-only

# Full review with Ollama
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --diff-file path/to/diff.diff \
    --full-file path/to/source.sh

# Post review to platform
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --repo owner/repo --pr 42 \
    --output platform
```

### 5. Process PR issue commands

```bash
pr-auto-reviewer process-commands --repo owner/repo --pr 42
```

### 6. Other commands

```bash
# Bootstrap / verify setup
pr-auto-reviewer bootstrap

# Clean state files
pr-auto-reviewer clean
```

---

## How Autonomous Language Detection Works

The system detects the programming language **automatically** from file
extensions in the PR diff — no configuration needed:

| Extension | Detected | Fragments loaded |
|---|---|---|
| `.sh` `.bash` | `shell` | `fragments/shell/` + `universal/` |
| `.py` | `python` | `fragments/python/` + `universal/` |
| `.go` | `go` | `fragments/go/` + `universal/` |
| `.rs` | `rust` | `fragments/rust/` + `universal/` |
| `.java` | `java` | `fragments/java/` + `universal/` |
| `.kt` | `kotlin` | `fragments/kotlin/` + `universal/` |
| `.scala` | `scala` | `fragments/scala/` + `universal/` |
| `.js` `.ts` `.rb` `.php` `.c` `.cpp` `.cs` `.swift` | (respective) | `universal/` only |

**Key design properties:**
- Scans **only PR diff files**, not the entire repository
- Returns **first match** → single language, no prompt bloat
- Universal fragments (SOLID, naming, docs, tests) always included
- Falls back to legacy prompt when no `fragments/` dir is present

---

## Language-Specific Fragment Coverage

| Language | Fragments |
|---|---|
| `shell` | shebang, error-handling (set -euo pipefail), quoting, security |
| `python` | async-await, error-handling, input-validation, resource-mgmt, type-hints |
| `go` | concurrency, context-usage, error-wrapping |
| `rust` | concurrency, error-handling, ownership-borrowing, unsafe-code |
| `java` | error-handling, immutability, null-safety, streams-lambdas |
| `kotlin` | coroutines, data-classes, null-safety, scope-functions |
| `scala` | error-handling, immutability, implicits, pattern-matching |

Universal (loaded for all): documentation, naming-conventions, SOLID, test-coverage.

---

## Running Tests

```bash
# All tests
uv run pytest

# Quick (no coverage report)
uv run pytest --no-cov

# Specific test file
uv run pytest tests/pr_auto_reviewer/infrastructure/llm/test_ollama_llm_adapter.py -v

# Language detection + fragment tests only
uv run pytest tests/pr_auto_reviewer/infrastructure/llm/test_ollama_llm_adapter.py -v \
    -k "TestDetectLanguage or TestFragmentLanguageSupport or TestAutonomousFragmentPipeline"
```

---

## Project Structure (simplified)

```
pr-auto-reviewer/
├── fragments/                  # Language-specific review prompts
│   ├── shell/ python/ java/ kotlin/ scala/ rust/ go/
│   └── universal/              # Language-agnostic (SOLID, docs, ...)
├── src/pr_auto_reviewer/       # Application source
│   ├── application/            # Use cases, ports, services
│   ├── domain/                 # Entities, value objects
│   ├── infrastructure/         # Ollama, Git platform adapters
│   └── presentation/           # CLI, daemon
├── scripts/review_with_fragments.py  # Standalone review
├── tests/                      # Test suite (761 tests)
├── pyproject.toml
└── .env                        # Your configuration
```
