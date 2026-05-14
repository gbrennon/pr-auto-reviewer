# Performance Notes

## `tests/.../test_repo_lister_adapter.py` — single API call

### Problem

The four integration tests in `test_repo_lister_adapter.py` were each
calling `GitRepoListerAdapter.list_repos()` independently, which issues
**two live HTTP requests per call** (`GET /user` + `GET /user/repos`).

| Test                                         | `list_repos()` calls (before) | API hits |
| -------------------------------------------- | ----------------------------- | -------- |
| `test_list_repos_returns_non_empty_list`     | 1                             | 2        |
| `test_list_repos_all_owned_by_authenticated_user` | 1                        | 2        |
| `test_list_repos_with_filter_short_circuits` | 1 (filtered — no API)         | 0        |
| `test_list_repos_returns_consistent_result`  | **2**                         | **4**    |
| **Total**                                    | 5                             | **8**    |

Each integration test suite invocation could hit the live Codeberg API
up to 8 times for the same data.

### Fix

1. `repo_lister_adapter` fixture renamed to **session scope** (was
   function scope) — the adapter wraps a session-scoped `http_client`
   already so this is safe.

2. A new **`repo_list`** fixture (session scope) calls
   `repo_lister_adapter.list_repos()` **exactly once** and caches the
   result.

3. Tests now inject `repo_list` (the already-fetched list) instead of
   calling `list_repos()` themselves.

| Test                                         | `list_repos()` calls (after) | API hits |
| -------------------------------------------- | ---------------------------- | -------- |
| `test_list_repos_returns_non_empty_list`     | 0                            | 0        |
| `test_list_repos_all_owned_by_authenticated_user` | 0                       | 0        |
| `test_list_repos_with_filter_short_circuits` | 1 (filtered — no API)        | 0        |
| `test_list_repos_returns_consistent_type`    | 0                            | 0        |
| `repo_list` fixture (one-time)               | 1                            | **2**    |
| **Total**                                    | 1                            | **2**    |

**Result: 8 API calls → 2 API calls (75 % reduction).**

### Files changed

- `tests/conftest.py` — added session-scoped `repo_list` fixture;
  changed `repo_lister_adapter` to session scope.
- `tests/pr_auto_reviewer/infrastructure/git_platform/test_repo_lister_adapter.py` —
  tests use `repo_list` instead of `list_repos()`.

### General pattern

For any integration test fixture that fetches immutable data from a
live API, prefer **session scope** and a dedicated caching fixture so
the data is fetched once regardless of how many test functions consume
it.
