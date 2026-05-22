# Fragment-Based Review — Usage Guide

## Quick Start

```bash
cd pr-auto-reviewer

# Create a test diff
cat > my.diff << 'DIFF'
+def login(user, pwd):
+    try:
+        q = "SELECT * FROM users WHERE name = '" + user + "'"
+        db.execute(q)
+    except:
+        pass
DIFF

# See the composed prompt (no Ollama needed)
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --diff-file my.diff --language python --prompt-only
```

---

## Modes

### 1. Prompt only — inspect what gets sent to the LLM

```bash
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --diff-file my.diff --language python --prompt-only
```

Prints the full assembled prompt to the terminal. No LLM call. Use to verify fragment selection and composition.

### 2. Full review — send to Ollama and read the result

```bash
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --diff-file my.diff --language python
```

Prints the AI-generated review directly to the terminal.

### 3. Review a PR from any provider (GitHub, Codeberg, self-hosted Forgejo)

```bash
# Needs GITHUB_TOKEN in .env
PYTHONPATH=src:. python scripts/review_with_fragments.py \
```

Fetches the diff from GitHub and runs the full pipeline.

---

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--diff-file PATH` | Local unified diff file | — |
| `--repo OWNER/REPO` | GitHub repository | — |
| `--pr NUMBER` | Pull request number | — |
| `--language LANG` | `python`, `go`, `rust`, `javascript`, … | required |
| `--model NAME` | Ollama model | `codellama` |
| `--prompt-only` | Only compose and print the prompt | off |

---

## Examples

```bash
# Review Python code from a file
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --diff-file changes.diff --language python

# Review Go code from a file
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --diff-file changes.diff --language go

# Review a closed PR from GitHub
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --repo gbrennon/pr-auto-reviewer --pr 1 --language python

# Use a different Ollama model
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --diff-file my.diff --language python --model llama3.2:3b

# Inspect the prompt without calling the LLM
PYTHONPATH=src:. python scripts/review_with_fragments.py \
    --diff-file my.diff --language python --prompt-only
```

---

## Understanding the Output

```
Loaded diff from my.diff (144 chars)

Selected 9 fragments:
  solid-principles                    pri=100 cat=architecture
  python-input-validation             pri= 90 cat=security
  python-error-handling               pri= 80 cat=error-handling
  python-resource-management          pri= 75 cat=security
  python-type-hints                   pri= 70 cat=best-practices
  test-coverage                       pri= 70 cat=quality
  python-async-await                  pri= 60 cat=concurrency
  naming-conventions                  pri= 50 cat=style
  documentation                       pri= 40 cat=quality

Tokens: 2338  Fragments: ['solid-principles', 'python-input-validation', ...]
```

- **Selected 9 fragments**: All fragments that matched the language (5 Python-specific + 4 universal)
- **pri**: Priority — higher fragments appear first in the prompt
- **cat**: Category — used for filtering and telemetry
- **Tokens**: Estimated token count (4 chars ≈ 1 token)

---

## Adding New Fragments

Drop a `.md` file into the right directory. The system picks it up automatically.

### File format

```markdown
---
id: python-my-check
language: python          # null for universal fragments
priority: 75              # higher = more important (sort descending)
category: best-practices
---

# My Custom Check

Review this code:

```python
{{ code }}
```

{% if 'bad_pattern' in code %}
Warning: bad pattern detected
{% endif %}
```

### Where to place it

```
fragments/
├── python/          ← language-specific checks
│   ├── error-handling.md
│   └── my-check.md          ← your new fragment
├── go/              ← Go-specific checks
│   └── concurrency.md
└── universal/       ← applies to all languages
    └── solid-principles.md
```

No code changes, no restarts — the `FileSystemFragmentRepository` scans the directory on every run.

---

## Environment

Create `.env` in the project root:

```bash
# Required for Codeberg PR fetching
FORGEJO_TOKEN=<your-codeberg-token>

# Optional — defaults shown
OLLAMA_HOST=http://localhost:11434
```

---

## Why Fragments Instead of a Single Template?

| Single template | Fragment system |
|-----------------|-----------------|
| One 5000-line file | 12 independent 50-line files |
| Hard to version diff | Git diff shows exactly which check changed |
| Cannot prioritize | Priority system ensures critical checks come first |
| All-or-nothing | Token budget drops low-priority fragments when context is tight |
| Cannot reuse | Universal fragments automatically apply to all languages |
| Hard to test | Each fragment is independently testable |

Fetches the diff from the provider's API and runs the full pipeline.
Works for open, closed, and merged PRs.


```bash
PYTHONPATH=src:. python scripts/review_with_fragments.py \
```
