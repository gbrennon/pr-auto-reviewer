# Generated Issue Format

Issues created by PR Auto Reviewer follow a standardized structure built by `IssueBodyBuilder`.

### Issue Title

The issue title is constructed as:

```text
[<SEVERITY>] <CATEGORY>: <truncated description>
```

- Severity is uppercase (e.g. `[CRITICAL]`, `[MAJOR]`, `[MINOR]`).
- Description is clipped at a sentence or word boundary to a maximum of 80 characters, avoiding mid-word truncations.

Example:

```text
[CRITICAL] BUG: Token expiration logic fails on leap year
```

### Issue Body Structure

The issue body contains full context from the review finding:

```markdown
## Review Item a3f2 from owner/repo#42

- **Severity:** CRITICAL
- **Category:** BUG
- **File:** `src/server/auth.py`

Token expiration logic fails on leap year calculations when timezone offset is negative.

### Current Code
```
expires_at = now + datetime.timedelta(days=365)
```

### Suggested Fix
```
expires_at = now + (datetime.timedelta(days=366) if is_leap_year(now.year) else datetime.timedelta(days=365))
```
```

Sections `### Current Code` and `### Suggested Fix` are included whenever present on the review finding.

---

## Required Platform Permissions

Processing commands and creating issues requires appropriate token permissions. For detailed token configuration instructions, refer to the [Token Setup Documentation](../tokens/README.md).

### GitHub Permissions

- **Owner Token (`GITHUB_OWNER_TOKEN`)**:
  - Issues: `Read and Write` (required to read PR comments and create tracker issues)
  - Pull requests: `Read and Write` (required to inspect PR data)
- **Reviewer Token (`GITHUB_REVIEWER_TOKEN`)**:
  - Issues: `Write` (required to post confirmation and validation comments on the PR)

### Codeberg / Forgejo Scopes

- **Owner Token (`FORGEJO_OWNER_TOKEN`)**:
  - `read:issue`, `write:issue` (required to read PR comments and create tracker issues)
  - `read:repository`, `write:repository` (required to access PR and review data)
- **Reviewer Token (`FORGEJO_REVIEWER_TOKEN`)**:
  - `write:issue` (required to post feedback comments on the PR)

---
