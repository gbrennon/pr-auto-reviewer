# PR Comment Commands Guide

This guide explains how to interact with PR Auto Reviewer directly via comments on pull requests across GitHub and Codeberg/Forgejo.

---

## Overview and Purpose

PR Auto Reviewer supports automation commands posted as PR discussion comments. The primary use case is converting findings from an automated code review into tracked repository issues without navigating away from the PR conversation.

When developers or maintainers review findings posted by the bot, they can comment with a command targeting one or more finding IDs. When processed, the tool extracts the finding details, creates dedicated repository issues, and comments back on the PR with references to the created issues.

---

## Supported Command Syntax

Commands are parsed by `IssueCommandParser` using a flexible regular expression that accommodates common prefix and separator conventions.

### Syntax Variations

The following formats are recognized interchangeably:

- `/create-issue <item_ids>`
- `/create issue <item_ids>`
- `/createissue <item_ids>`
- `create-issue <item_ids>`
- `create issue <item_ids>`
- `createissue <item_ids>`
- `/create-issue for <item_ids>`
- `/create issue for <item_ids>`
- `create-issue for <item_ids>`
- `create issue for <item_ids>`

### Casing and Whitespace Rules

- **Case-Insensitive**: Commands match regardless of casing. For example, `/CREATE ISSUE a1, b2` and `/create-issue a1, b2` behave identically.
- **Leading Slash Optional**: Commands work both with a leading slash (`/create-issue`) and without (`create-issue`).
- **Whitespace Tolerance**: Spaces or hyphens between `create` and `issue` are accepted. Optional `for` preposition is accepted.
- **Delimiter Tolerance**: Item IDs are separated by commas. Spaces surrounding commas are automatically stripped (for example, `a3f2 , b7d1` is parsed as `["a3f2", "b7d1"]`).

### Examples

```markdown
/create-issue a3f2
/create-issue a3f2, b7d1
create issue for c9e4, d1f0
/createissue 1a2b
```

### Dismissal

Non-blocking review items can be dismissed without creating a tracker issue:

```markdown
dismiss e03401 , b99602
```

Dismissal accepts item IDs from both findings and suggestions. The command records
the IDs as `dismissed` in persisted PR state and does not close an external
tracker issue.

### Blocking-item restriction

`create issue` and `dismiss` accept only open, non-blocking items. CRITICAL and
MAJOR severities, plus every SECURITY-category item, are rejected and remain
open for code changes and formal review. The bot acknowledges each rejected ID
instead of creating or dismissing it.

```markdown
Cannot create tracker issues for: b7d1. Only open non-blocking review items are
eligible; blocking findings must be handled through code changes and formal review.
```

---

## Finding Review Item IDs

Each actionable issue reported in the bot's review comment is assigned a unique identifier.

### Anatomy of a Review Item Header

Review items in the posted review body begin with a structured header formatted as:

```markdown
<id>. [<category>] [<severity>] <file_path>:<line>
```

Example review item header:

```markdown
a3f2. [BUG] [CRITICAL] src/server/auth.py:42
```

In this example, the item ID is `a3f2`.

### Listing Items via CLI

You can inspect the parsed items and their IDs for any reviewed PR from the terminal:

```bash
# Using pr-auto-reviewer CLI
pr-auto-reviewer list-items --repo owner/repo --pr 42

# Using Make
make list-items REPO=owner/repo PR=42
```

The output displays an ASCII table:

```text
#    | Severity   | Category     | File                           | Description
----------------------------------------------------------------------------------------------------
a3f2 | CRITICAL   | BUG          | src/server/auth.py:42          | Token expiration logic fails on leap year...
b7d1 | MAJOR      | SECURITY     | src/server/headers.py:15       | Unsanitized input in header parser...
```

The values in the `#` column correspond directly to the item IDs passed to issue creation commands.

---

## Command Processing Lifecycle

Commands placed in PR comments are executed via `process-commands`.

