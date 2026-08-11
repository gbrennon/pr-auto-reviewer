# How to Test

This document describes how to run tests and validate the application.

## Test Philosophy

- **Unit tests** — Use mocks, test single units in isolation (AAA pattern)
- **Integration tests** — Exercise real collaborator interactions, use fixtures derived from real dependency calls, never mocks
- **E2E tests** — Full application flow from entry point to outcome

## Running Tests

```bash
# All tests
uv run pytest tests/ -x -q

# Unit tests only (fast, isolated, mocked)
uv run pytest tests/ -m "unit" -x -q

# Integration tests only (require real API credentials)
uv run pytest tests/ -m integration -x -q

# E2E tests only (require full environment)
uv run pytest tests/ -m e2e -x -q

# Specific test file
uv run pytest tests/pr_auto_reviewer/infrastructure/llm/test_ollama_llm_adapter.py -x -q

# With coverage
uv run pytest tests/ --cov=src/pr_auto_reviewer --cov-report=term-missing
```

## Test Markers

| Marker | Purpose |
|--------|---------|
| `@pytest.mark.unit` | Fast, isolated tests with mocks |
| `@pytest.mark.integration` | Tests that exercise real collaborator interactions |
| `@pytest.mark.e2e` | Full application flow from entry point to outcome |

**Note:** Currently no tests are explicitly marked. Run `uv run pytest tests/` (no filter) to run all tests. The markers are defined for future use when tests are categorized.

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── pr_auto_reviewer/
│   ├── test_e2e_review_flow.py    # Full review flow E2E
│   ├── test_e2e_review_verdict.py # Verdict behavior E2E
│   ├── test_multilang_review_verdict.py
│   ├── presentation/              # CLI, daemon, composition root
│   ├── application/               # Services, ports
│   ├── domain/                    # Entities, value objects, services
│   └── infrastructure/            # Adapters, config, clients, etc.
```

## Key Test Patterns

### Unit Tests (Mocks Allowed)

```python
def test_review_item_parser_extracts_severity():
    # Arrange
    parser = ReviewItemParser()
    body = "1. [CRITICAL] [security] src/auth.py:42: SQL injection"
    # Act
    items = parser.parse(body)
    # Assert
    assert len(items) == 1
    assert items[0].severity == ItemSeverity.CRITICAL
```

### Integration Tests (Real Dependencies, Fixtures)

```python
# tests/pr_auto_reviewer/infrastructure/git_platform/test_review_publisher.py
# Uses real API calls recorded as fixtures in tests/pr_auto_reviewer/infrastructure/git_platform/fixtures/
```

Fixtures are stored as JSON files capturing real API responses. See `tests/pr_auto_reviewer/infrastructure/git_platform/fixtures/`.

### E2E Tests

```bash
# Requires configured .env with real tokens
uv run pytest tests/pr_auto_reviewer/test_e2e_review_flow.py -x -v
```

## Testing the Review Flow

### 1. Unit Test the Service

```bash
uv run pytest tests/pr_auto_reviewer/application/services/test_review_pull_request_service.py -x -q
```

### 2. Test LLM Adapter with Mock Ollama

```bash
uv run pytest tests/pr_auto_reviewer/infrastructure/llm/test_ollama_llm_adapter.py -x -q
```

### 3. Test Fragment Composition

```bash
uv run pytest tests/pr_auto_reviewer/infrastructure/fragments/test_compose_review_prompt_adapter.py -x -q
```

### 4. Test Publisher Logic

```bash
uv run pytest tests/pr_auto_reviewer/infrastructure/review_publishers/ -x -q
```

### 5. Test Multi-Platform Adapters

```bash
uv run pytest tests/pr_auto_reviewer/infrastructure/git_platform/multi_platform/ -x -q
```

## Manual Testing

### Single Review (Terminal Mode)

```bash
# No API calls, prints to stdout
REVIEW_OUTPUT=terminal uv run python -m pr_auto_reviewer review --repo owner/repo --pr N -v
```

### Verify Prompt Construction

```bash
# Dumps prompt to /tmp/ollama-prompt-try1-initial.txt
DEBUG=1 uv run python -m pr_auto_reviewer review --repo owner/repo --pr N -v
```

### Check State

```bash
cat ~/.config/pr-auto-reviewer/state.json | python3 -m json.tool
```

### Token Verification

```bash
# Auth check
curl -s -w "HTTP %{http_code}\n" -o /dev/null \
  -H "Authorization: Bearer $GITHUB_OWNER_TOKEN" \
  https://api.github.com/user

# Write access check
curl -s -w "HTTP %{http_code}\n" -o /dev/null \
  -X POST \
  -H "Authorization: Bearer $GITHUB_OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reviewers":[]}' \
  https://api.github.com/repos/OWNER/REPO/pulls/PR/requested_reviewers
```

## Test Fixtures

Integration test fixtures are in:
```
tests/pr_auto_reviewer/infrastructure/git_platform/fixtures/
├── github/
│   ├── pulls_list.json
│   ├── pull_diff.txt
│   ├── pull_commits.json
│   ├── file_contents.json
│   ├── review_publish_response.json
│   └── ...
└── forgejo/
    ├── pulls_list.json
    ├── pull_diff.txt
    └── ...
```

Fixtures are created by running real API calls and saving responses. They are used to test adapter parsing logic without hitting the API.

## CI/CD

Tests run automatically on push. See `.github/workflows/` for pipeline configuration.

```bash
# Pre-commit checks (run locally)
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/ -x -q
```