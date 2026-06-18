# Running PR Auto-Reviewer in Terminal Mode

This guide explains how to run the PR Auto-Reviewer to review Pull Requests from **GitHub** or **Codeberg** with the results output directly to your terminal instead of being posted as comments on the platform.

## 🚀 Quick Start (Zero Install)

If you have [uv](https://github.com/astral-sh/uv) installed, you can run a review without performing a full installation (no `make install` or `uv sync` required).

### Using the helper script
The easiest way is to use the provided helper script:

```bash
# Review a PR and output to terminal
./run-single-review.sh owner/repository 123 terminal

# Review a PR and post it to the platform
./run-single-review.sh owner/repository 123 platform
```

### Using a one-liner
Alternatively, you can use `uv run` directly:

```bash
REVIEW_OUTPUT=terminal uv run pr-auto-reviewer review --repo owner/repository --pr 123 --force --verbose
```

---

## 1. Prerequisites

Before running the application, ensure you have the following:

- **Python 3.14+**
- **Ollama** installed and running locally ([ollama.com](https://ollama.com))
- **API Tokens** for the platform you wish to review:
  - **GitHub**: A Personal Access Token (PAT) with `repo` scope.
  - **Codeberg/Forgejo**: An API token from your account settings.

## 2. Configuration

The application uses a `.env` file for configuration. Create one in the project root:

```bash
cp .env.example .env
```

Edit the `.env` file to set your platform and tokens. The application uses generic variables (`PLATFORM_TOKEN` and `REVIEWER_TOKEN`) to support both GitHub and Codeberg.

### For GitHub
```env
PLATFORM_MODE=github
PLATFORM_TOKEN=ghp_your_github_token
REVIEWER_TOKEN=ghp_your_reviewer_token
REVIEWER_USERNAME=code-reviewer-bot
OLLAMA_MODEL=code-review
OLLAMA_HOST=http://localhost:11434
```

### For Codeberg / Forgejo
```env
PLATFORM_MODE=codeberg
PLATFORM_TOKEN=your_codeberg_token
REVIEWER_TOKEN=your_reviewer_token
REVIEWER_USERNAME=code-reviewer-bot
OLLAMA_MODEL=code-review
OLLAMA_HOST=http://localhost:11434
```

## 3. Installation (Optional)

If you plan to use the application frequently or run tests, a formal installation is recommended:

```bash
# Using make
make install

# OR using uv (recommended)
uv sync
```

## 4. Running Terminal Reviews

To output the review to the terminal instead of posting it to the platform, you must set the `REVIEW_OUTPUT` environment variable to `terminal`.

### Option A: Using the Python CLI (Recommended)
This is the most flexible method and provides the most control.

```bash
REVIEW_OUTPUT=terminal python -m pr_auto_reviewer.cli review \
    --repo owner/repository \
    --pr 123 \
    --force \
    --verbose
```
**Flags explained:**
- `--repo`: The repository in `owner/repo` format.
- `--pr`: The PR number.
- `--force`: Bypasses the check that prevents re-reviewing the same commit.
- `--verbose`: Shows detailed progress and diagnostic information.

### Option B: Using Make
The `Makefile` provides a convenient shortcut for terminal reviews.

```bash
make review-terminal REPO=owner/repository PR=123
```

### Option C: Using the Validate command
You can also use the `validate-pr` command, which is specifically designed to print to stdout.

```bash
python -m pr_auto_reviewer.cli validate-pr -r owner/repository -p 123
```

## 5. Switching Platforms

To switch between GitHub and Codeberg, simply change the `PLATFORM_MODE` variable in your `.env` file:

- `PLATFORM_MODE=github` $\rightarrow$ Uses GitHub API.
- `PLATFORM_MODE=codeberg` $\rightarrow$ Uses Codeberg/Forgejo API.

## Summary Table

| Method | Command | Output | Setup |
| :--- | :--- | :--- | :--- |
| **Quick Start** | `./run-single-review.sh ...` | Terminal/Platform | Zero Install |
| **UV One-liner** | `uv run pr-auto-reviewer review ...` | Terminal/Platform | Zero Install |
| **CLI** | `REVIEW_OUTPUT=terminal python -m ...` | Terminal | Full Install |
| **Make** | `make review-terminal ...` | Terminal | Full Install |
| **Validate** | `python -m pr_auto_reviewer.cli validate-pr ...` | Terminal | Full Install |