### Invoking Command Processing

To trigger command processing for a pull request:

```bash
# Using the CLI
pr-auto-reviewer process-commands --repo owner/repo --pr 42 [-v]

# Using Make
make issues REPO=owner/repo PR=42
```

### End-to-End Processing Flow

`ProcessIssueCommandsService` handles the command lifecycle in the following sequence:

1. **Load Pull Request**: Fetches the `PullRequest` aggregate from the repository (`pr_repository.find`).
2. **Retrieve Latest Review**: Reads the raw markdown of the latest review comment (`review_reader.get_latest_review`).
3. **Parse Review Items**: Parses review items and their IDs from the review body (`review_item_parser.parse`).
4. **Fetch PR Comments**: Retrieves all comments posted on the PR (`comment_reader.get_comments`).
5. **Deduplication / Idempotency**: Evaluates each comment. If `pr.is_comment_processed(comment.id)` is true, the comment is skipped to prevent duplicate issue creation.
6. **Command Parsing**: Inspects unprocessed comments with `issue_command_parser.parse(comment.id, comment.body)`.
7. **Mark Processed**: Records the comment ID as processed on the PR entity (`pr.mark_comment_processed(comment.id)`).
8. **Item Validation**: Compares requested IDs against current review items:
   - **Unknown IDs**: A validation failure comment lists available items.
   - **Blocking or inactive IDs**: The ID is rejected and remains unchanged.
   - **Open non-blocking IDs**: The command proceeds with issue creation or dismissal.
9. **Apply Command**: Creates tracker issues or records dismissed IDs in the PR aggregate.
10. **Post Confirmation**: A comment lists created issues, dismissed IDs, or rejected IDs.
11. **Persist State**: Saves the updated pull request entity with processed comments and command state.

---

## Bot Feedback and Responses

The bot communicates the result of command execution by posting a comment on the pull request.

### Success Response

When all item IDs are valid, the bot creates the issues on the target repository and comments back with issue references:

```markdown
Created 2 issue(s):

- #101: [CRITICAL] BUG: Token expiration logic fails on leap year
  - review item `a3f2` (critical bug, blocking) — status: open (still relevant)
- #102: [MAJOR] SECURITY: Unsanitized input in header parser
  - review item `b7d1` (major security, blocking) — status: open (still relevant)
```

### Validation Failure Response

If any item ID cannot be found in the latest review, the bot halts issue creation and provides a helpful list of available item IDs:

```markdown
Could not find review items: #xyz9.

Available items:
- #a3f2: Token expiration logic fails on leap year...
- #b7d1: Unsanitized input in header parser...
```

### Atomic Validation Rule

Item validation is atomic per command: if even a single requested item ID is invalid, no issues are created from that comment. This prevents partial execution and ensures the user can review the error before retrying.

---

## Generated Issue Format

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

Processing commands and creating issues requires appropriate token permissions. For detailed token configuration instructions, refer to the [Token Setup Documentation](tokens/README.md).

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

## Practical Examples and Workflows


Here is a step-by-step example of the non-blocking issue command workflow:

1. **Review Posted**: PR Auto Reviewer reviews PR `#42` and identifies a minor suggestion:
   ```markdown
   c4e5. [STYLE] [MINOR] src/db/connection.py:88

   Simplify this connection setup.
   ```
2. **Maintainer Comments**: The reviewer or author wants to track this suggestion as an issue:
   ```markdown
   /create-issue c4e5
   ```
3. **Execution**: The operator runs command processing:
   ```bash
   pr-auto-reviewer process-commands --repo acme/backend --pr 42
   ```
4. **Issue Created**: Issue `#105` is created in `acme/backend` for the non-blocking suggestion.
5. **Bot Feedback**: The bot comments on PR `#42` with the created issue reference.
6. **Re-run Safety**: If `process-commands` is run again, the comment is recognized as already processed and skipped without creating duplicate issues.
