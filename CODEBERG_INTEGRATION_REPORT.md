# Codeberg Integration Fix — Fragment Review System

**Date**: 2026-05-14  
**Issue**: `review_with_fragments.py` used raw `requests` calls to GitHub API, ignoring the project's `.env` configuration  
**Fix**: Rewrote to use `GitPlatformHttpClient` — the same adapter the legacy system uses

---

## Problem

The fragment review script (`scripts/review_with_fragments.py`) was making raw HTTP calls directly to `https://api.github.com` with hardcoded GitHub-specific headers (`application/vnd.github.v3.diff`). It did not read the project's `.env` file (`FORGEJO_HOST`, `FORGEJO_TOKEN`), so it could not connect to Codeberg or any self-hosted Forgejo instance.

The legacy system worked because it uses `GitPlatformHttpClient` + `Config.load_config()` which reads `.env` properly.

## Fix

Rewrote the PR fetching to use the same infrastructure as the legacy system:

```python
def _build_http_client() -> object:
    from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
        GitPlatformHttpClient,
    )
    from pr_auto_reviewer.infrastructure.config.config import load_config
    cfg = load_config()
    return GitPlatformHttpClient(cfg.platform_api_url, cfg.platform_token)
```

- `Config.load_config()` reads `.env` → gets `FORGEJO_HOST` and `FORGEJO_TOKEN`
- `GitPlatformHttpClient` handles auth headers (`Authorization: token ...`)
- Paths are Forgejo/Gitea/GitHub-compatible: `/repos/{owner}/{repo}/pulls/{number}.diff`
- `get_raw()` returns the unified diff as text
- `get()` returns JSON for the file list

## Verification

Tested against `gbrennon/pr-auto-reviewer` on Codeberg:

```
PR #1:  9,252 chars, 3 files  → fetched, composed, prompt generated
PR #2: 37,697 chars, 12 files → fetched, composed, prompt generated
PR #3: 11,251 chars, 4 files  → fetched, composed, prompt generated
```

All three PRs returned valid diffs through `GitPlatformHttpClient`. Fragment selection and composition worked correctly for all.

## How the legacy system connects

```
.env → FORGEJO_HOST=https://codeberg.org/api/v1
       FORGEJO_TOKEN=<token>
         │
         ▼
Config.load_config()
  → Config(platform_api_url="https://codeberg.org/api/v1", platform_token="...")
         │
         ▼
GitPlatformHttpClient(base_url, token)
  → get_raw("/repos/gbrennon/pr-auto-reviewer/pulls/2.diff")  → diff text
  → get("/repos/gbrennon/pr-auto-reviewer/pulls/2/files")     → file list
```

## Same flow, fragment system

```
review_with_fragments.py
  → _build_http_client()  ← same Config + GitPlatformHttpClient
  → fetch_pr_diff()       ← get_raw() + get()
  → compose_prompt()      ← FragmentSelector + PromptComposer
  → call_ollama()         ← Optional, if Ollama is running
```

No more hardcoded GitHub URLs. No more provider flags. The `.env` file controls everything — just like the legacy CLI.
